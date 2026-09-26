from __future__ import annotations

import pytest

from zoya import app

PID = 4242
NEW_PID = 4343


@pytest.fixture(autouse=True)
def zoya_home(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "ZOYA_HOME", tmp_path)
    monkeypatch.setattr(app, "RUN_MARKER", tmp_path / "running")
    monkeypatch.setattr(app, "CRASH_LOG", tmp_path / "crashes.json")


def test_a_clean_start_is_not_a_crash():
    assert app.record_start(1000.0, PID) == (False, True)


def test_a_marker_left_by_another_process_is_a_crash():
    app.record_start(1000.0, PID)
    assert app.record_start(1010.0, NEW_PID) == (True, True)


def test_restarting_itself_with_execv_is_not_a_crash():
    app.record_start(1000.0, PID)
    assert app.record_start(1010.0, PID) == (False, True)


def test_the_third_crash_in_ten_minutes_stops_restarts():
    app.record_start(1000.0, 1)
    app.record_start(1010.0, 2)
    app.record_start(1020.0, 3)
    assert app.record_start(1030.0, 4) == (True, False)
    assert not app.RUN_MARKER.exists()


def test_crashes_older_than_the_window_do_not_count():
    app.record_start(1000.0, 1)
    app.record_start(1010.0, 2)
    app.record_start(1020.0, 3)
    assert app.record_start(1020.0 + 11 * 60, 4) == (True, True)
