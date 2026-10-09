"""Memory (§9.8, D8, D22, D147): ~/.zoya/memory.json, a secret filter, and two dev-only copies.

- `memory_add` rejects card numbers, OTPs, passwords, PINs and CVVs before anything is written
  (§9.8 privacy, §12.3). The filter is the only gate: the model is told, but not trusted.
- License users and the shipped app: memory.json is the only store (D147). Keyword search with
  folded, lightly stemmed words; every memory inline while there are few; the profile built locally.
- A developer's own SUPERMEMORY_API_KEY (dev checkout, no license) adds the Supermemory cloud,
  `dreaming="instant"` and `search_mode="hybrid"` (AUDIT B16). AWS_PROFILE adds DynamoDB.

SDK (supermemory 3.61.0, installed source): `Supermemory.add(content, container_tag, dreaming,
metadata)`, `Supermemory.search.memories(q, container_tag, limit, search_mode)` → results[].memory /
.chunk. Docs: https://supermemory.ai/docs
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Any

from strands import tool

from zoya import aws, events, memory_rules, tasks
from zoya.config import (
    APP_BUNDLE,
    JEV_LIVE_FACT_CONFIDENCE,
    JEV_STEP_CONFIDENCE,
    MEMORY_INLINE_MAX,
    MEMORY_LOCAL_FILE,
    MEMORY_PROFILE_MAX_TOKENS,
    MEMORY_SEARCH_LIMIT,
    MEMORY_TABLE,
    MEMORY_TIMEOUT_S,
    MEMORY_USER_TAG,
    license_key,
)
from zoya.tools import ToolError

log = logging.getLogger(__name__)

CATEGORIES = {
    "preference",
    "contact",
    "address",
    "order_history",
    "routine",
    "correction",
    "activity",
}
MAX_MEMORY_CHARS = 1000
LOCAL_MAX_ITEMS = 500
MIN_WORD_CHARS = 3
REMEMBERED = "Here's what I remember:\n"
REJECTED = "I can't remember that: it looks like a card number, password or one-time code."

# --- Secret filter (tests/test_memory_filter.py) --------------------------------------------

CARD_DIGITS = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
# Latin, Hinglish and Devanagari secret words. Devanagari has no reliable \b (vowel signs aren't
# \w), so those words match anywhere. "pin code", "zip code" and friends are addresses, not secrets.
SECRET_WORD = re.compile(
    r"\b(?:otp|one[- ]?time (?:password|code|pin)|verification code|security code|"
    r"auth(?:entication)? code|passcode|password|passwd|pass ?word|cvv|cvc|cvv2|upi pin|atm pin|"
    r"card pin|mpin|netbanking|net banking|card (?:number|no)|pin(?! ?code)|"
    r"(?<!pin )(?<!zip )(?<!postal )(?<!area )(?<!promo )(?<!coupon )(?<!dress )(?<!country )"
    r"(?<!qr )(?<!source )code)\b"
    r"|ओटीपी|पासवर्ड|सीवीवी|यूपीआई पिन|कार्ड नंबर|पिन(?! ?कोड)|(?<!पिन )(?<!पिन)कोड",
    re.I,
)
CARD_WORDS = re.compile(r"\b(?:card|debit|credit|visa|mastercard|rupay|amex)\b|कार्ड", re.I)
SHORT_NUMBER = re.compile(r"(?<!\d)\d{3,8}(?!\d)")
EXPIRY = re.compile(r"(?<!\d)(?:0[1-9]|1[0-2])\s*/\s*\d{2}(?:\d{2})?(?!\d)")
DIGIT_WORDS = {
    **dict.fromkeys(["zero", "oh", "शून्य"], "0"),
    **dict.fromkeys(["one", "एक"], "1"),
    **dict.fromkeys(["two", "दो"], "2"),
    **dict.fromkeys(["three", "तीन"], "3"),
    **dict.fromkeys(["four", "चार"], "4"),
    **dict.fromkeys(["five", "पांच", "पाँच"], "5"),
    **dict.fromkeys(["six", "छह", "छः", "छे"], "6"),
    **dict.fromkeys(["seven", "सात"], "7"),
    **dict.fromkeys(["eight", "आठ"], "8"),
    **dict.fromkeys(["nine", "नौ"], "9"),
}
REPEATS = {"double": 2, "triple": 3}
TOKEN = re.compile(r"[^\s,.;:!?()\-]+")
SPACED_DIGITS = re.compile(r"(?<!\d)\d(?:[\s,-]+\d){3,}(?!\d)")  # "4 8 2 9", from any spelling


def _ascii_digits(text: str) -> str:
    """Every Unicode decimal digit (Devanagari ४, fullwidth ４…) as 0–9."""
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)


def spoken_digits(text: str) -> str:
    """Digit words and "double/triple N" become spaced digits: "double four one" → "4 4 1"."""
    out: list[str] = []
    repeat = 1
    for token in TOKEN.findall(_ascii_digits(unicodedata.normalize("NFKC", text))):
        word = token.casefold()
        if word in REPEATS:
            repeat = REPEATS[word]
            continue
        digit = DIGIT_WORDS.get(word) or (token if token.isdigit() and len(token) == 1 else None)
        out += [digit] * repeat if digit else [word]
        repeat = 1
    return " ".join(out)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char) * (2 if index % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def secret_reason(text: str) -> str | None:
    """Why `text` must never be stored, or None. Errs toward refusing (a lost memory is cheap).

    Digits are normalised first (Devanagari/fullwidth → 0–9). Blocks: a Luhn-valid 13–19 digit
    number; any secret word (OTP, password, PIN but not "pin code", CVV, code, card number; English,
    Hinglish, Devanagari); card words with a short number or an expiry date; 4+ digits said one by
    one ("four eight two nine", "double four double one", "चार आठ दो नौ", "4 8 2 9").
    """
    plain = _ascii_digits(unicodedata.normalize("NFKC", text))
    for match in CARD_DIGITS.finditer(plain):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "card number"
    if SECRET_WORD.search(plain):
        return "secret word"
    if CARD_WORDS.search(plain) and (SHORT_NUMBER.search(plain) or EXPIRY.search(plain)):
        return "card details"
    if SPACED_DIGITS.search(spoken_digits(text)):
        return "spelled-out code"
    return None


# --- Stores ------------------------------------------------------------------------------------

_local_lock = threading.Lock()


def _supermemory() -> Any | None:
    """The Supermemory cloud, for a developer's own key only: no license user, not the app."""
    key = os.environ.get("SUPERMEMORY_API_KEY")
    if not key or license_key() or APP_BUNDLE:
        return None
    return _cloud(key)


