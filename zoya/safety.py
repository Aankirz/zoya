"""Safety gate (§9.9, §12, D7): nothing is paid, sent, deleted or submitted without the user's
spoken "confirm".

The model is untrusted (§12.2). So is page and tool text. What enforces this is the code
structure, not the prompt:

- **Risk registry** `TOOL_RISK`: every tool is free, guarded (the tool runs Guard 2 on its real
  target), confirm or blocked. A tool that isn't listed (a future skill or MCP tool) counts as
  **confirm** (fail closed).
- **Guard 1** `ConfirmationGate`: a Strands hook on every tool call (brain and direct
  `agent.tool.X()` calls both run it; strands 1.55.1 tools/executors/_executor.py `_stream`).
  Blocked → cancel. Confirm → the user must confirm by voice first. After a cancel, the task's
  next model call is refused, so a hijacked model can't retry or claim success.
- **Guard 2** `risky_label` + `require_confirmation`: click tools read the label of the element
  they will really click, whatever the model said it was, and call `require_confirmation`
  themselves. So a direct call or the router fast path can't skip it.
- **Tokens** are minted in exactly one place, `_VoiceChannel.reply`, which only the voice loop
  holds (`claim_voice_channel`, once per process). The rules: the reply started after Zoya
  finished speaking the exact summary plus the echo tail (D52); the words are a clear "confirm";
  the token is single use, dies after 60 s, and is bound to the sha256 of the spoken summary. The
  action recomputes its summary from the live page before it acts, so a changed page never
  matches.
- **Tasks (Phase 6, §9.13)**: a confirmation belongs to the task that asked (zoya/tasks.py
  ContextVar). One is pending at a time; a second task waits its turn (`waiting_confirmation`)
  instead of speaking over it. The prompt names the task when others run and waits until the user
  stops talking. A token only works for the task it was minted for; a cancel or stop is per task;
  while any task runs, a confirmation from outside a task is refused (fail closed).

Strands docs: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/
Source checked: strands/hooks/events.py BeforeToolCallEvent.cancel_tool; tools/_caller.py (direct
calls run the same executor and hooks, and cannot raise interrupts).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from strands.hooks import BeforeModelCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from zoya import aws, events, tasks
from zoya.config import (
    CONFIRM_PROMPTS,
    CONFIRM_REPLY_TIMEOUT_S,
    CONFIRM_SPEAK_TIMEOUT_S,
    CONFIRM_TOKEN_TTL_S,
    CONFIRM_TURN_WAIT_S,
    CONFIRMATION_AUDIT_TABLE,
    CONFIRMATION_LOG,
    ECHO_TAIL_S,
    LOG_DIR,
    TIMING_LOG,
    WARNING_EARCON_GAP_S,
)
from zoya.tools import ToolError

log = logging.getLogger(__name__)

RiskClass = Literal["free", "guarded", "confirm", "blocked"]
Reply = Literal["confirm", "cancel", "unclear"]
MS_PER_S = 1000
TURN_POLL_S = 0.05

# --- Risk registry (the harness permission layer) -----------------------------------------------

TOOL_RISK: dict[str, RiskClass] = {
    # T0 tools: reversible, no money, nothing leaves the Mac on the user's behalf (D57).
    "open_app": "free",
    "open_url": "free",
    "media_control": "free",
    "set_volume": "free",
    "volume_up": "free",
    "volume_down": "free",
    "mute": "free",
    "get_time": "free",
    "notes_create": "free",
    "notes_search": "free",
    "notes_append": "free",
    "get_weather": "free",
    "narrate": "free",
    # Phase 4. Reading, searching, remembering and navigating (GET) are free. Every recipe that
    # clicks is guarded: it clicks only through browser.click_checked (Guard 2) or
    # confirm_then_click (always asks). Skill metadata never changes these.
    "web_search": "free",
    "web_fetch": "free",
    "memory_add": "free",  # the secret filter runs inside; nothing leaves on the user's behalf
    "memory_search": "free",
    "nearby_places": "free",
    "handoff_to_user": "free",  # speaks, emails the trusted contact a fixed message, waits
    "skills": "free",  # Strands AgentSkills: returns a SKILL.md body as text
    "browser_screenshot": "free",
    "youtube_search": "free",
    "youtube_open_channel": "free",
    "youtube_play_video": "free",  # search, then navigate to the watch page (GET)
    "youtube_play_latest": "free",  # channel Videos tab, then navigate to the watch page (GET)
    "youtube_subscribe": "guarded",
    "youtube_like": "guarded",
    "youtube_comment": "guarded",
    "x_post": "guarded",  # confirm_then_click with the exact text and count; verified by X's toast
    "spotify_search": "free",
    "spotify_play_song": "guarded",
    "amazon_search": "free",
    "amazon_add_to_cart": "guarded",
    "amazon_buy_now": "guarded",  # the Buy Now form (KNOWN_SAFE_CLICKS), then a no-order check
    "amazon_buy": "guarded",  # search, Buy Now, then amazon_place_order's spoken confirm
    "amazon_cart": "free",
    "amazon_cart_remove": "guarded",  # the cart line's own Delete form only (KNOWN_SAFE_CLICKS)
    "amazon_checkout": "guarded",  # presses the fixed "Proceed to Buy" form; nothing is ordered
    "amazon_place_order": "guarded",
    "hotel_search": "free",  # builds a search URL (GET) and reads the results
    "hotel_book": "guarded",  # opens the hotel, picks a room, known-safe reserve/next clicks only
    "hotel_guest_details": "guarded",  # fill_checked (no secret fields), then the known-safe next
    # Browser: reading and navigating are free; clicks and typing check their real target.
    "browser_open": "free",
    "browser_read": "free",
    "browser_click": "guarded",
    "browser_type": "guarded",
    # Computer use (Phase 5): seeing and reading are free; every input to the Mac checks its target.
    "screenshot": "free",
    "scroll": "free",
    "ax_read": "free",
    "describe_screen": "free",
    "read_screen_text": "free",
    "read_document": "free",
    "list_shortcuts": "free",
    "click": "guarded",
    "type_text": "guarded",
    "key": "guarded",
    "ax_press": "guarded",
    "run_shortcut": "guarded",  # a user's shortcut can do anything: it always asks
    "computer_task": "guarded",  # its own agent runs the gate on every step
    # Phase 6. Documents: files Zoya writes in ~/Documents/Zoya/ and read-backs are free (nothing
    # leaves the Mac); sharing is a SEND and asks out loud inside the action (share.share_file).
    "document_agent": "guarded",  # its own agent runs the gate on every step
    "create_document": "free",
    "create_table": "free",
    "read_file_structure": "free",
    "read_file_part": "free",
    "edit_file_part": "free",  # only files Zoya made (office.zoya_file)
    "open_file": "free",
    "list_files": "free",
    "share_file": "guarded",  # always require_confirmation inside, rebuilt before sending
    "set_reminder": "free",  # speaks later; emails only the owner's own zoya-alerts topic
}
RISK_ORDER: dict[RiskClass, int] = {"free": 0, "guarded": 1, "confirm": 2, "blocked": 3}


def risk_of(tool_name: str) -> RiskClass:
    """Unknown tools (new skills, MCP tools) need confirmation: fail closed."""
    return TOOL_RISK.get(tool_name, "confirm")


# --- Text normalisation: labels and replies must survive look-alike tricks ----------------------

# Letters that look Latin but aren't (Cyrillic, Greek). NFKC already folds fullwidth letters.
CONFUSABLES = str.maketrans(
    "аеорсхуіјѕԁһӏАВЕКМНОРСТХУІЈЅαβεικνορτυχΑΒΕΖΗΙΚΜΝΟΡΤΥΧ",
    "aeopcxyijsdhlABEKMHOPCTXYIJSabeiknoptuxABEZHIKMNOPTYX",
)
LEET = str.maketrans("0134578@$", "oleastbas")
CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
LATIN_END = "\u0250"  # combining marks after these letters are accents
NON_WORD = re.compile(r"[^0-9a-zऀ-ॿ₹]+")


def normalise(text: str) -> str:
    """Casefolded Latin words: fullwidth, look-alike letters and invisible characters removed."""
    folded = unicodedata.normalize("NFKC", text)
    visible = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")  # zero-width etc.
    split = CAMEL_BOUNDARY.sub(
        " ", visible.translate(CONFUSABLES)
    )  # "btnPlaceOrder" → "btn Place Order"
    plain = ""
    for ch in unicodedata.normalize("NFKD", split):
        if unicodedata.combining(ch) and plain and plain[-1] < LATIN_END:
            continue  # "Plàce" → "place"; Devanagari vowel signs are letters, keep them
        plain += ch
    return " ".join(NON_WORD.sub(" ", plain.casefold()).split())


# --- Guard 2: risky click labels -----------------------------------------------------------------

RISKY_PHRASES: tuple[tuple[str, str, str], ...] = (
    # (kind, regex on normalised words, what Zoya says she will click)
    ("purchase", r"place (?:your |the |my )?order", "Place order"),
    ("purchase", r"buy(?: it)?(?: now)?", "Buy"),
    ("purchase", r"pay(?: now)?", "Pay"),
    ("purchase", r"proceed to pay(?:ment)?", "Pay"),
    ("purchase", r"(?:confirm|complete|submit) (?:purchase|order|payment)", "Confirm purchase"),
    ("purchase", r"purchase", "Purchase"),
    ("purchase", r"(?:complete|confirm|finish) (?:your |the |my )?(?:booking|reservation)", "Book"),
    ("purchase", r"book(?: and pay| now)|reserve and pay", "Book"),
    ("purchase", r"transfer(?: money| funds)?", "Transfer"),
    # Hindi (Devanagari) and Hinglish: "ऑर्डर करें", "खरीदें", "भुगतान करें", "order karo".
    (
        "purchase",
        r"ऑर्डर(?: \S+)?|खरीद\S*|भुगतान\S*|पे करें|order kar\w*|kharid\w*|bhugtan\w*|pay kar\w*",
        "Place order",
    ),
    ("checkout", r"checkout|check out|proceed to checkout", "Check out"),
    ("send", r"send(?: message| money)?", "Send"),
    ("send", r"post|publish|भेज\S*|bhej\w*", "Send"),
    (
        "delete",
        r"delete|remove|erase|trash|discard|हटा\S*|मिटा\S*|डिलीट\S*|hata\w*|mita\w*",
        "Delete",
    ),
    ("submit", r"submit|confirm|सबमिट\S*|जमा करें", "Submit"),
    # Phase 4: YouTube's known final buttons publish as the user (Phase 3 residual: list them).
    ("post", r"subscribe|subscribed|unsubscribe|like|comment|reply|सब्सक्राइब\S*", "Post"),
)
_RISKY = [
    (kind, re.compile(rf"(?:^| )(?:{pattern})(?: |$)"), say) for kind, pattern, say in RISKY_PHRASES
]
# Joined words with no case boundary ("buynow", "placeorder"), and letters spaced out ("P l a c e"):
# long phrases only, so "pay" never matches "display" and "delete" never matches "Deleted items".
SQUASHED = (
    ("purchase", "placeorder", "Place order"),
    ("purchase", "placeyourorder", "Place order"),
    ("purchase", "buynow", "Buy"),
    ("purchase", "paynow", "Pay"),
    ("purchase", "confirmpurchase", "Confirm purchase"),
    ("purchase", "submitorder", "Place order"),
    ("purchase", "proceedtopay", "Pay"),
    ("purchase", "completebooking", "Book"),
    ("checkout", "checkout", "Check out"),
    ("send", "sendmessage", "Send"),
    ("send", "sendmoney", "Send"),
)


@dataclass(frozen=True)
class RiskyLabel:
    kind: str  # purchase | send | delete | submit
    say: str  # canonical action name spoken to the user, never raw page text


def risky_label(labels: list[str]) -> RiskyLabel | None:
    """Guard 2: does any label of the real click target mean pay/send/delete/submit?

    Checked on every label source (text, aria-label, value, title), in plain and de-leeted form.
    One signal only: `click_risk` also asks on submit controls, unnamed targets and commerce pages.
    """
    found: list[RiskyLabel] = []
    for raw in labels:
        plain = normalise(raw)
        for variant in (plain, plain.translate(LEET)):
            found += [RiskyLabel(k, say) for k, pattern, say in _RISKY if pattern.search(variant)]
        squashed = plain.replace(" ", "")
        found += [
            RiskyLabel(k, say)
            for k, needle, say in SQUASHED
            if needle in squashed or needle in squashed.translate(LEET)
        ]
    # A purchase wins: "Pay and send" must get the amount check.
    return next((hit for hit in found if hit.kind == "purchase"), found[0] if found else None)


MIN_NAME_CHARS = 2
SPOKEN_NAME_WORDS = 6
COMMERCE_PATH_WORDS = {
    "checkout",
    "cart",
    "basket",
    "payment",
    "payments",
    "pay",
    "buy",
    "order",
    "orders",
    "compose",
    "send",
    "delete",
    "transfer",
    "billing",
}
CURRENCY_AMOUNT = re.compile(r"(?:₹|\brs\.?|\binr\b|\$|€|£)\s*\d|\d\s*(?:rupees|inr)\b", re.I)
ACCESSIBLE_NAME = re.compile(r'^- \w+(?: "(.*)")?', re.S)


@dataclass(frozen=True)
class ClickFacts:
    """What the page says about the element that will really be clicked (Playwright or AX)."""

    labels: list[str]  # text, aria-label, title, value, alt, accessible name
    is_submit: bool = False  # button type=submit / default inside a <form>, input submit/image
    path: str = ""  # URL path (no query: a search for "buy shoes" is not a checkout)
    nearby_text: str = ""  # text around the target (its form or a few ancestors)
    host: str = ""  # page host, for KNOWN_SAFE_CLICKS only
    control_name: str = ""  # the clickable's name attribute, for KNOWN_SAFE_CLICKS only


def spoken_name(labels: list[str]) -> str:
    """The target's own name, normalised and short; "" when it has none (icon-only)."""
    for label in labels:
        name = normalise(label)
        if sum(ch.isalnum() for ch in name) >= MIN_NAME_CHARS:
            return " ".join(name.split()[:SPOKEN_NAME_WORDS])
    return ""


