"""Memory (§9.8, D8, D22): Supermemory, a local copy and a DynamoDB copy, and a secret filter.

- `memory_add` rejects card numbers, OTPs, passwords, PINs and CVVs before anything leaves the Mac
  (§9.8 privacy, §12.3). The filter is the only gate: the model is told, but not trusted.
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
import uuid
from datetime import UTC, datetime
from functools import cache
from typing import Any

from strands import tool

from zoya import aws, events
from zoya.config import (
    MEMORY_LOCAL_FILE,
    MEMORY_SEARCH_LIMIT,
    MEMORY_TABLE,
    MEMORY_TIMEOUT_S,
    MEMORY_USER_TAG,
)
from zoya.tools import ToolError

log = logging.getLogger(__name__)

CATEGORIES = {"preference", "contact", "address", "order_history", "routine", "correction"}
MAX_MEMORY_CHARS = 1000
LOCAL_MAX_ITEMS = 500
MIN_WORD_CHARS = 3
REJECTED = "I can't remember that: it looks like a card number, password or one-time code."

# --- Secret filter (tests/test_memory_filter.py) --------------------------------------------

CARD_DIGITS = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
SECRET_WORD = re.compile(
    r"\b(?:otp|one[- ]?time (?:password|code|pin)|verification code|security code|"
    r"auth(?:entication)? code|passcode|password|passwd|pass ?word|cvv|cvc|cvv2|upi pin|atm pin|"
    r"card pin|mpin|"
    r"netbanking|net banking|pin(?! ?code))\b",
    re.I,
)
SPELLED_DIGITS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine)(?:[\s,-]+(?:zero|one|two|three|four|"
    r"five|six|seven|eight|nine)){3,}\b",
    re.I,
)
CARD_WORDS = re.compile(r"\b(?:card|debit|credit|visa|mastercard|rupay|amex)\b", re.I)
SHORT_NUMBER = re.compile(r"(?<!\d)\d{3,8}(?!\d)")
EXPIRY = re.compile(r"(?<!\d)(?:0[1-9]|1[0-2])\s*/\s*\d{2}(?:\d{2})?(?!\d)")


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char) * (2 if index % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def secret_reason(text: str) -> str | None:
    """Why `text` must never be stored, or None. Errs toward refusing (a lost memory is cheap).

    Blocks: a Luhn-valid 13–19 digit number; any secret word (OTP, password, PIN but not "pin code",
    CVV, net banking); card words with a short number or an expiry date; 4+ spelled-out digits.
    """
    for match in CARD_DIGITS.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "card number"
    if SECRET_WORD.search(text):
        return "secret word"
    if CARD_WORDS.search(text) and (SHORT_NUMBER.search(text) or EXPIRY.search(text)):
        return "card details"
    if SPELLED_DIGITS.search(text):
        return "spelled-out code"
    return None


# --- Stores ------------------------------------------------------------------------------------

_local_lock = threading.Lock()


@cache
def _supermemory() -> Any | None:
    key = os.environ.get("SUPERMEMORY_API_KEY")
    if not key:
        return None
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
        pk = f"{'order' if item['category'] == 'order_history' else 'memory'}#{MEMORY_USER_TAG}"
        dynamodb.put_item(
            TableName=MEMORY_TABLE,
            Item={"pk": {"S": pk}, "sk": {"S": f"{item['at']}#{item['id']}"}}
            | {key: {"S": value} for key, value in item.items()},
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
                container_tag=MEMORY_USER_TAG,
                dreaming="instant",
                metadata={"category": kind},
            )
            where = "in memory"
    except Exception as error:  # noqa: BLE001 — the local and DynamoDB copies still hold it
        log.warning("Supermemory add failed (%s)", type(error).__name__)
    log.info("memory_add %s in %d ms", where, round((time.monotonic() - started) * 1000))
    events.emit(events.EarconEvent("checkpoint"))
    return f"Saved {where}: {text}"


@tool
def memory_add(content: str, category: str = "preference") -> str:
    """Remember a fact about the user for later (usual groceries, favourite brands, addresses,
    contacts, routines, and corrections like "I meant Rahul Verma"). Never passwords, OTPs or cards.

    Args:
        content: The fact in one sentence, e.g. "Usual groceries: 2 L Amul milk, 12 eggs".
        category: preference | contact | address | order_history | routine | correction.
    """
    return remember(content, category)


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


TOOLS = [memory_add, memory_search]
