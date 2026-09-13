# Architecture Audit — 2026-09-14

Every major assumption in the design was checked against **primary evidence**: installed package source code, official AWS/Anthropic docs and pricing data, GitHub issues, and real tests on the owner's Mac (macOS 26, Apple Silicon, Bangalore). No design claim is trusted without one of these.

Verdicts: ✅ verified · ⚠️ risky / needs a design change · ❌ wrong.

---

## 1. Blocking findings

| # | Area | Verdict | Finding | Evidence | Change |
|---|---|---|---|---|---|
| A1 | Wake word | ❌ | Picovoice free tier ended 30 Jun 2026. sherpa-onnx KWS caught only 10/24 wake phrases (16/24 tuned, with 5 false triggers). | Home Assistant community notice; local 54-clip test | **Local Whisper `base.en` + VAD**: 21/24, 0/30 false triggers (D19) |
| A2 | Claude billing | ❌ likely | Promotional credits exclude AWS Marketplace; Claude on Bedrock is billed via Marketplace. On AWS India (AISPL) accounts, stored cards/UPI often fail for Marketplace (RBI rules); AWS's documented route is **Pay By Invoice**. | aws.amazon.com/awscredits terms; Haiku 4.5 model card; re:Post | Owner decision needed (see §4). Keep a **Nova-only path** that works on credits |
| A3 | Nova Canvas | ❌ | Legacy in Tokyo, **end-of-life 2026-09-30**. | Bedrock model card for Nova Canvas | **Removed.** PPT slides are text-only (D21) |
| A4 | Account | ⚠️ | All Bedrock calls return "account is currently being verified". Duration not documented (hours to days). | Live test on account 567487920371 | Wait; then Anthropic form; then support case if needed |

## 2. Design corrections

