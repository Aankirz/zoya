# Phase 8 — Rehearsal + submission (44–48h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-8-rehearsal-submission` · **Depends on:** all previous phases ("Done when" passing)

**Files this phase owns** (other agents must not edit them during this phase):
- `tests/voice/*`
- `README.md (final polish)`
- `docs/DEMO_NOTES.md`

**Goal:** the full demo is reliable, rehearsed, and backed up.

**Build / do**
- Prompt tuning from rehearsal logs; failure branches (Flows 9, 10, 11 branches).
- Scripted voice tests from recorded `.wav` utterances (§17.2).
- Flow checklist (§17.3) + noise test + demo-machine dry runs (§17.4).
- Freeze environment 12 h before demo (permissions bind to the Python binary).
- Backup video, README, architecture slide, submission form.

**Done when**
1. ☐ Demo script (§18) runs clean **3 times in a row** on the demo Mac.
2. ☐ Every row in §17.3 passes.
3. ☐ Backup video recorded; hotspot tested.
4. ☐ Total AWS spend recorded and under budget.

**Judge demo:** the full 3-minute script (§18).
