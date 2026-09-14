"""Regression replays for Phase 2 live bugs: junk after a wake, background music, follow-ups.

Owner's live run: "Hi Zoya!" → the wake chime (or Spotify) was captured as the command and
transcribed "you" / "감사합니다" → the wake was used up and the real command ignored. Root cause
confirmed with this replay: fails on 0f24774, passes after a8fcd83.

Feeds [synthetic "Hey Zoya"] → [junk: the wake chime or synthetic music] → [a command] through
the real VoiceLoop (VAD, spotter, turbo) with dispatch mocked. Needs the GPU models and macOS
`say` + ffmpeg, so it is an eval, not a pytest.
Usage: .venv/bin/python -u tests/evals/wake_junk_replay.py
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"  # pinned models from the cache only (AUDIT §6)

import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from zoya import audio, orchestrator, speech, voice  # noqa: E402
from zoya.config import MIC_SAMPLE_RATE_HZ, SOUNDS_DIR  # noqa: E402

SUBPROCESS_TIMEOUT_S = 30
REAL_DUCK, REAL_RESTORE = audio.duck, audio.restore
FAKE_VOLUME = 60
OSASCRIPT_DELAY_S = 0.09  # measured osascript cost
WAIT_BEFORE_COMMAND_S = 3.0  # owner: volume came back before they spoke
RADIO_GAIN = 0.15  # background vocals quieter than the user at the mic (louder defeats the gate)
MAX_DISPATCH_DELAY_S = 2.0  # endpoint 0.5 s + turbo ~0.7 s + slack
RATE = MIC_SAMPLE_RATE_HZ


def synthesize(text: str, folder: Path) -> np.ndarray:
    aiff, wav = folder / "clip.aiff", folder / "clip.wav"
    subprocess.run(
        ["say", "-v", "Samantha", "-o", aiff, text], check=True, timeout=SUBPROCESS_TIMEOUT_S
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", aiff, "-ar", str(RATE), "-ac", "1", wav],
        check=True,
        timeout=SUBPROCESS_TIMEOUT_S,
    )
    return sf.read(wav, dtype="float32")[0]


def chime() -> np.ndarray:
    samples, rate = sf.read(SOUNDS_DIR / "wake.wav", dtype="float32")
    positions = np.arange(0, len(samples), rate / RATE)
    return (np.interp(positions, np.arange(len(samples)), samples) * 0.5).astype("f4")


def music(rng: np.random.Generator, seconds: float = 3.0) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220, 277, 330)) * 0.05
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-((t % 0.5) * 20)) * 0.3
    hat = rng.standard_normal(len(t)) * np.exp(-((t % 0.25) * 60)) * 0.05
    return (chord + kick + hat).astype("f4")


def replay(loop: voice.VoiceLoop, stream: np.ndarray) -> None:
    blocks = stream[: len(stream) // voice.VAD_BLOCK * voice.VAD_BLOCK].reshape(-1, voice.VAD_BLOCK)
    started = time.monotonic()
    for index, block in enumerate(blocks):
        due = started + (index + 1) * voice.BLOCK_S
        if (lag := due - time.monotonic()) > 0:
            time.sleep(lag)
        loop._on_block(due, block)


def fresh(loop: voice.VoiceLoop) -> None:
    loop.segment, loop.awaiting_command_until, loop.follow_up_pending = None, 0.0, False
    loop.loudness.clear()


def replay_ducked(loop: voice.VoiceLoop, user: np.ndarray, background: np.ndarray) -> list[int]:
    """Background at the mic follows a fake system volume, so ducking really quiets it."""
    volume = {"level": FAKE_VOLUME, "history": []}

    def fake_volume(script: str) -> str:
        time.sleep(OSASCRIPT_DELAY_S)
        if script.startswith("output volume"):
            return str(volume["level"])
        volume["level"] = int(script.rsplit(" ", 1)[-1])
        volume["history"].append(volume["level"])
        return ""

    audio._volume = fake_volume
    audio.duck, audio.restore = REAL_DUCK, REAL_RESTORE
    started = time.monotonic()
    for index in range(len(user) // voice.VAD_BLOCK):
        due = started + (index + 1) * voice.BLOCK_S
        if (lag := due - time.monotonic()) > 0:
            time.sleep(lag)
        piece = slice(index * voice.VAD_BLOCK, (index + 1) * voice.VAD_BLOCK)
        gain = volume["level"] / FAKE_VOLUME
        loop._on_block(due, (user[piece] + background[piece] * gain).astype("f4"))
    time.sleep(1.0)
    audio.duck = audio.restore = lambda: None
    return volume["history"]


def main() -> int:
    audio.duck = audio.restore = lambda: None  # never touch the Mac's volume from an eval
    # Silent eval: no earcons, no Polly. A None task used to read as "three tasks running" and
    # Zoya said the FULL_MESSAGE aloud on every dispatch (coordinator, 2026-09-15).
    audio.earcon = lambda *_a: None
    audio.engine = lambda: SimpleNamespace(
        one_shot_at=0.0, silence_all=lambda: None, set_speech_gain=lambda _g: None
    )
    speech.narrate = lambda *_a, **_k: None
    speech.is_speaking = lambda: False
    dispatched: list[tuple[float, str]] = []

    def start_task(text: str, _pre: object = None, on_done: object = None) -> SimpleNamespace:
        dispatched.append((time.monotonic(), text))
        if on_done:  # Zoya "answered": opens the follow-up window
            decision = orchestrator.RouteDecision("orchestrator", text=text)
            result = orchestrator.CommandResult("replay", decision, "Which note?", True, {})
            threading.Thread(target=on_done, args=(result,), daemon=True).start()  # as in the app
        return SimpleNamespace(shared=False)

    orchestrator.start_task = start_task
    rng = np.random.default_rng(1)
    with tempfile.TemporaryDirectory() as folder:
        wake = synthesize("Hey Zoya", Path(folder))
        command = synthesize("What's the capital of Japan?", Path(folder))
        follow_up = synthesize("Just hello", Path(folder))
        radio = synthesize(
            "This is the evening news. The weather was warm with rain in the afternoon, traffic "
            "was heavy and trains were delayed. Now here is a song that everybody loves.",
            Path(folder),
        )
    loop = voice.VoiceLoop()
    silence = lambda s: (rng.standard_normal(int(s * RATE)) * 0.002).astype("f4")  # noqa: E731
    results: list[bool] = []

    # 1. Junk after a wake (chime / music) must not swallow the command.
    for name, junk in (("chime", chime()), ("music", music(rng))):
        dispatched.clear()
        fresh(loop)
        parts = [silence(0.5), wake, silence(0.8), junk, silence(0.8), command, silence(1.5)]
        replay(loop, np.concatenate(parts))
        results.append(any("japan" in text.lower() for _, text in dispatched))
        print(f"junk={name}: {[t for _, t in dispatched]} → {'PASS' if results[-1] else 'FAIL'}")

    # 2. Background vocals under the command: it must end when the user stops, not at the 15 s cap.
    dispatched.clear()
    fresh(loop)
    user = np.concatenate([silence(4.0), wake, silence(0.6), command, silence(8.0)])
    background = np.resize(radio, len(user)) * RADIO_GAIN
    started = time.monotonic()
    replay(loop, user + background)
    command_end_s = (4.0 * RATE + len(wake) + 0.6 * RATE + len(command)) / RATE
    late_s = dispatched[0][0] - started - command_end_s if dispatched else float("inf")
    results.append(late_s <= MAX_DISPATCH_DELAY_S)
    print(
        f"radio: dispatched {late_s:.1f} s after speech end → {'PASS' if results[-1] else 'FAIL'}"
    )

    # 3. Follow-up: after Zoya answers, the next sentence needs no wake word.
    dispatched.clear()
    fresh(loop)
    replay(
        loop,
        np.concatenate(
            [silence(3.5), wake, silence(0.6), command, silence(3.0), follow_up, silence(2.0)]
        ),
    )
    texts = [text for _, text in dispatched]
    results.append(len(texts) == 2 and "hello" in texts[1].lower())
    print(f"follow-up: {texts} → {'PASS' if results[-1] else 'FAIL'}")

    # 4. "Hey Zoya", a 3 s pause over music, then the command: stay ducked through the wait.
    dispatched.clear()
    fresh(loop)
    user = np.concatenate(
        [silence(4.0), wake, silence(WAIT_BEFORE_COMMAND_S), command, silence(3.0)]
    )
    history = replay_ducked(loop, user, np.resize(radio, len(user)) * RADIO_GAIN)
    texts = [text for _, text in dispatched]
    one_duck = history[:1] == [round(FAKE_VOLUME * 0.3)] and history[-1:] == [FAKE_VOLUME]
    results.append(any("japan" in t.lower() for t in texts) and one_duck and len(history) == 2)
    print(f"wait-over-music: {texts}, volume {history} → {'PASS' if results[-1] else 'FAIL'}")

    # 5. "Hey Zoya" said again inside the wait window is not a command.
    dispatched.clear()
    fresh(loop)
    replay(
        loop,
        np.concatenate(
            [silence(3.5), wake, silence(1.2), wake, silence(1.2), command, silence(2.0)]
        ),
    )
    texts = [text for _, text in dispatched]
    results.append(len(texts) == 1 and "japan" in texts[0].lower())
    print(f"repeated-wake: {texts} → {'PASS' if results[-1] else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
