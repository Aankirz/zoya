"""Memory hygiene rules (D163): which facts are live, and which memory a new one replaces.

Local, no network, no model. `tests/test_memory_hygiene.py`; measured by
`scripts/memory_hygiene_eval.py` on `tests/fixtures/memory_hygiene/`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_I = re.IGNORECASE

MOMENT = re.compile(
    r"\b(?:today|tonight|tomorrow|yesterday|right now|at the moment|last night|"
    r"this (?:morning|afternoon|evening|week|weekend|month)|aaj|kal|abhi)\b"
    r"|आज|कल|अभी",
    _I,
)
STATUS = re.compile(
    r"\b(?:arrives?|arriving|lands?|landing|departs|out for delivery|being delivered|"
    r"(?:is|are|running) late|\d+\s*(?:minutes?|mins?|hours?) late|late by|delayed|"
    r"rescheduled|postponed|cancell?ed|(?:got|been|was|is) moved to|"
    r"shift ho|stuck in|is down|not working|minutes? away|on (?:my|the|its) way|"
    r"aayega|aayegi|aa raha|aa rahi|pahunch(?:ega|egi))\b"
    r"|आएगा|आएगी|पहुंचेगा|पहुँचेगा",
    _I,
)
MARKET = re.compile(
    r"\b(?:stocks?|shares?|sensex|nifty|bitcoin|crypto|gold|silver|petrol|diesel|prices?|"
    r"rate|bhav|daam|keemat|costs?|fare|balance|owes?|udhaar|due|battery|aqi)\b"
    r"|कीमत|दाम|भाव|बैलेंस",
    _I,
)
DIGIT = re.compile(r"\d")
DELIVERY = re.compile(r"\b(?:parcel|package|courier|shipment|delivery|order)\b|पार्सल", _I)
ONE_DAY = re.compile(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b", _I)
WEATHER = re.compile(
    r"\b(?:raining|pouring|drizzling|snowing|thundering|\d+\s*degrees|temperature is|"
    r"(?:it'?s|it is) (?:\w+ )?(?:hot|cold|humid|sunny|cloudy|windy|foggy|chilly)|"
    r"barish ho rahi|baarish ho rahi|garmi|sardi)\b|°|बारिश|गर्मी|ठंड",
    _I,
)
BODY_NOW = re.compile(
    r"\b(?:headache|fever|feverish|sore throat|cough|unwell|feeling|tabiyat)\b"
    r"|\b(?:i'?m|i am|we'?re|we are) (?:at|in) (?:the|a|an)\b|बुखार",
    _I,
)
EVENT = re.compile(
    r"\b(?:meeting|appointment|interview|flight|train|match|show|movie|exam|reservation|"
    r"booking|webinar|party)\b",
    _I,
)
WHEN = re.compile(
    r"\b(?:at \d{1,2}(?::\d{2})?|\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)|"
    r"on (?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*)\b",
    _I,
)
RECURRING = re.compile(
    r"\b(?:every|each|daily|weekly|monthly|weekdays?|weekends|always|usually|often|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)days|har|roz|roj|rozana|hamesha|aksar)\b"
    r"|हर|रोज़|रोज|हमेशा",
    _I,
)


def live_reason(text: str) -> str | None:
    """Why `text` is a changing fact about the world or a moment (not saved), or None."""
    if MOMENT.search(text):
        return "moment"
    if STATUS.search(text):
        return "status"
    if DELIVERY.search(text) and (ONE_DAY.search(text) or WHEN.search(text)):
        return "a delivery"
    if MARKET.search(text) and DIGIT.search(text):
        return "price or balance"
    if WEATHER.search(text):
        return "weather"
    if BODY_NOW.search(text):
        return "how the user is right now"
    if EVENT.search(text) and WHEN.search(text) and not RECURRING.search(text):
        return "a one-time event"
    return None


# --- Supersede: same subject, new value -------------------------------------------------------

ENGLISH_SUBJECT = re.compile(
    r"^(?:my|our)\s+(?P<subject>[\w' -]{2,40}?)\s+(?:is|are|=)\s+(?P<value>.+)$", _I
)
LABEL_SUBJECT = re.compile(r"^(?P<subject>[\w' ]{2,30}):\s*(?P<value>.+)$", _I)
HINGLISH_SUBJECT = re.compile(
    r"^(?:mera|meri|mere|hamara|hamari|hamare)\s+"
    r"(?P<subject>(?:\w+\s+){0,2}?\w+\s+(?:ka|ki|ke)\s+\w+|"
    r"(?:favou?rite|usual|pasandida)\s+\w+|\w+)\s+(?P<value>.+?)\s+(?:hai|hain)\b",
    _I,
)
DEVANAGARI_SUBJECT = re.compile(
    r"^(?:मेरा|मेरी|मेरे|हमारा|हमारी|हमारे)\s+(?P<subject>(?:\S+\s+(?:का|की|के)\s+)?\S+)\s+"
    r"(?P<value>.+?)\s+(?:है|हैं)"
)
HOME = re.compile(
    r"^(?:i|we)\s+(?:now\s+)?(?:live|stay|moved|have moved|shifted)\s+(?:in|to|at)\s+(?P<value>.+)$"
    r"|^(?:main|hum)\s+(?P<hvalue>.+?)\s+(?:mein|me)\s+(?:rehta|rehti|rehte)\s+(?:hoon|hu|hain)",
    _I,
)
WORKPLACE = re.compile(r"^i\s+(?:now\s+)?work\s+(?:at|in|for)\s+(?P<value>.+)$", _I)
NAME = re.compile(r"^(?:please\s+)?call me\s+(?P<value>.+)$", _I)
DIET = re.compile(
    r"\b(?P<value>vegetarian|vegan|non-?veg(?:etarian)?|eggetarian|pescatarian|"
    r"shakahari|mansahari)\b",
    _I,
)
DIET_SPEAKER = re.compile(r"^(?:i'?m|i am|i eat|i'?ve (?:become|turned)|main|hum)\b", _I)
SUBJECT_ALIASES = {
    **dict.fromkeys(["office", "work", "workplace", "office address", "work address"], "office"),
    **dict.fromkeys(
        ["home", "home address", "address", "house", "ghar", "pata", "घर", "पता"], "home"
    ),
    **dict.fromkeys(["name", "naam", "नाम"], "name"),
    **dict.fromkeys(["mom", "mum", "mummy", "maa", "amma", "mother"], "mother"),
    **dict.fromkeys(["dad", "papa", "appa", "father"], "father"),
}
MANY = {
    # fmt: off
    "sister", "brother", "friend", "cousin", "son", "daughter", "child", "kid", "kids",
    "colleague", "neighbour", "neighbor", "uncle", "aunt", "aunty", "nephew", "niece",
    "behen", "bhai", "dost", "beta", "beti", "बहन", "भाई", "दोस्त",
    # fmt: on
}
VALUE_FILLER = re.compile(r"^(?:in|at|on|to|now)\s+|\s+(?:now|mein|me|par)$|[.!,;]+$", _I)
SAVED_AS = re.compile(r"^saved as\s+", _I)


@dataclass(frozen=True)
class Fact:
    subject: str
    value: str


def _clean_subject(subject: str) -> str:
    words = " ".join(subject.casefold().replace("’", "'").split())
    return SUBJECT_ALIASES.get(words, words)


def _clean_value(value: str) -> str:
    text = " ".join(value.casefold().split())
    previous = None
    while text != previous:
        previous = text
        text = VALUE_FILLER.sub("", text).strip()
    return text


def fact_of(text: str) -> Fact | None:
    """The single-valued subject a memory sets ("my office" → "HSR Layout"), or None."""
    text = " ".join(text.split()).rstrip(".!")
    if match := NAME.match(text):
        return Fact("name", match["value"])
    if (match := DIET.search(text)) and DIET_SPEAKER.match(text):
        return Fact("diet", match["value"])
    if match := HOME.match(text):
        return Fact("home", match["value"] or match["hvalue"])
    if match := WORKPLACE.match(text):
        return Fact("office", match["value"])
    for pattern in (ENGLISH_SUBJECT, HINGLISH_SUBJECT, DEVANAGARI_SUBJECT, LABEL_SUBJECT):
        if match := pattern.match(text):
            return Fact(_clean_subject(match["subject"]), match["value"].split(",")[0].strip())
    return None


def _single_valued(fact: Fact) -> bool:
    return not any(word in MANY for word in fact.subject.split())


def same_value(left: Fact, right: Fact) -> bool:
    return SAVED_AS.sub("", _clean_value(left.value)) == SAVED_AS.sub("", _clean_value(right.value))


def superseded(text: str, category: str, items: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Older memories that `text` contradicts: the same single-valued subject with another value,
    in the same category (a memory saved with the default "preference" matches any category)."""
    new = fact_of(text)
    if new is None or not _single_valued(new):
        return []
    found = []
    for item in items:
        kinds = {item.get("category", "preference"), category}
        if len(kinds) > 1 and "preference" not in kinds:
            continue
        old = fact_of(item.get("content", ""))
        if old is not None and old.subject == new.subject and not same_value(old, new):
            found.append(item)
    return found


def short_value(text: str) -> str:
    """What a replaced memory said, as briefly as it can be put back: "Koramangala"."""
    fact = fact_of(text)
    if fact is None:
        return text
    return VALUE_FILLER.sub("", fact.value.strip()).strip() or text
