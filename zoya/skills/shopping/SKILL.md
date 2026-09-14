---
name: shopping
description: Amazon.in shopping — search and compare, add to cart, check out, place an order after the user confirms.
metadata:
  tools: [amazon_search, amazon_add_to_cart, amazon_cart, amazon_checkout, amazon_place_order, memory_search, memory_add, browser_read, handoff_to_user]
  triggers:
    - action: amazon_search
      pattern: '^(?:search|look|find)\s+(?:for\s+)?(?P<query>.+?)\s+(?:on|in)\s+amazon(?:\.in)?$'
---
# Shopping on Amazon.in

Grounding rule: prices, stock, items and totals come only from tool results from the live page,
never from memory or guesses.

"Order my usual groceries":
1. `memory_search("usual groceries")`. If nothing is remembered, ask the user what to order and stop.
2. Say the list in one sentence ("Your usual: milk, eggs and bread. Adding them now.") with narrate.
3. For each item: `amazon_search(item)`, pick the result that best matches the remembered item
   (brand, size), `amazon_add_to_cart(result_number)`. If none fits or it's unavailable, skip it
   and say so at the end.
4. `amazon_checkout()`, then read the page's order total and item names exactly as shown.
5. `amazon_place_order(order_total, items)` with those exact values. Zoya's safety layer checks the
   total on the screen and asks the user to confirm out loud. Never ask yourself.
6. If the tool says the user cancelled: say "Cancelled. Nothing was ordered. Your cart is saved." and
   stop. If it says the total is above the test limit: say so and stop.

Search and compare ("best headphones under 3,000 rupees, top three"): `amazon_search` with the
budget in the query, then read the top three that fit the budget: name, price, rating.

Sign-in or CAPTCHA pages: `handoff_to_user`, then stop.
