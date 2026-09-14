# Phase 4 — Browser + shopping + memory (23–31h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-4-browser-shopping-memory` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/tools/browser.py`
- `zoya/agents/browser_agent.py`
- `zoya/tools/memory.py`
- `tests/test_memory_filter.py`

**Goal:** Zoya searches and reads back the web, remembers the user's preferences, and completes a real Amazon.in grocery order up to (and through) spoken confirmation.

**Build**
- `browser_agent` (§9.7): Playwright persistent **Zoya Chrome profile**, launched once at startup; DOM-first tools; screenshot fallback.
- Shopping skill prompt + grounding rule: confirmation summary read from the live checkout page (§9.12).
- Supermemory tools `memory_add` / `memory_search` with the secret filter (§9.8); auto-save after confirmed tasks; corrections memory (§13.5.6).
- Earcons: `progress-step`, `add-to-cart`, `purchase`, `checkpoint`, `mention`, `blocked`.
- Login/CAPTCHA handoff flow (Flow 10), plus an **SNS email to the trusted contact** when Zoya is blocked.
- **Order history + key-memory copy** in DynamoDB (fallback when Supermemory is unavailable).
- **Amazon Location Service** tool: "nearest pharmacy / what's near me".
- **Deep web research (Claude-style search → fetch → answer):** `web_search(query, intent)` and `web_fetch(url)` tools on the **TinyFish Search and Fetch APIs** (free tier: 30 searches/min, 150 fetches/min — https://docs.tinyfish.ai/search-api/reference, https://www.tinyfish.ai/blog/search-and-fetch-are-now-free-for-every-agent-everywhere). The brain searches, fetches the 2–3 best pages, and answers with the source name spoken ("according to…"). Fetched text is wrapped in `<untrusted_content>` (§12.2). API key in Secrets Manager `zoya/providers`; timeouts; only the query/URL leaves the Mac. Record as a DECISIONS entry. This handles "look it up" questions (population, news, comparisons) instead of the model guessing.
- **In-tab site control on the user's logged-in sites** (DOM-first, Playwright Zoya profile): "play <song> on Spotify web", "play <video> on YouTube", "search <x> on YouTube", "subscribe to this channel", "comment <text> on this video", "like this video". Playing, searching and opening are free actions. **Subscribe, like, comment and post go through the Phase 3 safety gate** (spoken summary + "confirm") because they publish as the user.
- `tests/test_memory_filter.py`.

**Not in this phase:** pixel computer use, multiple simultaneous tasks, PPT.

**Doc sections:** §6 Flows 3, 6, 10 · §9.7, §9.8, §9.12, §12.

**Done when**
1. ☐ "Search the best headphones under 3,000 rupees and read me the top three" → correct read-back from page text.
2. ☐ "Remember my usual groceries are…" → `checkpoint` earcon; visible in Supermemory.
3. ☐ "Order my usual groceries from Amazon" → correct items in cart → confirmation states the **real** page total.
4. ☐ "Cancel" path leaves cart intact, nothing ordered.
5. ☐ "Confirm" path places the order (cheap item) and saves order history to memory.
6. ☐ Logged-out session → handoff message, resumes after "done".
7. ☐ Card number / OTP rejected by `memory_add`.
8. ☐ "What's the population of Bangalore compared to New York?" → Zoya searches, reads sources, answers with a named source (no "I can't read the results").
9. ☐ "Play Love Me Not on Spotify" (Spotify web in the Zoya profile) → that exact song plays, not the last-played track.
10. ☐ On a YouTube video: "play <video title>" works; "comment 'great video'" → spoken confirmation → "cancel" posts nothing.

**Judge demo (90 s):** "Hey Zoya, remember my usual groceries are…" → "Hey Zoya, order my usual groceries from Amazon" → ticks per item → confirmation with real total → "Confirm" → `purchase` earcon.
