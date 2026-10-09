"""A2: a missing required detail is asked for before any action; a complete command is not."""

import pytest

from zoya.clarify import missing_detail

ASKS = {
    "post on LinkedIn": "What should the post say?",
    "tweet something about the monsoon": (
        "Should I draft a post about the monsoon, or tell me what it should say?"
    ),
    "publish a post on my blog": "What should the post say?",
    "send a message to Priya": "What should the message to Priya say?",
    "text that I'm running ten minutes late": "Who should I send that to?",
    "send a message": "Who should I send it to, and what should it say?",
    "email my landlord": "What should the message to your landlord say?",
    "whatsapp Neha": "What should the message to Neha say?",
    "buy something for me": "What would you like me to buy?",
    "order it": "What would you like me to buy?",
    "add stuff to my basket": "What should I add to your cart?",
    "set a reminder": "What should I remind you about, and when?",
    "get me something nice for the kitchen": "What would you like me to buy?",
    "share an update on Threads": "What should the post say?",
}

ACTS = [
    "post on Mastodon: finally fixed the brakes on my bike",
    "tweet good morning everyone",
    "WhatsApp Rohan that dinner is at 8",
    "send Kabir a message saying the meeting moved to 3",
    "email Sara that the report is attached",
    "buy a 65 watt USB-C charger",
    "order two packs of green tea",
    "add oat milk to my cart",
    "remind me to call the bank tomorrow at 11",
    "what can you post for me?",
    "open Messages",
    "add 5 and 7",
    "play some lo-fi beats",
    "share an update on Threads: back from the hills",
]


@pytest.mark.parametrize(("command", "question"), ASKS.items())
def test_a_missing_detail_gets_one_short_question(command, question):
    found = missing_detail(command)

    assert found is not None and found.text == question


@pytest.mark.parametrize("command", ACTS)
def test_a_command_with_its_details_is_not_questioned(command):
    assert missing_detail(command) is None
