"""Intent router (§13.5.3): Translate (Devanagari only) → rule matcher → skill trigger index →
learned picks → Jev → ROUTER_MODEL.

D44: ROUTER_MODEL takes ~2 s per call, so the ≤ 1 s fast path depends on the rule
matcher catching every common command with no model call. The model only sees
commands the rules miss, and its answer is a structured RouteChoice, which may pick a skill
(Phase 4 harness, zoya/harness.py).

Phase B puts Jev in front of that model (D81). One batched Choice over every
zero-argument destination answers a rule miss in ~625 ms p50 instead of ~2 s, and
ROUTER_MODEL stays as the fallback for two cases it still owns: a destination Jev
is not confident about, and a command naming a target Jev cannot extract.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel, Field
from typesafe_sdk import Choice

from zoya import aws, decisions, harness
from zoya.config import JEV_ROUTE_CONFIDENCE, JEV_TIMEOUT_S
from zoya.events import Route
from zoya.prompts import ROUTER_PROMPT, ROUTER_SKILLS
from zoya.tools.fast import WEB_APPS
from zoya.tools.handoff import pending_handoff, resume_command

log = logging.getLogger(__name__)

MAX_APP_NAME_WORDS = 4
MS_PER_S = 1000

FAST_TOOL_ARGS: dict[str, tuple[str, ...]] = {
    "open_app": ("app_name",),
    "open_url": ("url",),
    "notes_create": ("body", "title"),
    "notes_search": ("query",),
    "notes_append": ("note_name", "text"),
    "media_control": ("action", "app"),
    "set_volume": ("level",),
    "volume_up": (),
    "volume_down": (),
    "mute": (),
    "get_time": (),
}
REQUIRED_ARGS = {"notes_create": ("body",), "media_control": ("action",)}


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    source: Literal["rules", "model", "fallback", "trigger", "learned", "jev"] = "rules"
    text: str = ""
    timings_ms: dict[str, int] = field(default_factory=dict)
    skill: str = ""  # route "skill": the skill; `tool` is its action when one was picked


# --- Rule matcher ---------------------------------------------------------------

_I = re.IGNORECASE
LEADING_FILLER = re.compile(
    r"^(?:(?:hey|hi|ok|okay)\s+zoya|zoya|uh+|um+|hmm+|please|so|can you|could you|would you"
    r"|will you|zara|now|hey|ok|okay|just|also|i want you to|i'?d like you to"
    r"|go ahead and)[\s,.!?]+",
    _I,
)
TRAILING_FILLER = re.compile(
    r"[\s,]+(?:please|zoya|for me|now|right now|zara|na)$|[\s.!?]+$",
    _I,
)
MULTI_STEP_WORDS = re.compile(r"\b(?:and|then|after that|aur|phir|fir)\b", _I)
MULTI_STEP = re.compile(rf"{MULTI_STEP_WORDS.pattern}|[,;]", _I)
DOMAIN = re.compile(r"^(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#]\S*)?$", _I)

STOP = re.compile(
    r"^(?:stop|cancel|ruk\s*jao|ruko|rukiye|bas|chup)"
    r"(?:[\s,]+(?:it|that|now|everything|mat\s+kijiye|karo|what you'?re doing|the|this|my|current"
    r"|task|tasks))*$",
    _I,
)
# "Go back" is the browser's back, never the previous track (owner's run: a learned pick replayed
# media_control "previous" during an Amazon task). "previous song" stays MEDIA.
GO_BACK = re.compile(
    r"^(?:go|take me|navigate)\s+back(?:\s+(?:to\s+)?(?:the\s+)?(?:previous|last)\s+page)?$"
    r"|^go\s+to\s+the\s+(?:previous|last)\s+page$",
    _I,
)
# "What's on my screen?" goes straight to describe_screen (free, read-only): ~4 s less than a
# brain call that only picks that tool and repeats its answer (Phase 5, coordinator).
SCREEN_QUESTION = re.compile(
    r"^(?:(?:what(?:'s| is)|whats|tell me what(?:'s| is))(?: there)? on (?:my|the) screen"
    r"|describe (?:my|the) screen|what am i looking at|what do you see(?: on (?:my|the) screen)?"
    r"|(?:mere )?screen (?:pe|par) kya (?:hai|dikh raha hai))\??$",
    _I,
)
TIME = re.compile(
    r"^(?:what(?:'s| is)(?: the)? time(?: now)?|what time is it(?: now)?|tell me the time"
    r"|time kya (?:hai|hua)|kitne baje(?: hai| hain)?|samay kya hai)$",
    _I,
)
VOLUME_SET = re.compile(
    r"^(?:set\s+)?(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?$", _I
)
VOLUME_UP = re.compile(
    r"^(?:(?:turn|put)\s+(?:it|the volume|the sound)\s+up|(?:volume|sound)\s+up|louder"
    r"|increase(?: the)? volume|awaaz\s+(?:badhao|tez karo))$",
    _I,
)
VOLUME_DOWN = re.compile(
    r"^(?:(?:turn|put)\s+(?:it|the volume|the sound)\s+down|(?:volume|sound)\s+down|quieter"
    r"|softer|decrease(?: the)? volume|lower(?: the)? volume|awaaz\s+kam\s+karo)$",
    _I,
)
MEDIA = re.compile(
    r"^(?P<action>play|pause|resume|stop|next|skip|previous)(?:\s+playing)?"
    r"(?:\s+(?:the\s+)?(?:music|song|track|playback))?"
    r"(?:\s+(?:on|in|from)?\s*(?:the\s+)?(?P<app>spotify|music)(?:\s+app)?)?$",
    _I,
)
MEDIA_ACTIONS = {"resume": "play", "stop": "pause", "skip": "next"}
MUTE = re.compile(r"^(?:mute|mute(?: the)? (?:sound|volume|mac)|awaaz\s+band\s+karo)$", _I)
NOTE_APPEND = re.compile(
    r"^add\s+['\"]?(?P<text>.+?)['\"]?\s+to\s+(?:my|the)\s+(?P<note>.+?)\s+note$", _I
)
NOTE_SEARCH = re.compile(
    r"^(?:search|find|look\s+for)\s+(?:in\s+)?(?:my\s+)?notes?\s+(?:for|about)\s+(?P<query>.+)$",
    _I,
)
NOTE_CREATE = re.compile(
    r"^(?:(?:write|take|make|create|add|new)\s+(?:a\s+|new\s+)*note|note\s+(?:karo|kar\s+lo|likho)"
    r"|note(?:\s+(?:down|this))?)\b\s*[:,-]?\s*(?:that\s+|saying\s+)?(?P<body>.+)$",
    _I,
)
NOTE_CREATE_HINGLISH = re.compile(r"^(?P<body>.+?)\s+note\s+(?:kar\s*lo|kar\s*do|karo|likho)$", _I)
QUESTION = re.compile(
    r"^(?:what|what's|whats|who|who's|whom|whose|when|where|where's|why|how|how's|which"
    r"|is|are|was|were|do|does|did|should|tell me|explain|define)\b",
    _I,
)
OPEN = re.compile(
    r"^(?:open|launch|start)\s+(?:up\s+)?(?:the\s+)?(?P<target>.+?)"
    r"(?:\s+(?:app|application|website|site|browser))?$",
    _I,
)
# "Open Spotify in a browser" is a web task, not the app "Spotify in a" (owner's live run).
IN_BROWSER = re.compile(
    r"\b(?:in|on|using|with)\s+(?:a\s+|the\s+)?(?:web\s+)?(?:browser|google chrome|chrome|safari"
    r"|firefox|the web|web)\b",
    _I,
)
PAGE_ACTION = re.compile(
    r"\b(?:this|the|that)\s+(?:page|checkout|cart|site|website|form)\b|\bclick\b"
    r"|\bplace\s+(?:the\s+|my\s+|your\s+|an?\s+)?order\b|\bcheck\s*out\b|\bbuy\b|\bpay\b",
    _I,
)
# Flow 10: "done" after signing in resumes a pending handoff, and only then (coordinator).
DONE = re.compile(
    r"^(?:(?:i'?m|i am|i have|i'?ve|all|it'?s)\s+)?(?:already\s+)?"
    r"(?:done|finished|signed in|logged in|ho gaya|ho gya|kar liya)"
    r"(?:\s+(?:now|signing in|logging in))?$",
    _I,
)
OPEN_HINGLISH = re.compile(
    r"^(?P<target>.+?)\s+(?:khol(?:o|\s*do|\s*dijiye)?|open\s*kar(?:o|\s*do|do|\s*dijiye))$", _I
)


def clean_command(text: str) -> str:
    """Strip wake words, fillers, punctuation: "Hey Zoya, open Spotify!" → "open Spotify"."""
    cleaned = " ".join(text.split())
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = LEADING_FILLER.sub("", cleaned).strip()
        cleaned = TRAILING_FILLER.sub("", cleaned).strip()
    return cleaned


def _open_decision(target: str) -> RouteDecision | None:
    target = target.strip(" '\"")
    if not target or MULTI_STEP.search(target):
        return None
    if DOMAIN.match(target):
        return RouteDecision("fast", "open_url", {"url": target})
    if len(target.split()) > MAX_APP_NAME_WORDS or target.lower().startswith(("a ", "an ", "my ")):
        return None
    return RouteDecision("fast", "open_app", {"app_name": target})


EXPLICIT_APP = re.compile(r"\b(?:app|application)\b", _I)


def _note_decision(command: str) -> RouteDecision | None:
    if match := NOTE_APPEND.match(command):
        return RouteDecision(
            "fast", "notes_append", {"note_name": match["note"], "text": match["text"]}
        )
    if match := NOTE_SEARCH.match(command):
        return RouteDecision("fast", "notes_search", {"query": match["query"]})
    if match := NOTE_CREATE.match(command) or NOTE_CREATE_HINGLISH.match(command):
        return RouteDecision("fast", "notes_create", {"body": match["body"].strip(" '\"")})
    return None


def match_rules(text: str) -> RouteDecision | None:
    """The zero-latency rule matcher. None means "ask the router model"."""
    command = clean_command(text)
    if not command:
        return None
    if STOP.match(command):
        return RouteDecision("stop")
    if GO_BACK.match(command):
        return RouteDecision("orchestrator")
    if DONE.match(command) and pending_handoff():
        return RouteDecision("orchestrator")  # route() swaps in the task to resume
    if match := MEDIA.match(command):
        action = match["action"].lower()
        args = {
            "action": MEDIA_ACTIONS.get(action, action),
            "app": (match["app"] or "spotify").lower(),
        }
        if EXPLICIT_APP.search(command):
            args["in_app"] = True
        return RouteDecision("fast", "media_control", args)
    if SCREEN_QUESTION.match(command):
        return RouteDecision("fast", "describe_screen")
    if TIME.match(command):
        return RouteDecision("fast", "get_time")
    if match := VOLUME_SET.match(command):
        return RouteDecision("fast", "set_volume", {"level": int(match[1])})
    for pattern, tool_name in (
        (VOLUME_UP, "volume_up"),
        (VOLUME_DOWN, "volume_down"),
        (MUTE, "mute"),
    ):
        if pattern.match(command):
            return RouteDecision("fast", tool_name)
    if note := _note_decision(command):  # before OPEN: note text may contain "open"
        return note
    if OPEN.match(command) and IN_BROWSER.search(command):
        target = OPEN.match(IN_BROWSER.sub("", command).strip())
        generic = not re.search(r"chrome|safari|firefox", command, _I)  # default browser only
        if generic and target and target["target"].strip().lower() in WEB_APPS:
            return RouteDecision("fast", "open_app", {"app_name": target["target"].strip()})
        return RouteDecision("orchestrator")
    if (match := OPEN.match(command) or OPEN_HINGLISH.match(command)) and (
        decision := _open_decision(match["target"])
    ):
        if decision.tool == "open_app" and EXPLICIT_APP.search(command):
            return RouteDecision("fast", "open_app", {**decision.args, "prefer_web": False})
        return decision
    if PAGE_ACTION.search(command):
        # Clicking, buying or checking out on a page is always a brain task (Phase 3): the router
        # model took 2–8.6 s here before the safety question could even start.
        return RouteDecision("orchestrator")
    if MULTI_STEP_WORDS.search(command) or QUESTION.match(command):
        # Several steps, or a question the brain answers: skip the ~2 s router call (D44) —
        # spoken questions must reach the first word in ≤ 2 s (Phase 2 Done-when #3b).
        return RouteDecision("orchestrator")
    return None


# --- Jev ------------------------------------------------------------------------
#
# Every destination a rule miss can reach with no arguments to extract, plus two catch-alls.
# "needs_target" and "brain" are the "none of these" options Phase A found a Choice must have:
# without one, Jev always picks something and confidence is the only signal it was wrong.

JEV_DESTINATIONS: dict[str, str] = {
    "stop": "stop, cancel or abandon whatever the assistant is currently doing",
    "get_time": "say what the current time is",
    "volume_up": "make the Mac louder",
    "volume_down": "make the Mac quieter",
    "mute": "silence the Mac completely",
    "describe_screen": "describe what is currently on the screen",
    "media_play": "start or resume music playback that is already queued",
    "media_pause": "pause music playback",
    "media_next": "skip to the next track",
    "media_previous": "go back to the previous track",
    "needs_target": (
        "a simple action that names a specific thing the assistant must pick out of the "
        "sentence: open a named app or website, write or search a note, set the volume to a "
        "specific number, or play a named song or artist"
    ),
    "brain": (
        "anything else: a question to answer, research, shopping, several steps, or acting "
        "on a web page"
    ),
}
JEV_MEDIA_ACTIONS = {
    "media_play": "play",
    "media_pause": "pause",
    "media_next": "next",
    "media_previous": "previous",
}
JEV_ROUTE_QUESTION = "What is the speaker asking the assistant to do?"
JEV_ROUTE_STATE = "The user said to their voice assistant: {text!r}"
DEFAULT_MEDIA_APP = "spotify"


def jev_route_questions() -> dict[str, Choice]:
    return {
        "destination": Choice(instructions=JEV_ROUTE_QUESTION, criteria=JEV_DESTINATIONS),
    }


def jev_decision(destination: str) -> RouteDecision | None:
    """None means ROUTER_MODEL still owns this one: it has to extract the target."""
    if destination in ("needs_target", "brain"):
        return RouteDecision("orchestrator", source="jev") if destination == "brain" else None
    if destination == "stop":
        return RouteDecision("stop", source="jev")
    if action := JEV_MEDIA_ACTIONS.get(destination):
        args = {"action": action, "app": DEFAULT_MEDIA_APP}
        return RouteDecision("fast", "media_control", args, source="jev")
    return RouteDecision("fast", destination, source="jev")


def ask_jev_route(text: str) -> RouteDecision | None:
    """One batched Jev Choice over every zero-argument destination. None → ask ROUTER_MODEL.

    One attempt, no retry: ROUTER_MODEL is waiting right behind this call, so backing off costs
    the user more than falling through does.
    """
    answers = decisions.ask(
        JEV_ROUTE_STATE.format(text=text), jev_route_questions(), deadline_s=JEV_TIMEOUT_S
    )
    if not answers:
        log.info("jev route unavailable (%s) — falling back to the router model", answers.reason)
        return None
    pick = answers.pick("destination")
    if pick is None:
        return None
    if pick.confidence < JEV_ROUTE_CONFIDENCE:
        log.info("jev route %s at %.2f is below threshold", pick.name, pick.confidence)
        return None
    return jev_decision(pick.name)


# --- Router model ---------------------------------------------------------------


class RouteChoice(BaseModel):
    """Structured answer from ROUTER_MODEL."""

    route: Literal["fast", "skill", "orchestrator"]
    skill: str | None = Field(default=None, description="Skill name when route is skill")
    skill_action: str | None = Field(
        default=None, description="One of that skill's actions, when one call does the whole job"
    )
    name: str | None = None
    song: str | None = None
    artist: str | None = None
    city: str | None = None
    tool: Literal[tuple(FAST_TOOL_ARGS)] | None = Field(  # type: ignore[valid-type]
        default=None, description="Fast tool name; null when route is orchestrator"
    )
    app_name: str | None = None
    url: str | None = None
    body: str | None = None
    title: str | None = None
    query: str | None = None
    note_name: str | None = None
    text: str | None = None
    level: int | None = None
    action: str | None = None
    app: str | None = None


@cache
def _router_model() -> Any:
    from zoya.models import get_model

    return get_model("router")


@cache
def router_prompt() -> str:
    """Byte-stable: the static rules plus the skill catalogue (cached by OpenAI after one call)."""
    return f"{ROUTER_PROMPT}\n\n{ROUTER_SKILLS.format(menu=harness.menu())}"


def ask_router_model(text: str) -> RouteChoice:
    """One structured ROUTER_MODEL call. Built via get_model() → store=False (D36)."""
    from strands import Agent

    agent = Agent(model=_router_model(), system_prompt=router_prompt(), callback_handler=None)
    result = agent(text, structured_output_model=RouteChoice)
    return result.structured_output


def skill_decision(choice: RouteChoice) -> RouteDecision:
    """A skill pick: its action when the args are complete, else the brain with that skill only."""
    if choice.skill not in harness.catalog():
        return RouteDecision("orchestrator", source="model")
    action = choice.skill_action or ""
    if action not in harness.skill_tool_names(choice.skill) or action not in harness.all_tools():
        return RouteDecision("skill", source="model", skill=choice.skill)
    args = harness.signature_args(action, choice.model_dump())
    if any(name not in args for name in harness.required_args(action)):
        return RouteDecision("skill", source="model", skill=choice.skill)
    return RouteDecision("skill", action, args, source="model", skill=choice.skill)


def decision_from_choice(choice: RouteChoice) -> RouteDecision:
    """Turn the model's answer into a decision; incomplete fast answers go to the orchestrator."""
    if choice.route == "skill":
        return skill_decision(choice)
    if choice.route != "fast" or choice.tool not in FAST_TOOL_ARGS:
        return RouteDecision("orchestrator", source="model")
    args = {
        name: getattr(choice, name)
        for name in FAST_TOOL_ARGS[choice.tool]
        if getattr(choice, name) not in (None, "")
    }
    required = REQUIRED_ARGS.get(choice.tool, FAST_TOOL_ARGS[choice.tool])
    if any(name not in args for name in required):
        return RouteDecision("orchestrator", source="model")
    return RouteDecision("fast", choice.tool, args, source="model")


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * MS_PER_S)


