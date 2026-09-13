# Phase 1 — Brain + fast actions (2–8h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-1-brain-fast-actions` · **Depends on:** Phase 0 ("Done when" passing)

**Files this phase owns** (other agents must not edit them during this phase):
- `zoya/orchestrator.py`
- `zoya/router.py`
- `zoya/prompts.py`
- `zoya/tools/fast.py`
- `zoya/tools/notes.py`
- `zoya/audio.py (Polly narrate only)`
- `tests/evals/router_eval.py`
- `tests/test_router_rules.py`

**Goal:** a typed command makes the Mac do something within about a second, and Zoya says what it did.

**Build**
- Strands orchestrator agent on Sonnet 5 (§9.3) with prompt caching.
- **Intent router** (§13.5.3): rule matcher first, then Nova Micro.
- T0 tools (§9.4): `open_app`, `open_url`, `run_applescript` (allow-listed apps), `notes_create/search/append`, volume, time.
- `narrate(text)` via **Amazon Polly** (temporary voice until Phase 2).
- Simple text REPL: type a command, see route + tool + timing.
- **Router eval** (§17.1b): 40 utterances, Nova Micro vs Haiku 4.5 → keep the winner.
- Per-stage timing logs (§13.5.1).

**Not in this phase:** microphone, wake word, earcons, browser, screenshots, memory.

**Doc sections:** §9.3, §9.4, §10.1, §13.5, §17.1b.

**Done when**
1. ☐ "open Spotify", "open youtube.com", "write a note: buy milk" all work by typing.
2. ☐ Simple commands finish in **≤ 1 s** (router + tool), shown in the timing log.
3. ☐ "Plan a trip and book a hotel" is routed to the orchestrator, not the fast path.
4. ☐ Router eval passes ≥ 95% (or Haiku 4.5 adopted and noted).
5. ☐ Unknown app → polite spoken error, no crash.

**Judge demo (45 s):** type three commands in a row; Mac reacts instantly and speaks; show the timing log with sub-second fast paths.
