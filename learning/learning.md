# Learning Zoya — what we built, why, and what we learned

Zoya is a voice-first agent that operates a Mac for blind and low-vision people. This file explains the architecture and the story of phases 0–2 in plain words. Decision numbers like **D48** point to `docs/DECISIONS.md`.

---

## 1. Architecture at a glance

```
 Mic ──► Wake / stop spotter ──► End-of-turn detector ──► Speech-to-text ──► Router
        (Silero VAD +            (Smart Turn v3.2)        (Whisper turbo,     │
         Whisper base.en)                                  on the Mac)        │
                                                                              ▼
                                              ┌──────────── rules match? ─────────────┐
                                              │ yes (0 ms, no AI)                     │ no
                                              ▼                                       ▼
                                        Fast tool (T0)                    Cheap AI router (gpt-5.6-luna)
                                     open app / URL / note /                          │
                                     music / volume / time                            ▼
                                              │                          Brain agent (gpt-5.6-terra, Strands)
                                              │                          streams an answer, calls tools
                                              └───────────────┬───────────────────────┘
                                                              ▼
                          Speech out: Amazon Polly Kajal ──► ElevenLabs Tara ──► macOS voice
                          + earcons (short sounds: wake, success, error, stop…)
```

| Layer | What we use | Why |
|---|---|---|
| Agent framework | **Strands Agents SDK** (Python), one Agent per task | Tools, hooks, streaming, OpenTelemetry built in |
| Models | **OpenAI**: `gpt-5.6-luna` (router, cheap) and `gpt-5.6-terra` (brain, vision) — chosen by benchmark (D40) | AWS Bedrock had 0 quota; OpenAI gave the best capability for the money |
| Provider adapter | `zoya/models.py` → `get_model(role)` | One place that forces `store=False` (privacy, D36), `reasoning_effort="none"` (needed for tools, D43), timeouts and retries |
| Hearing | Silero VAD → Whisper `base.en` (wake / "stop") → Smart Turn (is the user done?) → Whisper `large-v3-turbo` (the command), all **local** on the Mac's GPU via mlx | Private, free, fast (D48, D51, D55) |
| Speaking | **Amazon Polly Kajal** (Indian English) → ElevenLabs → macOS `say` | Owner picked Kajal by ear; always a fallback so Zoya is never silent (D33, D41) |
| Mac control | Tiers **T0** direct (open, AppleScript with fixed scripts) → T1 Accessibility → T2 browser DOM → T3 pixel clicks | Fastest and most reliable first (D6) |
| AWS | Polly, Translate (Hindi → English), Secrets Manager (API keys), DynamoDB (task history), S3 (benchmarks), X-Ray (traces) | Real AWS use while Bedrock is blocked (D30) |
| Security | IAM user `zoya-app` with least privilege, `ap-south-1` only (D49); `store=False` on every OpenAI call; no free-form scripts | The model reads untrusted web/screen text, so a hijacked model must not reach anything dangerous |

**Team workflow:** one coordinator session reviews; each phase is built by a separate Claude Opus session in WezTerm on `main` (D47). Tests only for safety, money, privacy and parsers (D37); everything else is proven on the real Mac against each phase's "Done when" list.

---

## 2. Phase 0 — Foundations: prove everything before writing product code

**Goal:** every provider, model and permission works, and models are chosen by evidence, not guesswork.

**What was built**
- Pinned all dependency versions; `zoya/models.py` provider adapter; `zoya/config.py` with the $15/month budget and $0.50 per-task cap.
- `scripts/check_providers.py`: lists OpenAI models, pings Fireworks, ElevenLabs, Supermemory and Polly, and never prints a key.
- A privacy test that fails if any OpenAI config could store data.

**Benchmarks and results**
| Test | Result | Decision |
|---|---|---|
| Tool calling, 40 commands incl. Hinglish | luna 40/40, terra 40/40; luna ~18× cheaper | Router = luna, brain = terra (D40) |
| Screen reading, 10 screenshots | terra 10/10, no misread amounts | Vision = terra |
| Click tasks on local pages | 3/3 | — |
| Brain speed | first sentence ~1.6–1.9 s (misses 1 s target) | Simple commands must skip the AI (D44) |
| Voice speed | Polly 0.15 s vs ElevenLabs 0.57 s to first audio | Polly primary (D41) |
| Speech-to-text on **owner's 20 recordings** | Whisper 95.8%, 0.77 s; Transcribe 91.7%, 2.2 s | Whisper primary (D48) |

**Problems found in review and how we fixed them**
- `.env` had no model IDs, one benchmark file was missing, and results weren't saved → the builder was sent back, and it fixed them.
- **`get_model()` crashed with tools** (OpenAI 400: tools need `reasoning_effort="none"`) → fixed in the adapter and verified with a live tool call.
- Whisper writes Hindi in **Devanagari**, not Roman letters → the router must translate (D42).
- AWS was running as **root** → created least-privilege `zoya-app`, and root became `zoya-admin` (D49).
- The Transcribe script got a 403 reading a private S3 file → it now reads through the S3 client.

