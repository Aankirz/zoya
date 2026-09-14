"""Hotel booking on Booking.com up to the payment page, then stop (owner's demo flow).

MakeMyTrip was the first choice, but its Akamai bot manager serves a 6-byte "200-OK" page to
Zoya's Playwright Chrome from the second page load on; the owner declined evasion switches
(docs/AUDIT.md). Booking.com loads normally with browser.py's launch (3/3 consecutive searches).

Checked live on www.booking.com, 2026-09-15 (logged out):
- Search URL `searchresults.html?ss=<free text>&checkin=YYYY-MM-DD&checkout=…&group_adults=N&
  no_rooms=N&group_children=N&selected_currency=INR`; `ss` takes "MG Road, Bangalore" as is.
- Cards `[data-testid=property-card]` with `title`, `title-link`, `address-link`, `review-score`,
  `price-and-discounted-price` (whole stay), `taxes-and-charges`, `price-for-x-nights`.
- Hotel page `#hprt-table tbody tr`: `.hprt-roomtype-icon-link` (room name, first row of a type),
  "Max persons: N", "Price ₹ X", "+₹ Y taxes and charges", cancellation lines,
  `select[name^=nr_rooms_]`; `.js-reservation-button` "I'll reserve".
- Guest form: `input[name=firstname|lastname|email|phoneNumber]`, `button[name=book]`
  "Next: Final details". The final step (payment) was NOT inspected by the builder: the sandbox
  refused to submit a form with placeholder details, so its markers below are verified in the
  owner's live run.

Safety: every click goes through `browser.click_checked`. The reserve and next buttons are exact
`safety.KNOWN_SAFE_CLICKS`; any purchase label on booking.com (Pay, Book now, Complete booking)
raises `ConfirmationDeclined` in `safety.click_risk`, so Zoya can't pay even if a model asks.
"""

from __future__ import annotations

import contextlib
import difflib
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode

from strands import tool

from zoya import safety, tasks
from zoya.tools import ToolError, browser
from zoya.tools.handoff import handoff_to_user

from . import slots

HOST = "www.booking.com"
SEARCH = f"https://{HOST}/searchresults.html"
WAIT_MS = 15000
TOP_N = 3
MAX_CARDS = 25
MAX_ROOM_ROWS = 40
PAGE_SETTLE_MS = 1500
PAYMENT_WAIT_S = 20.0
POLL_S = 0.5
CARD = "[data-testid=property-card]"
ROOM_ROW = "#hprt-table tbody tr"
ROOM_NAME = ".hprt-roomtype-icon-link"
ROOM_SELECT = "select[name^=nr_rooms_]"
RESERVE = ".js-reservation-button"
GUEST_FIELDS = {"first name": "firstname", "last name": "lastname", "email": "email"}
PHONE_FIELD = "phoneNumber"
NEXT = "button[name=book]"
AMOUNT = re.compile(r"₹\s*([\d,]+)")
MAX_PERSONS = re.compile(r"Max(?:imum)? (?:persons|occupancy|guests):?\s*(\d+)", re.I)
# Occupancy in the room select's name, "nr_rooms_<room>_<rate>_<persons>_…": matched "Max persons"
# text on the Hyatt Centric MG Road page; some pages show persons only as icons.
SELECT_PERSONS = re.compile(r"^nr_rooms_\d+_\d+_(\d+)_")
ROW_PRICE = re.compile(r"Price\s*₹\s*([\d,]+)", re.I)
ROW_TAXES = re.compile(r"\+\s*₹\s*([\d,]+)\s*taxes", re.I)
CANCELLATION = re.compile(r"(?:free cancellation[^\n|]*|non-refundable|partially refundable)", re.I)
# Final step markers (owner's live run confirms): Booking.com's payment component or its copy.
PAYMENT_FRAME = "iframe[src*=payment i], iframe[title*=payment i], iframe[name*=payment i]"
PAYMENT_TEXT = re.compile(
    r"how do you want to pay|payment details|card number|pay (?:now|online)|complete booking", re.I
)
TOTAL = re.compile(r"(?:total|price)\s*(?:\(incl[^)]*\))?\s*₹\s*([\d,]+)", re.I)
ORDINALS = {"first": 1, "second": 2, "third": 3, "1st": 1, "2nd": 2, "3rd": 3, "last": TOP_N}
MAKEMYTRIP = re.compile(r"make\s*my\s*trip|mmt", re.I)
MAKEMYTRIP_SAY = "MakeMyTrip is blocking automated browsing, I'll use Booking.com instead."
GUEST_SAY = (
    "Booking.com needs the main guest's name, email and phone number, and they aren't saved. "
    "Please tell me them, or sign in to Booking.com in Zoya's browser and say done."
)


