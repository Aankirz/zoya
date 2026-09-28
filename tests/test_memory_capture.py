"""Phase H: what Zoya learns on her own is filtered by Jev and never holds a secret (D37)."""

from typing import Any

import pytest

from zoya import decisions
from zoya.tools import memory

SECRET_SHAPED = [
    "type my OTP 482913 into the bank page",
    "pay with card 4111 1111 1111 1111",
    "my password is hunter2, log me in",
    "enter the code four eight two nine",
]


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_LOCAL_FILE", tmp_path / "memory.json")
    monkeypatch.setattr(memory, "_supermemory", lambda: None)
    monkeypatch.setattr(memory, "_put_dynamodb", lambda _item: None)
    asked: list[str] = []
    return asked


def jev_says(monkeypatch, asked: list[str], worth: float | None) -> None:
    def ask(state: str, _questions: Any, **_: Any) -> decisions.Answers:
        asked.append(state)
        if worth is None:
            return decisions.unavailable("down")
        return decisions.Answers({"worth": {"noul": worth}})

    monkeypatch.setattr(decisions, "ask", ask)


@pytest.mark.parametrize("command", SECRET_SHAPED)
def test_a_secret_shaped_outcome_is_never_stored_nor_sent_to_jev(stores, monkeypatch, command):
    jev_says(monkeypatch, stores, 0.99)
    assert memory.capture_outcome(command) is False
    assert stores == []
    assert memory.memories() == []


def test_a_worthy_outcome_is_stored_and_shown_to_the_hub(stores, monkeypatch):
    jev_says(monkeypatch, stores, 0.9)
    assert memory.capture_outcome("find vegetarian restaurants near Indiranagar")
    [saved] = memory.memories()
    assert saved["content"] == "Asked Zoya: find vegetarian restaurants near Indiranagar"
    assert saved["category"] == "activity"


@pytest.mark.parametrize("worth", [0.5, None])
def test_an_unsure_or_unavailable_jev_keeps_nothing(stores, monkeypatch, worth):
    jev_says(monkeypatch, stores, worth)
    assert memory.capture_outcome("open the Music app") is False
    assert memory.memories() == []


def test_the_profile_block_drops_secrets_and_keeps_to_its_budget():
    lines = ["Name is Ankit", "Lives in Bengaluru", "OTP is 482913", "Name is Ankit"]
    block = memory.profile_block(lines + ["x" * 5000], max_tokens=60)
    assert "Bengaluru" in block and "482913" not in block
    assert block.count("Name is Ankit") == 1
    assert len(block) <= 60 * memory.CHARS_PER_TOKEN
