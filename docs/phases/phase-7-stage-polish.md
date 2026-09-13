# Phase 7 — Stage polish (41–44h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-7-stage-polish` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/overlay.py`
- `assets/avatars/*`

**Goal:** sighted judges can follow every step visually without it affecting the blind user's experience or the agent.

**Build**
- **CloudWatch dashboard** for judges: live agent traces (X-Ray), task latency, tool calls, AWS services used per task.
- Keep the overlay out of the model's screenshots with ScreenCaptureKit window exclusion (fallback: hide the panel ~50 ms during capture). `NSWindowSharingNone` does NOT work on macOS 15+ (AUDIT B11).
- Stage overlay (§9.11): non-activating, click-through `NSPanel`; avatar per state (Plane Agent Avatar Lab); live captions.
- Action highlight ring drawn after screenshots (§9.11).
- Computer-use prompt line to ignore the overlay.

**Not in this phase:** new capabilities.

**Doc sections:** §9.11.

**Done when**
1. ☐ Overlay never takes keyboard focus (typing into Notes works while visible).
2. ☐ Clicks pass through the overlay.
3. ☐ Ring shows the target *before* each click; it never appears in screenshots sent to the model.
4. ☐ Captions match what was said, both user and Zoya.

**Judge demo (30 s):** rerun the Phase 4 order with the projector on — audience sees avatar states, captions, and the ring landing on "Add to Cart".
