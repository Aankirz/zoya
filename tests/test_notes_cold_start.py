"""A4: a cold Notes launch gets the longer timeout; a running Notes keeps the short one."""

from zoya import config
from zoya.tools import notes


def test_a_cold_notes_launch_gets_the_cold_start_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(notes, "notes_running", lambda: False)
    monkeypatch.setattr(notes, "osascript", lambda *a, timeout: calls.append(timeout) or "")

    notes.notes_create(body="pick up the dry cleaning")

    assert calls == [config.NOTES_COLD_START_TIMEOUT_S]


def test_a_running_notes_keeps_the_short_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(notes, "notes_running", lambda: True)
    monkeypatch.setattr(notes, "osascript", lambda *a, timeout: calls.append(timeout) or "x")

    notes.notes_search(query="dry cleaning")

    assert calls == [config.OSASCRIPT_TIMEOUT_S]
