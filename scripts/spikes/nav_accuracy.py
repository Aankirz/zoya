"""Does Jev pick a control that LEADS TOWARD a goal, from a screen the goal is not on?

Gap 2's measurement. One batched step-loop call per (app, goal), from whatever screen the app
opens on, with nothing pressed: the answer is the loop's first navigation decision in isolation.

Run: .venv/bin/python scripts/spikes/nav_accuracy.py [repeats]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions  # noqa: E402
from zoya.agents import step_loop  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402
from zoya.tools import ax  # noqa: E402

LOCKED = "loginwindow"
FRONT_WAIT_S = 20.0
FRONT_POLL_S = 0.2
SETTLE_S = 1.5
OUT = LOG_DIR / "spikes" / "nav_accuracy.json"

ONLY = set(sys.argv[2:])

CASES = [
    ("System Settings", "turn on dark mode", "Appearance"),
    ("Mail", "write a new email to Priya", "New Message"),
    ("Finder", "show me my downloads", "Downloads"),
    ("Calendar", "show me this month", "Month"),
    ("Notes", "start a new note", "New Note"),
    ("Music", "search for a song", "Search"),
    ("Visual Studio Code", "open the search panel", "Search"),
]


def bring_front(name: str) -> bool:
    subprocess.run(["open", "-a", name], check=False)
    subprocess.run(["osascript", "-e", f'tell application "{name}" to activate'], check=False)
    deadline = time.monotonic() + FRONT_WAIT_S
    while time.monotonic() < deadline:
        if ax.front_app()[0] == name:
            return True
        time.sleep(FRONT_POLL_S)
    return False


def ask_once(goal: str) -> dict[str, object]:
    app, element = ax.front_app()
    items, web = ax.read_controls(element)
    candidates = step_loop.native_candidates(items)
    if not candidates:
        return {"app": app, "web": web, "error": "no pressable controls"}
    answers = decisions.ask(
        step_loop.step_state(app, goal, [], "", [c.label for c in candidates]),
        step_loop.step_questions(step_loop.criteria_of(candidates)),
    )
    pick = answers.pick("control")
    picked = step_loop.chosen(candidates, pick.name) if pick else None
    return {
        "app": app,
        "controls": len(candidates),
        "pick": picked.label if picked else (pick.name if pick else None),
        "confidence": round(pick.confidence, 3) if pick else 0.0,
        "done": round(answers.noul("done"), 3),
        "latency_ms": answers.latency_ms,
        "reason": answers.reason,
    }


def main() -> None:
    load_env()
    if ax.front_app()[0] == LOCKED:
        raise SystemExit("The screen is locked. Unlock it and run this again.")
    decisions.warm()
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    results = []
    for app, goal, expected in CASES:
        if ONLY and app not in ONLY:
            continue
        if not bring_front(app):
            results.append({"app": app, "goal": goal, "error": "could not bring to front"})
            continue
        time.sleep(SETTLE_S)
        for _ in range(repeats):
            row = {"goal": goal, "expected": expected, **ask_once(goal)}
            results.append(row)
            print(json.dumps(row))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
