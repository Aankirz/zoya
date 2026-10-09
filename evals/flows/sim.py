"""The flow simulator: commands run as Task Manager tasks, exactly as the voice loop starts them
(`orchestrator.start_task`), with speech captured instead of played."""

from __future__ import annotations

import json
import os
import statistics
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evals.flows import fakes

FLOWS_DIR = Path(__file__).parent
SETS = ("dev", "heldout", "repro")
TURN_LIMIT_S = 90.0
SILENCE_LIMIT_MS = 10_000
ASK_LIMIT_MS = 2_000
FIRST_WORD_TARGET_MS = 1_000
LONG_COMMAND_MS = 1_500
SHORT_REPLY_WORDS = 15
GENERIC_ACKS = frozenset({"On it.", "Okay.", "One moment.", "Sure.", "Still working on it."})
STOPPED = "Okay, stopped."


def load(names: tuple[str, ...] = SETS) -> list[dict[str, Any]]:
    scenarios = []
    for name in names:
        for scenario in json.loads((FLOWS_DIR / f"scenarios_{name}.json").read_text("utf-8")):
            scenarios.append({**scenario, "set": name})
    return scenarios


@dataclass
class Turn:
    scenario: str
    set: str
    category: str
    say: str
    said: list[tuple[int, str, str]] = field(default_factory=list)
    tools: list[tuple[int, str]] = field(default_factory=list)
    route: str = ""
    ok: bool = False
    spoken: str = ""
    model_calls: int = 0
    total_ms: int = 0
    first_word_ms: int | None = None
    first_useful_ms: int | None = None
    max_silence_ms: int = 0
    network_ms: int = 0
    tool_wait_ms: int = 0
    in_process_ms: int = 0
    failed: list[str] = field(default_factory=list)


class Patches:
    def __init__(self) -> None:
        self._undo: list[tuple[Any, str, Any]] = []

    def set(self, target: Any, name: str, value: Any) -> None:
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, value in reversed(self._undo):
            setattr(target, name, value)
        self._undo.clear()


class Simulator:
    def __init__(
        self,
        live: bool = False,
        scale: float = 1.0,
        log_dir: Path | None = None,
        check_silence: bool = True,
    ):
        self.live, self.scale = live, (1.0 if live else scale)
        self.check_silence = check_silence
        self.log_dir = log_dir or FLOWS_DIR / ".runs"
        self.recorder = fakes.Recorder(scale=self.scale)
        self.said: list[tuple[int, str, str]] = []
        self.steps: list[dict[str, Any]] = []
        self.turn: dict[str, Any] = {}
        self.patches = Patches()
        self.lock = threading.Lock()

    @contextmanager
    def installed(self) -> Iterator[Simulator]:
        from evals.flows import stubs

        environment = dict(os.environ)
        stubs.install(self)
        try:
            yield self
        finally:
            self.patches.undo()
            os.environ.clear()
            os.environ.update(environment)

    def hear(self, source: str) -> Callable[..., None]:
        def record(text: str, *_: Any, **__: Any) -> None:
            if text and text.strip():
                with self.lock:
                    self.said.append((self.recorder.now_ms(), text.strip(), source))

        return record

    def next_step(self) -> dict[str, Any]:
        with self.lock:
            return self.steps.pop(0) if self.steps else {"text": "Done."}

    def run(self, scenario: dict[str, Any]) -> list[Turn]:
        from zoya import orchestrator

        orchestrator._conversation.clear()
        return [self._turn(scenario, spec) for spec in scenario["turns"]]

    def _turn(self, scenario: dict[str, Any], spec: dict[str, Any]) -> Turn:
        from zoya import orchestrator

        self.turn = spec
        self.steps = list(
            spec.get("offline") or fakes.default_steps(scenario["category"], spec["say"])
        )
        self.said = []
        self.recorder.reset()
        timers = self._timers(spec)
        done, box = threading.Event(), {}

        def on_done(result: Any) -> None:
            box["result"] = result
            done.set()

        orchestrator.start_task(spec["say"], {}, on_done=on_done)
        finished = done.wait(TURN_LIMIT_S * self.scale)
        for timer in timers:
            timer.cancel()
        turn = self._measure(scenario, spec, box.get("result"), finished)
        _settle_tasks()
        return turn

    def _timers(self, spec: dict[str, Any]) -> list[threading.Timer]:
        timers = []
        if (at := spec.get("stop_at_s")) is not None:
            timers.append(threading.Timer(at * self.scale, self._user_stop))
        if (at := spec.get("internal_cancel_at_s")) is not None:
            timers.append(threading.Timer(at * self.scale, _internal_cancel))
        for timer in timers:
            timer.daemon = True
            timer.start()
        return timers

    def _user_stop(self) -> None:
        from zoya import orchestrator

        self.hear("voice")(orchestrator.stop_task())

    def _measure(self, scenario: dict, spec: dict, result: Any, finished: bool) -> Turn:
        turn = Turn(scenario["id"], scenario["set"], scenario["category"], spec["say"])
        turn.total_ms = self.recorder.now_ms()
        with self.lock:
            turn.said = list(self.said)
        turn.tools = list(self.recorder.tools)
        if result is not None:
            turn.route, turn.ok, turn.spoken = result.decision.route, result.ok, result.spoken
            turn.model_calls = _model_calls(result)
        timing(turn)
        split_time(turn, self.recorder, result)
        turn.failed = checks(turn, spec.get("expect") or {}, finished, self.check_silence)
        return turn