def accessible_name(snapshot: str) -> str:
    """Name from a Playwright aria snapshot line: '- button "Place order"' → 'Place order'."""
    match = ACCESSIBLE_NAME.match(snapshot.strip())
    return (match.group(1) or "") if match else snapshot


# Buttons on shops Zoya automates that never pay, which the context rules would otherwise ask about
# every time (Flow 6 "ticks per item"). (host, allowed names, name-attribute prefix): exact host,
# every label normalises to one of those exact names, and the element's name attribute starts with
# the prefix. "Add to Cart" is reversible (Done-when #4). Amazon's proceed forms only open checkout
# and amazon_checkout verifies no order page came back (coordinator review, gap A). Names as read
# from the owner's cart page, 2026-09-14 (value + accessible name).
# 2026-09-15 (owner-approved, agent-speed probe on the owner's profile): the product page's button
# now also carries "Add to Shopping Cart"; "Buy Now" (name submit.buy-now) only opens checkout for
# that one item, and amazon_buy_now verifies no order page came back, like the proceed forms; a
# cart line's "Delete <title>" (name submit.delete-active.<id>) removes it from the cart only.
# An allowed name ending in " *" matches that prefix followed by any words (the item's title).
KNOWN_SAFE_CLICKS = (
    ("www.amazon.in", frozenset({"add to cart", "add to shopping cart"}), ""),
    ("www.amazon.in", frozenset({"buy now"}), "submit.buy-now"),
    ("www.amazon.in", frozenset({"delete", "delete *"}), "submit.delete-active."),
    (
        "www.amazon.in",
        frozenset({"proceed to checkout", "proceed to buy now items"}),
        "proceedToALMCheckout",
    ),
    (
        "www.amazon.in",
        frozenset({"proceed to checkout", "proceed to buy buy amazon items"}),
        "proceedToRetailCheckout",
    ),
    # Booking.com (hotels_web): the room table's "I'll reserve" and the guest form's "Next: Final
    # details" (name="book") only move to the next form; the final step is payment (blocked below).
    # Labels as read from www.booking.com, 2026-09-15.
    ("www.booking.com", frozenset({"i ll reserve"}), ""),
    ("www.booking.com", frozenset({"next final details"}), "book"),
    ("secure.booking.com", frozenset({"next final details"}), "book"),
)
# Hotel sites where Zoya stops at the payment page: a purchase click there is never asked, only
# refused (owner: "Payment needs you"). Checked before KNOWN_SAFE_CLICKS, by exact host suffix.
PAYMENT_BLOCKED_HOSTS = ("booking.com",)
PAYMENT_BLOCKED_SAY = "I don't make payments or complete bookings. Payment needs you."


