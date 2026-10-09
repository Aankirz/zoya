"""S3-Memory (D163, D168): live facts stay at the source, new replaces old, every save is said and
"forget that" undoes it, and the memories that matter ride with the request."""

import json
from typing import Any

import pytest

from zoya import decisions, memory_rules, orchestrator
from zoya.tools import ToolError, memory
from zoya.tools.memory import _live_by_jev as real_live_by_jev

STABLE = ["my sister is Priya", "I'm vegetarian", "my office is in Koramangala", "call me Ankit"]
CHANGING = [
    "my parcel comes Friday",
    "the stock is at 420",
    "it's raining",
    "my meeting is at 3 today",
]


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_LOCAL_FILE", tmp_path / "memory.json")
    monkeypatch.setattr(memory, "_supermemory", lambda: None)
    monkeypatch.setattr(memory, "_put_dynamodb", lambda _item: None)
    monkeypatch.setattr(memory.aws, "client", lambda _name: None)
    monkeypatch.setattr(memory, "_undoable", None)
    monkeypatch.setattr(memory, "_announce", {})
    return tmp_path / "memory.json"


def saved(store) -> list[str]:
    return [item["content"] for item in json.loads(store.read_text())] if store.exists() else []


@pytest.mark.parametrize("fact", STABLE)
def test_a_lasting_fact_is_saved(store, fact):
    assert memory.remember(fact) == f"Remembered: {fact}"
    assert saved(store) == [fact]


@pytest.mark.parametrize("fact", CHANGING)
def test_a_changing_fact_is_never_saved(store, fact):
    assert memory.remember(fact) == memory.LIVE_SKIPPED
    assert saved(store) == []


def test_jev_catches_a_changing_fact_the_rules_keep_and_sees_only_that_fact(store, monkeypatch):
    sent: list[str] = []

    def ask(state: str, _questions: Any, **_: Any) -> decisions.Answers:
        sent.append(state)
        return decisions.Answers({"live": {"noul": 0.93}})

    monkeypatch.setattr(decisions, "ask", ask)
    monkeypatch.setattr(memory, "_live_by_jev", real_live_by_jev)
    assert memory.remember("Tata Motors is trading at 980") == memory.LIVE_SKIPPED
    assert sent == [memory.LIVE_STATE.format(text="Tata Motors is trading at 980")]
    assert saved(store) == []


def test_jev_unavailable_keeps_what_the_rules_keep(store, monkeypatch):
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: decisions.unavailable("down"))
    monkeypatch.setattr(memory, "_live_by_jev", real_live_by_jev)
    memory.remember("I'm left-handed")
    assert saved(store) == ["I'm left-handed"]


def test_a_secret_never_reaches_jev(store, monkeypatch):
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: pytest.fail("sent to Jev"))
    monkeypatch.setattr(memory, "_live_by_jev", real_live_by_jev)
    with pytest.raises(ToolError):
        memory.remember("my UPI PIN is 4821")
    assert saved(store) == []


@pytest.mark.parametrize(
    "old, new, was",
    [
        ("My office is in Koramangala", "My office is in HSR Layout", "Koramangala"),
        ("Mera dentist Dr. Kulkarni hai", "Mera dentist Dr. Shetty hai", "Dr. Kulkarni"),
        ("I'm vegetarian", "I'm vegan now", "vegetarian"),
        ("Home: 12 Lake View Road, Pune", "I moved to Baner, Pune", "12 Lake View Road"),
    ],
)
def test_a_contradicting_memory_replaces_the_old_one_and_says_so(store, old, new, was):
    memory.remember(old)
    assert memory.remember(new) == f"Updated: {new} (was {was})"
    assert saved(store) == [new]


@pytest.mark.parametrize(
    "first, second",
    [
        ("My sister is Priya", "My sister is Neha"),
        ("I like appam", "I like idiyappam"),
        ("My gym is Cult Fit in HSR", "My office is in Koramangala"),
        ("Our anniversary is on 18 November", "My birthday is on 2 March"),
    ],
)
def test_memories_that_do_not_contradict_both_stay(store, first, second):
    memory.remember(first)
    assert memory.remember(second) == f"Remembered: {second}"
    assert saved(store) == [first, second]


