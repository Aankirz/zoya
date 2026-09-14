"""Quit (D37): the phrase parser, and quitting cancels a waiting confirmation, never confirms."""

from __future__ import annotations

import signal
import threading

import pytest

from zoya import orchestrator, safety, shutdown, speech


@pytest.mark.parametrize(
    "text",
    [
        "Zoya, quit.",
        "quit",
        "Quit Zoya",
        "exit",
        "Zoya shut down",
        "band karo",
        "Zoya, band karo",
        "please quit",
        "Hey Zoya, exit now",
        "बंद करो",
    ],
)
def test_quit_phrases(text: str) -> None:
    assert shutdown.is_quit_phrase(text)


@pytest.mark.parametrize(
    "text",
    [
        "stop",
        "Zoya, stop",
        "music band karo",
        "quit the app",
        "exit full screen",
        "how do I quit",
        "don't quit",
        "goodbye",
        "light band karo",
    ],
)
def test_not_quit_phrases(text: str) -> None:
    assert not shutdown.is_quit_phrase(text)


def test_quit_cancels_pending_confirmation_and_signals_once(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(orchestrator, "stop_task", lambda name="": calls.append(("stop", name)))
    monkeypatch.setattr(safety, "cancel_pending", lambda task_id=None: calls.append("cancel"))
    monkeypatch.setattr(speech, "say_and_wait", lambda text, timeout_s: calls.append(text))
    monkeypatch.setattr(shutdown.os, "kill", lambda pid, sig: calls.append(sig))
    monkeypatch.setattr(shutdown, "_quitting", threading.Lock())

    shutdown.quit_zoya()
    shutdown.quit_zoya()  # a second press does nothing

    assert calls == [
        ("stop", "everything"),
        ("stop", ""),
        "cancel",
        shutdown.GOODBYE,
        signal.SIGTERM,
    ]
