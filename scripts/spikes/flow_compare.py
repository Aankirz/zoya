"""Run one spoken goal end to end and record what it cost (v2 Phase D, Done-when #2).

    .venv/bin/python scripts/spikes/flow_compare.py --label skill   "add basmati rice to my cart"
    .venv/bin/python scripts/spikes/flow_compare.py --label general --without shopping "<goal>"

`--without <skill>` hides that skill's directory for the run, so the router cannot reach its
triggers or tools and the command falls to the general path. Records route, tool, Jev calls,
language-model calls, wall time, every point the safety gate asked, and what Zoya said.

The gate is NOT bypassed. A confirmation is answered automatically only for the reversible and
navigational kinds; purchase, send and post always go unanswered and refuse, so no measurement
run can pay, order or post. Results append to logs/spikes/flow_compare.json.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions, safety, speech  # noqa: E402
from zoya.config import LOG_DIR, SKILLS_DIR, load_env  # noqa: E402

OUT = LOG_DIR / "spikes" / "flow_compare.json"
HIDDEN_SUFFIX = ".disabled"
ANSWERABLE = {"submit", "context", "unknown", "checkout"}

POLL_S = 0.1
MS_PER_S = 1000


@contextlib.contextmanager
def without(skill: str):
    """Hide zoya/skills/<skill>/ for the duration: no SKILL.md, no triggers, no tools."""
    if not skill:
        yield
        return
    live, hidden = SKILLS_DIR / skill, SKILLS_DIR / f"{skill}{HIDDEN_SUFFIX}"
    if not live.is_dir():
        raise SystemExit(f"no such skill directory: {live}")
    shutil.move(live, hidden)
    try:
        yield
    finally:
        shutil.move(hidden, live)


class Answerer(threading.Thread):
    """Answers the gate the way a user would, for navigational asks only.

    Every ask is recorded with the kind the guard gave it. Only `ANSWERABLE` kinds are answered;
    a purchase, send, delete or post is left unanswered, so the gate times out and refuses.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.channel = safety.claim_voice_channel()
        self.asked: list[dict[str, str]] = []
        self.answering = ""
        self.done = threading.Event()
        real = safety.require_confirmation

        def spy(action: safety.Action, current=None):  # noqa: ANN001, ANN202
            self.asked.append({"kind": action.kind, "summary": action.summary()})
            self.answering = action.kind if action.kind in ANSWERABLE else ""
            return real(action, current)

        safety.require_confirmation = spy

    def run(self) -> None:
        while not self.done.wait(POLL_S):
            if not self.answering or not safety.awaiting_reply():
                continue
            if self.channel.reply("confirm", heard_from=time.monotonic()):
                self.answering = ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal")
    parser.add_argument("--label", default="general")
    parser.add_argument("--without", default="")
    parser.add_argument("--answer", action="store_true", help="answer reversible asks out loud")
    args = parser.parse_args()

    load_env()
    decisions.warm()
    spoken: list[str] = []
    speech.narrate = spoken.append  # keep the measurement silent, keep every word
    answerer = Answerer() if args.answer else None
    if answerer:
        answerer.start()

    from zoya import orchestrator

    started = time.monotonic()
    with without(args.without):
        try:
            result = orchestrator.handle_command(args.goal)
            record = {
                "ok": result.ok,
                "route": result.decision.route,
                "source": result.decision.source,
                "skill": result.decision.skill or None,
                "tool": result.decision.tool or None,
                "model_calls": orchestrator.model_calls(result),
                "timings_ms": result.timings_ms,
                "said": result.spoken,
            }
        except Exception as error:  # noqa: BLE001 — a failed flow is a result, not a crash
            record = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    if answerer:
        answerer.done.set()

    record |= {
        "goal": args.goal,
        "label": args.label,
        "without": args.without or None,
        "total_ms": round((time.monotonic() - started) * MS_PER_S),
        "confirmations": answerer.asked if answerer else [],
        "narrated": spoken,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(OUT.read_text()) if OUT.exists() else []
    OUT.write_text(json.dumps([*history, record], indent=2, ensure_ascii=False))
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