def route(text: str, use_rules: bool = True) -> RouteDecision:
    """Route one command. `use_rules=False` forces the model (router eval only)."""
    timings: dict[str, int] = {}
    routed_text = text
    if aws.needs_translation(text):
        started = time.monotonic()
        routed_text = aws.translate_to_english(text) or text
        timings["translate_ms"] = _ms(started)

    if use_rules:
        started = time.monotonic()
        decision = match_rules(routed_text)
        if decision and DONE.match(clean_command(routed_text)):
            routed_text = resume_command() or routed_text
        elif (
            (not decision or _skill_may_win(decision))
            and not GO_BACK.match(clean_command(routed_text))
            and (pick := _pick_without_model(clean_command(routed_text)))
        ):
            decision = pick
        timings["rules_ms"] = _ms(started)
        if decision:
            return _with(decision, routed_text, timings)

    started = time.monotonic()
    jev = ask_jev_route(routed_text)
    timings["jev_ms"] = _ms(started)
    if jev:
        return _with(jev, routed_text, timings)

    started = time.monotonic()
    try:
        decision = decision_from_choice(ask_router_model(routed_text))
    except Exception as error:  # noqa: BLE001 — the orchestrator can still handle it
        log.warning("router model failed (%s) — sending to orchestrator", type(error).__name__)
        decision = RouteDecision("orchestrator", source="fallback")
    timings["model_ms"] = _ms(started)
    return _with(decision, routed_text, timings)


def _skill_may_win(decision: RouteDecision) -> bool:
    """Stop and the fast Mac tools keep priority; "open X" and brain catch-alls try skills first
    ("open the MrBeast channel on YouTube" is not an app)."""
    return decision.route == "orchestrator" or decision.tool == "open_app"


def _pick_without_model(command: str) -> RouteDecision | None:
    for source, pick in (("trigger", harness.match_trigger), ("learned", harness.learned_pick)):
        if found := pick(command):
            return RouteDecision("skill", found.action, found.args, source, skill=found.skill)
    return None


def _with(decision: RouteDecision, text: str, timings: dict[str, int]) -> RouteDecision:
    return RouteDecision(
        decision.route,
        decision.tool,
        decision.args,
        decision.source,
        text,
        timings,
        decision.skill,
    )
