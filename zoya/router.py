"""Intent router (§13.5.3): Translate (Devanagari only) → rule matcher → ROUTER_MODEL.

D44: ROUTER_MODEL takes ~2 s per call, so the ≤ 1 s fast path depends on the rule
matcher catching every common command with no model call. The model only sees
commands the rules miss, and its answer is a structured RouteChoice.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel, Field

from zoya import aws
from zoya.events import Route
from zoya.prompts import ROUTER_PROMPT

log = logging.getLogger(__name__)

MAX_APP_NAME_WORDS = 4
MS_PER_S = 1000

FAST_TOOL_ARGS: dict[str, tuple[str, ...]] = {
    "open_app": ("app_name",),
    "open_url": ("url",),
    "notes_create": ("body", "title"),
    "notes_search": ("query",),
    "notes_append": ("note_name", "text"),
    "set_volume": ("level",),
    "volume_up": (),
    "volume_down": (),
    "mute": (),
    "get_time": (),
}
REQUIRED_ARGS = {"notes_create": ("body",)}


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    source: Literal["rules", "model", "fallback"] = "rules"
    text: str = ""
    timings_ms: dict[str, int] = field(default_factory=dict)


# --- Rule matcher ---------------------------------------------------------------

_I = re.IGNORECASE
LEADING_FILLER = re.compile(
    r"^(?:(?:hey|hi|ok|okay)\s+zoya|zoya|uh+|um+|hmm+|please|so|can you|could you|would you"
    r"|will you|zara)[\s,.!?]+",
    _I,
)
TRAILING_FILLER = re.compile(
    r"[\s,]+(?:please|zoya|for me|now|right now|zara|na)$|[\s.!?]+$",
    _I,
)
MULTI_STEP = re.compile(r"\b(?:and|then|after that|aur|phir|fir)\b|[,;]", _I)
DOMAIN = re.compile(r"^(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#]\S*)?$", _I)

STOP = re.compile(
    r"^(?:stop|cancel|ruk\s*jao|ruko|rukiye|bas|chup)"
    r"(?:[\s,]+(?:it|that|now|everything|mat\s+kijiye|karo|what you'?re doing))*$",
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
OPEN = re.compile(
    r"^(?:open|launch|start)\s+(?:up\s+)?(?:the\s+)?(?P<target>.+?)"
    r"(?:\s+(?:app|application|website|site|browser))?$",
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
    if match := OPEN.match(command) or OPEN_HINGLISH.match(command):
        return _open_decision(match["target"])
    return None


# --- Router model ---------------------------------------------------------------


class RouteChoice(BaseModel):
    """Structured answer from ROUTER_MODEL."""

    route: Literal["fast", "orchestrator"]
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


@cache
def _router_model() -> Any:
    from zoya.models import get_model

    return get_model("router")


def ask_router_model(text: str) -> RouteChoice:
    """One structured ROUTER_MODEL call. Built via get_model() → store=False (D36)."""
    from strands import Agent

    agent = Agent(model=_router_model(), system_prompt=ROUTER_PROMPT, callback_handler=None)
    result = agent(text, structured_output_model=RouteChoice)
    return result.structured_output


def decision_from_choice(choice: RouteChoice) -> RouteDecision:
    """Turn the model's answer into a decision; incomplete fast answers go to the orchestrator."""
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
        timings["rules_ms"] = _ms(started)
        if decision:
            return _with(decision, routed_text, timings)

    started = time.monotonic()
    try:
        decision = decision_from_choice(ask_router_model(routed_text))
    except Exception as error:  # noqa: BLE001 — the orchestrator can still handle it
        log.warning("router model failed (%s) — sending to orchestrator", type(error).__name__)
        decision = RouteDecision("orchestrator", source="fallback")
    timings["model_ms"] = _ms(started)
    return _with(decision, routed_text, timings)


def _with(decision: RouteDecision, text: str, timings: dict[str, int]) -> RouteDecision:
    return RouteDecision(
        decision.route, decision.tool, decision.args, decision.source, text, timings
    )
