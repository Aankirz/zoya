"""Can Jev pick the control that LEADS TOWARD a goal, not just the one that achieves it?

    .venv/bin/python scripts/spikes/jev_navigation.py

Reads one screen (bring the app's top-level pane to the front first), then asks the same
batched step question once per goal, with the correct answer known in advance. Reports accuracy
and the confidence separation between right and wrong answers, the way Phase B set its
thresholds. Also asks a candidate `on_this_screen` noul, to measure whether it is worth adding.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from typesafe_sdk import Noul  # noqa: E402

from zoya import decisions  # noqa: E402
from zoya.agents import step_loop  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402
from zoya.tools import ax  # noqa: E402

PACING_S = 2.5
FRONT_WAIT_S = 20.0
OUT = LOG_DIR / "spikes" / "jev_navigation.json"
ON_THIS_SCREEN = (
    "Is a control that DIRECTLY achieves the goal present in this list, as opposed to a "
    "control that merely opens the section where it lives?"
)
CASES = [
    ("turn on dark mode", ("Appearance",)),
    ("change my wallpaper", ("Wallpaper",)),
    ("turn on bluetooth", ("Bluetooth",)),
    ("change the keyboard settings", ("Keyboard",)),
    ("turn on do not disturb", ("Focus", "Do Not Disturb")),
    ("make the sound louder", ("Sound",)),
    ("change the display resolution", ("Displays",)),
    ("manage my notifications", ("Notifications",)),
    ("set up screen time", ("Screen Time",)),
    ("change my trackpad settings", ("Trackpad",)),
]


def bring_front(name: str) -> bool:
    subprocess.run(["osascript", "-e", f'tell application "{name}" to activate'], check=False)
    deadline = time.monotonic() + FRONT_WAIT_S
    while time.monotonic() < deadline:
        if ax.front_app()[0] == name:
            return True
        time.sleep(0.2)
    return False


def ask(app: str, candidates: list, goal: str) -> dict:
    criteria = step_loop.criteria_of(candidates)
    state = step_loop.step_state(app, goal, [], "", [c.label for c in candidates])
    questions = {
        **step_loop.step_questions(criteria),
        "on_screen": Noul(instructions=ON_THIS_SCREEN),
    }
    answers = decisions.ask(state, questions)
    pick = answers.pick("control")
    chosen = step_loop.chosen(candidates, pick.name) if pick else None
    return {
        "goal": goal,
        "ok": bool(answers),
        "chose": chosen.label if chosen else (pick.name if pick else None),
        "confidence": round(pick.confidence, 3) if pick else 0.0,
        "on_screen": round(answers.noul("on_screen"), 3),
        "done": round(answers.noul("done"), 3),
        "jev_ms": answers.latency_ms,
    }


def main() -> None:
    load_env()
    decisions.warm()
    app_name = sys.argv[1] if len(sys.argv) > 1 else "System Settings"
    if not bring_front(app_name):
        raise SystemExit(f"Could not bring {app_name} to the front.")
    time.sleep(1.5)
    app, element = ax.front_app()
    candidates = step_loop.native_candidates(ax.read_controls(element)[0])
    if not candidates:
        raise SystemExit(f"{app} published no controls. Is a window open?")
    print(f"screen: {app}, {len(candidates)} candidates\n")

    runs = []
    for index, (goal, want) in enumerate(CASES):
        if index:
            time.sleep(PACING_S)
        row = ask(app, candidates, goal)
        row["want"] = list(want)
        row["right"] = bool(
            row["chose"] and any(option.lower() in row["chose"].lower() for option in want)
        )
        runs.append(row)
        mark = "OK  " if row["right"] else "WRONG"
        print(
            f"{mark} {goal:32} -> {str(row['chose'])[:34]:34} "
            f"conf={row['confidence']:.2f} on_screen={row['on_screen']:.2f}"
        )

    answered = [r for r in runs if r["ok"]]
    right = [r["confidence"] for r in answered if r["right"]]
    wrong = [r["confidence"] for r in answered if not r["right"]]
    summary = {
        "screen": app,
        "candidates": len(candidates),
        "cases": len(runs),
        "answered": len(answered),
        "correct": len(right),
        "accuracy": round(len(right) / len(answered), 3) if answered else None,
        "right_confidence_min": min(right) if right else None,
        "right_confidence_p50": statistics.median(right) if right else None,
        "wrong_confidence_max": max(wrong) if wrong else None,
        "on_screen_p50": (
            statistics.median([r["on_screen"] for r in answered]) if answered else None
        ),
        "jev_ms_p50": statistics.median([r["jev_ms"] for r in answered]) if answered else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