def known_safe_click(facts: ClickFacts) -> bool:
    names = {name for label in facts.labels if (name := normalise(label))}
    return bool(names) and any(
        facts.host.casefold() == host
        and all(_allowed_name(name, allowed) for name in names)
        and facts.control_name.startswith(prefix)
        for host, allowed, prefix in KNOWN_SAFE_CLICKS
    )


def _allowed_name(name: str, allowed: frozenset[str]) -> bool:
    return name in allowed or any(
        entry.endswith(" *") and name.startswith(entry[:-1]) for entry in allowed
    )


def payment_blocked_host(host: str) -> bool:
    host = host.casefold()
    return any(host == h or host.endswith(f".{h}") for h in PAYMENT_BLOCKED_HOSTS)


def click_risk(facts: ClickFacts) -> RiskyLabel | None:
    """Guard 2, failing closed: ask unless the click is clearly harmless.

    Asks when ANY holds: a risky label (English, Hindi, Hinglish, camelCase, joined), no usable
    name (icon-only / unknown), a submit control, or a commerce/compose page (URL path words, or
    a currency amount near the target). Coordinator review of cb10192 found the label-only guard
    failing open ("Checkout", "BuyNow", "खरीदें", icon-only).
    ponytail: a JS-handled <div> with a harmless name ("Continue") on a page with no amount and a
    neutral URL still passes. Phase 4 skills must list their known final buttons as risky.
    """
    hit = risky_label(facts.labels)
    if hit and hit.kind == "purchase" and payment_blocked_host(facts.host):
        raise ConfirmationDeclined(PAYMENT_BLOCKED_SAY)
    if known_safe_click(
        facts
    ):  # exact entries only; "Proceed to buy" would otherwise read as risky
        return None
    if hit:
        return hit
    name = spoken_name(facts.labels)
    if not name:
        return RiskyLabel("unknown", "click a button with no name")
    if facts.is_submit:
        return RiskyLabel("submit", f"submit {name}")
    path_words = set(normalise(facts.path).split())
    if path_words & COMMERCE_PATH_WORDS or CURRENCY_AMOUNT.search(facts.nearby_text):
        return RiskyLabel("context", f"click {name}")
    return None