@dataclass(frozen=True)
class Hotel:
    name: str
    area: str
    rating: str
    stay_price: int  # whole stay, before taxes
    taxes: int
    href: str

    def per_night(self, nights: int) -> int:
        return round((self.stay_price + self.taxes) / max(nights, 1))


@dataclass(frozen=True)
class Room:
    name: str
    max_persons: int
    price: int
    taxes: int
    cancellation: str
    index: int  # nth ROOM_ROW


_state: dict[str, Any] = {"request": None, "hotels": [], "room": None, "hotel": None}


def rupees(value: int) -> str:
    return f"₹{value:,}"


def search_url(req: slots.HotelRequest) -> str:
    """URL template (tests/test_hotel_slots.py)."""
    place = f"{req.area}, {req.city}" if req.area else req.city
    query = {
        "ss": place,
        "checkin": req.check_in.isoformat(),
        "checkout": req.check_out.isoformat(),
        "group_adults": req.adults,
        "no_rooms": req.rooms,
        "group_children": req.children,
        "selected_currency": "INR",
    }
    return f"{SEARCH}?{urlencode(query)}"


def _amount(text: str) -> int:
    found = AMOUNT.search(text or "")
    return int(found[1].replace(",", "")) if found else 0


def _field(card: Any, testid: str) -> str:
    part = card.locator(f"[data-testid={testid}]")
    return " ".join(part.first.inner_text().split()) if part.count() else ""


def _read_hotels(page: Any) -> list[Hotel]:
    page.locator(CARD).first.wait_for(timeout=WAIT_MS)
    hotels = []
    for card in page.locator(CARD).all()[:MAX_CARDS]:
        link = card.locator("[data-testid=title-link]")
        score = re.search(r"Scored ([\d.]+)", _field(card, "review-score"))
        hotels.append(
            Hotel(
                name=_field(card, "title"),
                area=_field(card, "address-link"),
                rating=score[1] if score else "",
                stay_price=_amount(_field(card, "price-and-discounted-price")),
                taxes=_amount(_field(card, "taxes-and-charges")),
                href=(link.first.get_attribute("href") or "") if link.count() else "",
            )
        )
    return [h for h in hotels if h.name and h.stay_price and h.href.startswith(f"https://{HOST}/")]


def within_budget(hotels: list[Hotel], req: slots.HotelRequest) -> list[Hotel]:
    """Decision (tests): hotels whose price per night with taxes fits the budget (0 = any)."""
    if not req.budget:
        return hotels
    return [h for h in hotels if h.per_night(req.nights) <= req.budget]


def readback(hotels: list[Hotel], req: slots.HotelRequest) -> str:
    lines = []
    for n, h in enumerate(hotels[:TOP_N], start=1):
        rating = f", rated {h.rating} out of 10" if h.rating else ""
        lines.append(
            f"{n}. {h.name}, {h.area}{rating}: about {rupees(h.per_night(req.nights))} a night, "
            f"{rupees(h.stay_price + h.taxes)} total for {req.nights} "
            f"night{'s' if req.nights > 1 else ''} with taxes."
        )
    return "\n".join(lines)


def _intro(req: slots.HotelRequest) -> str:
    year = f" I'm assuming {req.check_in:%Y}." if req.assumed_year else ""
    return (
        f"For {req.check_in:%-d %B} to {req.check_out:%-d %B}, {req.rooms} room, "
        f"{req.adults + req.children} guests.{year}"
    )


