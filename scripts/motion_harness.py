"""S2-Feel capture harness: drive the real pill and glow through every state with scripted
events, log every display frame inside the overlay child (zoya/overlay_probe.py), and report
each transition: event → first changed frame, frames to that change, how long it moves, and the
earcon-to-visual skew.

    uv run python scripts/motion_harness.py --out design/s2/after/light            # timings
    uv run python scripts/motion_harness.py --out ... --dark --reduce              # Reduce Motion
    uv run python scripts/motion_harness.py --out ... --backdrop night --record    # motion pass

Events go through overlay.to_message, the same mapping Zoya uses, and are written to the child's
stdin like Zoya's writer thread does. No voice, no sound, no Chrome: the overlay child runs from
source with HOME pointed at the fixture home (scripts/hub_fixture.py).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import Quartz

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hub_fixture  # noqa: E402

from zoya import events, overlay, overlay_probe  # noqa: E402

START_S = 4.0
DRAIN_S = 1.5
STEP_S = 0.6
LONG_S = 1.2
FRAME_MS = 1000 / 120
BLOCK_MS = 10.0
SPEAKERS = "Speakers"
FALLBACK_LATENCY_MS = {"high": 27.3, "low": 18.0}
LOOPED = frozenset({"working"})
FIRST_LIMIT_S = 0.1
QUIET_FRAMES = 3
VISUAL_KEYS = (
    "panel",
    "pill",
    "tint",
    "bubble",
    "eyes",
    "eyes_box",
    "label",
    "glow",
    "cursor",
    "rings",
    "windows",
)
SUMMARY = "I'm about to book the 7:40 pm table for four at Toit Indiranagar, total ₹2,000 deposit."
SAID = "मैंने कल सुबह साढ़े छह बजे का अलार्म लगा दिया है, और आपकी दवाई का रिमाइंडर भी।"
LONG_ASK = (
    "move my dentist appointment from Thursday afternoon to the first free slot next week "
    "and tell Dr. Rao's clinic I'll be ten minutes late if traffic on Old Airport Road is bad"
)
HINDI_ASK = "कल सुबह साढ़े छह बजे का अलार्म लगा दो"
RING = "620,690,140,32"


@dataclass(frozen=True)
class Step:
    name: str
    sends: tuple[Any, ...]
    kind: str = "enter"
    settle_s: float = STEP_S
    sound: str = ""
    frequent: bool = True


def _ear(kind: str) -> events.EarconEvent:
    return events.EarconEvent(kind)  # type: ignore[arg-type]


def _ask(task: str, decision: str = "pending") -> events.ConfirmationEvent:
    return events.ConfirmationEvent(task, SUMMARY, decision)  # type: ignore[arg-type]


def _task(task: str, status: str) -> events.TaskEvent:
    return events.TaskEvent(task, status, "book a table at toit for four", "orchestrator")  # type: ignore[arg-type]


def _beat(kind: str) -> Step:
    return Step(f"{kind} earcon", (_ear(kind),), "beat", sound=kind)


SCRIPT = (
    Step("start idle", (_task("t0", "done"),), "exit", LONG_S, frequent=False),
    Step("key-down → listening", (_ear("listening"),), sound="listening"),
    Step("voice level", ({"k": "level", "v": 0.8}, {"k": "level", "v": 0.3}), "level"),
    Step(
        "you said (caption grows)",
        (events.OverlayEvent(LONG_ASK, "listening", {"role": "user"}),),
    ),
    Step(
        "intent chips",
        (
            events.OverlayEvent(
                HINDI_ASK,
                "listening",
                {"role": "intent", "chips": "set reminder\nसुबह 6:30"},
            ),
        ),
    ),
    Step("key-up → heard + working", (_ear("heard"), _ear("working")), sound="heard"),
    Step("aim at the window", (events.OverlayEvent("", "working", {"ring": RING}),), "ring"),
    Step(
        "working (acting + glow)",
        (events.OverlayEvent("", "working", {"tool": "ax_press"}),),
        settle_s=LONG_S,
    ),
    Step(
        "ring + cursor glide", (events.OverlayEvent("", "working", {"ring": RING}),), "ring", LONG_S
    ),
    Step("progress tick", (_ear("progress-step"),), "beat", sound="progress-step"),
    Step("speaking", (events.NarrateEvent(SAID),)),
    Step("speech done", (events.OverlayEvent("", "idle", {"speech": "done"}),), "exit"),
    Step("asking (confirm)", (_ask("t1"),), settle_s=LONG_S),
    Step("warning earcon", (_ear("warning"),), "beat", sound="warning"),
    Step("warning earcon again", (_ear("warning"),), "beat", sound="warning"),
    Step("confirmed", (_ask("t1", "confirm"),)),
    Step("late duplicate ask (confirmed)", (_ask("t1"),), "door"),
    Step("purchase earcon", (_ear("purchase"),), "beat", sound="purchase"),
    Step("task done", (_task("t1", "done"), _ear("success")), "exit", LONG_S, sound="success"),
    Step("key-down → listening (2)", (_ear("listening"),), sound="listening"),
    Step("key-up → heard (2)", (_ear("heard"), _ear("working")), sound="heard"),
    Step("asking (2)", (_ask("t2"),), settle_s=LONG_S),
    Step("cancelled", (_ask("t2", "cancel"), _ear("cancel")), "exit", sound="cancel"),
    Step("late duplicate ask (cancelled)", (_ask("t2"),), "door"),
    Step("thinking (3)", (_task("t3", "started"),)),
    Step("error", (_ear("error"),), sound="error"),
    Step("thinking (4)", (_task("t4", "started"),)),
    _beat("add-to-cart"),
    _beat("checkpoint"),
    _beat("queued"),
    _beat("complete"),
    _beat("attention"),
    Step("blocked", (_ear("blocked"),), sound="blocked"),
    Step("thinking (5)", (_task("t5", "started"),)),
    Step("stopped", (_ear("stop"),), "exit", sound="stop"),
    Step("idle", (_task("t5", "done"),), "exit", LONG_S),
)


@dataclass
class Run:
    child: subprocess.Popen
    sent: list[dict[str, Any]] = field(default_factory=list)
    counter: int = 0


def _message(item: Any) -> dict[str, Any] | None:
    return dict(item) if isinstance(item, dict) else overlay.to_message(item)


def _send(run: Run, step: Step) -> None:
    messages = [m for m in (_message(item) for item in step.sends) if m is not None]
    started = Quartz.CACurrentMediaTime()
    ids = []
    for message in messages:
        run.counter += 1
        message.update({"probe": run.counter, "m": Quartz.CACurrentMediaTime()})
        run.child.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        run.child.stdin.flush()
        ids.append(run.counter)
    run.sent.append({"step": step.name, "m": started, "ids": ids})


def launch(home: Path, dark: bool, probe: Path, reduce: bool, source: Path) -> subprocess.Popen:
    style = ["-AppleInterfaceStyle", "Dark"] if dark else ["-NSRequiresAquaSystemAppearance", "YES"]
    env = {**os.environ, "HOME": str(home), overlay_probe.PROBE_ENV: str(probe)}
    if reduce:
        env[overlay_probe.REDUCE_ENV] = "1"
    return subprocess.Popen(
        [sys.executable, "-m", "zoya.overlay", *style],
        stdin=subprocess.PIPE,
        text=True,
        env=env,
        cwd=source,
    )


def drive(child: subprocess.Popen) -> list[dict[str, Any]]:
    overlay.caption_text("warm the caption filter before the clock starts")
    run = Run(child)
    for step in SCRIPT:
        _send(run, step)
        time.sleep(step.settle_s)
    time.sleep(DRAIN_S)
    return run.sent


# --- analysis ----------------------------------------------------------------------------------


def _load(probe: Path) -> tuple[list[dict], dict[int, dict]]:
    frames, messages = [], {}
    for line in probe.read_text("utf-8").splitlines():
        row = json.loads(line)
        if row["k"] == "frame":
            frames.append(row)
        elif row.get("id") is not None:
            messages[row["id"]] = row
    frames.sort(key=lambda r: r["t"])
    return frames, messages


def _look(frame: dict) -> tuple:
    return tuple(json.dumps(frame.get(key)) for key in VISUAL_KEYS)


def _differs(frame: dict, before: dict) -> bool:
    """A new look, or a move that wasn't running (a blink changes no frame or size)."""
    return _look(frame) != _look(before) or bool(set(frame["busy"]) - set(before["busy"]))


