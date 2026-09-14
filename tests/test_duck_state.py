"""A killed run must never leave the Mac quiet (duck state file, D37 user-harm path)."""

from __future__ import annotations

import pytest

from zoya import audio


@pytest.fixture
def mac(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    """A fake system volume behind osascript, and a fresh process's module state."""
    volume = {"level": 100}

    def fake_volume(script: str) -> str:
        if script.startswith("output volume"):
            return str(volume["level"])
        volume["level"] = int(script.rsplit(" ", 1)[-1])
        return ""

    monkeypatch.setattr(audio, "_volume", fake_volume)
    monkeypatch.setattr(audio, "DUCK_STATE_FILE", tmp_path / "duck_state.json")
    monkeypatch.setattr(audio, "_ducked_from", None)
    return volume


def kill(monkeypatch) -> None:  # noqa: ANN001
    """kill -9: no restore runs; the next process starts with empty module state."""
    monkeypatch.setattr(audio, "_ducked_from", None)


def test_restart_after_kill_restores_original_volume(mac, monkeypatch) -> None:  # noqa: ANN001
    audio._duck_now()
    kill(monkeypatch)
    audio.restore_after_kill()
    assert mac["level"] == 100 and not audio.DUCK_STATE_FILE.exists()


def test_repeated_kills_while_ducked_do_not_compound(mac, monkeypatch) -> None:  # noqa: ANN001
    for _ in range(3):
        audio._duck_now()
        kill(monkeypatch)
    assert mac["level"] == 30  # still one duck below the user's level, not 100 → 30 → 9 → 3
    audio.restore_after_kill()
    assert mac["level"] == 100


def test_normal_restore_clears_state(mac) -> None:  # noqa: ANN001
    audio._duck_now()
    audio._restore_now()
    audio.restore_after_kill()  # nothing left to undo
    assert mac["level"] == 100 and not audio.DUCK_STATE_FILE.exists()
