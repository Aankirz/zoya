"""Done-when 1: every flow scenario runs offline with the scripted brain and passes its checks.

Silence is checked by the CLI and live runs and by tests/test_progress.py: a background
pytest run on macOS stretched scaled sleeps up to five times, so wall-clock gaps here are noise."""

import pytest

from evals.flows import sim

SCALE = 0.15
SCENARIOS = sim.load()


@pytest.fixture(scope="module")
def simulator(tmp_path_factory):
    log_dir = tmp_path_factory.mktemp("flows")
    simulator = sim.Simulator(scale=SCALE, log_dir=log_dir, check_silence=False)
    with simulator.installed():
        yield simulator


def test_there_are_at_least_forty_scenarios_and_a_third_are_held_out():
    held_out = [s for s in SCENARIOS if s["set"] == "heldout"]
    tuned = [s for s in SCENARIOS if s["set"] == "dev"]
    assert len(held_out) + len(tuned) >= 40
    assert len(held_out) * 3 >= len(held_out) + len(tuned)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_passes_offline(simulator, scenario):
    turns = simulator.run(scenario)

    assert [t.failed for t in turns] == [[] for _ in turns]
