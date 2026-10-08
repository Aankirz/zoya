"""Ask for a missing detail before any browser or app action (A2, D157).

Posting needs the words, sending needs a recipient and the words, buying needs the item and a
reminder needs what to remind. These are the required arguments of every action of that kind on
any site or app, so the check reads the command, not the site: no tool runs and no model is
called before the question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from zoya.router import QUESTION, clean_command

_I = re.IGNORECASE
VAGUE = r"(?:something|anything|stuff|a\s+(?:post|tweet|message|note)|it|this|that)"
TOPIC = re.compile(rf"^{VAGUE}(?:\s+(?:about|on|regarding)\s+(?P<topic>.+))?$", _I)

NOT_A_NAME = r"(?!(?:that|saying|an?|to)\b)[\w']+"
SEPARATOR = r"(?:\s*[:,-]\s*|\s+(?:saying|that says|that|to say)\s+)"
POST = re.compile(
    r"^(?:post|tweet|publish|share\s+a\s+post|put\s+up(?:\s+a)?(?:\s+(?:post|story|status))?)"
    r"(?:\s+(?:a|my|the))?(?:\s+(?:post|tweet|story|status|update))?"
    r"(?:\s+(?:on|to|for)\s+(?P<where>(?:my\s+|the\s+)?[\w.]+))?"
    rf"(?:{SEPARATOR}|\s+)?(?P<text>.*)$",
    _I,
)
MESSAGE = re.compile(
    r"^(?P<verb>send(?:\s+an?)?(?:\s+(?:message|text|imessage|whatsapp|email|e-?mail|dm))?|text"
    r"|message|whatsapp|imessage|dm|e-?mail|mail)"
    rf"(?:\s+(?:to\s+)?(?P<who>{NOT_A_NAME}(?:\s+{NOT_A_NAME}){{0,2}}))?"
    r"(?:\s+an?\s+(?:message|text|imessage|whatsapp|email|e-?mail))?"
    rf"(?:{SEPARATOR}(?P<body>.*))?$",
    _I,
)
BUY = re.compile(
    r"^(?:buy|order|purchase|get\s+me|add)(?:\s+(?:me|for\s+me))?\s*(?P<item>.*?)"
    r"(?:\s+(?:to|in|into)\s+(?:my\s+|the\s+)?(?:cart|basket|bag))?(?:\s+for\s+me)?$",
    _I,
)
REMINDER = re.compile(r"^(?:set|add|create|make)\s+(?:a\s+|an?\s+new\s+)?reminder$", _I)

POST_QUESTION = "What should the post say?"
POST_TOPIC_QUESTION = "Should I draft a post about {topic}, or tell me what it should say?"
WHO_AND_WHAT = "Who should I send it to, and what should it say?"
WHO_QUESTION = "Who should I send that to?"
WHAT_QUESTION = "What should the message to {who} say?"
BUY_QUESTION = "What would you like me to buy?"
CART_QUESTION = "What should I add to your cart?"
REMINDER_QUESTION = "What should I remind you about, and when?"
CART = re.compile(r"\b(?:cart|basket|bag)\b", _I)
MESSAGE_SHAPE = re.compile(r"\b(?:message|text|whatsapp|imessage|dm|e-?mail|mail)\b", _I)
OWN = {"my": "your", "me": "you", "i": "you", "mine": "yours"}


@dataclass(frozen=True)
class Question:
    text: str
    kind: str


def missing_detail(command: str) -> Question | None:
    """The one short question to ask, or None when the command has what its action needs."""
    text = clean_command(command)
    if not text or QUESTION.match(text):
        return None
    for check in (_post, _message, _buy, _reminder):
        if found := check(text):
            return found
    return None


def _vague(value: str) -> re.Match[str] | None:
    return TOPIC.match(value.strip(" .'\"")) if value.strip() else None


def _post(text: str) -> Question | None:
    match = POST.match(text)
    if not match or MESSAGE_SHAPE.search(text.split()[0]):
        return None
    words = match["text"].strip(" .'\"")
    if words and not (vague := _vague(words)):
        return None
    topic = vague["topic"] if words and vague and vague["topic"] else ""
    if topic:
        return Question(POST_TOPIC_QUESTION.format(topic=_yours(topic)), "post")
    return Question(POST_QUESTION, "post")


def _message(text: str) -> Question | None:
    match = MESSAGE.match(text)
    if not match:
        return None
    who = (match["who"] or "").strip()
    body = (match["body"] or "").strip(" .'\"")
    if who.lower() in {"it", "this", "that", "something"}:
        who = ""
    if body and _vague(body):
        body = ""
    if who and body:
        return None
    if not who and not body:
        return Question(WHO_AND_WHAT, "message")
    if not who:
        return Question(WHO_QUESTION, "message")
    return Question(WHAT_QUESTION.format(who=_yours(who)), "message")


def _buy(text: str) -> Question | None:
    match = BUY.match(text)
    if not match:
        return None
    if text.lower().startswith("add") and not CART.search(text):
        return None
    item = match["item"].strip(" .'\"")
    if item and not _vague(item):
        return None
    return Question(CART_QUESTION if CART.search(text) else BUY_QUESTION, "buy")


def _reminder(text: str) -> Question | None:
    return Question(REMINDER_QUESTION, "reminder") if REMINDER.match(text) else None


def _yours(phrase: str) -> str:
    return " ".join(OWN.get(word.lower(), word) for word in phrase.split())
