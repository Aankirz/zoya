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
    assert entry["did"] == "Placing the order"


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