@tool
def hotel_search(request: str) -> str:
    """Search hotels on Booking.com from the user's words and read back the top three with the
    price per night and the total (from the live page). Asks one question when details are missing.

    Args:
        request: The user's words, e.g. "book a hotel in Goa, 17 to 19 October, 2 guests".
    """
    today = date.today()
    earlier = _state["request"]
    base = earlier if earlier and earlier.missing() else None  # only answers merge
    try:
        req = slots.parse(request, today, base)
    except slots.SlotError as error:
        return str(error)
    _state["request"] = req
    if ask := slots.question(req):
        return ask
    if MAKEMYTRIP.search(request):
        tasks.say(MAKEMYTRIP_SAY)
    tasks.say(f"Searching Booking.com for hotels in {req.area or req.city}.")
    browser.goto(search_url(req))
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("captcha")
        return "Waiting"
    hotels = within_budget(browser.on_page(_read_hotels), req)
    _state["hotels"] = hotels
    if not hotels:
        return f"Booking.com shows nothing in {req.city} that fits. Want me to drop the budget?"
    listing = safety.wrap_untrusted(readback(hotels, req))
    return f"{_intro(req)}\n{listing}\nWhich one should I book?"


def pick_hotel(choice: str, hotels: list[Hotel]) -> Hotel:
    """Decision (tests): "the second one", "2", or a hotel's name → that hotel. A name that isn't
    in the results raises with the closest matches."""
    if not hotels:
        raise ToolError("Search for hotels first, then tell me which one.")
    words = choice.casefold().split()
    for word in words:
        n = ORDINALS.get(word) or (int(word) if word.isdigit() else 0)
        if 1 <= n <= min(TOP_N, len(hotels)):
            return hotels[n - 1]
    names = [h.name for h in hotels]
    wanted = re.sub(r"\b(?:the|one|hotel|book|please)\b", " ", choice, flags=re.I).strip()
    for h in hotels:
        if wanted and safety.normalise(wanted) in safety.normalise(h.name):
            return h
    close = difflib.get_close_matches(wanted, names, n=TOP_N, cutoff=0.3) or names[:TOP_N]
    raise ToolError(
        f"I couldn't find {wanted} in the results. The closest are: {'; '.join(close)}."
    )


