# Phase 2 — Voice + sound (8–14h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-2-voice-sound` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/voice.py`
- `zoya/audio.py`
- `zoya/main.py`
- `sounds/*.wav`
- `scripts/build_sounds.sh`

**Goal:** Zoya is fully hands-free — wake word, natural conversation, and the calm earcon system — on top of Phase 1's actions.

**Build**
- Wake word **"Hey Zoya"** with **local Whisper** (§9.1): Silero VAD detects speech → `faster-whisper` `base.en` (int8, CPU) transcribes the short segment with `initial_prompt="Zoya"` → lenient name match in the first 3 words; "stop" + name for the stop command + push-to-talk **Control + Option** (§9.1).
- **Voice pipeline (STACK §2):** after wake, record until ~0.5 s silence → `mlx-whisper` `large-v3-turbo` (local, multilingual) → router / Strands Agent (streamed) → first complete sentence to **ElevenLabs streaming TTS** immediately → rest follows; macOS voice fallback if ElevenLabs fails.
- Conversation kept in the Strands Agent so follow-ups work; `start_task` / `stop_task` / `task_status` as local functions the voice loop calls (§9.2 semantics).
- TTS: **Amazon Polly `Kajal` neural en-IN (ap-south-1)** primary (D33), ElevenLabs fallback, then macOS voice. Amazon Transcribe used for Hindi/Hinglish if it won the benchmark.
- Audio engine (§9.10): preloaded WAV earcons (processed per §7.3), speech channel, working loop with ducking.
- Wire earcons: `wake`, `release`, `processing`, `success`, `error`, `stop`.
- Mic gating while Zoya speaks + local "Zoya, stop" spotter (§9.1).
- Stream audio from wake/key-down, not after speech ends (§13.5.2).

**Not in this phase:** confirmation, browser, memory, multiple tasks.

**Doc sections:** §7, §9.1, §9.2, §9.10, §13.1, §13.5.2.

**Done when**
1. ☐ "Hey Zoya" triggers from 1.5 m in ≥ 9 of 10 tries by the owner's real voice; the `wake` earcon plays **< 500 ms** after the phrase ends; no trigger on 10 everyday sentences incl. "Hey Sonia".
2. ☐ Zoya does **not** wake itself from its own speech (10 tries).
3. ☐ "Hey Zoya, open Spotify" → opened + `success` earcon, speech end → done ≤ 1.5 s.
3b. ☐ Question → first spoken word ≤ 2 s (timing log).
4. ☐ "Zoya, stop" while Zoya is talking silences it in **< 300 ms**.
5. ☐ Push-to-talk works when the wake word is disabled.
6. ☐ There is never more than ~1 s of silence during any action (working loop covers waits).
7. ☐ Zoya speaks in **Polly Kajal**; with Polly disabled she falls back to ElevenLabs, then the macOS voice — never silent.
8. ☐ "Hey Zoya, what's the capital of Japan?" → correct spoken answer with no action taken; a follow-up ("and its population?") keeps context.
9. ☐ "Hey Zoya, what's the weather in Bangalore today?" → Zoya says it's checking, then answers (live data via a task).
10. ☐ Hinglish: "Zoya, Spotify khol do" → Spotify opens.

**Judge demo (60 s):** hands visibly off the laptop: "Hey Zoya, what's the capital of Japan?" → "Hey Zoya, open YouTube" → "Hey Zoya, write a note: call mom at six" → mid-sentence "Zoya, stop." Point out each sound's meaning.
