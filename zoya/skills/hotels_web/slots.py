"""Hotel request slot parser (tests/test_hotel_slots.py, D37): city, area, dates, rooms, guests and
budget from one spoken sentence, merged with later answers so Zoya asks ONE question for all gaps.

Whisper writes numbers as digits and amounts as "Rs. 5,000" (D42), so both forms are accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta

MONTHS = {
    m: n
    for n, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for m in names
}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY = r"(?P<day{n}>\d{{1,2}})(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s+(?P<year{n}>20\d\d))?"


def _date_pattern(n: int) -> str:
    day, year = _DAY.format(n=n), _YEAR.format(n=n)
    return (
        rf"(?:{day}(?:\s+of)?\s+(?P<month{n}a>{_MONTH})\b\.?{year}"
        rf"|(?P<month{n}b>{_MONTH})\b\.?\s+{_DAY.format(n=f'{n}b')}{_YEAR.format(n=f'{n}b')})"
    )


DATE = re.compile(_date_pattern(0), re.I)
CHECK_IN = re.compile(r"check[- ]?in(?:\s+(?:date|on|from))?(?:\s+is)?\s*:?\s*$", re.I)
CHECK_OUT = re.compile(
    r"(?:check[- ]?out|checking out|till|until|to)(?:\s+(?:date|on))?(?:\s+is)?\s*:?\s*$", re.I
)
NIGHTS = re.compile(r"\bfor\s+(\d+|one|two|three|four|five)\s+nights?\b", re.I)
ADULTS = re.compile(
    r"\b(\d+|one|two|three|four|five|six)\s+(?:adults?|guests?|people|persons?)\b", re.I
)
CHILDREN = re.compile(r"\b(\d+|one|two|three|four)\s+(?:child|children|kids?)\b", re.I)
ROOMS = re.compile(r"\b(\d+|one|two|three|four)\s+rooms?\b", re.I)
BUDGET = re.compile(
    r"\b(?:under|below|less than|within|max(?:imum)?|budget(?: of| is)?|up to)\s+"
    r"(?:₹|rs\.?|inr)?\s*(?P<amount>\d[\d,]*)(?:\s*(?:rupees|rs|inr))?",
    re.I,
)
PLACE = re.compile(
    r"\b(?:hotels?|rooms?|stays?)\s+(?:in|at)\s+(?P<city>[a-z][a-z .'-]*?)"
    r"(?:\s+near\s+(?P<area>[a-z0-9][a-z0-9 .'&-]*?))?"
    r"(?=\s*(?:,|\.|$|\bcheck|\bfrom\b|\bfor\b|\bon\b|\bunder\b|\bbelow\b|\bwith\b|\d))",
    re.I,
)
ANSWER_CITY = re.compile(r"^(?:in|at|city is)\s+(?P<city>[a-z][a-z .'-]*?)\s*[,.]?$", re.I)
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
MAX_ADVANCE_DAYS = 365


@dataclass(frozen=True)
class HotelRequest:
    city: str = ""
    area: str = ""
    check_in: date | None = None
    check_out: date | None = None
    rooms: int = 1
    adults: int = 0
    children: int = 0
    budget: int = 0  # rupees per night, 0 = none
    assumed_year: bool = False

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days if self.check_in and self.check_out else 0

    def missing(self) -> list[str]:
        slots = (
            ("city", self.city),
            ("check-in date", self.check_in),
            ("check-out date", self.check_out),
            ("number of guests", self.adults),
        )
        return [name for name, value in slots if not value]


class SlotError(ValueError):
    """A request that can't be booked as said (past dates, check-out before check-in)."""


def _number(text: str) -> int:
    return int(text) if text.isdigit() else WORD_NUMBERS[text.lower()]


def _dates(text: str, today: date) -> tuple[list[tuple[int, date, bool]], bool]:
    """(position, date, labelled check-out) for every spoken date; True when a year was assumed."""
    found, assumed = [], False
    for match in DATE.finditer(text):
        g = match.groupdict()
        month = MONTHS[(g["month0a"] or g["month0b"]).lower()]
        day = int(g["day0"] or g["day0b"])
        year = g["year0"] or g["year0b"]
        if year:
            when = date(int(year), month, day)
        else:
            assumed = True
            when = date(today.year, month, day)
            if when < today:
                when = date(today.year + 1, month, day)
        before = text[: match.start()]
        found.append((match.start(), when, bool(CHECK_OUT.search(before))))
    return found, assumed


def parse(text: str, today: date, base: HotelRequest | None = None) -> HotelRequest:
    """Slots in `text`, filling only what `base` (the earlier, incomplete request) lacks or what
    the user now says explicitly. Raises SlotError for impossible dates."""
    req = base or HotelRequest()
    if place := PLACE.search(text):
        req = replace(req, city=place["city"].strip().title(), area=(place["area"] or "").strip())
    elif base and (answer := ANSWER_CITY.match(text.strip())):
        req = replace(req, city=answer["city"].strip().title())
    dates, assumed = _dates(text, today)
    for _, when, is_out in dates:
        if is_out or (req.check_in and not CHECK_IN.search(text) and when > req.check_in):
            req = replace(req, check_out=when)
        elif req.check_in is None or CHECK_IN.search(text):
            req = replace(req, check_in=when)
        else:
            req = replace(req, check_out=when)
    if dates:
        req = replace(req, assumed_year=req.assumed_year or assumed)
    if (nights := NIGHTS.search(text)) and req.check_in:
        req = replace(req, check_out=req.check_in + timedelta(days=_number(nights[1])))
    for pattern, slot in ((ADULTS, "adults"), (CHILDREN, "children"), (ROOMS, "rooms")):
        if found := pattern.search(text):
            req = replace(req, **{slot: _number(found[1])})
    if budget := BUDGET.search(text):
        req = replace(req, budget=int(budget["amount"].replace(",", "")))
    _validate(req, today)
    return req


def _validate(req: HotelRequest, today: date) -> None:
    if req.check_in and req.check_in < today:
        raise SlotError("That check-in date is in the past. Which date did you mean?")
    if req.check_in and req.check_in > today + timedelta(days=MAX_ADVANCE_DAYS):
        raise SlotError("Hotels can't be booked that far ahead. Which date did you mean?")
    if req.check_in and req.check_out and req.check_out <= req.check_in:
        raise SlotError("The check-out date has to be after check-in. When do you check out?")


def question(req: HotelRequest) -> str:
    """ONE question for every missing slot."""
    missing = req.missing()
    if not missing:
        return ""
    listed = missing[0] if len(missing) == 1 else f"{', '.join(missing[:-1])} and {missing[-1]}"
    verb = "is" if len(missing) == 1 else "are"
    return f"What {verb} the {listed}?"
