"""Done-when #5 of Phase H: a fresh session answers from the profile, with no memory_search.

    .venv/bin/python evals/harness/profile_check.py

Uses its own Supermemory container and a scratch local copy, so the owner's memories are never
read or written; every document it adds is deleted at the end.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run  # noqa: E402

from zoya import safety  # noqa: E402
from zoya.config import load_env  # noqa: E402
from zoya.tools import memory  # noqa: E402

CONTAINER = f"zoya_eval_profile_{run.RUN_ID}"
FACTS = [("My home city is Pune.", "address"), ("I am vegetarian.", "preference")]
CORRECTION = ("No, I meant my sister's name is Riya, not Rhea.", "correction")
PROFILE_WAIT_S = 180.0
PROFILE_POLL_S = 10.0
QUESTION = "what's my home city?"


def isolate() -> None:
    memory.MEMORY_USER_TAG = CONTAINER
    memory.MEMORY_LOCAL_FILE = Path(tempfile.mkdtemp()) / "memory.json"
    memory._put_dynamodb = lambda _item: None
    memory.refresh_profile = lambda *_: None


def profile_lines() -> list[str]:
    response = memory._supermemory().profile(
        container_tag=CONTAINER, timeout=memory.MEMORY_PROFILE_TIMEOUT_S
    )
    return [*(response.profile.static or []), *(response.profile.dynamic or [])]


def wait_for(words: list[str]) -> list[str]:
    deadline = time.monotonic() + PROFILE_WAIT_S
    lines: list[str] = []
    while time.monotonic() < deadline:
        lines = profile_lines()
        if all(any(w.casefold() in line.casefold() for line in lines) for w in words):
            return lines
        time.sleep(PROFILE_POLL_S)
    return lines


def ask_fresh(block: str) -> dict[str, Any]:
    from zoya import orchestrator

    searches: list[str] = []
    original = safety.ConfirmationGate.before_tool

    def before_tool(self: Any, event: Any) -> None:
        searches.append(str(event.tool_use.get("name", "")))
        original(self, event)

    safety.ConfirmationGate.before_tool = before_tool
    memory.user_profile = lambda: block
    orchestrator._conversation.clear()
    result = run.Run("profile", "memory", QUESTION)
    run.meter.run = result
    orchestrator.handle_command(QUESTION)
    run.meter.run = None
    return {
        "said": result.said,
        "tools": searches,
        "memory_search_calls": searches.count("memory_search"),
        "model_calls": result.model_calls,
        "prompt_has_block": block in orchestrator.brain_inputs()[0],
    }


def main() -> int:
    load_env()
    from zoya import aws

    aws.load_provider_secrets()
    isolate()
    run.meter = run.Meter()
    run.install_meters()
    run.install_voice()
    added = [memory.remember(text, kind) for text, kind in FACTS]
    try:
        lines = wait_for(["Pune", "vegetarian"])
        block = memory.profile_block(lines)
        memory.remember(*CORRECTION)
        corrected = wait_for(["Riya"])
        report = {
            "container": CONTAINER,
            "added": added,
            "profile_lines": lines,
            "block": block,
            "fresh_session": ask_fresh(block),
            "correction_in_profile": any("riya" in line.casefold() for line in corrected),
            "profile_after_correction": corrected,
        }
    finally:
        for item in memory.memories():
            memory.forget(item["id"])
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
