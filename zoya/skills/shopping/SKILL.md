---
name: shopping
description: Amazon.in shopping — search and compare, buy one item with Buy Now, add to or remove from the cart, check out, place an order after the user confirms.
metadata:
  tools: [amazon_search, amazon_buy, amazon_buy_now, amazon_add_to_cart, amazon_cart, amazon_cart_remove, amazon_checkout, amazon_place_order, memory_search, memory_add, browser_read, handoff_to_user]
  triggers:
    - action: amazon_search
      pattern: '^(?:search|look|find)\s+(?:for\s+)?(?P<query>.+?)\s+(?:on|in)\s+amazon(?:\.in)?$'
    - action: amazon_buy
      pattern: '^(?:i\s+(?:want|wanted|would\s+like|need)\s+to\s+|(?:can|could|will)\s+you\s+(?:please\s+)?|please\s+)?(?:buy|order|purchase|get)\s+(?:me\s+)?(?:this\s+|the\s+|some\s+)?(?P<query>.+?)\s+(?:from|on)\s+amazon(?:\.in)?(?:\s+for\s+me)?(?:[.,]?\s+(?:can|could|will)\s+you\s+(?:please\s+)?do\s+that(?:\s+for\s+me)?)?$'
    - action: amazon_cart_remove
      pattern: '^(?:please\s+)?(?:remove|delete|take\s+out)\s+(?:the\s+)?(?P<item>.+?)\s+from\s+(?:my\s+|the\s+)?(?:amazon\s+)?cart$'
---
# Shopping on Amazon.in

Grounding rule: prices, stock, items and totals come only from tool results from the live page,
never from memory or guesses.

Amazon.in sells products. It doesn't book hotels, cabs or restaurants: say so at once and offer a
web_search for a site that does, before asking the user any details.

"Buy X" (one item): `amazon_buy(query)` does it all in one call: it picks the first listing that
isn't a sponsored ad, uses Buy Now so only that item is checked out (Amazon.in still adds it to the cart), and the safety layer asks the user to confirm out loud. To buy a result the user chose from
a search: `amazon_buy_now(result_number)`, then `amazon_place_order` with the page's total and item.

"Only that one" / "remove the rest": `amazon_cart` lists the cart (saved-for-later items don't
count), then `amazon_cart_remove(item)` once per item to remove. Removing from the cart is free.

"Order my usual groceries":
1. `memory_search("usual groceries")`. If nothing is remembered, ask the user what to order and stop.
2. For each item: `amazon_search(item)`, pick the result that best matches the remembered item
   (brand, size; skip sponsored ads), `amazon_add_to_cart(result_number)`. If none fits or it's
   unavailable, skip it and say so at the end. If a tool says the store is closed, say that and stop:
   every Amazon Now item is closed too.
3. `amazon_checkout()`, then read the page's order total and item names exactly as shown.
4. `amazon_place_order(order_total, items)` with those exact values. Zoya's safety layer checks the
   total on the screen and asks the user to confirm out loud. Never ask yourself.
5. If the tool says the user cancelled: say "Cancelled. Nothing was ordered. Your cart is saved." and
   stop. If it says the total is above the test limit: say so and stop.

Search and compare ("best headphones under 3,000 rupees, top three"): `amazon_search` with the
budget in the query, then read the top three that fit the budget: name, price, rating.

Sign-in or CAPTCHA pages: `handoff_to_user`, then stop.
