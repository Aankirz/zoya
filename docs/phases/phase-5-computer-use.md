# Phase 5 — Computer use (31–36h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-5-computer-use` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/tools/computer.py`
- `zoya/tools/ax.py`
- `zoya/agents/computer_agent.py`
- `zoya/agents/screen_describer.py`
- `tests/test_coords.py`
- `tests/evals/screen_benchmark.py`

**Goal:** Zoya can see the screen and operate apps that have no shortcut, website DOM or accessibility label.

**Build**
- `computer_agent` (§9.6): `screenshot` (ScreenCaptureKit, excluding Zoya's own windows; per-display scale from `NSScreen.backingScaleFactor()`, captured at point size so screenshot coords = click coords; ~1280×800 ≈ 1,334 tokens), `click`, `type_text` (clipboard for Unicode), `key`, `scroll`; **Retina scaling**; verify-after-act; GUI lock.
- AX API tier T1 (`ax_read`, `ax_press`) before pixels (§9.4).
- `screen_describer` on `VISION_MODEL` (chosen in Phase 0); re-run the screen benchmark with real Zoya prompts.
- Context pruning: last 2 screenshots only (§9.3).
- **Harness, cheapest path first** ([`docs/research/harness.md`](../research/harness.md)): before any pixel loop, try the Shortcuts app (`shortcuts run`) and fixed AppleScript actions as skill recipes. Record each successful pixel/DOM task as a replayable flow keyed by intent + app, replay it at 0 model calls next time, and fall back to the brain if a step doesn't match. Every replayed step still goes through the Phase 3 gate.
- **Amazon Textract**: "read this PDF / bill / letter to me" (text + tables read aloud).
- **Rekognition DetectText** as a fast OCR tool for "read the text on my screen".
- `tests/test_coords.py`.

**Not in this phase:** multitasking, overlay.

**Doc sections:** §6 Flow 5 · §9.4, §9.6, §10.1, §13.2, §17.1b.

**Done when**
1. ☐ `pytest tests/test_coords.py` passes; clicks land correctly on Retina and with an external display plugged in.
2. ☐ "What's on my screen?" on 5 different screens → correct app, dialogs first, exact amounts.
3. ☐ "Turn on dark mode" done via clicks in System Settings (not AppleScript) → verified by screenshot.
4. ☐ A pixel task gives up honestly after 3 failed attempts.
5. ☐ Screen benchmark run; model choice recorded.

**Judge demo (60 s):** "Hey Zoya, what's on my screen?" on a busy page → accurate description → "Hey Zoya, switch to dark mode" → cursor visibly moves and clicks in Settings.