# Native Mac apps (Phase 5): system and data-loss buttons a web page rarely has. Checked before
# click_risk for AX and pixel clicks only, so browser behaviour is unchanged.
NATIVE_RISKY_PHRASES: tuple[tuple[str, str, str], ...] = (
    ("system", r"shut ?down|power off", "Shut down"),
    ("system", r"restart|reboot", "Restart"),
    ("system", r"log ?out|sign ?out|log off", "Log out"),
    ("system", r"(?:force )?quit", "Quit"),
    ("delete", r"don ?t save|do not save|discard changes|revert", "Don't save"),
    ("delete", r"replace|overwrite|reset|format|wipe", "Replace or reset"),
    ("system", r"(?:un)?install|update now", "Install"),
    ("send", r"share|reply|forward|call|facetime", "Share or call"),
    ("submit", r"accept|agree|sign", "Accept"),
)
_NATIVE = [
    (kind, re.compile(rf"(?:^| )(?:{pattern})(?: |$)"), say)
    for kind, pattern, say in NATIVE_RISKY_PHRASES
]


# macOS permission prompts are the owner's to answer (coordinator): blocked, a voice token can't
# unlock them. Any input while a prompt app is in front, or on a control that grants access.
PERMISSION_APPS = {"UserNotificationCenter", "SecurityAgent", "CoreServicesUIAgent"}
PERMISSION_LABEL = re.compile(
    r"(?:^| )(?:(?:always |don t |dont |do not )?allow|grant|authori[sz]e|unlock)(?: |$)"
)
PERMISSION_MESSAGE = "That's a macOS permission prompt. Please answer it yourself; I never do."


def native_input_blocked(labels: list[str], app: str) -> bool:
    """True for a permission prompt or a grant-access control: no input, even with "confirm"."""
    if app in PERMISSION_APPS:
        return True
    return any(PERMISSION_LABEL.search(normalise(label)) for label in labels)


def native_click_risk(facts: ClickFacts) -> RiskyLabel | None:
    """Guard 2 for Mac apps (AX press, pixel click, keys): system actions, then `click_risk`."""
    for raw in facts.labels:
        plain = normalise(raw)
        for kind, pattern, say in _NATIVE:
            if pattern.search(plain) or pattern.search(plain.translate(LEET)):
                return RiskyLabel(kind, say)
    return click_risk(facts)


# --- Money ---------------------------------------------------------------------------------------

AMOUNT = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d{1,2}))?(?![\d,])")
CURRENCY_WORDS = {
    "₹": "rupees",
    "rs": "rupees",
    "inr": "rupees",
    "rupees": "rupees",
    "rupee": "rupees",
    "$": "dollars",
    "usd": "dollars",
}
STRONG_TOTAL = re.compile(
    r"order total|grand total|total amount|amount payable|total payable|you pay|to pay|payable|"
    r"\bpay\s*(?:₹|rs\.?|inr)?\s*\d",  # "Pay ₹2,847", not "Pay in 3 EMIs"
    re.I,
)
WEAK_TOTAL = re.compile(r"\btotal\b", re.I)


def parse_amounts(text: str) -> list[Decimal]:
    """Every money-looking number: "₹2,847.00" → 2847.00, "Rs. 1,23,456" → 123456."""
    values = []
    for whole, cents in AMOUNT.findall(text):
        try:
            values.append(Decimal(whole.replace(",", "") + (f".{cents}" if cents else "")))
        except InvalidOperation:
            continue
    return values


def parse_claimed_amount(text: str) -> tuple[Decimal, str] | None:
    """The amount the agent read, e.g. "₹2,847" → (2847, "rupees"). Exactly one number."""
    values = parse_amounts(text)
    if len(values) != 1:
        return None
    lowered = text.casefold()
    currency = next((word for key, word in CURRENCY_WORDS.items() if key in lowered), "rupees")
    return values[0], currency  # D14: Zoya's shops are ₹ unless a currency is written


def spoken_amount(value: Decimal, currency: str) -> str:
    number = f"{value:,.2f}".removesuffix(".00")
    return f"{number} {currency}"


@dataclass(frozen=True)
class OcrRow:
    """One visual row of OCR text and its vertical extent in the captured image (0..1)."""

    text: str
    top: float = 0.0
    bottom: float = 0.0


