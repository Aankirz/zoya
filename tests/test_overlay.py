"""Stage overlay (Phase 7, D37): captions never show secrets, and every display capture leaves the
overlay out. No UI tests: the look is checked on the demo Mac."""

from __future__ import annotations

import ast
import json
import os
import sys
import types
from pathlib import Path

import pytest

from zoya import events, overlay, screen

SECRETS = [
    "my OTP is 482913",
    "the password is hunter2",
    "card 4111 1111 1111 1111",
    "four eight two nine",
    "मेरा ओटीपी 4829 है",
    "CVV 123",
]


@pytest.mark.parametrize("text", SECRETS)
def test_user_caption_hides_secrets(text: str) -> None:
    message = overlay.to_message(events.OverlayEvent(text, "listening", {"role": "user"}))
    assert message == {"k": "user", "text": overlay.HIDDEN_CAPTION}


@pytest.mark.parametrize("text", SECRETS)
def test_zoya_caption_hides_secrets(text: str) -> None:
    assert overlay.to_message(events.NarrateEvent(text))["text"] == overlay.HIDDEN_CAPTION


def test_long_number_redacted_even_without_secret_word() -> None:
    caption = overlay.caption_text("account 1234 5678 9012")
    assert "5678" not in caption


def test_step_caption_is_masked() -> None:
    message = overlay.to_message(events.OverlayEvent("", "working", {"tool": "type OTP 4829"}))
    assert message["state"] == "acting"
    assert message["step"] == overlay.HIDDEN_CAPTION


def test_plain_caption_kept() -> None:
    assert overlay.caption_text("Adding eggs to the cart") == "Adding eggs to the cart"


class _App:
    def __init__(self, pid: int) -> None:
        self.pid = pid

    def processID(self) -> int:  # noqa: N802 — ScreenCaptureKit shape
        return self.pid


def test_display_filter_excludes_zoya_and_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    overlay_pid, other_pid = 424242, 434343
    monkeypatch.setattr(overlay, "pids", lambda: {overlay_pid})
    seen = {}

    class Filter:
        @staticmethod
        def alloc() -> type:
            return Filter

        @staticmethod
        def initWithDisplay_excludingApplications_exceptingWindows_(  # noqa: N802
            display: object, apps: list, windows: list
        ) -> str:
            seen.update(display=display, pids={a.processID() for a in apps}, windows=windows)
            return "filter"

    monkeypatch.setitem(
        sys.modules, "ScreenCaptureKit", types.SimpleNamespace(SCContentFilter=Filter)
    )
    content = types.SimpleNamespace(
        applications=lambda: [_App(os.getpid()), _App(overlay_pid), _App(other_pid)]
    )
    assert screen.display_filter(content, "display") == "filter"
    assert seen == {"display": "display", "pids": {os.getpid(), overlay_pid}, "windows": []}


def test_every_capture_filter_goes_through_display_filter() -> None:
    """A capture path building its own display filter would put the overlay in front of the model.
    Window filters (initWithDesktopIndependentWindow_) render one window only: no exclusion."""
    allowed: list[tuple[Path, range]] = []
    calls: list[tuple[Path, int, str]] = []
    for path in Path("zoya").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "display_filter":
                allowed.append((path, range(node.lineno, node.end_lineno + 1)))
            name = getattr(node, "attr", "")
            if name.startswith("initWith") and "Display" in name:
                calls.append((path, node.lineno, name))
    assert calls, "screen.display_filter must build the display filter"
    offenders = [c for c in calls if not any(c[0] == p and c[1] in r for p, r in allowed)]
    assert offenders == []


@pytest.mark.parametrize(
    ("summary", "stake"),
    [
        (
            "I'm about to place the order for boAt earphones total ₹1,249.",
            "Place the order for boAt earphones, ₹1,249",
        ),
        ("I'm about to send the email to Priya.", "Send the email to Priya"),
        ("I'm about to delete the file report.pdf.", "Delete the file report.pdf"),
        ("Pay now?", "Pay now?"),
        ("", ""),
    ],
)
def test_confirm_pill_states_the_stake(summary: str, stake: str) -> None:
    assert overlay.stake_line(summary) == stake


def test_confirm_pill_hides_a_secret_in_the_stake() -> None:
    message = overlay.to_message(
        events.ConfirmationEvent("t1", "I'm about to type the OTP 482913.")
    )
    assert "482913" not in json.dumps(message)


def test_intent_chips_name_what_the_prepared_route_understood():
    from zoya.router import RouteDecision

    skill = RouteDecision("skill", "play", {"song": "Kesariya"}, skill="spotify_web")
    assert overlay.intent_chips(skill) == ("spotify", "kesariya")
    assert overlay.intent_chips(RouteDecision("orchestrator")) == ()


def test_intent_chips_hide_a_secret_the_user_said():
    from zoya.router import RouteDecision

    typed = RouteDecision("fast", "notes_create", {"title": "my password is hunter2"})
    assert "hunter2" not in " ".join(overlay.intent_chips(typed))
