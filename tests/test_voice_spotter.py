"""Wake-word and "Zoya, stop" spotters are parsers on the safety path (D37, §9.1).

A miss means Zoya can't be stopped; a false hit means she wakes or stops on her own.
"""

import pytest

from zoya.voice import is_stop, is_stop_command, is_wake


@pytest.mark.parametrize(
    "heard",
    [
        "Hey Zoya.",
        "hey zoia, open Spotify",
        "Okay Zooeya what's the time",
        "Zoa?",
        "Hi, Zoyah!",
        "Hizoya.",  # Whisper merged the greeting
        "Zoya, what's the weather?",
    ],
)
def test_wake_on_zoya_like_name_in_first_three_words(heard):
    assert is_wake(heard)


@pytest.mark.parametrize(
    "heard",
    [
        "Hey Sonia",
        "Hey Siri",
        "I bought soya milk",
        "Hey Zoe",
        "Please tell my friend Zoya",  # name after the first 3 words
        "I bought Zoya milk today.",  # how Whisper heard "I bought soya milk today"
        "Hey Soya!",
        "Tell Zoya hi",  # only greetings may come before the name
        "",
    ],
)
def test_no_wake_on_near_misses(heard):
    assert not is_wake(heard)


@pytest.mark.parametrize(
    "heard",
    [
        "Zoya, stop.",
        "Stop, Zoya!",
        "Hey Zoya stop everything",
        "Zoya, ruko",
        "Ruk jao Zoya",
        "zoia cancel",
        "Zoya Stop.",
    ],
)
def test_stop_needs_name_and_stop_word(heard):
    assert is_stop(heard)


@pytest.mark.parametrize(
    "heard",
    [
        "Okay, stopped.",  # Zoya's own speech must never stop her
        "stop",
        "Zoya, open Spotify",
        "Hey Sonia, stop",
        "Soya stop",
        "Tokyo is the capital of Japan and Zoya can stop by the store later today",
    ],
)
def test_no_stop_without_name_or_in_long_speech(heard):
    assert not is_stop(heard)


def test_captured_stop_command_without_name_still_stops():
    assert is_stop_command("Hey Zoya, cancel")
    assert is_stop_command("ruk jao")
