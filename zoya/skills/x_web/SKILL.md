---
name: x-web
description: X (Twitter) in Zoya's browser — post a tweet from the user's account.
metadata:
  tools: [x_post]
  triggers:
    # "Hey Zoya, tweet: testing Zoya, my voice assistant" (demo flow)
    - action: x_post
      pattern: '^(?:post\s+(?:a\s+)?)?tweet(?:\s+this)?\s*[:,-]?\s+(?P<text>.+)$'
    - action: x_post
      pattern: '^post\s+(?:on|to)\s+(?:x|twitter)\s*[:,-]?\s+(?P<text>.+)$'
---
# X

- "Tweet <text>" or "post on X <text>": call `x_post(text)` with the user's exact words. Don't
  rewrite, shorten or add hashtags unless the user asked.
- Zoya's safety layer reads the tweet and its character count back and waits for "confirm". Don't
  ask yourself. If the tool says the user cancelled, stop: nothing was posted.
- Too long: say the count and offer to shorten. Only post a shorter version the user approved.
- Say what happened in one short sentence, using the tool's words ("Posted.").
