---
name: hotels-web
description: Hotels on Booking.com — search a city or area for dates and guests, read the top three with prices, book one up to the payment page and stop; also the answers to Zoya's hotel question and the guest's name, email and phone.
metadata:
  tools: [hotel_search, hotel_book, hotel_guest_details, browser_read]
  triggers:
    - action: hotel_book
      pattern: '^(?:please\s+)?(?:book|reserve|take|choose|pick|select|go\s+with)\s+(?P<choice>(?:the\s+)?(?:first|second|third|last|1st|2nd|3rd|[1-3])(?:\s+(?:one|hotel|option))?)(?:\s+please)?$'
    - action: hotel_search
      pattern: '^(?P<request>.*\b(?:book|find|search|look|get|reserve)\b.*\b(?:hotels?|rooms?|stays?)\b.*)$'
    # The answer to Zoya's one slot question ("Checkout is 18th October, 2 adults"): a number and a slot word.
    - action: hotel_search
      pattern: '^(?P<request>(?=.*\d).*\b(?:check[- ]?out|checkout|check[- ]?in|guests?|adults?|people|persons?|nights?)\b.*)$'
---
# Hotels on Booking.com

Grounding rule: hotel names, prices, rooms, policies and totals come only from tool results.

- "Book a hotel in <city> …": `hotel_search(request)` with the user's words exactly. It asks one
  question when details are missing; pass the user's answer to `hotel_search` again.
- MakeMyTrip blocks automated browsing, so hotel_search uses Booking.com and says so.
- "The second one" / a hotel's name: `hotel_book(choice)`. It stops at the payment page.
- If a tool asks for the guest's name, email and phone, ask the user and pass exactly what they say
  to `hotel_guest_details`. Never invent or guess them. Never type passwords or codes.
- Zoya never pays or completes a booking: if the user says "pay now", say payment needs them.
