from datetime import date

import pytest

from zoya.skills.hotels_web.slots import HotelRequest, SlotError, parse, question

TODAY = date(2026, 9, 15)
FULL = (
    "go to MakeMyTrip and book a hotel in Bangalore near MG Road, check-in 17th October, "
    "check-out 19th October, 1 room, 2 guests, under Rs. 5,000 a night"
)


def test_full_sentence_fills_every_slot():
    req = parse(FULL, TODAY)
    assert (req.city, req.area) == ("Bangalore", "MG Road")
    assert (req.check_in, req.check_out, req.nights) == (date(2026, 10, 17), date(2026, 10, 19), 2)
    assert (req.rooms, req.adults, req.budget, req.missing()) == (1, 2, 5000, [])


def test_missing_checkout_and_guests_is_one_question():
    req = parse("book a hotel in Jaipur, check-in October 17", TODAY)
    assert question(req) == "What are the check-out date and number of guests?"


def test_answer_merges_into_the_earlier_request():
    first = parse("book a hotel in Jaipur, check-in October 17", TODAY)
    req = parse("Checkout date is 18th October, 2 adults", TODAY, first)
    assert (req.city, req.check_out, req.adults, req.missing()) == (
        "Jaipur",
        date(2026, 10, 18),
        2,
        [],
    )


def test_year_defaults_to_next_occurrence_and_is_flagged():
    req = parse("book a hotel in Goa from 2nd March to 4th March for 2 people", TODAY)
    assert (req.check_in, req.assumed_year) == (date(2027, 3, 2), True)


def test_nights_set_checkout():
    assert parse("hotel in Pune on 1 Oct 2026 for two nights", TODAY).check_out == date(2026, 10, 3)


def test_checkout_before_checkin_is_refused():
    with pytest.raises(SlotError):
        parse("hotel in Pune, check-in 20 October 2026, check-out 18 October 2026", TODAY)


def test_past_date_is_refused():
    with pytest.raises(SlotError):
        parse("hotel in Pune, check-in 1 September 2026", TODAY)


def test_complete_request_has_no_question():
    assert question(HotelRequest("Pune", "", TODAY, date(2026, 9, 16), 1, 2)) == ""


# --- hotels_web decisions and money readbacks ------------------------------------------------

from zoya.skills.hotels_web import actions  # noqa: E402
from zoya.tools import ToolError  # noqa: E402

REQ = parse(FULL, TODAY)
HOTELS = [
    actions.Hotel("Pelican Inn", "MG Road", "8.7", 8550, 428, "https://www.booking.com/a"),
    actions.Hotel(
        "Hyatt Centric MG Road", "MG Road", "8.3", 20270, 3649, "https://www.booking.com/b"
    ),
    actions.Hotel("Church's Inn", "MG Road", "4.2", 2723, 213, "https://www.booking.com/c"),
]


def test_search_url_uses_booking_query_format():
    url = actions.search_url(REQ)
    assert "ss=MG+Road%2C+Bangalore" in url and "checkin=2026-10-17" in url
    assert "checkout=2026-10-19&group_adults=2&no_rooms=1&group_children=0" in url


def test_budget_is_per_night_with_taxes():
    assert [h.name for h in actions.within_budget(HOTELS, REQ)] == ["Pelican Inn", "Church's Inn"]


def test_readback_says_per_night_and_total():
    assert "about ₹4,489 a night, ₹8,978 total for 2 nights with taxes" in actions.readback(
        HOTELS, REQ
    )


def test_second_one_picks_the_second_hotel():
    assert actions.pick_hotel("the second one", HOTELS).name == "Hyatt Centric MG Road"


def test_missing_named_hotel_offers_closest_matches():
    with pytest.raises(ToolError, match="couldn't find Taj.*closest"):
        actions.pick_hotel("the Taj", HOTELS)


def test_cheapest_room_that_fits_the_guests():
    rooms = [
        actions.Room("Single", 1, 1000, 100, "", 0),
        actions.Room("Twin", 2, 3000, 300, "", 1),
        actions.Room("Deluxe", 3, 2900, 500, "", 2),
    ]
    assert actions.cheapest_room(rooms, guests=2, rooms_wanted=1).name == "Twin"


def test_payment_readback_mentions_a_total_mismatch():
    said = actions.payment_readback("Pelican Inn", REQ, expected=8978, shown=9200)
    assert "total ₹9,200. I'll stop here. Payment needs you." in said and "₹8,978" in said


def test_payment_total_reads_the_last_total():
    assert actions.payment_total("Price ₹ 8,550 ... Total ₹ 8,978") == 8978
