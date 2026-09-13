# Phase 4 — Browser + shopping + memory (23–31h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-4-browser-shopping-memory` · **Depends on:** Phases 1 and 3 ("Done when" passing) · **Note:** memory tools can start right after Phase 1

**Files this phase owns** (other agents must not edit them during this phase):
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
- Login/CAPTCHA handoff flow (Flow 10).
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

**Judge demo (90 s):** "Hey Zoya, remember my usual groceries are…" → "Hey Zoya, order my usual groceries from Amazon" → ticks per item → confirmation with real total → "Confirm" → `purchase` earcon.
