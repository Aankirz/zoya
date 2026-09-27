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