@cache
def _cloud(key: str) -> Any:
    from supermemory import Supermemory

    return Supermemory(api_key=key, timeout=MEMORY_TIMEOUT_S, max_retries=0)


def _read_local() -> list[dict[str, str]]:
    try:
        return json.loads(MEMORY_LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_local(item: dict[str, str]) -> None:
    with _local_lock:
        items = [*_read_local(), item][-LOCAL_MAX_ITEMS:]
        try:
            MEMORY_LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_LOCAL_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            log.warning("local memory copy failed (%s)", type(error).__name__)


def _put_dynamodb(item: dict[str, str]) -> None:
    try:
        dynamodb = aws.client("dynamodb")
        if dynamodb is None:
            return
        dynamodb.put_item(
            TableName=MEMORY_TABLE,
            Item=_dynamodb_key(item) | {key: {"S": value} for key, value in item.items()},
        )
    except Exception as error:  # noqa: BLE001 — a copy; the local file already has it
        log.warning("DynamoDB memory copy failed (%s)", aws._reason(error))


def _query_dynamodb() -> list[dict[str, str]]:
    try:
        dynamodb = aws.client("dynamodb")
        if dynamodb is None:
            return []
        items = []
        for kind in ("memory", "order"):
            response = dynamodb.query(
                TableName=MEMORY_TABLE,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": {"S": f"{kind}#{MEMORY_USER_TAG}"}},
                ScanIndexForward=False,
                Limit=LOCAL_MAX_ITEMS,
            )
            items += [{k: v["S"] for k, v in row.items()} for row in response.get("Items", [])]
        return items
    except Exception as error:  # noqa: BLE001 — search falls back to nothing, said politely
        log.warning("DynamoDB memory query failed (%s)", aws._reason(error))
        return []


def _dynamodb_key(item: dict[str, str]) -> dict[str, dict[str, str]]:
    kind = "order" if item.get("category") == "order_history" else "memory"
    return {"pk": {"S": f"{kind}#{MEMORY_USER_TAG}"}, "sk": {"S": f"{item['at']}#{item['id']}"}}


def _document_ids(client: Any, item: dict[str, str]) -> list[str]:
    try:
        return [client.documents.get(item["id"]).id]
    except Exception as error:  # noqa: BLE001
        log.info(
            "no Supermemory document by custom id (%s), matching by text", type(error).__name__
        )
    listed = client.documents.list(
        container_tags=[MEMORY_USER_TAG], include_content=True, limit=LOCAL_MAX_ITEMS
    )
    return [d.id for d in listed.memories if (d.content or "").strip() == item["content"]]


def _forget_supermemory(item: dict[str, str]) -> None:
    client = _supermemory()
    if client is None:
        return
    for document_id in _document_ids(client, item):
        client.documents.delete(document_id)


def _forget_dynamodb(item: dict[str, str]) -> None:
    dynamodb = aws.client("dynamodb")
    if dynamodb is not None:
        dynamodb.delete_item(TableName=MEMORY_TABLE, Key=_dynamodb_key(item))


def memories() -> list[dict[str, str]]:
    return list(reversed(_read_local()))


def forget(item_id: str) -> bool:
    item = next((i for i in _read_local() if i.get("id") == item_id), None)
    if item is None:
        return False
    try:
        _forget_supermemory(item)
        _forget_dynamodb(item)
    except Exception as error:  # noqa: BLE001
        log.warning("memory delete failed (%s)", type(error).__name__)
        return False
    with _local_lock:
        kept = [i for i in _read_local() if i.get("id") != item_id]
        MEMORY_LOCAL_FILE.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    log.info("memory deleted from every copy")
    return True


# --- Local search (D147) ---------------------------------------------------------------------

WORD = re.compile(r"[\w\u0900-\u097f]+")
LATIN_ACCENTS = re.compile(r"[\u0300-\u036f]")
STOPWORDS = {
    # fmt: off
    "the", "and", "are", "was", "for", "you", "your", "what", "which", "who", "whom", "when",
    "where", "how", "does", "did", "have", "has",
    "kya", "hai", "hain", "tha", "thi", "mera", "meri", "mere", "mujhe", "mujhko", "kaun",
    "kaunsa", "kaunsi", "kab", "kahan", "aur", "myself",
    "क्या", "है", "हैं", "मेरा", "मेरी", "मेरे", "मुझे", "कौन", "कब", "कहाँ", "और",
    # fmt: on
}
KEEP_S = ("ss", "us", "is", "as")
KEEP_DOUBLE = "lsz"


def _stem(word: str) -> str:
    """Plurals and -ing only, on long enough words: "chais" → "chai", "running" → "run"."""
    if word.endswith("ing") and len(word) >= 6:
        stem = word[:-3]
        return stem[:-1] if stem[-1] == stem[-2] and stem[-1] not in KEEP_DOUBLE else stem
    if word.endswith("ies") and len(word) >= 5:
        return word[:-3] + "y"
    if word.endswith("s") and len(word) >= 4 and not word.endswith(KEEP_S):
        return word[:-1]
    return word


def search_words(text: str) -> set[str]:
    """Case- and accent-folded words plus their stems. A Hinglish word always keeps its own form."""
    folded = LATIN_ACCENTS.sub("", unicodedata.normalize("NFKD", text.casefold()))
    words = {w for w in WORD.findall(unicodedata.normalize("NFC", folded)) if w not in STOPWORDS}
    return {form for w in words if len(w) >= MIN_WORD_CHARS for form in (w, _stem(w))}


def local_matches(query: str, items: list[dict[str, str]]) -> list[str]:
    """Memories sharing the most words with the query, newest first on ties."""
    wanted = search_words(query)
    scored = []
    for index, item in enumerate(items):
        if hits := len(wanted & search_words(item.get("content", ""))):
            scored.append((hits, index, item["content"]))
    return [content for *_, content in sorted(scored, reverse=True)[:MEMORY_SEARCH_LIMIT]]


# --- Saving: live facts stay at the source, new replaces old, every save is said (D163) -------

DATED_RECORDS = {"order_history", "activity"}
LIVE_SKIPPED = "That changes, so I won't save it. I'll check it fresh next time."
ALREADY_SAVED = "I already remember that."
SAVED_LINE = "Remembered: {text}"
UPDATED_LINE = "Updated: {text} (was {old})"
FORGOT_LINE = "Okay, forgotten: {text}"
RESTORED_LINE = "Okay, forgotten. Back to: {old}"
FORGET_FAILED = "I couldn't forget that just now. You can delete it in the Hub."
SPOKEN_MAX_CHARS = 120
ANNOUNCE_KEEP = 20
FORGET_THAT = re.compile(
    r"^(?:(?:no|nahi|nahin|wait|actually|oh|arre|ok|okay|hey|zoya|never mind|sorry)\s+)*"
    r"(?:please\s+)?(?:"
    r"forget (?:that|it|this|what i (?:just )?said)|(?:don'?t|do not) (?:remember|save|keep) "
    r"(?:that|it|this)|(?:ye|yeh|ise|isko|woh|wo|use|usko)?\s*(?:bhool ja(?:o|iye|na)?|"
    r"mat yaad rakh(?:o|na|iye)?|yaad mat rakh(?:o|na|iye)?)|"
    r"(?:इसे|ये|यह|वो|उसे)?\s*(?:भूल जाओ|भूल जाइए|याद मत रखो|याद मत रखना|मत याद रखो)"
    r")(?:\s+please)?$"
)
PUNCTUATION = re.compile(r"[,.!?।]+")


@dataclass(frozen=True)
class Undo:
    item: dict[str, str]
    replaced: tuple[dict[str, str], ...]


_said_lock = threading.Lock()
_announce: dict[str, list[str]] = {}
_undoable: Undo | None = None


def _new_item(text: str, kind: str) -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "category": kind,
        "content": text,
    }


