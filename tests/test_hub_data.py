"""P3c: the Hub shows what Zoya did, never a password, OTP, card number or key (§12.3, D37)."""

import json
from datetime import datetime

import pytest

from zoya import config, hub_data

TODAY = datetime.now().astimezone()
AT = TODAY.isoformat(timespec="milliseconds")


def _timing(command: str, **extra: object) -> dict:
    return {
        "at": AT,
        "task_id": extra.pop("task_id", "t1"),
        "route": "skill",
        "ok": True,
        "command": command,
    } | extra


@pytest.fixture
def logs(tmp_path, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setattr(config, "TIMING_LOG", tmp_path / "timing.log")
    monkeypatch.setattr(config, "CONFIRMATION_LOG", tmp_path / "confirmations.log")
    monkeypatch.setattr(config, "SAID_LOG", tmp_path / "said.log")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abcdefghijklmnop")
    return tmp_path


def _write(path, rows: list) -> None:  # noqa: ANN001
    path.write_text("\n".join(json.dumps(r) if isinstance(r, dict) else r for r in rows) + "\n")


@pytest.mark.parametrize(
    "command",
    [
        "my card number is 4111 1111 1111 1111",
        "the OTP is 482913",
        "my password is hunter2",
        "use the key sk-proj-abcdefghijklmnop",
    ],
)
def test_history_never_shows_a_secret(logs, command) -> None:  # noqa: ANN001
    _write(logs / "timing.log", [_timing(command)])
    shown = json.dumps(hub_data.history())
    for secret in ("4111", "482913", "hunter2", "sk-proj-abcdefghijklmnop"):
        assert secret not in shown


def test_history_joins_the_confirmation_to_its_request(logs) -> None:  # noqa: ANN001
    _write(
        logs / "timing.log", [_timing("buy the earphones", task_id="t9", tool="amazon_place_order")]
    )
    confirm = {
        "task_id": "t9",
        "at": AT,
        "action": "place order",
        "amount": "₹1,249",
        "recipient_or_item": "amazon.in",
        "decision": "confirmed",
    }
    _write(logs / "confirmations.log", [confirm])
    [entry] = hub_data.history()
    assert entry["heard"] == "buy the earphones"
    assert entry["confirm"]["decision"] == "confirmed"
    assert entry["outcome"] == "Ordered · ₹1,249 · you said confirm"


def test_history_skips_broken_lines_and_is_newest_first(logs) -> None:  # noqa: ANN001
    older = _timing("first", task_id="a", at="2026-09-01T10:00:00.000+00:00")
    _write(
        logs / "timing.log",
        [older, "{not json", "[1, 2]", _timing("second", task_id="b"), {"at": AT}],
    )
    assert [e["heard"] for e in hub_data.history()] == ["second", "first"]


def test_today_holds_only_today(logs) -> None:  # noqa: ANN001
    older = _timing("last week", task_id="a", at="2026-09-01T10:00:00.000+00:00")
    _write(logs / "timing.log", [older, _timing("this morning", task_id="b")])
    assert [e["heard"] for e in hub_data.today()] == ["this morning"]


def test_no_logs_is_an_empty_history(logs) -> None:  # noqa: ANN001
    assert hub_data.history() == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            {"valid": True, "month": "2026-09", "usedCents": 123.46, "capCents": 500},
            {"month": "2026-09", "usedCents": 123.46, "capCents": 500},
        ),
        ({"valid": True}, None),
        ({"valid": True, "month": "2026-09", "usedCents": "12", "capCents": 500}, None),
        ({"valid": True, "month": "2026-09", "usedCents": -1, "capCents": 500}, None),
        ({"valid": True, "month": "2026-09", "usedCents": 1, "capCents": True}, None),
        ([], None),
    ],
)
def test_plan_accepts_only_a_well_formed_reply(body, expected) -> None:  # noqa: ANN001
    assert hub_data.parse_plan(body) == expected


def test_clearing_history_empties_it_for_good(logs) -> None:  # noqa: ANN001
    confirm = {"task_id": "t1", "at": AT, "action": "send", "decision": "cancel"}
    _write(logs / "timing.log", [_timing("first", task_id="t1"), _timing("second", task_id="t2")])
    _write(logs / "confirmations.log", [confirm])
    assert hub_data.clear_history() == 2
    assert hub_data.history() == []
    assert (logs / "confirmations.log").read_text() == ""


def test_what_zoya_said_is_scrubbed_before_it_is_written(logs) -> None:  # noqa: ANN001
    hub_data.record_said("t0", "Your OTP is 482913, and I typed it.")
    hub_data.record_said("t1", "Opened Notes for you.")
    written = config.SAID_LOG.read_text()
    assert "482913" not in written
    _write(logs / "timing.log", [_timing("open notes", task_id="t1", tool="open_app")])
    [entry] = hub_data.history()
    assert entry["said"] == "Opened Notes for you."
    assert entry["outcome"] == "Opened Notes"
    assert entry["app"] == "Notes"


def test_history_speaks_in_human_words_and_collapses_repeats(logs) -> None:  # noqa: ANN001
    rows = [
        _timing("remember my sister's birthday is 12 March", task_id="a", tool="memory_add"),
        _timing("when is my sister's birthday", task_id="b", route="orchestrator"),
        _timing("when is my sister's birthday", task_id="c", route="orchestrator"),
        _timing("why is the sky blue", task_id="d", ok=False),
    ]
    _write(logs / "timing.log", rows)
    entries = hub_data.history()
    words = json.dumps(entries)
    for internal in ("remembering", "answered", "Didn't finish"):
        assert internal not in words
    assert [e["heard"] for e in entries] == [
        "why is the sky blue",
        "when is my sister's birthday",
        "remember my sister's birthday is 12 March",
    ]
    assert entries[1]["times"] == 2
    assert entries[2]["outcome"] == "Remembered"
    assert entries[0]["failed"] is True


@pytest.mark.parametrize(
    ("command", "tool", "app"),
    [
        ("open notes", "open_app", "Notes"),
        ("please open system settings", "open_app", "System Settings"),
        ("play some lofi", "spotify_play_song", "Spotify"),
        ("open ../../etc/passwd", "open_app", None),
        ("remember I like chai", "memory_add", None),
    ],
)
def test_each_request_names_its_app_safely(logs, command, tool, app) -> None:  # noqa: ANN001
    _write(logs / "timing.log", [_timing(command, tool=tool)])
    [entry] = hub_data.history()
    assert entry.get("app") == app


def test_the_sidebar_counts_things_done_with_repeats_and_without_failures(
    logs,
) -> None:  # noqa: ANN001
    rows = [
        _timing("open notes", task_id="a", tool="open_app"),
        _timing("open notes", task_id="b", tool="open_app"),
        _timing("book a table", task_id="c", ok=False),
    ]
    _write(logs / "timing.log", rows)
    assert hub_data.done_count(hub_data.today()) == 2


def test_with_wispr_flow_installed_the_default_hotkey_stays_off_fn(monkeypatch, tmp_path):
    from zoya import hotkey

    monkeypatch.setattr(hub_data, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(hotkey, "wispr_flow_installed", lambda: True)
    hotkey.default_choice.cache_clear()
    try:
        assert hub_data.settings()["hotkey"] == "control-option"
        assert "fn" not in hotkey.chosen()
    finally:
        hotkey.default_choice.cache_clear()