def _model_calls(result: Any) -> int:
    from zoya import orchestrator

    return orchestrator.model_calls(result)


def _internal_cancel() -> None:
    from zoya import tasks

    running = tasks.running()
    if running:
        running[-1].cancel.set()


def _settle_tasks() -> None:
    from zoya import tasks

    deadline = time.monotonic() + TURN_LIMIT_S
    while tasks.running() and time.monotonic() < deadline:
        time.sleep(0.05)


NETWORK_STAGES = ("jev_ms", "model_ms", "translate_ms")


def split_time(turn: Turn, recorder: fakes.Recorder, result: Any) -> None:
    """Model and Jev network time, tool waiting, and the rest: Zoya's own in-process time."""
    stages = result.timings_ms if result is not None else {}
    router_ms = sum(stages.get(name, 0) for name in NETWORK_STAGES)
    brain_ms = recorder.model_s * 1000 / recorder.scale
    turn.network_ms = round(router_ms / recorder.scale + brain_ms)
    turn.tool_wait_ms = round(recorder.tool_s * 1000 / recorder.scale)
    turn.in_process_ms = max(0, turn.total_ms - turn.network_ms - turn.tool_wait_ms)


def time_split_table(turns: list[Turn]) -> str:
    lines = [
        "| id | total ms | model+Jev network ms | tool wait ms | in-process ms | in-process % |",
        "|---|---|---|---|---|---|",
    ]
    for t in turns:
        share = round(100 * t.in_process_ms / t.total_ms) if t.total_ms else 0
        lines.append(
            f"| {t.scenario} | {t.total_ms} | {t.network_ms} | {t.tool_wait_ms}"
            f" | {t.in_process_ms} | {share} |"
        )
    shares = sorted(t.in_process_ms / t.total_ms for t in turns if t.total_ms)
    if shares:
        p90 = shares[min(len(shares) - 1, round(0.9 * (len(shares) - 1)))]
        median = statistics.median(shares)
        lines.append(f"\nIn-process share: p50 {median:.0%}, p90 {p90:.0%} (n={len(shares)})")
    return "\n".join(lines)


def timing(turn: Turn) -> None:
    times = [at for at, _text, _source in turn.said]
    turn.first_word_ms = times[0] if times else None
    useful = [at for at, text, _s in turn.said if text not in GENERIC_ACKS]
    turn.first_useful_ms = useful[0] if useful else None
    marks = [0, *times, turn.total_ms]
    turn.max_silence_ms = max(b - a for a, b in zip(marks, marks[1:], strict=False))


