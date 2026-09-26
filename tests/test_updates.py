from __future__ import annotations

import pytest

from zoya import updates


@pytest.mark.parametrize(
    ("heard", "choice"),
    [
        ("Yes.", updates.INSTALL),
        ("Zoya, yes please", updates.INSTALL),
        ("okay, update now", updates.INSTALL),
        ("haan", updates.INSTALL),
        ("No.", updates.DISMISS),
        ("not now", updates.DISMISS),
        ("later please", updates.DISMISS),
        ("yes open Safari", ""),
        ("what's the weather", ""),
        ("no, play music", ""),
    ],
)
def test_update_answers(heard, choice):
    assert updates.reply_for(heard) == choice
