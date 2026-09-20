"""What a page is showing, as items a blind user can be told about (v2 Phase D2, D98).

Three site-specific skills (`amazon_search`, `spotify_search`, `youtube_search`,
`hotel_search`) all answered one question with four selector maps: what is on this
results page, and what does each one cost. This module answers it once, from the
agent-browser snapshot alone.

The structural fact every results page shares: one result card links to one
destination, and every link inside that card carries the same URL. So grouping a
snapshot's links by URL recovers the cards without knowing the site. Cards whose
URLs share a path shape are one family, and a page's families are its lists --
results, navigation, footer. Which family the user asked for is a pick among a
handful of labelled options, which is the question shape Jev answers well (D97);
which words are the name and the price is read off the snapshot, because Jev
cannot extract a span (D86).

Snapshot format: https://github.com/vercel-labs/agent-browser (`snapshot --urls`,
`- role "name" [ref=eN, url=...]`, indentation carrying the tree).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

MAX_SPOKEN_ITEMS = 5
MIN_FAMILY_ITEMS = 3
MAX_FAMILIES = 8
NAME_MAX_CHARS = 90
MIN_NAME_CHARS = 3
ID_SEGMENT_CHARS = 16
SITE_LABELS = 2

LINE = re.compile(
    r"^(?P<indent>\s*)-\s+(?P<role>[A-Za-z][\w-]*)"
    r'(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?'
    r"(?:\s+\[(?P<attrs>[^\]]*)\])?"
    r"(?P<tail>.*)$"
)
URL_ATTR = re.compile(r"(?:^|,\s*)url=(?P<url>\S+?)(?=,\s*\w+=|$)")
REF_ATTR = re.compile(r"(?:^|,\s*)ref=(e\d+)\b")

PRICE_TRIM = re.compile(r"^[\s.,\-%]*|[\s.,\-%]*(?:off)?[\s.,\-%]*$", re.I)
PRICE = re.compile(
    r"(?:₹|\bRs\.?|\bINR\b|\$|€|£|¥)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"|\b\d[\d,]*(?:\.\d{1,2})?\s?(?:rupees|dollars|euros|pounds)\b",
    re.I,
)
RATING = re.compile(
    r"\b\d(?:\.\d)?\s*(?:out of\s*\d|/\s*5|★|stars?\b)|\b(?:rated|rating)\s*\d(?:\.\d)?", re.I
)
REVIEW_SCORE = re.compile(r"\bscored\s*\d{1,2}(?:\.\d)?|\b\d(?:\.\d)?\s*(?:out of|/)\s*10\b", re.I)
HEADING = "heading"
URL_NAME = re.compile(r"^(?:https?://|www\.)\S+$", re.I)
A11Y_SUFFIX = re.compile(r"\s*opens? in (?:a )?new (?:window|tab)(?: or tab)?\s*$", re.I)
AD = re.compile(r"^(?:sponsored|ad|advertisement|promoted|paid)\b", re.I)
DIGITS = re.compile(r"\d")
SEGMENT_ID = "*"


@dataclass(frozen=True)
class Node:
    indent: int
    role: str
    name: str
    url: str
    ref: str
    value: str = ""


@dataclass(frozen=True)
class Item:
    """One card: where it goes, what it is called, and what the page prints beside it."""

    url: str
    name: str
    price: str = ""
    rating: str = ""
    ad: bool = False
    ref: str = ""

    def spoken(self) -> str:
        parts = [self.name]
        if self.price:
            parts.append(self.price)
        if self.rating:
            parts.append(self.rating)
        line = " — ".join(parts)
        return f"{line}, sponsored ad" if self.ad else line


@dataclass(frozen=True)
class Family:
    """Cards whose URLs share a path shape: one list on the page."""

    key: str
    items: list[Item]

    def label(self) -> str:
        first = self.items[0]
        return f"{len(self.items)} items under {self.key}, the first being {first.name!r}"


def parse(snapshot_text: str) -> list[Node]:
    nodes = []
    for line in snapshot_text.splitlines():
        match = LINE.match(line)
        if match is None:
            continue
        attrs = match.group("attrs") or ""
        url = URL_ATTR.search(attrs)
        ref = REF_ATTR.search(attrs)
        raw = match.group("name") or ""
        tail = (match.group("tail") or "").strip()
        nodes.append(
            Node(
                value=tail[1:].strip() if tail.startswith(":") else "",
                indent=len(match.group("indent")),
                role=match.group("role"),
                name=raw.replace('\\"', '"').replace("\\\\", "\\").strip(),
                url=url.group("url").rstrip(",") if url else "",
                ref=ref.group(1) if ref else "",
            )
        )
    return nodes


def _shape(path: str) -> list[str]:
    return [
        SEGMENT_ID if DIGITS.search(s) or len(s) > ID_SEGMENT_CHARS else s.lower()
        for s in path.split("/")
        if s
    ]


def site(netloc: str) -> str:
    """The site, not the subdomain: one artist per subdomain is still one list of albums."""
    labels = netloc.casefold().split(":")[0].split(".")
    return ".".join(labels[-SITE_LABELS:]) if len(labels) > SITE_LABELS else ".".join(labels)


def family_key(url: str) -> str:
    """The URL's path shape: site plus segments, with identifiers blanked out."""
    parsed = urlparse(url)
    return f"{site(parsed.netloc)}/{'/'.join(_shape(parsed.path))}"


