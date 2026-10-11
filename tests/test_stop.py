"""The stop grammar is a parser on the safety path (D37, D177).

A miss means Zoya can't be stopped; a false hit means she stops on her own.
"""

import pytest

from zoya import speech, stop


@pytest.mark.parametrize(
    "heard",
    [
        "Zoya, stop.",
        "Stop, Zoya!",
        "Hey Zoya stop everything",
        "Zoya, ruko",
        "Ruk jao Zoya",
        "zoia cancel",
        "Soya stop",
        "Zoya, be quiet",
        "Zoya bas karo",
    ],
)
def test_named_stops(heard):
    found = stop.parse(heard)
    assert found is not None and found.named


@pytest.mark.parametrize(
    "heard",
    ["stop", "Stop it.", "cancel that", "ruk jao", "stop the task", "Rukiye, mat kijiye"]
    + ["Stop, don't do that"],
)
def test_bare_stops_parse_without_a_name(heard):
    found = stop.parse(heard)
    assert found is not None and not found.named and found.target == ""


@pytest.mark.parametrize(
    "heard",
    [
        "Okay, stopped.",
        "Zoya, don't stop the music",
        "Zoya ruko mat",
        "play something quiet Zoya",
        "the bus stop is near",
        "Say confirm or cancel",
        "Zoya, open Spotify",
        "Hey Sonia, stop",
        "Tokyo is the capital of Japan and Zoya can stop by the store later today",
    ],
)
def test_a_stop_word_inside_a_sentence_is_not_a_stop(heard):
    assert stop.parse(heard) is None


def test_targets_resolve_against_running_tasks():
    known = {"presentation"}.__contains__

    assert stop.parse("Zoya, stop the presentation", known).target == "presentation"
    assert stop.parse("stop all tasks", known).target == "everything"
    assert stop.parse("stop by the store", known) is None
    assert stop.parse("stop the music", known) is None


def test_an_unknown_target_stays_a_target_when_anything_may_be_named():
    assert stop.parse("Zoya, stop the presentation").target == "presentation"


def test_a_bare_word_zoya_just_said_counts_as_her_own_echo(monkeypatch):
    monkeypatch.setattr(speech, "_said", __import__("collections").deque(maxlen=8))
    speech._said.append([frozenset({"confirm", "or", "cancel"}), float("inf")])

    assert speech.recently_said("cancel", within_s=2.6)
    assert not speech.recently_said("stop", within_s=2.6)


def test_an_old_sentence_is_not_an_echo(monkeypatch):
    monkeypatch.setattr(speech, "_said", __import__("collections").deque(maxlen=8))
    speech._said.append([frozenset({"cancel"}), 0.0])

    assert not speech.recently_said("cancel", within_s=2.6)