def _store(item: dict[str, str]) -> None:
    _save_local(item)
    threading.Thread(target=_put_dynamodb, args=(item,), daemon=True).start()
    started = time.monotonic()
    where = "on this Mac"
    try:
        client = _supermemory()
        if client is not None:
            client.add(
                content=item["content"],
                custom_id=item["id"],
                container_tag=MEMORY_USER_TAG,
                dreaming="instant",
                metadata={"category": item["category"]},
            )
            where = "in memory"
    except Exception as error:  # noqa: BLE001 — the local and DynamoDB copies still hold it
        log.warning("Supermemory add failed (%s)", type(error).__name__)
    log.info("memory_add %s in %d ms", where, round((time.monotonic() - started) * 1000))


def _spoken(text: str) -> str:
    if len(text) <= SPOKEN_MAX_CHARS:
        return text
    return text[:SPOKEN_MAX_CHARS].rsplit(" ", 1)[0] + "…"


def _task_key() -> str:
    task = tasks.current()
    return task.id if task is not None else ""


def _announced(line: str) -> str:
    with _said_lock:
        _announce.setdefault(_task_key(), []).append(line)
        while len(_announce) > ANNOUNCE_KEEP:
            del _announce[next(iter(_announce))]
    return line


def take_announcements(spoken: str = "") -> str:
    """This task's save lines, said once at its end; any already in `spoken` are left out."""
    with _said_lock:
        lines = _announce.pop(_task_key(), [])
    heard = unicodedata.normalize("NFKC", spoken)
    return " ".join(
        line for line in dict.fromkeys(lines) if unicodedata.normalize("NFKC", line) not in heard
    )


