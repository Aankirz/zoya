# Phase 1 — Brain + fast actions (2–8h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-1-brain-fast-actions` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/orchestrator.py`
- `zoya/router.py`
- `zoya/prompts.py`
- `zoya/tools/fast.py`
- `zoya/tools/notes.py`
- `zoya/speech.py` (Polly narrate; Phase 2 may replace its internals)
- `zoya/events.py` (shared event names and payloads — the contract other phases build against)
- `zoya/config.py` (shared settings loaded from env; other phases add keys append-only)
- `tests/evals/router_eval.py`
- `tests/test_router_rules.py`

**Goal:** a typed command makes the Mac do something within about a second, and Zoya says what it did.

**Build**
- **Contracts first:** `config.py` (loads the few `.env` values; all other settings — voices `kiara`/`Kajal`, limits, sound pack, paths — are named constants here, not env vars), `events.py` (event names + payload dataclasses for narrate, earcon, task, confirmation, overlay), and the tool/agent registration convention (each tools/agents module exposes a `TOOLS` list; the orchestrator collects them).
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
