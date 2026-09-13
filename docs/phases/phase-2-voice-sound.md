# Phase 2 — Voice + sound (8–14h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
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
- Porcupine custom wake word **"Hey Zoya"** + push-to-talk **Control + Option** (§9.1).
- Voice layer: Strands `BidiAgent` + Nova 2 Sonic with `start_task` / `stop_task` / `task_status` tools (§9.2). Fallback flag: Transcribe + Polly.
- Audio engine (§9.10): preloaded WAV earcons (processed per §7.3), speech channel, working loop with ducking.
- Wire earcons: `wake`, `release`, `processing`, `success`, `error`, `stop`.
- Mic gating while Zoya speaks + local "Zoya, stop" spotter (§9.1).
- Stream audio from wake/key-down, not after speech ends (§13.5.2).

**Not in this phase:** confirmation, browser, memory, multiple tasks.

**Doc sections:** §7, §9.1, §9.2, §9.10, §13.1, §13.5.2.

**Done when**
1. ☐ "Hey Zoya" triggers from 1.5 m; the `wake` earcon plays in **< 200 ms**.
2. ☐ Zoya does **not** wake itself from its own speech (10 tries).
3. ☐ "Hey Zoya, open Spotify" → opened + `success` earcon, speech end → done ≤ 1.5 s.
4. ☐ "Zoya, stop" while Zoya is talking silences it in **< 300 ms**.
5. ☐ Push-to-talk works when the wake word is disabled.
6. ☐ There is never more than ~1 s of silence during any action (working loop covers waits).
7. ☐ Zoya speaks in the **`kiara`** feminine voice (set via `NOVA_SONIC_VOICE`), not a system/robot voice.
8. ☐ "Hey Zoya, what's the capital of Japan?" → correct spoken answer with no action taken; a follow-up ("and its population?") keeps context.
9. ☐ "Hey Zoya, what's the weather in Bangalore today?" → Zoya says it's checking, then answers (live data via a task).
10. ☐ Hinglish: "Zoya, Spotify khol do" → Spotify opens.

**Judge demo (60 s):** hands visibly off the laptop: "Hey Zoya, what's the capital of Japan?" → "Hey Zoya, open YouTube" → "Hey Zoya, write a note: call mom at six" → mid-sentence "Zoya, stop." Point out each sound's meaning.