def card_key(url: str) -> str:
    """What the card points at. A path carrying an identifier already names the thing, so its
    query is tracking and two links that differ only there are one card; a path that does not
    (`/watch?v=...`) is told apart by its query alone."""
    parsed = urlparse(url)
    shape = _shape(parsed.path)
    if SEGMENT_ID not in shape:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def best_name(names: list[str]) -> str:
    """The longest name that is not a price and not the bare URL, cut to a speakable length."""
    cleaned = [A11Y_SUFFIX.sub("", name).strip() for name in names]
    spoken = [
        n
        for n in cleaned
        if len(n) >= MIN_NAME_CHARS and not _only_price(n) and not URL_NAME.match(n)
    ]
    if not spoken:
        return ""
    plain = [n for n in spoken if not PRICE.search(n)]
    longest = max(plain or spoken, key=len)
    return longest[:NAME_MAX_CHARS].rstrip() if len(longest) > NAME_MAX_CHARS else longest


def _only_price(name: str) -> bool:
    return not PRICE_TRIM.sub("", PRICE.sub("", name))


def _first(pattern: re.Pattern[str], texts: list[str]) -> str:
    for text in texts:
        for found in pattern.finditer(text):
            if any(ch in "123456789" for ch in found.group(0)):
                return found.group(0).strip()
    return ""


def cards(nodes: list[Node]) -> list[Item]:
    """One Item per distinct URL, with the text printed between it and the next card."""
    linked = [index for index, node in enumerate(nodes) if node.url]
    by_url: dict[str, list[int]] = {}
    for index in linked:
        by_url.setdefault(card_key(nodes[index].url), []).append(index)
    made = []
    for url, indexes in by_url.items():
        region = _region(nodes, indexes)
        text = [node.name for node in region if node.name]
        linked = [nodes[i].name for i in indexes]
        name = best_name([n.name for n in region if n.role == HEADING and n.name]) or best_name(
            linked
        )
        if not name:
            continue
        made.append(
            Item(
                url=url,
                name=name,
                price=_first(PRICE, linked + text),
                rating=_first(REVIEW_SCORE, text) or _first(RATING, text + linked),
                ad=any(AD.match(line) for line in text),
                ref=nodes[indexes[0]].ref,
            )
        )
    return made


def _region(nodes: list[Node], indexes: list[int]) -> list[Node]:
    """The card: its own lines plus the unlinked ones around them, up to the neighbouring cards.

    A title often sits in a heading just above the link that carries the URL, and the price just
    below it, so the region runs in both directions until another card's link ends it.
    """
    start, stop = indexes[0], indexes[-1] + 1
    indent = nodes[start].indent
    while start > 0 and not nodes[start - 1].url and nodes[start - 1].indent >= indent:
        start -= 1
    while stop < len(nodes) and (not nodes[stop].url or nodes[stop].url == nodes[indexes[0]].url):
        stop += 1
    return nodes[start:stop]


def families(snapshot_text: str) -> list[Family]:
    """The page's repeated lists, biggest first, capped so one Jev question can hold them."""
    grouped: dict[str, list[Item]] = {}
    for item in cards(parse(snapshot_text)):
        grouped.setdefault(family_key(item.url), []).append(item)
    named = {key: _named(key, items) for key, items in grouped.items()}
    found = [Family(key, items) for key, items in named.items() if len(items) >= MIN_FAMILY_ITEMS]
    found.sort(key=lambda f: len(f.items), reverse=True)
    return found[:MAX_FAMILIES]


def _named(key: str, items: list[Item]) -> list[Item]:
    """One card per name: drop a name that restates its own URL shape (a bare "Watch" link) and
    the second copy of a thing the page links to twice."""
    shape, seen, kept = key.casefold(), set(), []
    for item in items:
        name = item.name.casefold()
        if name in shape or name in seen:
            continue
        seen.add(name)
        kept.append(item)
    return kept


def read_back(family: Family, limit: int = MAX_SPOKEN_ITEMS) -> str:
    return "\n".join(
        f"{n}. {item.spoken()}" for n, item in enumerate(family.items[:limit], start=1)
    )


RESULTS_QUESTION = (
    "A blind user asked for this page. Which of these lists on it holds the results they "
    "asked for, as opposed to navigation, adverts, or the site's own furniture?"
)
NO_LIST = "none of these lists holds what the user asked for"
RESULTS_STATE = """\
A voice assistant is reading a web page aloud to a blind user.

What the user asked for: {goal}
Page title: {title}

The repeated lists this page shows, one per line:
{lists}"""


def results_state(goal: str, title: str, found: list[Family]) -> str:
    from zoya import safety

    lists = "\n".join(f"{family.key}: {family.label()}" for family in found)
    return RESULTS_STATE.format(goal=goal, title=title, lists=safety.wrap_untrusted(lists))