LIVE_STATE = "The user asked their voice assistant to remember: {text!r}"
LIVE_QUESTION = (
    "Is this a changing fact about the world or about a moment (a delivery date, a price, a "
    "balance, today's weather, a one-time appointment, how someone feels right now), rather than "
    "a lasting fact about the user?"
)


def _live_by_jev(text: str) -> bool:
    """Jev sees only the fact. Unavailable or unsure means it is kept."""
    from typesafe_sdk import Noul

    from zoya import decisions

    question = {"live": Noul(instructions=LIVE_QUESTION)}
    answers = decisions.ask(LIVE_STATE.format(text=text), question)
    return bool(answers) and answers.noul("live") >= JEV_LIVE_FACT_CONFIDENCE


def live_fact(text: str) -> str | None:
    """Why `text` is a changing fact that stays at its source, or None. The local rules first; Jev
    only for what they would keep (it caught phrasings the rules missed on the held-out sets)."""
    if reason := memory_rules.live_reason(text):
        return reason
    return "jev" if _live_by_jev(text) else None


def _same_text(left: str, right: str) -> bool:
    return " ".join(left.casefold().split()) == " ".join(right.casefold().split())


def remember(content: str, category: str = "preference") -> str:
    """Save one memory and return the one line that says so. Raises ToolError on a secret.

    A changing fact is not saved; a fact that contradicts an older one replaces it; the line is
    said at the end of the task, and "forget that" on the next turn undoes it.
    """
    global _undoable
    text = " ".join(content.split())[:MAX_MEMORY_CHARS]
    if not text:
        raise ToolError("What should I remember?")
    if secret_reason(text):
        raise ToolError(REJECTED)
    kind = category if category in CATEGORIES else "preference"
    if kind in DATED_RECORDS:
        _store(_new_item(text, kind))
        return f"Saved: {text}"
    if reason := live_fact(text):
        log.info("memory not saved: a live fact (%s)", reason)
        return _announced(LIVE_SKIPPED)
    existing = _read_local()
    if any(_same_text(i.get("content", ""), text) for i in existing):
        return _announced(ALREADY_SAVED)
    old = memory_rules.superseded(text, kind, existing)
    item = _new_item(text, kind)
    _store(item)
    replaced = tuple(i for i in old if forget(i["id"]))
    with _said_lock:
        _undoable = Undo(item, replaced)
    if replaced:
        was = memory_rules.short_value(replaced[0]["content"])
        return _announced(UPDATED_LINE.format(text=_spoken(text), old=_spoken(was)))
    return _announced(SAVED_LINE.format(text=_spoken(text)))