def ocr_rows(lines: list[tuple[str, float, float, float]]) -> list[OcrRow]:
    """Join OCR lines on the same visual row (text, left, top, height), left to right.

    "Order total" and its right-aligned "₹2,847" come back from Rekognition as two lines.
    """
    rows: list[list[tuple[str, float, float, float]]] = []
    for line in sorted(lines, key=lambda item: item[2]):
        centre = line[2] + line[3] / 2
        for row in rows:
            ref = row[0]
            if abs(ref[2] + ref[3] / 2 - centre) < max(ref[3], line[3]) / 2:
                row.append(line)
                break
        else:
            rows.append([line])
    return [
        OcrRow(
            " ".join(item[0] for item in sorted(row, key=lambda item: item[1])),
            min(item[2] for item in row),
            max(item[2] + item[3] for item in row),
        )
        for row in rows
    ]


def rows_from_ocr(lines: list[tuple[str, float, float, float]]) -> list[str]:
    return [row.text for row in ocr_rows(lines)]


@dataclass(frozen=True)
class StruckPrice:
    """A visible struck-out price ("M.R.P. ~~₹331~~"), placed in the captured window (0..1)."""

    amount: Decimal
    top: float
    bottom: float


def struck_prices(dom: dict[str, Any]) -> list[StruckPrice]:
    """Parser for browser.STRUCK_JS (page data, untrusted): keep only elements that are rendered
    (checkVisibility, non-zero size, inside the viewport), have line-through on themselves, and hold
    exactly one amount. Maps viewport pixels to the window capture: Chrome's toolbar is the
    outer-minus-inner height above the viewport."""
    if not isinstance(dom, dict):
        return []
    outer, inner, width = (float(dom.get(k) or 0) for k in ("outer", "inner", "width"))
    if outer <= 0 or not 0 < inner <= outer:
        return []
    found = []
    for item in dom.get("items") or []:
        box = [float(item.get(k) or 0) for k in ("top", "bottom", "left", "right")]
        rendered = item.get("visible") is True and item.get("lineThrough") is True
        on_screen = 0 <= box[0] < box[1] <= inner and 0 <= box[2] < box[3] <= width
        values = parse_amounts(str(item.get("text", "")))
        if rendered and on_screen and len(values) == 1:
            chrome = outer - inner
            found.append(
                StruckPrice(values[0], (chrome + box[0]) / outer, (chrome + box[1]) / outer)
            )
    return found


AMBIGUOUS = Decimal(-1)  # never equals an amount the agent can claim
# A struck price is an old price only if the kept one is a plausible discount of it (≤ 80% off):
# "Order total ₹1 ~~₹2,847~~" is a mismatch (coordinator re-attack of 0a83a3d).
MIN_KEPT_FRACTION = Decimal("0.2")


@dataclass(frozen=True)
class TotalCheck:
    ok: bool
    dropped: tuple[Decimal, ...] = ()  # struck-out prices ignored, for the audit row


def _row_total(row: OcrRow, struck: list[StruckPrice]) -> tuple[Decimal | None, Decimal | None]:
    """(total, dropped struck price). A struck price counts only if it overlaps this row, is one
    of the row's numbers, is the only one, and is higher than what's left but by at most 80%."""
    values = parse_amounts(row.text)
    if not values:
        return None, None
    on_row = {p.amount for p in struck if p.top < row.bottom and p.bottom > row.top}
    old = on_row & set(values)
    if not old:
        return max(values), None
    if len(old) > 1:
        return AMBIGUOUS, None
    price = old.pop()
    kept = list(values)
    kept.remove(price)
    if not kept or price <= max(kept) or max(kept) < price * MIN_KEPT_FRACTION:
        return AMBIGUOUS, None
    return max(kept), price


def check_total(claimed: Decimal, rows: list[OcrRow], struck: list[StruckPrice]) -> TotalCheck:
    """The agent's amount must be THE total the screen shows (independent OCR, not page DOM).

    Every strong row ("order total", "pay ₹…", "payable") must show exactly the claimed amount:
    an injected second total disagreeing with the real one is a mismatch (coordinator review).
    With no strong row, the largest plain "total" must be it ("Items total" is a subtotal).
    No total at all → mismatch → never confirm. Struck-out prices: `_row_total` (Amazon Now shows
    "You pay ₹243 ~~₹331~~" on one row and OCR can't see the line; coordinator review of f283fbc).
    ponytail: a row's largest number is its total ("Order total ₹2,847 incl. ₹48 delivery").
    """
    for pattern in (STRONG_TOTAL, WEAK_TOTAL):
        found = [
            total_and_drop
            for row in rows
            if pattern.search(row.text)
            if (total_and_drop := _row_total(row, struck))[0] is not None
        ]
        if not found:
            continue
        totals = [total for total, _ in found]
        dropped = tuple(drop for _, drop in found if drop is not None)
        if AMBIGUOUS in totals:
            return TotalCheck(False, dropped)
        ok = (
            all(t == claimed for t in totals) if pattern is STRONG_TOTAL else max(totals) == claimed
        )
        return TotalCheck(ok, dropped)
    return TotalCheck(False)


def amount_on_screen(claimed: Decimal, rows: list[str]) -> bool:
    """`check_total` on plain OCR rows with no struck prices (native apps, tests)."""
    return check_total(claimed, [OcrRow(row) for row in rows], []).ok


MIN_TARGET_WORD_CHARS = 3
TARGET_WORDS_ON_SCREEN = 0.6


def target_on_screen(target: str, rows: list[str]) -> bool:
    """Most words of the item/recipient the agent named are visible on screen."""
    wanted = [w for w in normalise(target).split() if len(w) >= MIN_TARGET_WORD_CHARS]
    if not wanted:
        return False
    seen = set(normalise(" ".join(rows)).split())
    return sum(w in seen for w in wanted) / len(wanted) >= TARGET_WORDS_ON_SCREEN


# --- Replies -------------------------------------------------------------------------------------

