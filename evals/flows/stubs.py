"""Patches for one simulator run: speech captured, side effects faked, logs kept out of logs/."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from evals.flows import fakes

if TYPE_CHECKING:
    from evals.flows.sim import Simulator


def install(sim: Simulator) -> None:
    from zoya import config

    config.load_env()
    _speech(sim)
    _quiet_side_effects(sim)
    _logs(sim)
    _tools(sim)
    if not sim.live:
        _offline_models(sim)


def _speech(sim: Simulator) -> None:
    from zoya import speech

    p = sim.patches
    p.set(speech, "narrate", sim.hear("zoya"))
    p.set(speech, "say_and_wait", lambda text, *_a, **_k: (sim.hear("zoya")(text), True)[1])
    p.set(speech, "is_speaking", lambda: False)
    p.set(speech, "cancel", lambda: None)


def _quiet_side_effects(sim: Simulator) -> None:
    from zoya import aws, harness, hub_data, orchestrator
    from zoya.tools import memory

    p = sim.patches
    p.set(orchestrator.browser, "task_tabs", lambda: frozenset())
    p.set(orchestrator.browser, "close_task_tabs", lambda _before: [])
    p.set(memory, "capture_outcome", lambda *_a, **_k: None)
    p.set(orchestrator.memory, "user_profile", lambda: "")
    p.set(orchestrator, "recent_corrections", lambda: [])
    p.set(aws, "record_task", lambda *_a, **_k: None)
    p.set(hub_data, "record_said", lambda *_a, **_k: None)
    p.set(harness, "learned_pick", lambda _command: None)
    p.set(harness, "learn_pick", lambda *_a, **_k: None)
    p.set(orchestrator.events, "emit", lambda _event: None)


def _logs(sim: Simulator) -> None:
    from zoya import orchestrator, safety, tasks

    sim.log_dir.mkdir(parents=True, exist_ok=True)
    timing_log = sim.log_dir / "timing.log"
    for module in (orchestrator, safety, tasks):
        sim.patches.set(module, "TIMING_LOG", timing_log)
    sim.patches.set(tasks, "LOG_DIR", sim.log_dir)
    sim.patches.set(safety, "CONFIRMATION_LOG", sim.log_dir / "confirmations.log")


def _tools(sim: Simulator) -> None:
    from zoya import harness, orchestrator
    from zoya.tools import ToolError

    real_build = orchestrator.build_orchestrator

    def build(**kwargs: Any) -> Any:
        agent = real_build(**kwargs)
        agent.hooks.add_hook(fakes.SimTools(sim.recorder))
        return agent

    def run_action(action: str, args: dict[str, Any]) -> str:
        sim.recorder.tool(action)
        if hang := sim.turn.get("hang_actions_s"):
            sim.recorder.wait(hang)
            raise ToolError("The browser couldn't do that (TimeoutError).")
        sim.recorder.wait(fakes.TOOL_LATENCY_S.get(action, fakes.DEFAULT_TOOL_LATENCY_S))
        return fakes.fixture(action, args)

    def run_fast_tool(decision: Any) -> str:
        sim.recorder.tool(decision.tool or "")
        sim.recorder.wait(fakes.TOOL_LATENCY_S.get(decision.tool, fakes.DEFAULT_TOOL_LATENCY_S))
        return fakes.fixture(decision.tool or "", decision.args)

    sim.patches.set(orchestrator, "build_orchestrator", build)
    sim.patches.set(harness, "run_action", run_action)
    sim.patches.set(orchestrator, "run_fast_tool", run_fast_tool)


def _offline_models(sim: Simulator) -> None:
    from zoya import aws, models, router

    def brain(cache_key: str = "", effort: str = "high") -> Any:
        return fakes.ScriptedBrain(sim.next_step, sim.recorder, effort)

    def jev(text: str) -> Any:
        time.sleep(fakes.JEV_S * sim.scale)
        return router.RouteDecision("orchestrator", source="jev")

    p = sim.patches
    p.set(models, "brain_planning_model", brain)
    p.set(router, "ask_jev_route", jev)
    p.set(aws, "needs_translation", lambda _text: False)