def _plain(command: str) -> str:
    return " ".join(PUNCTUATION.sub(" ", command.casefold().replace("’", "'")).split())


def next_turn(command: str) -> str | None:
    """A new command. "Forget that" right after a save undoes exactly that save (and puts back a
    memory it replaced) and returns the line to say; anything else closes the window: None."""
    global _undoable
    with _said_lock:
        last, _undoable = _undoable, None
    if last is None or not FORGET_THAT.match(_plain(command)):
        return None
    if not forget(last.item["id"]):
        return FORGET_FAILED
    for old in last.replaced:
        _store(old)
    if last.replaced:
        return RESTORED_LINE.format(old=_spoken(last.replaced[0]["content"]))
    return FORGOT_LINE.format(text=_spoken(last.item["content"]))


# --- Tools -------------------------------------------------------------------------------------


@tool
def memory_add(content: str, category: str = "preference") -> str:
    """Remember a lasting fact about the user (favourite brands, addresses, contacts, routines,
    and corrections like "I meant Rahul Verma"). Never passwords, OTPs or cards. Changing facts
    (a delivery date, a price, today's weather, a one-time appointment) are not kept: read them
    fresh from the app or site. Zoya says each save herself at the end; don't repeat it.

    Args:
        content: The fact in one sentence, e.g. "Home address: 12 Lake View Road, Pune".
        category: preference | contact | address | order_history | routine | correction.
    """
    said = remember(content, category)
    events.emit(events.EarconEvent("checkpoint"))
    return said


@tool
def memory_search(query: str) -> str:
    """Look up what Zoya remembers about the user. Call it before asking a preference question.
    While Zoya remembers only a few things, it returns all of them: use the ones that fit.

    Args:
        query: What to look for, e.g. "usual groceries".
    """
    query = " ".join(query.split())
    if not query:
        raise ToolError("What should I look up?")
    local = _read_local()
    if local and len(local) <= MEMORY_INLINE_MAX:
        return REMEMBERED + _bullets([i["content"] for i in reversed(local)])
    if search_words(query):
        found = _cloud_search(query) or local_matches(query, local or _query_dynamodb())
    else:
        found = _profile_lines(local)[:MEMORY_SEARCH_LIMIT]
    if not found:
        return f"I don't remember anything about {query}."
    return REMEMBERED + _bullets(found)


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {text}" for text in lines)