DEVANAGARI_WORDS = {
    "कन्फर्म": "confirm",
    "कंफर्म": "confirm",
    "हाँ": "haan",
    "हां": "haan",
    "हा": "haan",
    "नहीं": "nahi",
    "नही": "nahi",
    "कैंसल": "cancel",
    "कैन्सल": "cancel",
    "रुको": "ruko",
    "मत": "mat",
    "करो": "karo",
}
_DEVANAGARI = {normalise(key): value for key, value in DEVANAGARI_WORDS.items()}
CONFIRM_WORDS = {"confirm", "confirmed"}
NEGATIVE_WORDS = {
    "no",
    "cannot",
    "can",  # "I can't confirm" → "can", "t": a negation must never read as yes
    "won",
    "wont",
    "not",
    "don",
    "dont",
    "never",
    "nope",
    "nahi",
    "nahin",
    "na",
    "mat",
    "cancel",
    "cancelled",
    "stop",
    "wait",
    "ruko",
    "ruk",
    "bas",
    "abort",
    "hold",
}
# Words allowed next to "confirm": "haan confirm", "yes, confirm it", "Zoya, confirm karo".
CONFIRM_FILLERS = {
    "yes",
    "yeah",
    "haan",
    "han",
    "ha",
    "ji",
    "ok",
    "okay",
    "i",
    "it",
    "please",
    "zoya",
    "karo",
    "kar",
    "do",
    "go",
    "ahead",
    "order",
}


def classify_reply(text: str) -> Reply:
    """Only a clear, short "confirm" is yes. Any negation cancels. Everything else is unclear.

    "yes" alone, "okay", noise, "confirm the other one" → unclear (re-prompt, never yes).
    """
    spoken = [_DEVANAGARI.get(word, word) for word in normalise(text).split()]
    if any(word in NEGATIVE_WORDS for word in spoken):
        return "cancel"
    if not any(word in CONFIRM_WORDS for word in spoken):
        return "unclear"
    if all(word in CONFIRM_WORDS or word in CONFIRM_FILLERS for word in spoken):
        return "confirm"
    return "unclear"


# --- Untrusted content and secrets (§12.1, §12.2) ---------------------------------------------

UNTRUSTED_TAG = re.compile(r"<\s*/?\s*untrusted_content\s*>", re.I)


def wrap_untrusted(text: str) -> str:
    """Page/screen text as data. A page can't close the tag early to smuggle in instructions."""
    return f"<untrusted_content>\n{UNTRUSTED_TAG.sub('[tag removed]', text)}\n</untrusted_content>"


SECRET_FIELD = re.compile(
    r"pass(?:word|code|wd)?|\botp\b|one.?time|\bcvv\b|\bcvc\b|\bpin\b(?!\s*code)|"
    r"card.?number|cc-(?:number|csc|exp)|security.?code|verification.?code",
    re.I,
)
CARD_OR_LONG_NUMBER = re.compile(r"(?:\d[ -]?){8,}\d")
SECRET_VALUE = re.compile(r"\b(otp|password|passcode|pin|cvv)\b(\W*)\S+", re.I)


def is_secret_field(
    input_type: str = "", autocomplete: str = "", name: str = "", ax_subrole: str = ""
) -> bool:
    """Password/OTP/card fields: Zoya never types into them and hands off to the user (§12.1)."""
    if ax_subrole == "AXSecureTextField" or input_type.casefold() == "password":
        return True
    return bool(SECRET_FIELD.search(f"{autocomplete} {name}"))


def redact(text: str) -> str:
    """Audit/log text: never card numbers, OTPs or passwords (AGENTS.md §6)."""
    return SECRET_VALUE.sub(r"\1\2[redacted]", CARD_OR_LONG_NUMBER.sub("[redacted]", text))


# --- Tokens and the voice channel --------------------------------------------------------------


@dataclass(frozen=True)
class Action:
    """What will happen, in the words Zoya speaks. Build it from the live page, not the model."""

    kind: str  # purchase | send | delete | submit | tool
    say: str  # "Place order"
    target: str = ""  # item / recipient / file, verified on screen where possible
    amount: str = ""  # "2,847 rupees", verified on screen for purchases
    note: str = ""  # audit only, never spoken: e.g. a struck-out price the total check skipped

    def summary(self) -> str:
        parts = [f"I'm about to {self.say.lower()}"]
        if self.target:
            parts.append(f"{SUMMARY_CONNECTOR.get(self.kind, 'on')} {self.target}".strip())
        if self.amount:
            parts.append(f"total {self.amount}")
        return " ".join(parts) + "."


SUMMARY_CONNECTOR = {"purchase": "for", "send": "to", "delete": "", "tool": "", "post": ""}


def summary_hash(summary: str) -> str:
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Token:
    summary_hash: str
    issued_at: float
    task_id: str  # the task whose confirmation minted it; useless to any other task


@dataclass
class _Pending:
    summary: str
    task_id: str = ""
    task_name: str = ""  # spoken before the summary when other tasks run ("Grocery order: …")
    spoken_hash: str = ""  # hash of the summary as it was actually spoken
    window_opened_at: float | None = None  # replies must start after this
    reply: Reply | None = None
    token_id: str | None = None
    stopped: bool = False
    answered: threading.Event | None = None


class ConfirmationDeclined(Exception):
    """The user cancelled, said stop, stayed silent, or the page changed. The task must end."""


_lock = threading.Lock()
_tokens: dict[str, _Token] = {}
_pending: _Pending | None = None
_channel: _VoiceChannel | None = None
_declined: set[str] = set()  # task ids whose confirmation was declined: no more model calls
_task_id = ""  # the task outside a Task Manager task (tests, direct handle_command calls)
_now: Callable[[], float] = time.monotonic


class _VoiceChannel:
    """The voice loop's handle. `reply` is the only code that mints a token."""

    def reply(self, text: str, heard_from: float) -> bool:
        """Hand a transcribed user utterance to a waiting confirmation. True if it was consumed.

        `heard_from`: monotonic time the utterance started (its first voiced block).
        """
        with _lock:
            pending = _pending
            if self is not _channel or pending is None or pending.answered is None:
                return False
            if pending.window_opened_at is None or heard_from < pending.window_opened_at:
                return False  # started while Zoya was still speaking: maybe her own echo (D52)
            if _speaking():
                return False
            if not normalise(text):
                return True  # junk the transcriber dropped: not an answer, silence keeps counting
            verdict = classify_reply(text)
            pending.reply = verdict
            if verdict == "confirm" and pending.spoken_hash == summary_hash(pending.summary):
                token_id = secrets.token_hex(16)
                _tokens[token_id] = _Token(pending.spoken_hash, _now(), pending.task_id)
                pending.token_id = token_id
            pending.answered.set()
        return True