| # | Area | Verdict | Finding | Change |
|---|---|---|---|---|
| B1 | Strands voice (`BidiAgent`) | ⚠️ | Real class: `strands.experimental.bidi.models.BedrockNovaSonicModel(model_id="amazon.nova-2-sonic-v1:0", region=..., audio={"voice": "kiara"})`. Audio I/O is `BidiAudioIO` on **PyAudio** (needs `brew install portaudio` + extras `bidi,bidi-pyaudio,bidi-aec`). Still experimental; renames planned (#3979, #3980). | Pin `strands-agents[bidi,bidi-pyaudio,bidi-aec,otel]==1.55.1`; wrap bidi imports behind one adapter module |
| B2 | Echo / barge-in | ⚠️ | Without echo cancellation, laptop speakers cause false interruptions. | `BidiAudioIO(audio_processor=True)` (AEC); headset for demo |
| B3 | Spoken progress | ⚠️ | `agent.send(text)` arrives as a **user** turn; there is no "speak as assistant" API. Nova drops the connection after ~55 s without audio. | Send progress as an instruction (`[status] tell the user: …`); keep activity inside the idle window |
| B4 | Session limit | ✅ | 8-min connection limit; Strands auto-reconnects at 420 s, but a tool result that finishes after a reconnect isn't replayed. | Keep long tasks' results in our own task registry and re-announce after `BidiConnectionRestartEvent` |
| B5 | Confirmation hook | ✅/⚠️ | `BeforeToolCallEvent.cancel_tool = "reason"` is real. Hook-based **interrupts** are not supported in bidi (#3934). | Ask by voice, cancel via hook (our design already does this) |
| B6 | Sub-agents | ✅/⚠️ | `agent.as_tool()` exists. One `Agent` instance can't run two calls at once (`ConcurrencyException`). | One Agent instance per background task |
| B7 | Prompt caching | ⚠️ | `cache_prompt`/`cache_tools` deprecated → `CacheConfig(strategy="auto", system_prompt_ttl=True, tools_ttl=True)`. Sonnet 5 needs ≥ 4,096 tokens per cache breakpoint. | Update §9.3; keep system prompt + tools above the threshold or skip caching |
| B8 | Sonnet 5 latency | ⚠️ | Thinking is always on for Sonnet 5 on Bedrock. | Low effort setting; filler speech ("Looking at your screen…") |
| B9 | Computer-use tool | ⚠️ | On Bedrock only the beta `computer_20251124` tool is offered; custom screenshot/click tools also work. `strands_tools.use_computer` asks for y/n consent on stdin (would hang a voice app). | Prefer Anthropic's `computer_20251124` or our own tools; never the stdin-consent tool without `BYPASS_TOOL_CONSENT=true` + our hook |
| B10 | Screen coordinates | ❌ | "Screenshots are 2×" is wrong: scale differs per display (external 1920×1080 at 1.0, built-in Retina at 2.0). | Per-display `NSScreen.backingScaleFactor()`; capture at point size so screenshot coords = click coords |
| B11 | Overlay hidden from screenshots | ❌ | `NSWindowSharingNone` is ignored by ScreenCaptureKit on macOS 15+. | Capture with ScreenCaptureKit excluding Zoya's windows; fallback: hide panel ~50 ms during capture |
| B12 | Permissions | ⚠️ | Screenshots/AX fail without permission (AX error −25204, not "permission denied"). macOS 15+ re-asks about screen recording periodically. Automation prompt for Notes (error −1743). | Startup check with `CGPreflightScreenCaptureAccess()` / `AXIsProcessTrusted()`; speak problems aloud; ship as signed `.app` eventually |
| B13 | Nova Micro router | ⚠️ | Tokyo: only via regional cross-region profile. ~0.85 s time-to-first-token (third-party benchmark) — breaks the 300 ms router budget. | **Rules first** for all common commands; Nova Micro only for the rest; JSON schema + router eval (§17.1b) |
| B14 | Nova Sonic latency | ⚠️ | ~1.39 s to first audio (AWS blog case study). | Earcon within 200 ms covers the gap; target "first word < 1.5 s" is tight |
| B15 | Hinglish voice | ⚠️ | Only `tiffany`/`matthew` are documented as polyglot/code-switching voices; `kiara` is en-IN + hi-IN. | Test Hinglish with `kiara` in Phase 2; fallback `tiffany` |
| B16 | Supermemory | ⚠️ | Works, but default `search_mode="memories"` found nothing after 2 min. With `dreaming="instant"` a memory was searchable after ~7 s; `search_mode="hybrid"` found it. Search latency from India **~0.55 s (0.53–1.4 s)**. Free plan **pauses** when the $5 usage runs out. | Use `dreaming="instant"` + `search_mode="hybrid"`; run search in parallel with planning; local cache of key facts as fallback |
| B17 | Regions / network | ⚠️ | TCP connect from Bangalore: Mumbai 23 ms, Singapore 44 ms, Tokyo 111 ms, US East 214 ms, US West 284 ms. Mumbai offers Sonnet 5 (global), Haiku 4.5 (global) and Nova Micro (APAC) but not Nova Sonic. | Phase 0: measure end-to-end latency for Mumbai vs Tokyo text models once the account is verified; Sonic stays Tokyo |
| B18 | Menu bar | ⚠️ | `rumps` last PyPI release 2022. | OK for MVP; fallback plain pyobjc `NSStatusItem` |
| B19 | Keynote | ⚠️ | Installed as "Keynote Creator Studio.app". | Launch apps by bundle id (`open -b com.apple.Keynote`) |

## 3. Verified as designed

| Area | Evidence |
|---|---|
| Playwright + dedicated Chrome profile (Chrome 153): launches, cookies persist, clicks work unfocused | Local test |
| `sounddevice` + `soundfile`: bundled PortAudio/libsndfile, playback works | Local test |
| Accessibility API via `pyobjc-framework-ApplicationServices` | Local import/call test |
| Model IDs in Tokyo (Sonic, Sonnet 5 global, Haiku 4.5 jp, Nova Micro apac) | `aws bedrock list-inference-profiles` on the account |
| OpenTelemetry tracing (`otel` extra) | Local test |
| `open -a` needs no permission | Research + local lookup |

## 4. Corrected costs

| Item | Old estimate | Verified |
|---|---|---|
| 1280×800 screenshot | 1,200–1,600 tokens | **1,334 tokens** (⌈w/28⌉×⌈h/28⌉) |
| 20-step computer-use task on Sonnet 5 ($2/$10 per 1M) | $0.30–0.80 | **~$0.80–0.90 uncached; ~$0.21–0.31 cached** |
| "What's on my screen" on Haiku 4.5 | < $0.01 | **~$0.004** |
| Router call on Nova Micro | fraction of a cent | **~$0.000025** |
| Nova 2 Sonic voice | not estimated | **~$0.005/min listening, ~$0.022/min speaking; ~$0.60–0.80 per hour of mixed talk** |

**Owner decision needed — Claude path (A2):**
1. **Claude with its own payment:** request *Pay By Invoice* on the AISPL account; Claude usage is billed separately from the credits. Best quality for computer use (OSWorld-Verified ~81% Sonnet 5 vs ~51% Haiku 4.5).
2. **Nova-only on credits:** Nova 2 Lite / Nova Pro replace Claude for the orchestrator and screen description; computer use becomes much weaker, so rely on fast tools, Accessibility API and browser DOM instead of pixels.
