# Current Stack — primary path without AWS (2026-09-14)

> **This file is the source of truth for models, voice and providers.** It overrides the model, voice, region and AWS sections of `ZOYA_TECHNICAL_DOC.md` and the AWS-only findings in `AUDIT.md`.
>
> **Why:** the AWS account (567487920371) has **0 Bedrock quotas** and a pending support case (#178933419100474), and promotional credits most likely don't cover Claude. Zoya is built **now** without AWS. If AWS/Bedrock Claude becomes available in time, the owner will say so and we switch the provider setting — see §5.

---

## 1. What changed and what didn't

| Area | Primary path (now) | Was | Unchanged |
|---|---|---|---|
| **Agent framework** | **Strands Agents SDK** (normal `Agent`, streaming) | Strands `BidiAgent` for voice | ✅ Strands stays the core |
| **Brain (planning, tools, computer use)** | **OpenAI** or **Fireworks (Kimi etc.)** — winner of the Phase 0 benchmark | Claude Sonnet 5 on Bedrock | |
| **Screen understanding** | Vision-capable model from the same benchmark | Claude Haiku 4.5 | |
| **Router** | Rules first (0 ms) → cheapest fast model from the benchmark | Nova Micro | |
| **Listening (speech → text)** | **Local Whisper on the Mac** (`mlx-whisper`, `large-v3-turbo`, multilingual) | Nova 2 Sonic | |
| **Speaking (text → speech)** | **ElevenLabs streaming TTS**, Indian female voice picked by ear | Nova 2 Sonic `kiara` | |
| **Wake word + stop** | Local Whisper `base.en` + Silero VAD (tested 21/24, 0 false triggers) | — | ✅ D19 |
| **Memory** | Supermemory (`dreaming="instant"`, `search_mode="hybrid"`) | — | ✅ D22 |
| **Mac control, safety gate, earcons, overlay, Task Manager** | — | — | ✅ unchanged |
| **Slide images** | None | — | ✅ D21 |

## 2. Voice pipeline

```
🎙 Mic ─► Silero VAD (local, always on, low power)
            │
            ├─► Whisper base.en (local) ── "Hey Zoya" / "Zoya stop" ──► earcon (instant)
            │
            ▼  after wake: record until ~0.5 s silence
       Whisper large-v3-turbo via mlx-whisper (Apple GPU, local, multilingual) → text
            │
            ▼
       Router: rules (0 ms) ──► fast Mac action + earcon
            │ otherwise
            ▼
       Strands Agent (brain provider from config), streamed text
            │  first complete sentence → speak immediately, then the rest
            ▼
       ElevenLabs streaming TTS (Indian female voice) ─► speaker
            │ fallback if ElevenLabs fails / out of credits
            ▼
       macOS built-in voice (never silent)
```

**Rules**
- **Privacy:** microphone audio never leaves the Mac; only transcribed text goes to the brain, only reply text goes to ElevenLabs.
- **Turn-taking:** VAD end-of-speech (~0.5 s silence) ends a turn; push-to-talk (Control + Option) always available.
- **Barge-in:** "Zoya stop" (local) stops playback and the current task instantly. While Zoya speaks, the mic ignores everything except the stop phrase (echo protection); headset for the demo.
- **Confirmations:** "confirm" / "cancel" recognised locally; the safety gate (§9.9) is unchanged.
- **Conversation memory:** the Strands Agent keeps the conversation, so follow-ups ("and its population?") work.
- **Latency targets:** simple command ≈ 1 s (rules + local transcription); question → first spoken word ≈ 1.5–2 s. Earcon within 200 ms of wake always.

## 3. Brain providers in Strands

One setting, `MODEL_PROVIDER`, selects the provider; model IDs come from `.env`, chosen by the Phase 0 benchmark from the models each key actually lists (never guessed).

| Provider | Strands class | Notes |
|---|---|---|
| `openai` | `strands.models.openai.OpenAIModel` (or `openai_responses.OpenAIResponsesModel`) | Install `strands-agents[openai]`. Custom screenshot/click tools return images to vision models |
| `fireworks` | `OpenAIModel` with `client_args={"api_key": FIREWORKS_API_KEY, "base_url": <Fireworks OpenAI-compatible URL>}` | Verify base URL and tool-calling support per model in Fireworks docs; only vision models can do screen understanding |
| `bedrock` (optional, later) | `strands.models.bedrock.BedrockModel` | Only if AWS unblocks — see §5 |

All model calls go through **one adapter module** (`zoya/models.py`) so switching providers never touches agent code.

## 4. Phase 0 benchmark (decides the models)

Run before any product code, with real calls, saving raw results to `tests/evals/results/`:

| Test | What | Pass bar |
|---|---|---|
| Model list | List models available on the OpenAI and Fireworks keys | — |
| Tool calling | 40 router/tool utterances (incl. Hinglish, names) | ≥ 95% correct tool + args |
| Screen understanding | 10 real screenshots (Amazon checkout, pop-up, error dialog, WhatsApp, login page…) | Zero misread amounts/names |
| Computer-use loop | 3 short scripted click tasks on local test pages | ≥ 2/3 complete |
| Brain latency | Time to first token and first sentence | Record; prefer ≤ 1 s to first sentence |
| Whisper `large-v3-turbo` | 20 recorded commands (English + Hinglish) on this Mac | ≥ 90% word-correct on names/amounts; ≤ 0.5 s per command |
| ElevenLabs | 5 Zoya sentences (greeting, "412 rupees", Hinglish line, confirmation, long read-back); 3–5 Indian female voices | Time to first audio recorded; owner picks voice by ear |
| Cost per call | Tokens × price for each candidate | Record in DECISIONS |

## 5. If AWS / Bedrock Claude becomes available

1. Owner confirms the support case is resolved and `check AWS` passes.
2. Set `MODEL_PROVIDER=bedrock` and fill the Bedrock model IDs; run the same Phase 0 benchmark for Claude.
3. Voice stays on the Whisper + ElevenLabs pipeline unless the owner decides otherwise.
4. Update DECISIONS (D26 superseded or amended).

## 6. Hackathon requirement risk

The hackathon asks for **AWS + Strands**. Strands remains central. **AWS usage is currently blocked by the account's zero Bedrock quotas**, so the AWS part of the requirement is **at risk** until the support case is resolved. Mitigations: keep the Bedrock provider ready behind the switch; ask the organisers whether a Strands build on other providers is acceptable given the blocked account; keep the support-case evidence.

## 7. Budget

| Service | Covered by | Guardrail |
|---|---|---|
| OpenAI API | Owner's key (paid) | Set a monthly limit in the OpenAI dashboard (e.g. $50); per-task cap $2 in code |
| Fireworks | Owner's key (paid/credits) | Per-task cap in code |
| ElevenLabs | Owner's credits | Track characters used; fallback voice when exhausted |
| Supermemory | Free plan ($5 usage) | Local fallback cache |
| Whisper, VAD, earcons | Local, free | — |

## 8. AWS without Bedrock models (use now, pending a quick access check)

The zero quotas are on **Bedrock**. Other AWS services on the paid account may work and are covered by the credits. Phase 0 checks access first; build on them only if the check passes.

| AWS service | Use in Zoya | Value |
|---|---|---|
| **Amazon CloudWatch** (via Strands OpenTelemetry → AWS Distro / OTLP) | Traces of every agent turn, tool call and latency; a dashboard for judges | Shows AWS + Strands working together; debugging |
| **Amazon SNS** (email) | "Trusted contact" alerts: Zoya emails a family member when it's blocked (CAPTCHA/login) or after an order is placed | Real accessibility feature; tiny cost |
| **Amazon Polly** (neural, Indian English voice) | Second fallback voice if ElevenLabs fails (before the macOS voice) | Better than the robotic system voice |
| **AWS Secrets Manager** | Stores the OpenAI / Fireworks / ElevenLabs / Supermemory keys instead of `.env` for the demo build | Good practice, visible AWS use |
| **Amazon S3** | Stores benchmark results and demo recordings | Optional |
| **Amazon Bedrock** | Brain / vision models | ⏳ Only after the support case unblocks quotas (§5) |

