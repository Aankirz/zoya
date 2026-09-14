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
- **Agent "presence" (AgentPet-style, Apple-made feel):** the avatar is a living character that *shows what Zoya is doing and thinking*, driven only by `zoya/events.py` — states **idle · listening · thinking (caption = current step, e.g. "Checking the cart total…") · acting (tool name) · speaking · waiting for your yes · stopped · error**. One subtle, distinct animation per state (breathing when idle, a gentle pulse while listening, a slow shimmer while thinking); no new state logic.
- **Design direction — Apple Human Interface Guidelines** (https://developer.apple.com/design/):
  - *Materials:* the panel is a floating functional layer above content, so use Liquid Glass (`NSGlassEffectView`, macOS 26) if PyObjC exposes it — verify first — else the standard material `NSVisualEffectView` (`.hudWindow`). Use glass sparingly: one panel, no glass inside it. ([Materials](https://developer.apple.com/design/human-interface-guidelines/materials))
  - *Motion:* purposeful, brief and precise; never the only signal (earcons + captions carry the same state); honour **Reduce Motion** (static state images instead of animation). ([Motion](https://developer.apple.com/design/human-interface-guidelines/motion))
  - *Type & symbols:* system font (SF Pro via `NSFont.systemFont`), SF Symbols for state glyphs, captions large enough to read on a projector.
  - *Accessibility:* honour **Reduce Transparency** (solid background) and **Increase Contrast**; captions meet contrast in light and dark. ([Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))
  - Calm and quiet like Siri — no gamification, levels or pixel-pet XP; the user is blind, the visuals are for the room.
- Action highlight ring drawn after screenshots (§9.11).
- Computer-use prompt line to ignore the overlay.

**Not in this phase:** new capabilities.

**Doc sections:** §9.11.

**Done when**
1. ☐ Overlay never takes keyboard focus (typing into Notes works while visible).
2. ☐ Clicks pass through the overlay.
3. ☐ Ring shows the target *before* each click; it never appears in screenshots sent to the model.
4. ☐ Captions match what was said, both user and Zoya.
5. ☐ Every state (idle, listening, thinking + step caption, acting, speaking, waiting for yes, stopped, error) is visibly distinct from across a room, and changes within ~100 ms of its event.
6. ☐ With macOS Reduce Motion / Reduce Transparency on, the overlay shows static states on a solid background, still readable.
7. ☐ Owner judges the look "feels like Apple made it" on the projector (screenshot light + dark).

**Judge demo (30 s):** rerun the Phase 4 order with the projector on — audience sees avatar states, captions, and the ring landing on "Add to Cart".
