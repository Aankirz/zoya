# Architecture Audit — 2026-09-14

> Bedrock/Nova/Claude-on-AWS findings apply only to the optional Bedrock provider. Current primary stack: [`STACK.md`](STACK.md).

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

## 5. Echo cancellation for laptop speakers (Phase 2 findings, 2026-09-14) — for the AEC session

**Problem (owner live runs, D52/D53):** on laptop speakers the mic hears the Mac's own playback as loud as the user. (1) With Spotify playing, "Hey Zoya" is misheard, so no wake and no duck. (2) "Zoya, stop" isn't heard while Zoya's TTS plays. Headset + fn + Shift work.

**Measured** (replay loop: owner's real "Hey Zoya" clips + background vocals mixed at the mic; VAD, loudness gate, mlx base.en spotter; scripts in the Phase 2 builder scratchpad, method reproducible with `tests/evals/wake_junk_replay.py`):

| Music RMS / voice RMS | 0.10 | 0.29 | 0.58 | 1.16 |
|---|---|---|---|---|
| Wakes (5 owner clips) | 4/5 | 2/5 | 2/5 | 1/5 |

Segments end correctly (the D53 loudness gate works); the spotter mishears the name over music ("He is after me"). **Rejected cheap fix:** ducking other apps on *any* voice onset raised wakes but pumped — 48 volume changes in 20 s of music alone, and it left the Mac ducked. Reverted, not committed.

| Option | Cancels our TTS | Cancels Spotify / other apps | Verdict |
|---|---|---|---|
| Apple voice processing I/O (`AVAudioEngine.inputNode.setVoiceProcessingEnabled`) | Only if the TTS plays through the same engine | ❌ Ducks other apps instead of cancelling them | Not enough. WWDC23 "Enhance your app's audio experience with AirPods / voice processing" https://developer.apple.com/videos/play/wwdc2023/10235/ ; measured ~0 dB removal of system audio: https://github.com/screenpipe/screenpipe/issues/3938 ; fragile setup + leaking tails: https://barock.dev/2026/04/22/why-your-ios-voice-agent-still-hears-itself ; dropouts on Spatial Audio Macs: https://www.forasoft.com/ship-log/spatial-audio-vpio |
| **WebRTC AEC3** via `livekit` `rtc.AudioProcessingModule(echo_cancellation=True, noise_suppression=True)` | ✅ reverse stream = our TTS PCM | ✅ if the reverse stream also gets system audio | **Recommended.** 10 ms frames; `process_stream` (mic) / `process_reverse_stream` (playback) / `set_stream_delay_ms`. livekit python-sdks `livekit-rtc/livekit/rtc/apm.py`, `media_devices.py` (sounddevice wiring, delay from PortAudio `outputBufferDacTime`/`inputBufferAdcTime`) https://github.com/livekit/python-sdks |
| Speex AEC (speexdsp) | Partly | Partly | Older and weaker. No direct comparison with AEC3 was found |
| Duck other apps on voice onset | — | Removes the music, doesn't cancel it | Pumping (measured above); keep only as a backstop behind AEC |

**Reference design (OpenWhispr meeting mode):**
- A Core Audio **process tap** captures all processes except our own: `CATapDescription` (exclusive, mono mixdown, private) plus a private aggregate device (`resources/macos-audio-tap.swift`).
- A native WebRTC AEC3 helper runs at 48 kHz in 10 ms frames, with noise suppression moderate and AGC off (`native/meeting-aec-helper/src/aec_processor.cc`). The tap feeds `ProcessReverseStream`; the mic feeds `ProcessStream`.
- The helper runs as a separate binary over stdio. https://github.com/OpenWhispr/openwhispr
- For Zoya: reverse stream = Polly PCM from our mixer + the tap of other apps. AEC runs before Silero VAD. Keep the post-TTS echo tail gate (a real device needed ~800 ms: barock.dev).

**Dependencies (need owner approval, AGENTS §3):**
- `livekit` (arm64 wheel ~9.3 MB; pin the version at build time).
- `pyobjc-framework-CoreAudio==12.2.2`, matching the pinned pyobjc: exposes `AudioHardwareCreateProcessTap`, `CATapDescription`, `AudioDeviceCreateIOProcIDWithBlock`.
- Process taps need macOS 14.2+ (unverified against Apple's page) and probably a new audio-capture permission prompt.
- Fallback: a small Swift helper over stdio, as OpenWhispr does.

**Risks / unverified:**
- **Alignment (the main risk):** the delay between the tap or mixer reference and the mic must be estimated and kept stable, or AEC3 removes little.
- AEC3 CPU at 16 kHz, and whether 16 kHz works at all (livekit defaults to 48 kHz, so resample if needed).
- Tap-to-mic latency, and behaviour when the output device changes (headphones plugged in).
- **Measure before committing:** dB of echo removed and wake rate at each music level above, plus stop latency while TTS plays on speakers.

## 6. Startup hang: Hugging Face revision checks over a black-holed IPv6 route (2026-09-14)

**Found by the coordinator during the owner's run:** `python -m zoya.main` froze after the "tracing:" line. The main thread was blocked in `sock_connect` with an IPv6 SYN_SENT to 2600:9000:… (CloudFront, the Hugging Face CDN). mlx-whisper's `load_model(repo)` calls `snapshot_download(repo)`, and huggingface-hub checks the latest revision **even when the model is cached**. This network drops IPv6 silently, so Python waited for the TCP timeout: an unbounded startup hang, breaking the "bound every blocking call" rule.

**Fix (verified):**
- `zoya/main.py` sets `HF_HUB_OFFLINE=1` before any HF/mlx import.
- Models load from `snapshot_download(repo, revision=<pinned>, local_files_only=True)`, and the local path goes to mlx-whisper.
- All models are pinned in `zoya/config.py` `MODEL_PINS` (revision + weights sha256) and downloaded once by `python -m zoya.setup_models`, which bounds calls with `HF_HUB_ETAG_TIMEOUT=5` and `HF_HUB_DOWNLOAD_TIMEOUT=30` and verifies checksums.
- A missing model fails fast: "Zoya can't start: Model … is not downloaded. Run once: .venv/bin/python -m zoya.setup_models". Smart Turn falls back to the 0.5 s silence rule.
- `tests/evals/wake_junk_replay.py` runs offline too.

**Checks:**
- `HF_ENDPOINT=http://10.255.255.1` (unroutable) → "ready in 10.3 s".
- Empty `HF_HUB_CACHE` → the fail-fast message.
- Setup → all three pinned weights "ok".

**Rule for later phases:** no model or library may reach the network at startup or on the voice path without an explicit timeout; downloads belong in setup.
