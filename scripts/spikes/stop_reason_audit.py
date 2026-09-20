"""What the step loop SAYS at each terminal path, against what actually happened.

Gap 2 follow-up. The VS Code acceptance test found the loop saying "I couldn't find a way to
do that in this app" when it had found the way and been blocked. This drives every path that
ends `run()` with stubs and prints the reason each one really produces, so the remaining
conflations are data rather than a reading of the source.

Run: .venv/bin/python scripts/spikes/stop_reason_audit.py
No GUI: every screen and every Jev answer here is a stub.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions  # noqa: E402
from zoya.agents import step_loop  # noqa: E402
from zoya.config import COMPUTER_MAX_JEV_STEPS, LOG_DIR  # noqa: E402
from zoya.tools import ToolError  # noqa: E402

OUT = LOG_DIR / "spikes" / "stop_reason_audit.json"
TWO_CONTROLS = [("AXButton", "Appearance", object()), ("AXButton", "Dark", object())]


def reply(control="c0", confidence=1.0, done=0.0, worked=1.0, failure="transient"):
    return decisions.Answers(
        {
            "control": {"choice": control, "confidence": confidence, "probabilities": {}},
            "done": {"noul": done},
            "worked": {"noul": worked},
            "irreversible": {"noul": 0.0},
            "failure": {"choice": failure, "confidence": 1.0, "probabilities": {}},
        },
        latency_ms=500,
    )


def changing_screen() -> Any:
    """A different control set every look, so the step budget runs out before the circle rule."""
    seen = {"n": 0}

    def read(_app):
        seen["n"] += 1
        return [("AXButton", f"Section {seen['n']}", object())], False

    return read


def drive(replies: list[Any], press: Any = None, controls: Any = TWO_CONTROLS) -> Any:
    """`run()` against a stubbed screen and a scripted Jev, with the real control flow."""
    import zoya.tools.ax as ax_module

    saved = (ax_module.front_app, ax_module.read_controls, ax_module.ax_press)
    queue = list(replies)
    step_loop.ax.front_app = lambda: ("System Settings", object())
    step_loop.ax.read_controls = (
        controls if callable(controls) else (lambda _app: (controls, False))
    )
    step_loop.ax.ax_press = press or (lambda label, occurrence=1: None)
    step_loop.tasks.gui_checkpoint = lambda _lock: False
    step_loop.computer.log_stage = lambda *a, **k: None
    step_loop.time.sleep = lambda _s: None
    step_loop.decisions.ask = lambda *_a, **_k: (
        queue.pop(0) if queue else decisions.unavailable("empty")
    )
    step_loop.computer.begin_session()
    try:
        return step_loop.run("turn on dark mode", [], threading.Event())
    finally:
        ax_module.front_app, ax_module.read_controls, ax_module.ax_press = saved


def refusing(label, occurrence=1):  # noqa: ARG001 — ax_press's own signature
    raise ToolError("Zoya doesn't press permission prompts.")


CASES = [
    (
        "pick below JEV_STEP_CONFIDENCE on the first screen",
        "nothing on this screen looked right",
        lambda: drive([reply(confidence=0.5)]),
    ),
    (
        "Jev names a dead end after a press",
        "pressed something, the screen cannot reach the goal",
        lambda: drive([reply(), reply(worked=0.0, failure="dead_end")]),
    ),
    (
        "every candidate dropped by the wrong_element triage",
        "found and tried both controls; they were wrong",
        lambda: drive(
            [
                reply(control="c0"),
                reply(control="c0", worked=0.0, failure="wrong_element"),
                reply(control="c1"),
                reply(control="c1", worked=0.0, failure="wrong_element"),
                reply(),
            ]
        ),
    ),
    (
        "every press refused by a guarded tool",
        "found the controls; the tools refused to press them",
        lambda: drive([reply(control="c0"), reply(control="c1"), reply()], press=refusing),
    ),
    (
        "COMPUTER_MAX_JEV_STEPS exhausted",
        f"pressed up to {COMPUTER_MAX_JEV_STEPS} times without arriving",
        lambda: drive(
            [reply(control="c0")] * (COMPUTER_MAX_JEV_STEPS + 2), controls=changing_screen()
        ),
    ),
    (
        "the loop returned to a screen it had acted from",
        "went round in a circle",
        lambda: drive([reply(control="c0")] * COMPUTER_MAX_JEV_STEPS),
    ),
    (
        "the app published no pressable controls",
        "the app really publishes nothing",
        lambda: drive([reply()], controls=[]),
    ),
    (
        "Jev unreachable",
        "the classifier did not answer",
        lambda: drive([decisions.unavailable("timed out")]),
    ),
]


def main() -> None:
    rows = []
    for path, truth, run_case in CASES:
        outcome = run_case()
        rows.append(
            {
                "path": path,
                "what_happened": truth,
                "reason_said": outcome.reason,
                "steps": outcome.steps,
                "pressed": outcome.pressed,
            }
        )
        print(f"{path}\n    happened: {truth}\n    says:     {outcome.reason!r}\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
