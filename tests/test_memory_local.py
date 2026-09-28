"""D147: memory.json is the only store for license users, searched well enough and never online."""

import socket

import pytest

from zoya.tools import memory

LABELLED = [
    ("I like masala chai with less sugar", "what chai do I like?"),
    ("Usual groceries: 2 L Amul milk, 12 eggs", "order my usual grocery"),
    ("Mummy ka number Airtel wala hai", "mummy ka phone"),
    ("Café Mocha at Blue Tokai is my favourite", "which cafe do I love"),
    ("I go running in Cubbon Park on Sundays", "where do I run"),
    ("Riya is my sister", "who are my sisters"),
    ("Mujhe paneer tikka pasand hai", "paneer wala khana kya pasand hai"),
    ("Office address: 4th floor, Prestige Tower, MG Road", "office kahan hai"),
]


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_LOCAL_FILE", tmp_path / "memory.json")
    monkeypatch.setattr(memory, "_put_dynamodb", lambda _item: None)
    monkeypatch.setattr(memory.events, "emit", lambda _event: None)


@pytest.fixture
def licensed(local, monkeypatch):
    monkeypatch.setenv("ZOYA_LICENSE_KEY", "zoya_live_license")
    monkeypatch.setenv("SUPERMEMORY_API_KEY", "sm_dev_key_left_in_env")
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    def refuse(*_args, **_kwargs):
        raise AssertionError("memory went online")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.mark.parametrize("expected, query", LABELLED)
def test_search_puts_the_labelled_memory_first(local, expected, query):
    items = [{"content": text} for text, _ in LABELLED]
    assert memory.local_matches(query, items)[0] == expected


def test_newest_wins_a_tie():
    items = [{"content": "I like filter coffee"}, {"content": "I like cold coffee now"}]
    assert memory.local_matches("coffee", items)[0] == "I like cold coffee now"


def test_under_the_cap_search_returns_every_memory(local, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 3)
    for text in ("I like masala chai", "Riya is my sister", "I live in Pune"):
        memory.remember(text)
    said = memory.memory_search("anything at all")
    assert all(text in said for text in ("masala chai", "Riya", "Pune"))


def test_over_the_cap_search_returns_only_matches(local, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 1)
    memory.remember("I like masala chai")
    memory.remember("Riya is my sister")
    said = memory.memory_search("chai")
    assert "masala chai" in said and "Riya" not in said


def test_a_license_user_remembers_searches_profiles_and_forgets_offline(licensed, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 0)
    memory.remember("I like masala chai")
    assert "masala chai" in memory.memory_search("what chai do I like?")
    assert "masala chai" in memory.user_profile()
    [item] = memory.memories()
    assert memory.forget(item["id"]) is True
    assert "masala chai" not in memory.memory_search("chai")
    assert memory.MEMORY_LOCAL_FILE.read_text() == "[]"


def test_over_the_cap_about_me_answers_from_the_profile(local, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 0)
    memory.remember("I like masala chai")
    assert "masala chai" in memory.memory_search("me")