def results_criteria(found: list[Family]) -> dict[str, str]:
    return {**{family.key: family.label() for family in found}, NONE: NO_LIST}


NONE = "none_of_these"


def choose(goal: str, title: str, found: list[Family]) -> tuple[Family | None, float]:
    """Which list the user asked for. `(None, confidence)` when Jev cannot say."""
    from typesafe_sdk import Choice

    from zoya import decisions
    from zoya.config import JEV_STEP_CONFIDENCE

    if not found:
        return None, 0.0
    if len(found) == 1:
        return found[0], 1.0
    answers = decisions.ask(
        results_state(goal, title, found),
        {"list": Choice(instructions=RESULTS_QUESTION, criteria=results_criteria(found))},
    )
    pick = answers.pick("list")
    if pick is None or pick.confidence < JEV_STEP_CONFIDENCE:
        return None, pick.confidence if pick else 0.0
    return next((f for f in found if f.key == pick.name), None), pick.confidence


MAX_SUBJECTS = 8
SUBJECT_QUESTION = (
    "The assistant is about to press this control. Which of these is what the action is about "
    "-- the channel it will subscribe to, the words it will post or send, the item it will buy, "
    "the room it will book, the file it will delete? Choose none_of_these when none of them is."
)
NO_SUBJECT = "none of these is what the action is about"
SUBJECT_STATE = """\
A voice assistant is about to do something irreversible on a web page for a blind user, and
must say out loud what it is about to do before asking the user to confirm.

The action: {say}
The control it will press: {control}
Page title: {title}

What the page shows around that control -- text already typed into a field first, then names
the page prints, nearest the control first:
{names}"""
TITLE_SPLIT = re.compile(r"\s+[|–—-]\s+")
TYPED = {"textbox", "searchbox", "combobox"}


@dataclass(frozen=True)
class Subject:
    key: str
    name: str


def _title_names(title: str) -> list[str]:
    """A page title minus the site's own name: "MrBeast - YouTube" offers "MrBeast"."""
    parts = [part.strip() for part in TITLE_SPLIT.split(title) if part.strip()]
    return parts[:1] if parts else []


def subject_candidates(snapshot_text: str, ref: str, title: str) -> list[Subject]:
    """Names the page prints around the control, nearest first: headings, then the control's
    own neighbours. Only names -- never page text that could carry instructions."""
    nodes = parse(snapshot_text)
    anchor = next((i for i, node in enumerate(nodes) if node.ref == ref), len(nodes) // 2)
    typed = [
        f'"{node.value.strip()}"' for node in nodes if node.role in TYPED and node.value.strip()
    ]
    named = sorted(
        (abs(index - anchor), node.name.strip())
        for index, node in enumerate(nodes)
        if node.name.strip() and (node.role == HEADING or node.url)
    )
    ordered = typed + _title_names(title) + [name for _distance, name in named]
    made, seen = [], set()
    for name in ordered:
        cleaned = A11Y_SUFFIX.sub("", name).strip()[:NAME_MAX_CHARS]
        if len(cleaned) < MIN_NAME_CHARS or cleaned.casefold() in seen or URL_NAME.match(cleaned):
            continue
        seen.add(cleaned.casefold())
        made.append(cleaned)
    return [Subject(f"s{index}", name) for index, name in enumerate(_cores(made)[:MAX_SUBJECTS])]


def _cores(names: list[str]) -> list[str]:
    """One entry per thing named. "Hotel Lotus", "Hotel Lotus, Candolim - Check location" and
    "Hotel Lotus, Candolim (updated prices 2027)" are one hotel, and offering Jev all three
    splits its confidence across them; the shortest is the name and the rest are decoration."""
    kept = []
    for name in sorted(names, key=len):
        if not any(core.casefold() in name.casefold() for core in kept):
            kept.append(name)
    return sorted(kept, key=names.index)


def subject_state(say: str, control: str, title: str, subjects: list[Subject]) -> str:
    from zoya import safety

    names = "\n".join(f"{s.key}: {s.name}" for s in subjects)
    return SUBJECT_STATE.format(
        say=say, control=control, title=title, names=safety.wrap_untrusted(names)
    )


def subject(say: str, control: str, title: str, subjects: list[Subject]) -> tuple[str, float]:
    """What the action is about, in the page's own words. `("", confidence)` when Jev cannot say.

    Naming the wrong thing is worse than naming nothing, so an unconfident answer names nothing
    and the caller falls back to the vaguer summary it already had.
    """
    from typesafe_sdk import Choice

    from zoya import decisions
    from zoya.config import JEV_STEP_CONFIDENCE

    if not subjects:
        return "", 0.0
    answers = decisions.ask(
        subject_state(say, control, title, subjects),
        {
            "subject": Choice(
                instructions=SUBJECT_QUESTION,
                criteria={**{s.key: s.name for s in subjects}, NONE: NO_SUBJECT},
            )
        },
    )
    pick = answers.pick("subject")
    if pick is None or pick.confidence < JEV_STEP_CONFIDENCE:
        return "", pick.confidence if pick else 0.0
    found = next((s for s in subjects if s.key == pick.name), None)
    return (found.name if found else ""), pick.confidence