def checks(
    turn: Turn, expect: dict[str, Any], finished: bool, check_silence: bool = True
) -> list[str]:
    failed = [] if finished else ["did not finish"]
    texts = [text for _at, text, _source in turn.said]
    actions = [(at, name) for at, name in turn.tools if fakes.is_action(name)]
    if STOPPED in texts and not expect.get("stopped"):
        failed.append("said 'Okay, stopped.' without a user stop")
    if expect.get("stopped") and STOPPED not in texts:
        failed.append("user stop not honoured")
    if check_silence and turn.max_silence_ms >= SILENCE_LIMIT_MS:
        failed.append(f"silent {turn.max_silence_ms} ms")
    failed += _ask_checks(turn, expect, actions)
    if expect.get("acts") is True and not actions and not expect.get("stopped"):
        failed.append("no action taken")
    if expect.get("acts") is False and actions:
        failed.append(f"acted: {actions[0][1]}")
    if expect.get("short") and len(" ".join(texts).split()) > SHORT_REPLY_WORDS:
        failed.append("long reply to junk")
    return failed


def _ask_checks(turn: Turn, expect: dict[str, Any], actions: list[tuple[int, str]]) -> list[str]:
    question = next(((at, t) for at, t, s in turn.said if t.endswith("?") and s == "zoya"), None)
    if expect.get("asks") is True:
        if question is None:
            return ["did not ask for the missing detail"]
        if question[0] > ASK_LIMIT_MS:
            return [f"asked after {question[0]} ms"]
        if any(at <= question[0] for at, _name in actions):
            return ["acted before asking"]
    if expect.get("asks") is False and question and (not actions or question[0] < actions[0][0]):
        return ["asked although the detail was given"]
    return []


def summary(turns: list[Turn]) -> dict[str, Any]:
    by_set: dict[str, list[Turn]] = {}
    for turn in turns:
        by_set.setdefault(turn.set, []).append(turn)
    long_turns = [
        t for t in turns if t.total_ms > LONG_COMMAND_MS and t.first_useful_ms is not None
    ]
    useful = [t.first_useful_ms for t in long_turns]
    return {
        "passed": {name: _passed(group) for name, group in by_set.items()},
        "first_useful_p50_ms": round(statistics.median(useful)) if useful else None,
        "first_word_p50_ms": _p50([t.first_word_ms for t in long_turns]),
        "max_silence_ms": max((t.max_silence_ms for t in turns), default=0),
        "long_turns": len(long_turns),
    }


def _p50(values: list[int | None]) -> int | None:
    present = [v for v in values if v is not None]
    return round(statistics.median(present)) if present else None


def _passed(turns: list[Turn]) -> str:
    scenarios: dict[str, bool] = {}
    for turn in turns:
        scenarios[turn.scenario] = scenarios.get(turn.scenario, True) and not turn.failed
    return f"{sum(scenarios.values())}/{len(scenarios)}"


def table(turns: list[Turn]) -> str:
    lines = [
        "| id | set | say | route | tools | model calls | first word ms | first useful ms"
        " | total ms | max silence ms | ok | result |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in turns:
        tools = ", ".join(name for _at, name in t.tools) or "-"
        result = "pass" if not t.failed else "FAIL: " + "; ".join(t.failed)
        lines.append(
            f"| {t.scenario} | {t.set} | {t.say[:48]} | {t.route} | {tools[:40]} | {t.model_calls}"
            f" | {t.first_word_ms} | {t.first_useful_ms} | {t.total_ms} | {t.max_silence_ms}"
            f" | {t.ok} | {result} |"
        )
    return "\n".join(lines)


def save(turns: list[Turn], label: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = {"summary": summary(turns), "turns": [asdict(t) for t in turns]}
    (out_dir / f"{label}.json").write_text(json.dumps(body, indent=1, ensure_ascii=False), "utf-8")
    report = out_dir / f"{label}.md"
    text = f"{json.dumps(body['summary'])}\n\n{table(turns)}\n\n{time_split_table(turns)}\n"
    report.write_text(text, "utf-8")
    return report
