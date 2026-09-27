"""Memory (§9.8, D8, D22): Supermemory, a local copy and a DynamoDB copy, and a secret filter.

- `memory_add` rejects card numbers, OTPs, passwords, PINs and CVVs before anything leaves the Mac
  (§9.8 privacy, §12.3). The filter is the only gate: the model is told, but not trusted.
- Supermemory local (zoya/memory_server.py) for license users, the cloud with SUPERMEMORY_API_KEY.
- Supermemory with `dreaming="instant"` (searchable in ~7 s) and `search_mode="hybrid"` (AUDIT B16).
- Every saved memory is also written to ~/.zoya/memory.json and DynamoDB `zoya-memory`, so search
  still works when Supermemory is down or the free plan pauses (D22).

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
from datetime import UTC, datetime
from functools import cache
from typing import Any

from strands import tool

from zoya import aws, events, memory_server
from zoya.config import (
    JEV_STEP_CONFIDENCE,
    MEMORY_LOCAL_FILE,
    MEMORY_LOCAL_SEARCH_THRESHOLD,
    MEMORY_PROFILE_MAX_TOKENS,
    MEMORY_PROFILE_SETTLE_S,
    MEMORY_PROFILE_TIMEOUT_S,
    MEMORY_PROFILE_TTL_S,
    MEMORY_SEARCH_LIMIT,
    MEMORY_SERVER_LOCAL_KEY,
    MEMORY_TABLE,
    MEMORY_TIMEOUT_S,
    MEMORY_USER_TAG,
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


@cache
def _supermemory() -> Any | None:
    from supermemory import Supermemory

    if key := os.environ.get("SUPERMEMORY_API_KEY"):
        return Supermemory(api_key=key, timeout=MEMORY_TIMEOUT_S, max_retries=0)
    if memory_server.wanted():
        memory_server.wait_ready()
        return Supermemory(
            api_key=MEMORY_SERVER_LOCAL_KEY,
            base_url=memory_server.base_url(),
            timeout=MEMORY_TIMEOUT_S,
            max_retries=0,
        )
    return None


def _search_options() -> dict[str, float]:
    """Supermemory local runs bge-m3, whose scores sit under the cloud's default threshold."""
    if not memory_server.wanted():
        return {}
    return {"threshold": MEMORY_LOCAL_SEARCH_THRESHOLD}


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
    refresh_profile()
    return True


def local_matches(query: str, items: list[dict[str, str]]) -> list[str]:
    """Keyword fallback: memories sharing the most words with the query, newest first on ties."""
    wanted = {w for w in re.findall(r"\w+", query.casefold()) if len(w) >= MIN_WORD_CHARS}
    scored = []
    for index, item in enumerate(items):
        words = set(re.findall(r"\w+", item.get("content", "").casefold()))
        if hits := len(wanted & words):
            scored.append((hits, index, item["content"]))
    return [content for *_, content in sorted(scored, reverse=True)[:MEMORY_SEARCH_LIMIT]]


# --- Tools -------------------------------------------------------------------------------------


def remember(content: str, category: str = "preference") -> str:
    """Save one memory. Raises ToolError when it holds a secret. Used by tools and auto-save."""
    text = " ".join(content.split())[:MAX_MEMORY_CHARS]
    if not text:
        raise ToolError("What should I remember?")
    if secret_reason(text):
        raise ToolError(REJECTED)
    kind = category if category in CATEGORIES else "preference"
    item = {
        "id": uuid.uuid4().hex,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "category": kind,
        "content": text,
    }
    _save_local(item)
    threading.Thread(target=_put_dynamodb, args=(item,), daemon=True).start()
    started = time.monotonic()
    where = "on this Mac"
    try:
        client = _supermemory()
        if client is not None:
            client.add(
                content=text,
                custom_id=item["id"],
                container_tag=MEMORY_USER_TAG,
                dreaming="instant",
                metadata={"category": kind},
            )
            where = "in memory"
    except Exception as error:  # noqa: BLE001 — the local and DynamoDB copies still hold it
        log.warning("Supermemory add failed (%s)", type(error).__name__)
    log.info("memory_add %s in %d ms", where, round((time.monotonic() - started) * 1000))
    refresh_profile(MEMORY_PROFILE_SETTLE_S)
    return f"Saved {where}: {text}"


