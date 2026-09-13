# Phase 0 — Foundations (0–2h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-0-foundations` · **Depends on:** nothing

**Files this phase creates:**
- `pyproject.toml` (pinned versions)
- `zoya/models.py` (provider adapter: `openai` | `fireworks` | `bedrock`)
- `scripts/check_providers.py`
- `tests/evals/router_eval.py`, `tests/evals/screen_benchmark.py`, `tests/evals/voice_benchmark.py`
- `tests/evals/results/` (raw benchmark outputs)
- `.env` (local only, never committed)

**Goal:** every provider, local model and macOS permission Zoya needs is proven on the demo Mac, and the models are **chosen by benchmark**, before product code exists.

**Build**
- Pin dependencies after verifying on PyPI/docs: `strands-agents[openai,otel]`, `openai`, `elevenlabs`, `mlx-whisper`, `faster-whisper`, plus the existing list.
- `zoya/models.py`: one function returning a Strands model for `MODEL_PROVIDER` (STACK §3). Fireworks via `OpenAIModel` with its OpenAI-compatible base URL (verify in Fireworks docs).
- `scripts/check_providers.py`: lists models on the OpenAI and Fireworks keys; one tiny call each; ElevenLabs voices list; Supermemory ping. Never prints keys.
- **Benchmarks (STACK §4):** tool calling (40 utterances), screen understanding (10 screenshots), 3 computer-use loops on local test pages, brain latency, Whisper `large-v3-turbo` on 20 recorded commands, ElevenLabs time-to-first-audio on 5 sentences with 3–5 Indian female voices (save audio files for the owner).
- Record chosen `BRAIN_MODEL`, `VISION_MODEL`, `ROUTER_MODEL`, `ELEVENLABS_VOICE_ID` in `.env` and the reasoning + numbers in `docs/DECISIONS.md`.
- Set spending limits: OpenAI dashboard monthly limit; note Fireworks/ElevenLabs balances.
- **AWS voice/speech benchmark (STACK §8):** Polly Kajal (neural, generative) vs ElevenLabs on the same 5 sentences; Amazon Transcribe (en-IN/hi-IN) vs local Whisper on the 20 recorded commands. Decide primary vs fallback and record in DECISIONS.
- Create S3 bucket for benchmark results; store results there too.
- Grant Microphone, Accessibility, Screen Recording to the terminal/Python that will run Zoya.
- Pick the earcon pack: `sounds/audition.sh` (`zen` or `soft`).

**Not in this phase:** agent logic, voice loop, UI.

**Done when**
1. ☐ `check_providers.py` lists models and gets a reply from each provider; no key printed.
2. ☐ All STACK §4 benchmarks run; results saved; models + voice chosen and recorded in DECISIONS.
3. ☐ Owner has listened to the ElevenLabs samples and picked the voice.
4. ☐ Spending limits set.
5. ☐ `screencapture` and a test click work without permission errors.
6. ☐ Earcon pack chosen.

**Judge demo (45 s):** show the benchmark table: "we tested N models on tool use, screen reading and speed, and picked these with evidence" + play the chosen Zoya voice.
