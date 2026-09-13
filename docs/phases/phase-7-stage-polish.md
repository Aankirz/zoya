# Phase 7 — Stage polish (41–44h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-7-stage-polish` · **Depends on:** Phase 2 ("Done when" passing) · **Note:** can run in parallel with Phases 4–6

**Files this phase owns** (other agents must not edit them during this phase):
- `zoya/overlay.py`
- `assets/avatars/*`

**Goal:** sighted judges can follow every step visually without it affecting the blind user's experience or the agent.

**Build**
- Stage overlay (§9.11): non-activating, click-through `NSPanel`; avatar per state (Plane Agent Avatar Lab); live captions.
- Action highlight ring drawn after screenshots (§9.11).
- Computer-use prompt line to ignore the overlay.
- Optional: CloudWatch trace dashboard via Strands OpenTelemetry.

**Not in this phase:** new capabilities.

**Doc sections:** §9.11.

**Done when**
1. ☐ Overlay never takes keyboard focus (typing into Notes works while visible).
2. ☐ Clicks pass through the overlay.
3. ☐ Ring shows the target *before* each click; it never appears in screenshots sent to the model.
4. ☐ Captions match what was said, both user and Zoya.

**Judge demo (30 s):** rerun the Phase 4 order with the projector on — audience sees avatar states, captions, and the ring landing on "Add to Cart".