def _moving(frame: dict, previous: dict) -> bool:
    return bool(frame["busy"]) or frame["contexts"] > 0 or _look(frame) != _look(previous)


def latencies_ms() -> dict[str, float]:
    try:
        import sounddevice as sd

        speakers = next(d for d in sd.query_devices() if SPEAKERS in d["name"])
        return {
            "high": speakers["default_high_output_latency"] * 1000,
            "low": speakers["default_low_output_latency"] * 1000,
        }
    except (StopIteration, ImportError, OSError):
        return dict(FALLBACK_LATENCY_MS)


def _window(frames: list[dict], start: float, end: float) -> list[dict]:
    return [f for f in frames if start <= f["t"] < end]


def _changes(frames: list[dict], before: dict) -> tuple[dict | None, dict | None, int]:
    """The first frame that looks different (within FIRST_LIMIT_S of the event, or it belongs to
    something else) and the last frame of the run of movement it starts."""
    previous, first, last, count, quiet = before, None, None, 0, 0
    for index, frame in enumerate(frames):
        moving = _moving(frame, previous)
        previous = frame
        if first is None:
            if frame["t"] - frames[0]["t"] > FIRST_LIMIT_S:
                return None, None, 0
            if moving and _differs(frame, before):
                first, last, count = frame, frame, index + 1
            continue
        quiet = 0 if moving else quiet + 1
        if quiet >= QUIET_FRAMES:
            break
        if moving:
            last = frame
    return first, last, count