def test_the_same_fact_twice_is_kept_once(store):
    memory.remember("I'm allergic to cashews")
    assert memory.remember("i'm allergic to  cashews") == memory.ALREADY_SAVED
    assert saved(store) == ["I'm allergic to cashews"]


def test_every_save_is_one_short_line(store):
    said = memory.remember("My landlord is Mr. Dsouza, saved as Landlord " + "and more " * 40)
    assert "\n" not in said and len(said) <= len("Remembered: ") + memory.SPOKEN_MAX_CHARS + 1


def test_a_mid_task_save_joins_the_end_once(store):
    memory.remember("My gym is Cult Fit in HSR")
    memory.remember("the stock is at 420")
    end = memory.take_announcements("Booked your slot for 7 am.")
    assert end == f"Remembered: My gym is Cult Fit in HSR {memory.LIVE_SKIPPED}"
    assert memory.take_announcements("") == ""


def test_a_save_that_was_the_whole_reply_is_not_said_twice(store):
    said = memory.remember("Call me Meenu")
    assert memory.take_announcements(said) == ""


@pytest.mark.parametrize("undo", ["forget that", "Zoya, don't remember that.", "ise bhool jao"])
def test_forget_that_removes_exactly_the_last_saved_memory(store, undo):
    memory.remember("My gym is Cult Fit in HSR")
    memory.next_turn("remember my blood group is B positive")
    memory.remember("My blood group is B positive")
    assert memory.next_turn(undo) == "Okay, forgotten: My blood group is B positive"
    assert saved(store) == ["My gym is Cult Fit in HSR"]


def test_forget_that_after_an_update_puts_the_old_memory_back(store):
    memory.remember("My office is in Koramangala")
    memory.next_turn("my office moved")
    memory.remember("My office is in HSR Layout")
    assert (
        memory.next_turn("forget that") == "Okay, forgotten. Back to: My office is in Koramangala"
    )
    assert saved(store) == ["My office is in Koramangala"]


def test_forget_that_only_works_on_the_next_turn(store):
    memory.remember("My gym is Cult Fit in HSR")
    assert memory.next_turn("what's the weather") is None
    assert memory.next_turn("forget that") is None
    assert saved(store) == ["My gym is Cult Fit in HSR"]


def test_forget_that_routes_to_one_spoken_line(store):
    memory.remember("Call me Meenu")
    decision = orchestrator.forget_that("Hey Zoya, forget that")
    assert decision.route == "ask" and decision.args["question"].startswith("Okay, forgotten")
    assert orchestrator.forget_that("forget that") is None


def test_order_records_are_kept_as_dated_history(store):
    memory.remember(
        "Ordered Tata Gold tea 500 g from Amazon.in on 02 October 2026", "order_history"
    )
    assert len(saved(store)) == 1
    assert memory.take_announcements("") == ""


def _many(count: int) -> list[dict[str, str]]:
    return [
        {"category": "preference", "content": f"I like raga number {n} on the veena in the evening"}
        for n in range(count)
    ]


def test_over_the_cap_the_memories_that_matter_ride_with_the_request(monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 10)
    items = [{"category": "preference", "content": "My shoe size is UK 9"}, *_many(80)]
    assert "My shoe size is UK 9" not in memory.profile_block(memory._profile_lines(items))
    assert "My shoe size is UK 9" in memory.relevant_block("find me running shoes", items)


def test_under_the_cap_nothing_extra_is_inlined(monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 150)
    assert memory.relevant_block("find me running shoes", _many(80)) == ""


def test_the_picked_memories_never_hold_a_secret(monkeypatch):
    monkeypatch.setattr(memory, "MEMORY_INLINE_MAX", 1)
    items = [{"category": "preference", "content": "My netbanking password is tiger"}, *_many(80)]
    assert "tiger" not in memory.relevant_block("my netbanking password", items)


def test_the_rules_alone_read_a_recurring_event_as_lasting():
    assert memory_rules.live_reason("My standup meeting is at 10 every weekday") is None
    assert memory_rules.live_reason("My dentist appointment is on Thursday at 4")
