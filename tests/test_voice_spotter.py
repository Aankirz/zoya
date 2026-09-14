"""Wake-word and "Zoya, stop" spotters are parsers on the safety path (D37, §9.1).

A miss means Zoya can't be stopped; a false hit means she wakes or stops on her own.
"""

import pytest

from zoya.voice import (
    after_wake,
    is_bare_confirmation,
    is_junk_reply,
    is_runaway,
    is_stop,
    is_stop_command,
    is_usable_command,
    is_wake,
    stop_name,
    strip_wake,
    vetoes_wake,
)


@pytest.mark.parametrize(
    "heard",
    [
        "Hey Zoya.",
        "hey zoia, open Spotify",
        "Okay Zooeya what's the time",
        "Zoa?",
        "Hi, Zoyah!",
        "Hizoya.",  # Whisper merged the greeting
        "Here Zoya.",  # how base.en heard the owner's real "Hey Zoya"
        "He's Zoya",
        "Zoya, what's the weather?",
        "ज़ोया, स्पॉटिफ़ाई खोल दो",  # turbo writes Hinglish in Devanagari (D42)
        "Hey Zoëa!",  # turbo's accent on the owner's real "Hey Zoya"
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


def test_words_after_wake_name_are_the_command():
    assert after_wake("Here Zoya, open Spotify.") == "open spotify"
    assert after_wake("He's Zoya") == ""


@pytest.mark.parametrize(
    "heard",
    [
        *("you", "Thank you.", "ん", "예소야", "", "Hey Zoya!", "um", "Uh."),
        *("Good.", "No.", "Tadam!", "Lehmadbur."),  # one-word fragments from the owner's run
        "Zoya no " + "no " * 200,
    ],
)
def test_hallucinations_and_empty_commands_are_dropped(heard):
    assert not is_usable_command(heard)


@pytest.mark.parametrize(
    "heard",
    [
        *("Hey Zoya, open Spotify", "स्पॉटिफ़ाई खोल दो", "and its population?"),
        *("pause", "Mute.", "Just hello"),  # known one-word commands; fillers still count
    ],
)
def test_real_commands_are_kept(heard):
    assert is_usable_command(heard)


@pytest.mark.parametrize(
    "turbo_heard", ["Zoe is coming", "Hey, so yeah.", "Joya!", "हे सोनिया", "Hey Sonia", "Hey Zoe"]
)
def test_turbo_vetoes_sound_alike_names(turbo_heard):
    assert vetoes_wake(turbo_heard)


@pytest.mark.parametrize(
    "turbo_heard",
    [
        "Hey Zoya!",
        "He's aware.",
        "He is doya.",
        "Hey Zoëa!",
        "Hey Zoya, open Spotify",
        "Hey Zoya, so what's the weather",  # "so" after the name is a real command
        "Zoya so play music",
        "Hey, Soya.",  # turbo on a real "Hey Zoya"
        "",
    ],
)
def test_turbo_does_not_veto_real_wakes(turbo_heard):
    assert not vetoes_wake(turbo_heard)


def test_runaway_repeats_and_overlong_transcripts_are_detected():
    assert is_runaway("Zoya no no no no no")
    assert is_runaway("word " * 61)
    assert not is_runaway("no, no, I meant Rahul Verma")


def test_a_number_after_the_name_is_an_answer_not_a_repeated_wake():
    # Owner's run: "Zoya 5000" (the budget) was swallowed as "still listening".
    assert after_wake("Zoya 5000") == "5000"
    assert strip_wake("Here's Zoya 5000.") == "5000."
    assert strip_wake("Zoya, my budget is 5,000 rupees") == "my budget is 5,000 rupees"
    assert strip_wake("book a hotel") == "book a hotel"
    assert is_usable_command("5000")


@pytest.mark.parametrize("heard", ["Hey Zoeya, it's confirmed.", "confirm", "Yes, confirm."])
def test_a_late_confirmation_is_recognised_so_it_never_starts_a_task(heard):
    assert is_bare_confirmation(heard)


@pytest.mark.parametrize("heard", ["confirm my Amazon order for eggs", "book a hotel", "cancel"])
def test_commands_are_not_bare_confirmations(heard):
    assert not is_bare_confirmation(heard)


@pytest.mark.parametrize("heard", ["", "Boom.", "Yes.", "Uh."])
def test_junk_replies_do_not_count_as_answers(heard):
    assert is_junk_reply(heard)


@pytest.mark.parametrize(
    "heard", ["confirm", "cancel", "no", "confirm karo", "Yes, confirm the order"]
)
def test_real_replies_count(heard):
    assert not is_junk_reply(heard)


def test_stop_the_task_is_a_bare_stop():
    assert is_stop_command("stop the task.")
    assert stop_name("stop the task", known_only=False) == ""
    assert stop_name("stop all tasks", known_only=False) == "everything"