def _states(frames: list[dict], before: dict) -> list[str]:
    seen = [before.get("state")]
    for frame in frames:
        if frame["state"] != seen[-1]:
            seen.append(frame["state"])
    return seen


def measure(step: Step, sent: dict, frames: list[dict], end: float, latency: dict) -> dict:
    start = sent["m"]
    before = next((f for f in reversed(frames) if f["t"] < start), frames[0])
    window = _window(frames, start, end)
    first, last, count = _changes(window, before)
    row = {"step": step.name, "kind": step.kind, "sound": step.sound, "messages": len(sent["ids"])}
    row["states"] = " → ".join(s or "·" for s in _states(window, before))
    if first is None:
        row.update({"visual": False, "first_ms": None, "frames": 0, "total_ms": None})
    else:
        row.update({"visual": True, "frames": count})
        row["first_ms"] = round((first["next"] - start) * 1000, 1)
        row["total_ms"] = round((last["next"] - start) * 1000, 1)
        row["motion_ms"] = round((last["next"] - first["next"]) * 1000, 1)
    if step.sound and step.sound not in LOOPED and first is not None:
        for name, ms in latency.items():
            onset = start * 1000 + BLOCK_MS / 2 + ms
            row[f"skew_{name}_ms"] = round(first["next"] * 1000 - onset, 1)
    return row


def analyse(probe: Path, sent: list[dict]) -> list[dict]:
    frames, _messages = _load(probe)
    latency = latencies_ms()
    rows = []
    for index, (step, record) in enumerate(zip(SCRIPT, sent, strict=True)):
        end = sent[index + 1]["m"] if index + 1 < len(sent) else frames[-1]["t"] + 1
        rows.append(measure(step, record, frames, end, latency))
    return rows


COLUMNS = (
    "step",
    "kind",
    "states",
    "first frame ms",
    "frames",
    "settled ms",
    "motion ms",
    "sound",
    "skew high",
    "skew low",
)