def _cloud_search(query: str) -> list[str]:
    try:
        client = _supermemory()
        if client is None:
            return []
        response = client.search.memories(
            q=query, container_tag=MEMORY_USER_TAG, limit=MEMORY_SEARCH_LIMIT, search_mode="hybrid"
        )
        return [text for r in response.results if (text := r.memory or r.chunk)]
    except Exception as error:  # noqa: BLE001 — the local copy answers instead
        log.warning("Supermemory search failed (%s)", type(error).__name__)
        return []


def recent_corrections(limit: int = 3) -> list[str]:
    """Latest corrections from the local copy (§13.5.6), added to the brain's request. No
    network."""
    return [i["content"] for i in _read_local() if i.get("category") == "correction"][-limit:]


def home_address() -> str:
    """The newest saved address (local copy), for "near me"."""
    return next(
        (i["content"] for i in reversed(_read_local()) if i.get("category") == "address"), ""
    )


# --- The user's profile in the brain's prompt (Phase H, D147) -----------------------------------

CHARS_PER_TOKEN = 4
PROFILE_HEADING = (
    "About the user (from Zoya's memory; answer from it without memory_search when it is enough):"
)
NOT_PROFILE = {"activity"}


def profile_block(lines: list[str], max_tokens: int = MEMORY_PROFILE_MAX_TOKENS) -> str:
    """The profile as a short prompt block: secrets dropped, duplicates folded, capped."""
    budget = max_tokens * CHARS_PER_TOKEN - len(PROFILE_HEADING)
    kept: list[str] = []
    for line in dict.fromkeys(" ".join(line.split()) for line in lines):
        if not line or secret_reason(line):
            continue
        cost = len(line) + len("\n- ")
        if cost > budget:
            break
        kept.append(line)
        budget -= cost
    return "\n".join([PROFILE_HEADING, *(f"- {line}" for line in kept)]) if kept else ""


def _profile_lines(items: list[dict[str, str]]) -> list[str]:
    return [i["content"] for i in reversed(items) if i.get("category") not in NOT_PROFILE]


def user_profile() -> str:
    """The newest preferences and facts from memory.json, capped. One file read, no network."""
    return profile_block(_profile_lines(_read_local()))


PICKED = "[From Zoya's memory, picked for this request: {lines}]"


def relevant_block(request: str, items: list[dict[str, str]] | None = None) -> str:
    """Over MEMORY_INLINE_MAX memories: the few that matter for `request` and aren't already in
    the profile, as one line for the request (D168 #5). The local keyword search, no network."""
    items = _read_local() if items is None else items
    if len(items) <= MEMORY_INLINE_MAX:
        return ""
    shown = profile_block(_profile_lines(items))
    rest = [i for i in items if i.get("content") and i["content"] not in shown]
    picks = [line for line in local_matches(request, rest) if not secret_reason(line)]
    return PICKED.format(lines="; ".join(picks)) if picks else ""


# --- Learning from what Zoya does (Phase H) -------------------------------------------------------

WORTH_REMEMBERING = (
    "Does this request reveal something lasting about the user worth remembering, such as a "
    "preference, a habit, a person they deal with or a place they care about, rather than a "
    "routine one-off command?"
)
OUTCOME_STATE = "The user asked their voice assistant, and it was done: {command!r}"
OUTCOME_LINE = "Asked Zoya: {command}"


def capture_outcome(command: str) -> bool:
    """After a task completes: keep one line about it when Jev says it's worth remembering.

    A secret-shaped command never leaves the Mac, not even to Jev. Jev unavailable or unsure means
    nothing is kept. Returns whether a line was saved.
    """
    from typesafe_sdk import Noul

    from zoya import decisions

    command = " ".join(command.split())[:MAX_MEMORY_CHARS]
    if not command or secret_reason(command):
        return False
    answers = decisions.ask(
        OUTCOME_STATE.format(command=command), {"worth": Noul(instructions=WORTH_REMEMBERING)}
    )
    if not answers or answers.noul("worth") < JEV_STEP_CONFIDENCE:
        return False
    try:
        remember(OUTCOME_LINE.format(command=command), "activity")
    except ToolError:
        return False
    return True


TOOLS = [memory_add, memory_search]
