# Current Stack — primary path without AWS (2026-09-14)

> **This file is the source of truth for models, voice and providers.** It overrides the model, voice, region and AWS sections of `ZOYA_TECHNICAL_DOC.md` and the AWS-only findings in `AUDIT.md`.
>
> **Why:** the AWS account (567487920371) has **0 Bedrock quotas** and a pending support case (#178933419100474), and promotional credits most likely don't cover Claude. Zoya is built **now** without AWS. If AWS/Bedrock Claude becomes available in time, the owner will say so and we switch the provider setting — see §5.

---

## 1. What changed and what didn't

| Area | Primary path (now) | Was | Unchanged |
|---|---|---|---|
| **Agent framework** | **Strands Agents SDK** (normal `Agent`, streaming) | Strands `BidiAgent` for voice | ✅ Strands stays the core |
| **Brain (planning, tools, computer use)** | **OpenAI** (primary). Bedrock Claude when AWS unblocks. Fireworks = fallback only (D34) | Claude Sonnet 5 on Bedrock | |
| **Screen understanding** | OpenAI vision model chosen in Phase 0 | Claude Haiku 4.5 | |
| **Router** | Rules first (0 ms) → cheap OpenAI model (e.g. gpt-5.6-luna) | Nova Micro | |
| **Listening (speech → text)** | **Local Whisper on the Mac** (`mlx-whisper`, `large-v3-turbo`, multilingual) | Nova 2 Sonic | |
| **Speaking (text → speech)** | **Amazon Polly `Kajal` (neural, en-IN, ap-south-1)** — chosen by ear (D33); ElevenLabs fallback | Nova 2 Sonic `kiara` | |
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
       Amazon Polly Kajal neural (streamed audio) ─► speaker
            │ fallback: ElevenLabs, then
            ▼
       macOS built-in voice (never silent)
```

**Rules**
- **Privacy:** microphone audio never leaves the Mac; only transcribed text goes to the brain, only reply text goes to Polly (or ElevenLabs as fallback).
- **Turn-taking:** VAD end-of-speech (~0.5 s silence) ends a turn; push-to-talk (Control + Option) always available.
- **Barge-in:** "Zoya stop" (local) stops playback and the current task instantly. While Zoya speaks, the mic ignores everything except the stop phrase (echo protection); headset for the demo.
- **Confirmations:** "confirm" / "cancel" recognised locally; the safety gate (§9.9) is unchanged.
- **Conversation memory:** the Strands Agent keeps the conversation, so follow-ups ("and its population?") work.
- **Latency targets:** simple command ≈ 1 s (rules + local transcription); question → first spoken word ≈ 1.5–2 s. Earcon within 200 ms of wake always.

## 3. Brain providers in Strands

**Provider order (D34): `openai` (primary now) → `bedrock` (when AWS unblocks) → `fireworks` (fallback only, used automatically if OpenAI errors).** One setting, `MODEL_PROVIDER`, selects the primary provider; model IDs come from `.env`, chosen by the Phase 0 benchmark from the models each key actually lists (never guessed).

| Provider | Strands class | Notes |
|---|---|---|
| `openai` | `strands.models.openai.OpenAIModel` (or `openai_responses.OpenAIResponsesModel`) | Install `strands-agents[openai]`. Custom screenshot/click tools return images to vision models |
| `fireworks` | `OpenAIModel` with `client_args={"api_key": FIREWORKS_API_KEY, "base_url": <Fireworks OpenAI-compatible URL>}` | Verify base URL and tool-calling support per model in Fireworks docs; only vision models can do screen understanding |
| `bedrock` (optional, later) | `strands.models.bedrock.BedrockModel` | Only if AWS unblocks — see §5 |

All model calls go through **one adapter module** (`zoya/models.py`) so switching providers never touches agent code.

**Privacy rule — `store=false` on every OpenAI request (D36, mandatory):** Zoya's requests contain screenshots, voice commands, addresses and orders, so nothing may be stored in OpenAI's logs.
- `OpenAIResponsesModel`: keep `stateful=False` (the default). Strands then sends `"store": False` on every request (verified in `strands/models/openai_responses.py`, where `store` is set from `stateful` after `params`). Never set `stateful=True`.
- `OpenAIModel` (Chat Completions): pass `params={"store": False, ...}`.
- Any direct `openai` SDK call outside Strands (router, benchmarks, scripts): pass `store=False` explicitly.
- Enforced in one place: `zoya/models.py` builds every OpenAI client/model; a unit test fails if any OpenAI config lacks `store=False` / `stateful=False`.
- Owner check after Phase 1: platform.openai.com → **Logs** shows no stored Zoya requests.

## 4. Phase 0 benchmark (decides the models)

Run before any product code, with real calls, saving raw results to `tests/evals/results/`:

| Test | What | Pass bar |
|---|---|---|
| Model list | List models available on the OpenAI key (Fireworks only to confirm the fallback works) | — |
| Tool calling | 40 router/tool utterances (incl. Hinglish, names) | ≥ 95% correct tool + args |
| Screen understanding | 10 real screenshots (Amazon checkout, pop-up, error dialog, WhatsApp, login page…) | Zero misread amounts/names |
| Computer-use loop | 3 short scripted click tasks on local test pages | ≥ 2/3 complete |
| Brain latency | Time to first token and first sentence | Record; prefer ≤ 1 s to first sentence |
| Whisper `large-v3-turbo` | 20 recorded commands (English + Hinglish) on this Mac | ≥ 90% word-correct on names/amounts; ≤ 0.5 s per command |
| Voice | ✅ Decided: Polly Kajal neural (D33). Phase 0 only measures time-to-first-audio on 5 Zoya sentences incl. Hinglish | Record latency |
| Cost per call | Tokens × price for each candidate | Record in DECISIONS |

## 5. If AWS / Bedrock Claude becomes available

1. Owner confirms the support case is resolved and `check AWS` passes.
2. Set `MODEL_PROVIDER=bedrock` and fill the Bedrock model IDs; run the same Phase 0 benchmark for Claude.
3. Voice stays on the Whisper + ElevenLabs pipeline unless the owner decides otherwise.
4. Update DECISIONS (D26 superseded or amended).

## 6. Hackathon requirement risk

The hackathon asks for **AWS + Strands**. Strands remains central. **AWS usage is currently blocked by the account's zero Bedrock quotas**, so the AWS part of the requirement is **at risk** until the support case is resolved. Mitigations: keep the Bedrock provider ready behind the switch; ask the organisers whether a Strands build on other providers is acceptable given the blocked account; keep the support-case evidence.

## 7. Budget (keep usage very low)

Verified prices, 2026-09-14 (per 1M tokens, input / output): **gpt-5.6-luna $0.20 / $1.20**, **gpt-5.6-terra $2.00 / $12.00**, gpt-5.6-sol $4.00 / $20.00 (promo). Fireworks fallback: DeepSeek V4 Flash $0.22 / $0.66.

| Job | Model | Why |
|---|---|---|
| Common commands | Rules (no model) | Free, instant |
| Router fallback, summaries, simple answers | gpt-5.6-luna | Cheapest |
| Planning, screen understanding, computer use, confirmations | gpt-5.6-terra | Quality where it matters |

**Estimated total for the hackathon: ~$8–15** (≈800 brain calls, ≈150 computer-use tasks, ≈300 screen descriptions, rehearsals). Voice (Polly) ≈ $1 from AWS credits.

**Guardrails:** OpenAI monthly budget **$15** in the dashboard; hard stop **$0.50 per task** in code; page text before screenshots; keep only the last 2 screenshots; Phase 0 benchmark uses small test sets (< $1).

| Service | Covered by | Guardrail |
|---|---|---|
| OpenAI API | Owner's key | $15 monthly budget; $0.50 per-task cap |
| Fireworks (fallback) | Owner's key | Only used when OpenAI fails; small top-ups |
| AWS (Polly, DynamoDB, SNS…) | $120 credits | Budget alarm $75 |
| ElevenLabs (fallback voice) | 10,000 characters | Fallback only |
| Supermemory | Free plan | Local fallback copy in DynamoDB |
| Whisper, VAD, earcons | Local, free | — |

## 8. AWS services in use (everything except Bedrock models)

**Access verified 2026-09-14** on account 567487920371 with tiny test calls (`zoya` profile, `ap-south-1` Mumbai — 23 ms from Bangalore): ✅ Polly (Kajal neural en-IN; Kajal *generative* only in `us-east-1`), Transcribe, Translate, Rekognition DetectText, Textract, SNS, DynamoDB, S3, Secrets Manager, SSM Parameter Store, CloudWatch Logs, X-Ray, Location Service, Lambda, EventBridge Scheduler. ❌ Bedrock (0 quotas).

**Rule:** use AWS wherever it does a real job for the user. Region `ap-south-1` for everything except Polly generative (`us-east-1`).

| AWS service | Job in Zoya | Phase |
|---|---|---|
| **Amazon Polly** (Kajal, neural, en-IN, Mumbai) | **Zoya's voice** (D33); ElevenLabs fallback, then macOS voice | 2 |
| **Amazon Transcribe** (streaming, en-IN / hi-IN) | Benchmarked vs local Whisper for Hinglish; used as the Hindi/Hinglish recogniser or fallback if it wins | 0, 2 |
| **Amazon Translate** | Normalises Hindi commands to English before the router ("Spotify khol do" → "open Spotify") | 1 |
| **AWS Secrets Manager** | Holds OpenAI / Fireworks / ElevenLabs / Supermemory keys; `.env` only names the secret | 1 |
| **Amazon DynamoDB** | Task history, confirmation audit log (who confirmed what, amount, time), order history, local copy of key memories (fallback when Supermemory is down) | 1, 3, 4 |
| **Amazon CloudWatch + AWS X-Ray** (Strands OpenTelemetry → ADOT/OTLP) | Traces of every agent turn and tool call, latency metrics, judge dashboard | 1, 7 |
| **Amazon Rekognition DetectText** | Fast OCR of the screen; **double-checks amounts and names on the checkout page before a confirmation is spoken** (safety) | 3, 5 |
| **Amazon Textract** | "Read this PDF / letter / bill to me" — document text and tables read aloud | 5 |
| **Amazon SNS** (email) | Trusted-contact alerts: Zoya is blocked (CAPTCHA/login), order placed, emergency "tell my sister I need help" | 4 |
| **Amazon S3** | Stores created documents for sharing (pre-signed link sent via SNS), benchmark results, demo recordings | 0, 6 |
| **Amazon EventBridge Scheduler** | Reminders and routines ("remind me to take my medicine at 9 pm") → one-time schedule with the templated SNS Publish target (no Lambda, D67) → email; Zoya speaks it from a local timer | 6 |
| **Amazon Location Service** | "What's the nearest pharmacy?" / place search tool | 4 |
| **Amazon Bedrock** | Brain / vision models | ⏳ after the support case (§5) |

## 9. Creating documents: docs, sheets, slides — "make anything"

**How HeyClicky-style apps do it (researched 2026-09-14):** HeyClicky's current agent features are closed source. Its best-known open-source clone, **Glide** (shujanshaikh/glide), does **not** click around Google Sheets in a browser; it calls **app APIs through Composio** (Google Docs, Notion, Gmail, Slack…) so the model creates content directly via each app's API.

**Zoya's approach — three tiers, fastest and most reliable first:**

| Tier | How | Formats | When |
|---|---|---|---|
| **1. Local files (default)** | `document_agent` writes real files with libraries: **python-docx** (Word), **openpyxl** (Excel, incl. formulas), **python-pptx** (slides), **reportlab** (PDF), CSV/Markdown. Saves to `~/Documents/Zoya/`, opens in Pages/Numbers/Keynote/Word/Excel by bundle id, then **reads a summary aloud** ("Your budget sheet has 12 rows; total 18,400 rupees") | .docx .xlsx .pptx .pdf .csv .md | Every "make me a document / sheet / presentation" request |
| **2. Share / cloud copy** | Upload to **S3**, send a pre-signed link via **SNS** email; optionally Google Docs/Sheets via the Google APIs (or Composio) once the user connects an account | Same files, shareable | "Send it to my teacher", "put it in Google Sheets" |
| **3. Browser UI automation (last resort)** | `browser_agent` / `computer_agent` operates Google Sheets or Docs in Chrome | Anything the web app does | Only when the user explicitly wants to work inside an existing online doc |

**Why not browser-first:** typing into Google Sheets' canvas grid by clicks is slow (many screenshots), fragile, expensive, and hard to verify for a blind user. Files + APIs are exact, fast and can be read back reliably.

**Reading back is part of creating:** after every document, Zoya speaks the structure (title, sections or sheet columns, row count, totals) and offers "read section 2" / "read row 5".
