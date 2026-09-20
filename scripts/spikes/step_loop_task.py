"""Run one whole goal through the Phase C loop and print the call counts (Done-when #3, #4, #5).

    .venv/bin/python scripts/spikes/step_loop_task.py "turn on dark mode"

Bring the app to the front first; the Mac must be UNLOCKED. Prints Jev calls, language-model
calls, steps and per-step wall time. The safety gate still runs: a risky control asks out loud.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya.agents import step_loop  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402
from zoya.tools import ax, computer  # noqa: E402

LOCKED = "loginwindow"
OUT = LOG_DIR / "spikes" / "step_loop_task.json"


def main() -> None:
    load_env()
    goal = sys.argv[1] if len(sys.argv) > 1 else "turn on dark mode"
    if ax.front_app()[0] == LOCKED:
        raise SystemExit("The screen is locked. Unlock it and run this again.")
    computer.begin_session()
    started = time.monotonic()
    outcome = step_loop.run(goal, [], threading.Event())
    total_ms = round((time.monotonic() - started) * 1000, 1)
    result = {
        "goal": goal,
        "done": outcome.done,
        "reason": outcome.reason,
        "steps": outcome.steps,
        "jev_calls": outcome.jev_calls,
        "model_calls": 0,
        "jev_ms_total": outcome.jev_ms,
        "total_ms": total_ms,
        "per_step_ms": round(total_ms / outcome.steps, 1) if outcome.steps else None,
        "pressed": outcome.pressed,
        "recorded_steps": len(outcome.recorded),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
