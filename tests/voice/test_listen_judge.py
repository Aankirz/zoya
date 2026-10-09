"""L1: "is this meant for me, and is it actionable?" in both directions (Blind Spot #2)."""

import pytest

from zoya.listen import Channel, judge

HANDS_FREE = (Channel.AFTER_WAKE, Channel.FOLLOW_UP, Channel.WAKE)


@pytest.mark.parametrize(
    "heard",
    [
        "pause",
        "next",
        "dark mode",
        "stop",
        "Zoya, stop",
        "open the downloads folder",
        "what's the time in London",
        "can you read that again",
        "I want to order some flowers for Mum",
        "remind me at five to leave",
        "and tomorrow?",
        "wifi off",
        "Spotify pe kuch lofi chalao",
        "भाई को व्हाट्सऐप पर मैसेज भेजो",
        "kal ka weather kaisa rahega",
        "mujhe ek cab book karni hai",
    ],
)
@pytest.mark.parametrize("channel", HANDS_FREE)
def test_real_commands_still_run_hands_free(heard, channel):
    assert judge(heard, channel).act


@pytest.mark.parametrize(
    "heard",
    [
        "the quarterly numbers look better than we expected",
        "I'm just showing how this part works",
        "there's the settings page",
        "he said he'd be late again",
        "and then it opens the page and reads it out",
        "मुझे ये करना है",
        "accha theek hai main dekh leta hoon",
        "from the station",
        "Thank you.",
        "um",
        "Good.",
    ],
)
@pytest.mark.parametrize("channel", HANDS_FREE)
def test_remarks_and_side_talk_are_dropped_hands_free(heard, channel):
    assert not judge(heard, channel).act


@pytest.mark.parametrize("heard", ["Namaste", "lights", "from the station", "yes", "5000"])
@pytest.mark.parametrize("channel", [Channel.PUSH_TO_TALK, Channel.ANSWER])
def test_the_keys_and_answers_to_her_question_are_trusted(heard, channel):
    assert judge(heard, channel).act


@pytest.mark.parametrize("heard", ["", "you", "um", "ん", "no " * 70])
@pytest.mark.parametrize("channel", list(Channel))
def test_noise_is_dropped_on_every_channel(heard, channel):
    assert not judge(heard, channel).act


def test_music_under_a_hands_free_window_is_background():
    assert judge("open Spotify", Channel.AFTER_WAKE, voiced_fraction=0.1).reason == "background"
    assert judge("open Spotify", Channel.PUSH_TO_TALK, voiced_fraction=0.1).act
