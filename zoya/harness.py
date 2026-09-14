"""Zoya harness, layers 1–2 (docs/research/harness.md): skills directory, trigger index, direct
actions, per-skill tool scoping, stable prompt prefixes.

Dispatch (zoya/router.py): rules → trigger index (0 model calls) → learned picks (0 calls) → one
router-model call that may pick a skill → brain with only that skill's tools.

Strands primitives used: `Skill` (SKILL.md parsing, strands/vended_plugins/skills/skill.py),
`AgentSkills` (the no-pick brain gets the whole catalogue and loads a body with its `skills` tool),
`@tool` actions, direct `agent.tool.X(record_direct_tool_call=False)` calls with no model call
(strands/tools/_caller.py; they run the same executor and hooks), `structured_output_model` for the
pick, OpenAI `prompt_cache_key` through `params`. Custom (Strands has none): the trigger regex index
with slot capture, per-skill tool lists (Strands shows `allowed_tools` as text only, "not yet
enforced"), learned picks.

Security: skill metadata never decides risk. Every action is in `safety.TOOL_RISK` (unknown =
confirm), risky actions check the voice token inside themselves, and a direct call whose guard
declined ends the task like a brain call does (tests/test_harness.py).
Docs: https://strandsagents.com/docs/user-guide/concepts/plugins/skills/ ,
https://strandsagents.com/docs/user-guide/concepts/tools/ (direct tool calls).
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import threading
import time
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from strands.vended_plugins.skills import Skill

from zoya import safety
from zoya.config import LEARNED_PICK_TTL_S, LEARNED_PICKS_FILE, PROMPT_CACHE_KEY_PREFIX, SKILLS_DIR
from zoya.tools import ToolError, collect_tools

# Always available to a skill-scoped brain, next to the skill's own tools.
GENERIC_TOOLS = ("narrate", "memory_search", "memory_add", "handoff_to_user", "browser_screenshot")
ERROR_PREFIX = re.compile(r"^Error: (?:\w+ - )?")


@dataclass(frozen=True)
class Trigger:
    skill: str
    action: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SkillMatch:
    skill: str
    action: str = ""
    args: dict[str, str] = field(default_factory=dict)


# --- Catalogue ---------------------------------------------------------------------------------


@cache
def catalog() -> dict[str, Skill]:
    """Every zoya/skills/<dir>/SKILL.md by skill name, in directory order (stable prompts)."""
    skills: dict[str, Skill] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = Skill.from_content(skill_md.read_text(encoding="utf-8"))
        skill.path = skill_md.parent
        skills[skill.name] = skill
    return skills


@cache
def action_tools() -> dict[str, Any]:
    """Every @tool in zoya/skills/*/actions.py, by tool name."""
    tools: dict[str, Any] = {}
    for actions in sorted(SKILLS_DIR.glob("*/actions.py")):
        module = importlib.import_module(f"zoya.skills.{actions.parent.name}.actions")
        tools.update({t.tool_name: t for t in getattr(module, "TOOLS", [])})
    return tools


@cache
def all_tools() -> dict[str, Any]:
    """Every tool the brain may be given: zoya/tools, zoya/agents and skill actions."""
    tools = {t.tool_name: t for t in collect_tools("zoya.tools", "zoya.agents")}
    return tools | action_tools()


def compile_triggers(skills: dict[str, Skill]) -> list[Trigger]:
    """Parser (tests/test_harness.py): `metadata.triggers` → compiled, whole-command regexes.

    A trigger's named groups must be arguments of its action; a bad trigger fails at startup.
    """
    triggers = []
    for name, skill in skills.items():
        for entry in skill.metadata.get("triggers") or []:
            pattern = re.compile(entry["pattern"], re.IGNORECASE)
            triggers.append(Trigger(name, entry["action"], pattern))
    return triggers


@cache
def trigger_index() -> list[Trigger]:
    triggers = compile_triggers(catalog())
    tools = all_tools()
    for trigger in triggers:
        tool = tools.get(trigger.action)
        if tool is None:
            raise RuntimeError(f"skill {trigger.skill}: unknown action {trigger.action}")
        params = set(tool.tool_spec["inputSchema"]["json"].get("properties", {}))
        if unknown := set(trigger.pattern.groupindex) - params:
            raise RuntimeError(f"skill {trigger.skill}: {trigger.action} has no args {unknown}")
    return triggers


def match_trigger(command: str, triggers: list[Trigger] | None = None) -> SkillMatch | None:
    """0 model calls: the first trigger that matches the whole cleaned command, with its slots."""
    for trigger in trigger_index() if triggers is None else triggers:
        if match := trigger.pattern.match(command.strip()):
            args = {k: v.strip(" '\"") for k, v in match.groupdict().items() if v and v.strip()}
            return SkillMatch(trigger.skill, trigger.action, args)
    return None