def claim_voice_channel() -> _VoiceChannel:
    """Called once by the voice loop at startup. A second claim is a bug or an attack."""
    global _channel
    with _lock:
        if _channel is not None:
            raise RuntimeError("the voice channel is already claimed")
        _channel = _VoiceChannel()
        return _channel


def awaiting_reply() -> bool:
    """True while a spoken summary is waiting for "confirm" / "cancel" (voice loop hook)."""
    with _lock:
        return _pending is not None and _pending.window_opened_at is not None


def consume_token(token_id: str | None, summary: str) -> bool:
    """Single use (removed on first look), ≤ 60 s old, bound to exactly this summary and task."""
    with _lock:
        token = _tokens.pop(token_id or "", None)
    if token is None or _now() - token.issued_at > CONFIRM_TOKEN_TTL_S:
        return False
    if not secrets.compare_digest(token.task_id, current_task_id()):
        return False
    return secrets.compare_digest(token.summary_hash, summary_hash(summary))


def current_task_id() -> str:
    task = tasks.current()
    return task.id if task is not None else _task_id


def begin_task(task_id: str) -> None:
    """A new user command: forget this task's cancel, drop its leftover tokens. Other running
    tasks keep theirs."""
    global _task_id
    with _lock:
        if tasks.current() is None:
            _task_id = task_id
        key = current_task_id()
        _declined.discard(key)
        for token_id in [i for i, token in _tokens.items() if token.task_id == key]:
            del _tokens[token_id]


def task_declined() -> bool:
    return current_task_id() in _declined


def pending_task_id() -> str | None:
    """The task whose confirmation holds the floor, or None."""
    with _lock:
        return _pending.task_id if _pending is not None else None


def cancel_pending(task_id: str | None = None) -> None:
    """A waiting confirmation ends now with no token. `task_id` given ("stop the presentation"):
    only if that task's confirmation is the one waiting; another task's is never touched."""
    with _lock:
        if _pending is None or _pending.answered is None:
            return
        if task_id is not None and _pending.task_id != task_id:
            return
        _pending.stopped = True
        _pending.token_id = None
        _pending.answered.set()


def _speaking() -> bool:
    from zoya import speech

    return speech.is_speaking()


# --- The confirmation dialogue ---------------------------------------------------------------

NO_VOICE_MESSAGE = "I can only do that when you confirm by voice."
BUSY_MESSAGE = "I'm already waiting for your answer on something else."
NO_TASK_MESSAGE = "I can't tell which task this confirmation is for, so I didn't ask."
ALREADY_DECLINED = "The user cancelled this action. Do not try again; tell them nothing happened."
CANCELLED_SAY = "Cancelled. Nothing was done."
TIMEOUT_SAY = "I didn't hear confirm, so I cancelled. Nothing was done."
STOPPED_TO_MODEL = "Stopped by the user. Nothing was done."
CHANGED_SAY = "The page changed while I was asking, so I cancelled. Nothing was done."
ASK_SUFFIX = " Say confirm, or cancel."
REPROMPT_PREFIX = "I need a clear answer. "


def require_confirmation(action: Action, current: Callable[[], Action] | None = None) -> None:
    """Block until the user confirms `action` by voice, or raise.

    `current` rebuilds the action from the live page right before acting; its summary must hash
    to the token's. Raises ToolError (fixable: no voice, busy) or ConfirmationDeclined (the task
    ends: cancel, silence, stop, page changed). Returning means: act now, exactly once.
    """
    if task_declined():
        raise ConfirmationDeclined(ALREADY_DECLINED)
    if _channel is None:
        raise ToolError(NO_VOICE_MESSAGE)
    if tasks.current() is None and tasks.running():
        raise ToolError(NO_TASK_MESSAGE)  # can't tell which task is asking: never guess
    pending = _open(action.summary())
    started = _now()
    try:
        token_id, outcome = _ask(pending)
        if token_id is None:
            _decline(action, outcome)
        try:
            live = current() if current else action
        except ToolError:
            live = None  # the page can no longer be verified: same as changed
        if live is None or not consume_token(token_id, live.summary()):
            _decline(action, "changed")
        _audit(action, "confirmed")
        events.emit(events.ConfirmationEvent(current_task_id(), action.summary(), "confirm"))
    finally:
        _close(pending)
        _log_timing({"event": "confirmation", "wait_ms": round((_now() - started) * MS_PER_S)})


def _open(summary: str) -> _Pending:
    """Claim the one confirmation slot. Inside a task, wait (bounded, stoppable) while another
    task's confirmation holds it; outside a task, busy is an error as before."""
    task = tasks.current()
    deadline = _now() + CONFIRM_TURN_WAIT_S
    waited = False
    try:
        while True:
            claimed = _try_open(summary, task)
            if claimed is not None:
                return claimed
            if task is None or _now() > deadline:
                raise ToolError(BUSY_MESSAGE)
            if task.cancel.is_set():
                raise ConfirmationDeclined(STOPPED_TO_MODEL)
            if not waited:
                tasks.set_status("waiting_confirmation", task)
                waited = True
            time.sleep(TURN_POLL_S)
    finally:
        if waited:
            tasks.set_status("running", task)


def _try_open(summary: str, task: tasks.Task | None) -> _Pending | None:
    global _pending
    with _lock:
        if _pending is not None:
            return None
        _pending = _Pending(
            summary,
            task_id=current_task_id(),
            task_name=task.spoken_name() if task is not None and task.shared else "",
            answered=threading.Event(),
        )
        return _pending


def _close(pending: _Pending) -> None:
    global _pending
    with _lock:
        if _pending is pending:
            _pending = None
        if pending.token_id:
            _tokens.pop(pending.token_id, None)  # an unconsumed token never outlives its dialogue


