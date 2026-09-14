---
name: spotify-web
description: Spotify web player in Zoya's browser — play one exact song, or search tracks.
metadata:
  tools: [spotify_play_song, spotify_search, media_control, browser_read]
  triggers:
    - action: spotify_play_song
      pattern: '^play\s+(?:the\s+)?(?:song\s+)?(?P<song>.+?)(?:\s+by\s+(?P<artist>.+?))?\s+(?:on|in|from)\s+spotify(?:\s+web)?$'
    - action: spotify_search
      pattern: '^(?:search|look up|find)\s+(?:for\s+)?(?P<query>.+?)\s+(?:on|in)\s+spotify$'
---
# Spotify web

- "Play <song> (by <artist>) on Spotify": call `spotify_play_song(song, artist)`. It plays that exact
  track and checks the now-playing bar. Never press the media play key for a named song: that
  resumes whatever played last.
- Pause, resume, next and previous for what is already playing: `media_control`.
- Without a match, say you couldn't find it and offer `spotify_search` results.
