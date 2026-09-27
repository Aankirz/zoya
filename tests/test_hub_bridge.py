"""P3c, D119: the Hub page can ask Zoya for a fixed list of things, and nothing else (§12.2)."""

import pytest

from zoya import hub_bridge

GOOD_ID = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize(
    "body",
    [
        {"cmd": "getPage", "id": 1, "args": {"page": "today"}},
        {"cmd": "deleteMemory", "id": 2, "args": {"memory": GOOD_ID}},
        {"cmd": "openPermissionPane", "id": 3, "args": {"pane": "microphone"}},
        {"cmd": "checkForUpdates", "id": 4, "args": {}},
        {"cmd": "sendProblemReport", "id": 5, "args": {}},
        {"cmd": "setSetting", "id": 6, "args": {"key": "largerText", "value": True}},
        {"cmd": "setSetting", "id": 8, "args": {"key": "easierLetters", "value": False}},
        {"cmd": "setSetting", "id": 7, "args": {"key": "pillPosition", "value": "left"}},
    ],
)
def test_allowed_commands_pass(body) -> None:  # noqa: ANN001
    command = hub_bridge.parse(body)
    assert command is not None
    assert command.name == body["cmd"]


@pytest.mark.parametrize(
    "body",
    [
        {"cmd": "runPython", "id": 1, "args": {"code": "import os"}},
        {"cmd": "shell", "id": 1, "args": {}},
        {"cmd": "__class__", "id": 1, "args": {}},
        {"cmd": "quit", "id": 1, "args": {}},
    ],
)
def test_unknown_commands_are_refused(body) -> None:  # noqa: ANN001
    assert hub_bridge.parse(body) is None


@pytest.mark.parametrize(
    "body",
    [
        None,
        "getPage",
        ["getPage"],
        {},
        {"cmd": "getPage"},
        {"cmd": "getPage", "id": "1", "args": {"page": "today"}},
        {"cmd": "getPage", "id": True, "args": {"page": "today"}},
        {"cmd": "getPage", "id": 1, "args": {"page": "../../etc/passwd"}},
        {"cmd": "getPage", "id": 1, "args": {"page": "today", "extra": 1}},
        {"cmd": "getPage", "id": 1, "args": "today"},
        {"cmd": "deleteMemory", "id": 1, "args": {"memory": "*"}},
        {"cmd": "deleteMemory", "id": 1, "args": {"memory": GOOD_ID + "0"}},
        {"cmd": "openPermissionPane", "id": 1, "args": {"pane": "x-apple.systempreferences:evil"}},
        {"cmd": "setSetting", "id": 1, "args": {"key": "largerText", "value": "yes"}},
        {"cmd": "setSetting", "id": 1, "args": {"key": "pillPosition", "value": "top"}},
        {"cmd": "setSetting", "id": 1, "args": {"key": "__proto__", "value": True}},
        {"cmd": "checkForUpdates", "id": 1, "args": {"now": True}},
        {"cmd": "getPage", "id": 1, "args": {"page": "today"}, "more": 1},
    ],
)
def test_malformed_commands_are_refused(body) -> None:  # noqa: ANN001
    assert hub_bridge.parse(body) is None


@pytest.mark.parametrize(
    "body",
    [
        {"cmd": "prepareClearHistory", "id": 1, "args": {}},
        {"cmd": "clearHistory", "id": 2, "args": {"token": GOOD_ID}},
        {"cmd": "pageState", "id": 3, "args": {"page": "history"}},
    ],
)
def test_history_and_page_commands_pass(body) -> None:  # noqa: ANN001
    assert hub_bridge.parse(body) is not None


@pytest.mark.parametrize(
    "body",
    [
        {"cmd": "clearHistory", "id": 1, "args": {}},
        {"cmd": "clearHistory", "id": 1, "args": {"token": "yes"}},
        {"cmd": "clearHistory", "id": 1, "args": {"token": True}},
        {"cmd": "pageState", "id": 1, "args": {"page": "history", "headerVisible": True}},
        {"cmd": "pageState", "id": 1, "args": {"page": "nope"}},
    ],
)
def test_malformed_history_and_page_commands_are_refused(body) -> None:  # noqa: ANN001
    assert hub_bridge.parse(body) is None


def test_clearing_history_needs_the_confirm_steps_token() -> None:
    guard = hub_bridge.ClearGuard()
    assert guard.redeem(GOOD_ID) is False
    token = guard.issue()
    assert guard.redeem(GOOD_ID) is False
    assert guard.redeem(token) is True
    assert guard.redeem(token) is False


def test_a_confirm_token_expires() -> None:
    now = [100.0]
    guard = hub_bridge.ClearGuard(clock=lambda: now[0])
    token = guard.issue()
    now[0] += hub_bridge.CLEAR_TOKEN_TTL_S + 1
    assert guard.redeem(token) is False


def test_a_typed_request_passes_as_plain_text() -> None:
    command = hub_bridge.parse({"cmd": "ask", "id": 9, "args": {"text": "  open notes  "}})
    assert command is not None and command.args == {"text": "  open notes  "}
    assert hub_bridge.ask_text(command.args["text"]) == "open notes"


@pytest.mark.parametrize(
    "args",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "x" * (hub_bridge.ASK_MAX_CHARS + 1)},
        {"text": 'open notes\n{"cmd": "quit"}'},
        {"text": "open notes\u0000"},
        {"text": "open notes‮"},
        {"text": 42},
        {"text": ["open notes"]},
        {"text": "open notes", "cmd": "quit"},
        {"words": "open notes"},
    ],
)
def test_a_typed_request_cannot_smuggle_anything_else(args) -> None:  # noqa: ANN001
    assert hub_bridge.parse({"cmd": "ask", "id": 9, "args": args}) is None