def skill_of(action: str) -> str:
    return next((n for n, s in catalog().items() if action in skill_tool_names(n)), "")


def skill_tool_names(name: str) -> tuple[str, ...]:
    listed = catalog()[name].metadata.get("tools") or []
    return tuple(dict.fromkeys([*listed, *GENERIC_TOOLS]))  # ordered, unique: a stable tools array


def menu() -> str:
    """The static catalogue for the router prompt: skill, one line, its actions and their args."""
    lines = []
    tools = all_tools()
    for name, skill in catalog().items():
        actions = []
        for tool_name in skill.metadata.get("tools") or []:
            props = tools[tool_name].tool_spec["inputSchema"]["json"].get("properties", {})
            actions.append(f"{tool_name}({', '.join(props)})")
        lines.append(f"- {name}: {skill.description} Actions: {'; '.join(actions)}")
    return "\n".join(lines)


def skill_prompt(base: str, name: str) -> str:
    """Byte-identical per skill: persona + rules, then the skill body. Nothing dynamic."""
    skill = catalog()[name]
    return f'{base}\n\n<skill name="{name}">\n{skill.instructions}\n</skill>'


def cache_key(name: str | None) -> str:
    return f"{PROMPT_CACHE_KEY_PREFIX}-brain-{name or 'all'}"


# --- Layer 1: direct actions ---------------------------------------------------------------------


@cache
def _actions_agent() -> Any:
    """One long-lived Agent that only runs direct tool calls: the model is never called, the hooks
    (ConfirmationGate, registered last) still run on every call."""
    from strands import Agent
    from strands.tools.executors import SequentialToolExecutor

    from zoya.models import get_model

    return Agent(
        model=get_model("router"),
        tools=list(all_tools().values()),
        hooks=[safety.ConfirmationGate()],
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,
        record_direct_tool_call=False,
    )


def required_args(action: str) -> list[str]:
    spec = all_tools()[action].tool_spec["inputSchema"]["json"]
    return list(spec.get("required", []))


def run_action(action: str, args: dict[str, Any]) -> str:
    """Layer 1: call a tool with no model call. Raises ToolError or ConfirmationDeclined."""
    if action not in all_tools():
        raise ToolError("I don't know how to do that yet.")
    if missing := [name for name in required_args(action) if not args.get(name)]:
        raise ToolError(f"I need the {', '.join(missing)} for that.")
    caller = getattr(_actions_agent().tool, action)
    result = caller(record_direct_tool_call=False, **args)
    text = " ".join(block.get("text", "") for block in result.get("content", []))
    if safety.task_declined():
        raise safety.ConfirmationDeclined(safety.ALREADY_DECLINED)
    if result.get("status") == "error":
        raise ToolError(ERROR_PREFIX.sub("", text) or "That didn't work.")
    return text


def signature_args(action: str, values: dict[str, Any]) -> dict[str, Any]:
    """Keep only the values the action accepts (router-model fields → tool args)."""
    tool = all_tools()[action]
    params = inspect.signature(tool._tool_func).parameters  # noqa: SLF001 — decorated function
    return {k: v for k, v in values.items() if k in params and v not in (None, "")}


# --- Learned picks: a command the router model mapped once costs 0 calls next time ---------

_learned_lock = threading.Lock()


def _load_learned() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(LEARNED_PICKS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _learn_key(command: str) -> str:
    """The cleaned command, as the router looks it up ("could you … for me" → "…")."""
    from zoya.router import clean_command

    return clean_command(command).casefold()


def learned_pick(command: str) -> SkillMatch | None:
    entry = _load_learned().get(_learn_key(command))
    if not entry or time.time() - entry["at"] > LEARNED_PICK_TTL_S:
        return None
    if entry["action"] not in all_tools():
        return None
    return SkillMatch(entry["skill"], entry["action"], entry["args"])


def learn_pick(command: str, pick: SkillMatch) -> None:
    """Only free actions, by the safety registry (coordinator review, gap E): a guarded tool
    (play a song, share a file) is never replayed from a remembered phrase."""
    if safety.risk_of(pick.action) != "free":
        return
    with _learned_lock:
        learned = _load_learned()
        learned[_learn_key(command)] = {
            "skill": pick.skill,
            "action": pick.action,
            "args": pick.args,
            "at": time.time(),
        }
        try:
            LEARNED_PICKS_FILE.parent.mkdir(exist_ok=True)
            LEARNED_PICKS_FILE.write_text(json.dumps(learned, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