@tool
def memory_add(content: str, category: str = "preference") -> str:
    """Remember a fact about the user for later (usual groceries, favourite brands, addresses,
    contacts, routines, and corrections like "I meant Rahul Verma"). Never passwords, OTPs or cards.

    Args:
        content: The fact in one sentence, e.g. "Usual groceries: 2 L Amul milk, 12 eggs".
        category: preference | contact | address | order_history | routine | correction.
    """
    said = remember(content, category)
    events.emit(events.EarconEvent("checkpoint"))
    return said


@tool
def memory_search(query: str) -> str:
    """Look up what Zoya remembers about the user. Call it before asking a preference question.

    Args:
        query: What to look for, e.g. "usual groceries".
    """
    query = " ".join(query.split())
    if not query:
        raise ToolError("What should I look up?")
    found: list[str] = []
    try:
        client = _supermemory()
        if client is not None:
            response = client.search.memories(
                q=query,
                container_tag=MEMORY_USER_TAG,
                limit=MEMORY_SEARCH_LIMIT,
                search_mode="hybrid",
                **_search_options(),
            )
            found = [text for r in response.results if (text := r.memory or r.chunk)]
    except Exception as error:  # noqa: BLE001 — fall back to the copies
        log.warning("Supermemory search failed (%s)", type(error).__name__)
    if not found:
        found = local_matches(query, _read_local() or _query_dynamodb())
    if not found:
        return f"I don't remember anything about {query}."
    return "Memories:\n" + "\n".join(f"- {text}" for text in found)


def recent_corrections(limit: int = 3) -> list[str]:
    """Latest corrections from the local copy (§13.5.6), added to the brain's request. No
    network."""
    return [i["content"] for i in _read_local() if i.get("category") == "correction"][-limit:]


def home_address() -> str:
    """The newest saved address (local copy), for "near me"."""
    return next(
        (i["content"] for i in reversed(_read_local()) if i.get("category") == "address"), ""
    )


# --- The user's profile in the brain's prompt (Phase H) ------------------------------------------

CHARS_PER_TOKEN = 4
PROFILE_HEADING = (
    "About the user (from Zoya's memory; answer from it without memory_search when it is enough):"
)
_profile: dict[str, Any] = {"block": "", "at": 0.0, "fetching": False}
_profile_lock = threading.Lock()


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


def _fetch_profile(delay_s: float) -> None:
    time.sleep(delay_s)
    try:
        client = _supermemory()
        if client is None:
            return
        response = client.profile(container_tag=MEMORY_USER_TAG, timeout=MEMORY_PROFILE_TIMEOUT_S)
        lines = [*(response.profile.static or []), *(response.profile.dynamic or [])]
        with _profile_lock:
            _profile["block"], _profile["at"] = profile_block(lines), time.monotonic()
        log.info("profile: %d lines", len(lines))
    except Exception as error:  # noqa: BLE001 — the brain still has memory_search
        log.warning("Supermemory profile failed (%s)", type(error).__name__)
    finally:
        with _profile_lock:
            _profile["fetching"] = False


def refresh_profile(delay_s: float = 0.0) -> None:
    """Fetch the profile in the background: at session start and after every memory write."""
    with _profile_lock:
        if _profile["fetching"] and not delay_s:
            return
        _profile["fetching"] = True
    threading.Thread(
        target=_fetch_profile, args=(delay_s,), name="zoya-profile", daemon=True
    ).start()


def user_profile() -> str:
    """The cached "About the user" block, never waited on; a stale one is refreshed behind."""
    with _profile_lock:
        block, age = _profile["block"], time.monotonic() - _profile["at"]
    if not _profile["at"] or age > MEMORY_PROFILE_TTL_S:
        refresh_profile()
    return block


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