**Lesson:** benchmarks with real data (the owner's voice) beat assumptions; synthetic audio hid real behaviour.

---

## 3. Phase 1 — Brain + fast actions: typed commands that act within a second

**Goal:** type "open Spotify" → the Mac does it in ≤ 1 s and Zoya says what she did.

**What was built**
- `events.py`: an event contract (narrate, earcon, task, confirmation, overlay) that every later phase builds on.
- `router.py`: Devanagari → Amazon Translate → **regex rules** (English + Hinglish) → luna with a JSON schema if no rule matches.
- `tools/fast.py` + `tools/notes.py`: open app / URL, notes, volume, mute, time.
- `orchestrator.py`: a fresh Strands Agent per task, **cost cap $0.50 and 40 tool calls** enforced by a hook *before* each model call, a timing log (JSONL) and an OpenTelemetry span.
- `speech.py`: the Polly → ElevenLabs → `say` chain. `aws.py`: cached clients with 2 s timeouts. A text REPL (`python -m zoya`).

**Results:** "open Spotify" 48 ms, "open youtube.com" 38 ms, "write a note" 155 ms (all rules, no AI). Router eval 40/40 system, 97.4% model-only.

**Problems found in review and how we fixed them**
- 🔴 **Security:** the AppleScript tool blocked `do shell script` with a regex, but AppleScript's line-continuation `¬` slipped past it, which meant shell commands could run. **Fix:** deleted free-form AppleScript entirely and replaced it with `media_control(action, app)`, which only runs fixed scripts. Regression tests added.
- **Slow complex commands** (~9 s): "plan a trip **and** book" still waited for the AI router → multi-step words now go straight to the brain.
- **30-minute hang:** the OpenAI SDK defaults to a 600 s timeout with 2 retries → per-role timeouts (router 10 s, brain 60 s) and 1 retry.

**Lesson:** rules first gives ~0 ms for common commands; never try to secure code execution with a blocklist, remove the capability instead; bound every network call.

---

## 4. Phase 2 — Voice + sound: fully hands-free

**Goal:** "Hey Zoya…" → natural conversation, calm earcons, interruptible with "Zoya, stop".

**What was built**
- `voice.py`: the listening loop (wake word, stop spotter, push-to-talk **fn + Shift**, 8 s follow-up window with no wake word).
- `audio.py`: preloaded `zen` earcons, a speech channel, a "working" loop, and ducking of other audio while Zoya listens.
- Streamed spoken answers: the first sentence is spoken as soon as it's ready; interrupted answers can "continue".
- `tools/weather.py`: live weather via Open-Meteo, with no key, fixed hosts and 3 s timeouts (D50).

**How we made it smooth (the research loop)**
Every complaint from the owner's live runs was **replayed from recordings** before fixing, so fixes were based on evidence, not guesses:

| Owner noticed | Root cause found | Fix |
|---|---|---|
| Stop checks lagged 5 s | faster-whisper on CPU takes 207–530 ms per check | Run base.en on the Apple GPU with mlx: 25–58 ms (D51) |
| "Hey Sonia"/"soya milk" woke Zoya | Whisper's "Zoya" hint pulls sound-alikes toward the name | Wake only on a whole utterance, name first or after a greeting; the bigger model **vetoes** sound-alikes (Zoe/Joya/Sonia) → 12/13 wakes, 0 false (D54) |
| "Hears 'you' / Korean, then ignores me" | The wake chime or Spotify became the "command" and used up the wake | Junk no longer consumes the wake; a replay test guards it |
| Commands 7–13 s late with music | Music vocals counted as speech, so the mic never closed | Voice must be ≥ 2× background loudness → dispatched ~1.1 s after speech ends (D53) |
| Zoya stopped herself | Her own speech was heard as "stop" | Removed cross-window memory, added a 2 s stop cooldown, echo gate on self-wake |
| Waiting for silence felt slow | Fixed 0.5 s silence rule | **Smart Turn v3.2** (small local model) decides when you're done → 266–309 ms (D55) |
| Froze at startup | Hugging Face update check hanging on a broken IPv6 route | Models load offline (`HF_HUB_OFFLINE=1`); downloads become a setup step |

**What's still open**
- **Laptop speakers:** the mic hears Zoya's voice and music, so wake and stop fail. The real fix is echo cancellation (WebRTC AEC3, like OpenWhispr) — running as a **separate parallel session** (D56). Use a headset for the demo.
- Question → first spoken word is ~3.5 s against a 2 s target, mostly model start-up time.
- "Play <song> on Spotify" needs song search → Phase 4.

**Lessons:** always test with the real voice in the real room; replay recordings to find the root cause before fixing; offline accuracy ≠ live accuracy; small local models (VAD, Smart Turn, base.en) make voice feel fast, while the big model is only used where it adds value.

---

## 5. Cost and token-saving habits (applies to every phase)
- Rules before AI: most common commands cost **0 tokens**.
- Cheap model for routing, expensive model only for thinking.
- OpenAI prompt caching: keep the system prompt and tool list **identical and in a fixed order**; changing text goes last. Cached input is up to 90% cheaper (1,024+ tokens on GPT-5.6). `cached_tokens` is logged.
- Timeouts everywhere, a per-task cost cap, and a monthly budget.