def _ask(pending: _Pending) -> tuple[str | None, str]:
    """warning ×2 → summary → wait 20 s; unclear or silent → once more → auto-cancel."""
    events.emit(events.ConfirmationEvent(pending.task_id, pending.summary, "pending"))
    task = tasks.current()
    tasks.mark_active(task)
    name = f"{pending.task_name}: " if pending.task_name else ""
    for attempt in range(CONFIRM_PROMPTS):
        prompt = name + ("" if attempt == 0 else REPROMPT_PREFIX) + pending.summary + ASK_SUFFIX
        with _lock:
            pending.window_opened_at, pending.reply = None, None
            pending.answered.clear()
        # §9.13: never over the user. Silence while they talk isn't consent: it's not asked yet.
        if not tasks.wait_for_turn(pending.task_id, lambda: pending.stopped, CONFIRM_TURN_WAIT_S):
            return None, "stop" if pending.stopped else "timeout"
        if not _speak_prompt(prompt) or pending.stopped:
            return None, "stop"
        with _lock:
            pending.spoken_hash = summary_hash(pending.summary)
            pending.window_opened_at = _now() + ECHO_TAIL_S
        pending.answered.wait(CONFIRM_REPLY_TIMEOUT_S + ECHO_TAIL_S)
        if pending.stopped:
            return None, "stop"
        if pending.token_id:
            return pending.token_id, "confirm"
        if pending.reply == "cancel":
            return None, "cancel"
    return None, "timeout"


def _speak_prompt(prompt: str) -> bool:
    """Two warning tones, then the summary. False if speech was cut off (stop)."""
    from zoya import audio, speech

    audio.earcon("warning")
    time.sleep(WARNING_EARCON_GAP_S)
    audio.earcon("warning")
    time.sleep(WARNING_EARCON_GAP_S)
    return speech.say_and_wait(prompt, CONFIRM_SPEAK_TIMEOUT_S)


def _decline(action: Action, outcome: str) -> None:
    """Every "no" path: cancel earcon, say what happened, audit, end the task."""
    from zoya import audio

    _declined.add(current_task_id())
    _audit(action, outcome)
    decision = "timeout" if outcome == "timeout" else "cancel"
    events.emit(events.ConfirmationEvent(current_task_id(), action.summary(), decision))
    if outcome == "stop":
        raise ConfirmationDeclined(STOPPED_TO_MODEL)  # the stop path already played its earcon
    audio.earcon("cancel")
    said = {"timeout": TIMEOUT_SAY, "changed": CHANGED_SAY}.get(outcome, CANCELLED_SAY)
    tasks.say(said)  # alone: spoken now; beside other tasks: named, after the user stops talking
    raise ConfirmationDeclined(said)


# --- Guard 1: the Strands hook -----------------------------------------------------------------

BLOCKED_MESSAGE = "This action is blocked for safety."


class ConfirmationGate(HookProvider):
    """Register LAST on every Agent that has tools: it sees the final tool_use other hooks leave.

    Guarded tools enforce Guard 2 themselves; confirm-class and unknown tools are confirmed here.
    """

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(BeforeModelCallEvent, self.before_model)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        names = {str(event.tool_use.get("name", ""))}
        if event.selected_tool is not None:
            names.add(event.selected_tool.tool_name)
        risk = max((risk_of(name) for name in names), key=RISK_ORDER.__getitem__)
        if task_declined():
            event.cancel_tool = ALREADY_DECLINED
        elif risk == "blocked":
            event.cancel_tool = BLOCKED_MESSAGE
        elif risk == "confirm":
            tool = " ".join(sorted(names)).replace("_", " ")
            try:
                require_confirmation(Action("tool", f"use the tool {tool}"))
            except (ToolError, ConfirmationDeclined) as refused:
                event.cancel_tool = str(refused)

    def before_model(self, _event: BeforeModelCallEvent) -> None:
        if task_declined():
            raise ConfirmationDeclined(ALREADY_DECLINED)


def fast_tool_allowed(tool_name: str) -> bool:
    """The router's fast path calls tools without an Agent: only free tools may go that way."""
    return risk_of(tool_name) == "free"


# --- Audit log (DynamoDB zoya-confirmations + local copy) -----------------------------------------


def _audit(action: Action, decision: str) -> None:
    item = {
        "confirmation_id": uuid.uuid4().hex,
        "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "task_id": current_task_id(),
        "action": redact(action.say),
        "amount": redact(action.amount),
        "recipient_or_item": redact(action.target),
        "note": redact(action.note),
        "decision": decision,  # confirmed | cancel | timeout | stop | changed
    }
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with CONFIRMATION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    except OSError as error:
        log.warning("local confirmation log failed (%s)", type(error).__name__)
    threading.Thread(target=_put_audit, args=(item,), daemon=True).start()


def audit_event(action: Action, decision: str) -> None:
    """An audit row outside a confirmation dialogue (e.g. "unexpected order placed")."""
    _audit(action, decision)


def _put_audit(item: dict[str, str]) -> None:
    try:
        dynamodb = aws.client("dynamodb")
        if dynamodb is None:
            return
        dynamodb.put_item(
            TableName=CONFIRMATION_AUDIT_TABLE,
            Item={key: {"S": value} for key, value in item.items() if value},
        )
    except Exception as error:  # noqa: BLE001 — the local copy already has it
        log.warning("DynamoDB confirmation audit failed (%s)", aws._reason(error))


def _log_timing(record: dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        line = {
            "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "safety": True,
            **record,
        }
        with TIMING_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
    except OSError:
        pass


def log_safety_timing(**record: Any) -> None:
    """Per-stage latency on the confirmation path (§13.5): capture, OCR, probe."""
    _log_timing(record)


def _reset_for_tests() -> None:
    global _pending, _channel, _task_id, _now
    with _lock:
        _tokens.clear()
        _declined.clear()
        _pending, _channel, _task_id, _now = None, None, "", time.monotonic