def table(rows: list[dict]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        cells = [r["step"], r["kind"], r["states"], r["first_ms"], r["frames"], r["total_ms"]]
        cells.append(r.get("motion_ms"))
        cells += [r["sound"], r.get("skew_high_ms", ""), r.get("skew_low_ms", "")]
        lines.append("| " + " | ".join("—" if c is None else str(c) for c in cells) + " |")
    return "\n".join(lines)


# --- side processes ----------------------------------------------------------------------------


def _backdrop(name: str) -> subprocess.Popen:
    script = Path(__file__).resolve().parent / "motion_backdrop.py"
    return subprocess.Popen([sys.executable, str(script), name])


def _recorder(out: Path, seconds: float) -> subprocess.Popen:
    import AppKit

    script = Path(__file__).resolve().parent / "motion_recorder.py"
    screen = AppKit.NSScreen.mainScreen().frame().size
    width, height = 1160, 640
    rect = [(screen.width - width) / 2, screen.height - height, width, height]
    command = [sys.executable, str(script), str(out), *map(str, rect), str(seconds)]
    return subprocess.Popen(command)


def _script_s() -> float:
    return START_S + sum(step.settle_s for step in SCRIPT) + DRAIN_S + 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--reduce", action="store_true", help="Reduce Motion, forced in the child")
    parser.add_argument("--backdrop", choices=("daylight", "night", "vivid"))
    parser.add_argument("--record", action="store_true", help="record the screen frame by frame")
    parser.add_argument("--again", action="store_true", help="re-analyse a finished run")
    parser.add_argument("--source", type=Path, default=hub_fixture.REPO, help="code to run")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.again:
        saved = json.loads((args.out / "rows.json").read_text())
        return _report(args.out, saved["sent"], saved.get("dark", args.dark))
    if Quartz.CGDisplayIsAsleep(Quartz.CGMainDisplayID()):
        sys.exit("The display is asleep, so no frames tick: wake it first (caffeinate -u -t 2).")
    probe = args.out / "probe.jsonl"
    probe.unlink(missing_ok=True)
    helpers = [_backdrop(args.backdrop)] if args.backdrop else []
    if args.record:
        helpers.append(_recorder(args.out / "motion.mp4", _script_s()))
    child = launch(hub_fixture.make_home(), args.dark, probe, args.reduce, args.source)
    try:
        time.sleep(START_S)
        sent = drive(child)
    finally:
        child.stdin.close()
        child.wait()
    for helper in helpers:
        if helper.args[1].endswith("motion_backdrop.py"):
            helper.terminate()
        helper.wait()
    return _report(args.out, sent, args.dark)


JUMP_PT = 1.0
SPIKE = 0.2


def _pill_spot(frame: dict) -> tuple[float, float] | None:
    if frame["panel"] is None:
        return None
    x, y = frame["panel"][0] + frame["pill"][0], frame["panel"][1] + frame["pill"][1]
    return x + frame["pill"][2] / 2, y


def _alphas(frame: dict) -> list[float]:
    return [(frame[key] or [0.0] * 5)[4] for key in ("panel", "glow", "cursor")]


def _spike(before: dict, frame: dict, after: dict) -> bool:
    trio = zip(_alphas(before), _alphas(frame), _alphas(after), strict=True)
    return any(min(a, c) - b > SPIKE or b - max(a, c) > SPIKE for a, b, c in trio)


def audit(frames: list[dict], dark: bool) -> list[str]:
    """Frame by frame: a wrong-theme frame, the pill's anchored spot moving (a jump), or a
    window's opacity spiking or dipping for a frame (a flash)."""
    issues = []
    for index, frame in enumerate(frames):
        at = f"{frame['t']:.3f}"
        if frame.get("dark", dark) != dark:
            issues.append(f"{at} wrong theme")
        if 0 < index < len(frames) - 1 and _spike(frames[index - 1], frame, frames[index + 1]):
            issues.append(f"{at} flash")
        spot, last = _pill_spot(frame), _pill_spot(frames[index - 1]) if index else None
        if spot and last and max(abs(a - b) for a, b in zip(spot, last, strict=True)) > JUMP_PT:
            issues.append(f"{at} jump {last} → {spot}")
    return issues


def _report(out: Path, sent: list[dict], dark: bool) -> int:
    rows = analyse(out / "probe.jsonl", sent)
    frames, _messages = _load(out / "probe.jsonl")
    issues = audit(frames, dark)
    (out / "audit.txt").write_text(f"{len(frames)} frames\n" + "\n".join(issues) + "\n")
    print(f"audit: {len(frames)} frames, {len(issues)} issues", *issues[:20], sep="\n")
    saved = {"sent": sent, "rows": rows, "dark": dark}
    (out / "rows.json").write_text(json.dumps(saved, indent=1))
    (out / "table.md").write_text(table(rows) + "\n")
    print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
