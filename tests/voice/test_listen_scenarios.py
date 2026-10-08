"""S1-Listen: the scripted scenarios through the real VoiceLoop (tests/voice/sim.py)."""

from __future__ import annotations

import pytest

from tests.voice.scenarios import DEV, HELDOUT, Case
from tests.voice.sim import run_script

# Fails on the code this simulator was written against; each fix removes its names.
KNOWN_FAILING = {
    "after wake: Hindi news anchor on TV",
    "push-to-talk cancel while she speaks",
}


def cases(group: list[Case]) -> list:
    return [
        pytest.param(
            case,
            id=case.name,
            marks=[pytest.mark.xfail(strict=True)] if case.name in KNOWN_FAILING else [],
        )
        for case in group
    ]


def outcome(monkeypatch: pytest.MonkeyPatch, case: Case) -> tuple[list[str], int]:
    trace, _loop = run_script(
        monkeypatch, case.sounds, replies=case.replies, running=list(case.running)
    )
    return trace.dispatched, len(trace.stops)


def passes(dispatched: list[str], stops: int, case: Case) -> bool:
    if len(dispatched) != len(case.dispatched) or stops != case.stops:
        return False
    return all(
        want.lower() in got.lower() for want, got in zip(case.dispatched, dispatched, strict=True)
    )


@pytest.mark.parametrize("case", cases(DEV))
def test_dev_scenario(monkeypatch, case):
    dispatched, stops = outcome(monkeypatch, case)
    assert passes(dispatched, stops, case), (dispatched, stops)


@pytest.mark.parametrize("case", cases(HELDOUT))
def test_heldout_scenario(monkeypatch, case):
    dispatched, stops = outcome(monkeypatch, case)
    assert passes(dispatched, stops, case), (dispatched, stops)


def test_the_simulator_is_deterministic(monkeypatch):
    first = [outcome(monkeypatch, case) for case in DEV]
    assert first == [outcome(monkeypatch, case) for case in DEV]
