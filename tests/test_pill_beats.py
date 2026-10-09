"""Earcons as punctuation and one-way doors (D152): every sound has something to see, and a late
or repeated ask never brings the confirm state back."""

from __future__ import annotations

from typing import get_args

import pytest

from zoya import events, overlay, pill_beats

SUMMARY = "I'm about to pay ₹4,180 to Bescom for the October electricity bill."
OTHER = "I'm about to send ₹600 to Meera for the cab."


def _through_doors(doors: pill_beats.Doors, *items: events.Event) -> list[str]:
    shown = []
    for item in items:
        message = overlay.to_message(item)
        if message is not None and doors.admit(message):
            shown.append(message.get("state") or message["k"])
    return shown


@pytest.mark.parametrize("kind", get_args(events.EarconKind))
def test_every_earcon_has_a_visual(kind: str) -> None:
    message = overlay.to_message(events.EarconEvent(kind))
    assert message is not None
    assert message["k"] == "beat" or message["state"] in {
        "listening",
        "thinking",
        "error",
        "stopped",
    }


def test_no_earcon_is_both_a_state_and_a_beat() -> None:
    assert not set(pill_beats.STATE_EARCONS) & pill_beats.BEAT_EARCONS


def test_a_late_ask_after_confirm_never_shows_asking_again() -> None:
    doors = pill_beats.Doors()
    shown = _through_doors(
        doors,
        events.ConfirmationEvent("t1", SUMMARY, "pending"),
        events.ConfirmationEvent("t1", SUMMARY, "confirm"),
        events.ConfirmationEvent("t1", SUMMARY, "pending"),
    )
    assert shown == ["waiting", "thinking"]


def test_a_duplicate_ask_after_cancel_never_shows_asking_again() -> None:
    doors = pill_beats.Doors()
    shown = _through_doors(
        doors,
        events.ConfirmationEvent("t2", SUMMARY, "pending"),
        events.ConfirmationEvent("t2", SUMMARY, "cancel"),
        events.EarconEvent("cancel"),
        events.ConfirmationEvent("t2", SUMMARY, "pending"),
        events.ConfirmationEvent("t2", SUMMARY, "pending"),
    )
    assert shown == ["waiting", "stopped", "stopped"]


def test_cancel_goes_straight_to_stopped_without_a_thinking_flicker() -> None:
    message = overlay.to_message(events.ConfirmationEvent("t3", SUMMARY, "cancel"))
    assert message["state"] == "stopped"


def test_an_ended_task_never_asks_again() -> None:
    doors = pill_beats.Doors()
    shown = _through_doors(
        doors,
        events.ConfirmationEvent("t4", SUMMARY, "pending"),
        events.TaskEvent("t4", "cancelled", "pay the electricity bill", "orchestrator"),
        events.ConfirmationEvent("t4", OTHER, "pending"),
    )
    assert shown == ["waiting", "stopped"]


def test_a_new_action_in_the_same_task_may_still_ask() -> None:
    doors = pill_beats.Doors()
    shown = _through_doors(
        doors,
        events.ConfirmationEvent("t5", SUMMARY, "pending"),
        events.ConfirmationEvent("t5", SUMMARY, "confirm"),
        events.ConfirmationEvent("t5", OTHER, "pending"),
    )
    assert shown == ["waiting", "thinking", "waiting"]


def test_the_ask_key_never_carries_the_summary() -> None:
    message = overlay.to_message(events.ConfirmationEvent("t6", SUMMARY, "pending"))
    assert "4,180" not in message["ask"] and "Bescom" not in message["ask"]
