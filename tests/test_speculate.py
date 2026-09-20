"""Speculation (Phase B item 2, D82): a route prepared while the user was still speaking is
handed over only when the final transcript says the same thing, and is thrown away otherwise."""

from __future__ import annotations

import time

import pytest

from zoya import speculate
from zoya.router import RouteDecision


@pytest.fixture(autouse=True)
def clean():
    speculate.discard()
    yield
    speculate.discard()


def fake_route(calls: list[str], delay: float = 0.0):
    def routed(text: str) -> RouteDecision:
        calls.append(text)
        time.sleep(delay)
        return RouteDecision("fast", "mute", source="jev", text=text, timings_ms={"jev_ms": 600})

    return routed


def test_a_matching_final_transcript_gets_the_prepared_route(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(speculate, "route", fake_route(calls))
    speculate.prepare("kill the sound")

    decision = speculate.commit("kill the sound")

    assert decision is not None
    assert decision.tool == "mute"
    assert decision.timings_ms["speculated_ms"] >= 0
    assert calls == ["kill the sound"]


def test_filler_and_case_do_not_count_as_divergence(monkeypatch):
    monkeypatch.setattr(speculate, "route", fake_route([]))
    speculate.prepare("kill the sound")

    assert speculate.commit("Zoya, kill the sound please") is not None


def test_a_diverging_final_transcript_is_discarded(monkeypatch):
    monkeypatch.setattr(speculate, "route", fake_route([]))
    speculate.prepare("kill the")

    assert speculate.commit("kill the lights in the bedroom") is None
    assert speculate.commit("kill the") is None


def test_nothing_prepared_means_route_normally():
    assert speculate.commit("open Spotify") is None


def test_repeating_the_same_partial_does_not_route_again(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(speculate, "route", fake_route(calls))
    speculate.prepare("kill the sound")
    speculate.prepare("kill the sound!")
    speculate.prepare("  kill   the   sound ")

    assert calls == ["kill the sound"]


def test_a_route_that_has_not_landed_is_not_waited_on_forever(monkeypatch):
    monkeypatch.setattr(speculate, "route", fake_route([], delay=5.0))
    monkeypatch.setattr(speculate, "SPECULATION_WAIT_S", 0.05)
    speculate.prepare("kill the sound")

    started = time.monotonic()
    assert speculate.commit("kill the sound") is None
    assert time.monotonic() - started < 1.0


def test_a_stale_preparation_is_not_committed(monkeypatch):
    monkeypatch.setattr(speculate, "route", fake_route([]))
    monkeypatch.setattr(speculate, "SPECULATION_TTL_S", -1.0)
    speculate.prepare("kill the sound")

    assert speculate.commit("kill the sound") is None


def test_a_failing_route_degrades_instead_of_raising(monkeypatch):
    def broken(text: str) -> RouteDecision:
        raise RuntimeError("router exploded")

    monkeypatch.setattr(speculate, "route", broken)
    speculate.prepare("kill the sound")

    assert speculate.commit("kill the sound") is None


def test_repeating_the_same_partial_does_not_spend_the_utterance_budget(monkeypatch):
    monkeypatch.setattr(speculate, "route", fake_route([]))

    assert speculate.prepare("turn it") is True
    assert speculate.prepare("turn it") is False
    assert speculate.prepare("turn it please") is False
    assert speculate.prepare("turn it down") is True
