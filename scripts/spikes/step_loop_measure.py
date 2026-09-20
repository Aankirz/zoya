"""Measure one step of the Phase C Jev loop: AX read, then one batched Jev call.

    .venv/bin/python scripts/spikes/step_loop_measure.py "turn on dark mode" [repeats]

Bring the app you want measured to the front first. The Mac must be UNLOCKED: a locked screen
makes every app read ~250 controls and reports no web area, so the numbers are meaningless
(Phase B). The script refuses to measure `loginwindow`.

Writes logs/spikes/step_loop.json.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions  # noqa: E402
from zoya.agents import step_loop  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402
from zoya.tools import ax  # noqa: E402

LOCKED = "loginwindow"
PACING_S = 2.5
OUT = LOG_DIR / "spikes" / "step_loop.json"


def one_step(goal: str) -> dict[str, object]:
    started = time.monotonic()
    app, element = ax.front_app()
    if app == LOCKED:
        raise SystemExit("The screen is locked. Unlock it and run this again.")
    items, web = ax.read_controls(element)
    ax_ms = round((time.monotonic() - started) * 1000, 1)
    if web:
        raise SystemExit(f"{app} is showing a web page: that is the browser substrate, not this.")
    controls = step_loop.pressable(items)
    criteria = step_loop.criteria_of(controls)
    state = step_loop.step_state(app, goal, [], "", list(criteria.values())[:-1])
    answers = decisions.ask(state, step_loop.step_questions(criteria))
    pick = answers.pick("control")
    index = step_loop.index_of(pick.name, len(controls)) if pick else None
    return {
        "app": app,
        "controls": len(controls),
        "state_chars": len(state),
        "ax_ms": ax_ms,
        "jev_ms": answers.latency_ms,
        "step_ms": round((time.monotonic() - started) * 1000, 1),
        "jev_ok": bool(answers),
        "reason": answers.reason,
        "chose": step_loop._label(controls[index]) if index is not None else pick and pick.name,
        "confidence": round(pick.confidence, 3) if pick else None,
        "done": round(answers.noul("done"), 3),
        "irreversible": round(answers.noul("irreversible"), 3),
    }


def main() -> None:
    load_env()
    goal = sys.argv[1] if len(sys.argv) > 1 else "turn on dark mode"
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    runs = []
    for attempt in range(repeats):
        if attempt:
            time.sleep(PACING_S)
        runs.append(one_step(goal))
        print(json.dumps(runs[-1]))
    jev = sorted(run["jev_ms"] for run in runs if run["jev_ok"])
    step = sorted(run["step_ms"] for run in runs if run["jev_ok"])
    summary = {
        "goal": goal,
        "runs": len(runs),
        "answered": len(jev),
        "jev_p50": statistics.median(jev) if jev else None,
        "jev_max": max(jev) if jev else None,
        "step_p50": statistics.median(step) if step else None,
        "step_max": max(step) if step else None,
        "ax_p50": statistics.median(sorted(run["ax_ms"] for run in runs)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
