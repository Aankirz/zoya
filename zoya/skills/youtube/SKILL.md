---
name: youtube
description: YouTube in Zoya's browser — search, open a channel, play a video, subscribe, like, comment.
metadata:
  tools: [youtube_search, youtube_open_channel, youtube_play_video, youtube_subscribe, youtube_like, youtube_comment, browser_read]
  triggers:
    - action: youtube_open_channel
      pattern: '^(?:open|show|go to|take me to)\s+(?:me\s+)?(?:the\s+)?(?P<name>.+?)(?:''s)?\s+(?:youtube\s+)?channel(?:\s+(?:on|in)\s+youtube)?$'
    - action: youtube_open_channel
      pattern: '^(?:open|show)\s+youtube\s+(?!music$)(?P<name>.+?)(?:\s+channel)?$'
    - action: youtube_open_channel
      pattern: '^(?:open|show)\s+(?P<name>.+?)\s+(?:on|in)\s+youtube$'
    - action: youtube_play_video
      pattern: '^play\s+(?:the\s+)?(?:video\s+)?(?P<title>.+?)\s+(?:on|in|from)\s+youtube$'
    - action: youtube_search
      pattern: '^(?:search|look up|find)\s+(?:for\s+)?(?P<query>.+?)\s+(?:on|in)\s+youtube$'
    - action: youtube_search
      pattern: '^(?:search\s+)?youtube\s+(?:for|search)\s+(?P<query>.+)$'
    - action: youtube_comment
      pattern: '^(?:post\s+(?:a\s+)?)?comment\s+[''"“]?(?P<text>.+?)[''"”]?(?:\s+on\s+(?:this|the)\s+video)?$'
    - action: youtube_subscribe
      pattern: '^subscribe(?:\s+to\s+(?:this|the)\s+channel)?$'
    - action: youtube_like
      pattern: '^like\s+(?:this|the)\s+video$'
---
# YouTube

- Opening a channel: always call `youtube_open_channel(name)`. It searches and opens the matching
  channel; never type a guessed `youtube.com/@handle` address.
- Playing: `youtube_play_video(title)` searches and opens the best match, which plays by itself.
  On a video page, "play <title>" means that other video.
- Subscribe, like and comment publish as the user. Call `youtube_subscribe`, `youtube_like` or
  `youtube_comment(text)` on the open page; Zoya's safety layer reads the summary and waits for the
  user's spoken "confirm". Don't ask yourself. If the tool says the user cancelled, stop.
- If the page shows a sign-in wall, call `handoff_to_user`.
- Say what happened in one short sentence, using the tool's words ("Opened MrBeast's channel").