def cheapest_room(rooms: list[Room], guests: int, rooms_wanted: int) -> Room:
    """Decision (tests): the cheapest option (price + taxes) where every room fits its guests."""
    per_room = -(-guests // max(rooms_wanted, 1))
    fitting = [r for r in rooms if r.max_persons >= per_room and r.price]
    if not fitting:
        raise ToolError("None of this hotel's rooms fit your guests. Pick another hotel?")
    return min(fitting, key=lambda r: r.price + r.taxes)


def _read_rooms(page: Any) -> list[Room]:
    page.locator(ROOM_SELECT).first.wait_for(timeout=WAIT_MS)
    rooms, name = [], ""
    for index, row in enumerate(page.locator(ROOM_ROW).all()[:MAX_ROOM_ROWS]):
        if row.locator(ROOM_NAME).count():
            name = " ".join(row.locator(ROOM_NAME).first.inner_text().split())
        if not row.locator(ROOM_SELECT).count():
            continue
        text = row.inner_text()
        persons = MAX_PERSONS.search(text) or SELECT_PERSONS.match(
            row.locator(ROOM_SELECT).first.get_attribute("name") or ""
        )
        price, taxes = ROW_PRICE.search(text), ROW_TAXES.search(text)
        cancel = CANCELLATION.search(text)
        rooms.append(
            Room(
                name=name,
                max_persons=int(persons[1]) if persons else 0,
                price=int(price[1].replace(",", "")) if price else 0,
                taxes=int(taxes[1].replace(",", "")) if taxes else 0,
                cancellation=(
                    " ".join(cancel[0].split()) if cancel else "no free cancellation shown"
                ),
                index=index,
            )
        )
    return rooms


def _select_room(room: Room, count: int) -> Any:
    def find(page: Any) -> Any:
        page.locator(ROOM_ROW).nth(room.index).locator(ROOM_SELECT).first.select_option(str(count))
        page.wait_for_timeout(PAGE_SETTLE_MS)
        button = page.locator(RESERVE).filter(visible=True)
        if not button.count():
            raise ToolError("I can't find the reserve button on this hotel's page.")
        return button.first

    return find


def _guest_form_state(page: Any) -> dict[str, str]:
    page.locator(NEXT).first.wait_for(timeout=WAIT_MS)
    names = [*GUEST_FIELDS.values(), PHONE_FIELD]
    return {n: page.locator(f"input[name={n}]").first.input_value() for n in names}


@tool
def hotel_book(choice: str) -> str:
    """Book one hotel from the last hotel_search up to Booking.com's payment page, then stop:
    opens it, picks the cheapest room that fits the guests, reserves, and moves past the guest
    details when they're already filled. Zoya never pays.

    Args:
        choice: Which hotel: "2", "the second one", or its name.
    """
    req, hotel = _state["request"], pick_hotel(choice, _state["hotels"])
    tasks.say(f"Opening {hotel.name}.")
    browser.goto(hotel.href)
    room = cheapest_room(browser.on_page(_read_rooms), req.adults + req.children, req.rooms)
    _state.update(hotel=hotel, room=room)
    total = (room.price + room.taxes) * req.rooms
    tasks.say(
        f"The cheapest room for {req.adults + req.children} is the {room.name}, "
        f"{room.cancellation}, {rupees(total)} with taxes for "
        f"{req.check_in:%-d %B} to {req.check_out:%-d %B}. Reserving it."
    )
    browser.click_checked(browser.probe_with(_select_room(room, req.rooms)), "I'll reserve")
    return _continue_from_guest_form()


def _continue_from_guest_form() -> str:
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("sign_in")
        return "Waiting"
    state = browser.on_page(_guest_form_state)
    if not all(state.values()):
        return GUEST_SAY
    tasks.say("Your details are filled in. Going to the payment step.")
    browser.click_checked(browser.probe_with(_next_button), "Next: Final details")
    return _at_payment()


def _next_button(page: Any) -> Any:
    button = page.locator(NEXT).filter(visible=True)
    if not button.count():
        raise ToolError("I can't find the next button on the guest details page.")
    return button.first


@tool
def hotel_guest_details(first_name: str, last_name: str, email: str, phone: str) -> str:
    """Fill the main guest's details on the open Booking.com guest form, only with what the user
    just said out loud, then continue to the payment page and stop.

    Args:
        first_name: As the user said it.
        last_name: As the user said it.
        email: As the user said it.
        phone: As the user said it, digits only.
    """
    values = {"firstname": first_name, "lastname": last_name, "email": email, PHONE_FIELD: phone}
    if not all(v.strip() for v in values.values()):
        return GUEST_SAY

    def fill(page: Any) -> None:
        for name, value in values.items():
            browser.fill_checked(page.locator(f"input[name={name}]").first, value.strip(), name)

    tasks.say("Filling guest details.")
    browser.on_page(fill)
    return _continue_from_guest_form()


def _payment_page(page: Any) -> str:
    """Body text once the final step shows, "" if it didn't."""
    deadline = time.monotonic() + PAYMENT_WAIT_S
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            text = page.inner_text("body")
            if page.locator(PAYMENT_FRAME).count() or PAYMENT_TEXT.search(text):
                return text
        page.wait_for_timeout(int(POLL_S * 1000))
    return ""


def payment_total(text: str) -> int:
    """Parser (tests): the last "Total/Price ₹X" on the payment page, 0 when none."""
    found = TOTAL.findall(text)
    return int(found[-1].replace(",", "")) if found else 0


def payment_readback(hotel: str, req: slots.HotelRequest, expected: int, shown: int) -> str:
    """What Zoya says on the payment page (tests): the page's total, and any mismatch."""
    amount = shown or expected
    said = (
        f"You're on the payment page for {hotel}, {req.check_in:%-d %B} to "
        f"{req.check_out:%-d %B}, total {rupees(amount)}. I'll stop here. Payment needs you."
    )
    if shown and shown != expected:
        said += f" Note: the page's total differs from the {rupees(expected)} I read earlier."
    elif not shown:
        said += " I couldn't read the total on this page, so please check it."
    return said


def _at_payment() -> str:
    text = browser.on_page(_payment_page)
    if not text:
        return "The payment step didn't open the way I expected, so I stopped. Nothing was booked."
    hotel, room, req = _state["hotel"], _state["room"], _state["request"]
    expected = (room.price + room.taxes) * req.rooms
    browser.on_page(lambda page: page.bring_to_front())
    return payment_readback(hotel.name, req, expected, payment_total(text))


TOOLS = [hotel_search, hotel_book, hotel_guest_details]
