"""Echo cancellation evidence (D62): laptop-speaker echo, then wake/stop replays with AEC off vs on.

1. `record` — plays Zoya's Polly voice through the real mixer and "music with vocals" through a
   separate process (so it reaches AEC only via the Core Audio tap) on the MacBook speakers at the
   current volume, while the mic records. Saves raw mic + the reference exactly as the live
   capture path pairs them (logs/aec/, git-ignored), and reports ERLE, AEC ms per block and CPU.
2. `replay` — mixes the owner's real clips (logs/wake_clips*, local only) into that recorded echo
   at music/voice RMS 0.10 / 0.29 / 0.58 / 1.16, runs AEC off vs on, and scores wakes (base.en
   + turbo veto, as VoiceLoop), false wakes (D54 negatives and echo alone) and "Zoya, stop"
   (synthetic voices over Zoya's recorded speech, checked like the stop spotter).

Needs the GPU models, macOS `say` + ffmpeg and the speakers, so it is an eval, not a pytest.
Usage: .venv/bin/python -u tests/evals/aec_replay.py record [volume] | replay | barge-in
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"  # pinned models from the cache only (AUDIT §6)

import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from zoya import aec, config, voice  # noqa: E402
from zoya.config import (  # noqa: E402
    AEC_MIC_DELAY_BLOCKS,
    DUCK_FRACTION,
    LOG_DIR,
    MIC_SAMPLE_RATE_HZ,
    STT_MODEL_REPO,
    WAKE_MODEL,
    WAKE_WINDOW_S,
    load_env,
)

RATE = MIC_SAMPLE_RATE_HZ
OUT = LOG_DIR / "aec"
RESULTS = Path(__file__).parent / "results" / "aec_replay.json"
SUBPROCESS_TIMEOUT_S = 60
VOLUME = 70  # speaker volume for `record`; the previous volume and mute state are restored
STORY = (
    "Here is a short story. Once upon a time in a small village near the mountains, there lived "
    "an old potter who made the most beautiful blue pots. Every morning she walked to the river "
    "to collect clay, and every evening the children gathered to watch her shape it on the wheel. "
    "One day a traveller asked her secret, and she smiled and said that the river told her."
)
VOCALS = (
    "This is the evening news. The weather was warm with rain in the afternoon, traffic was heavy "
    "and trains were delayed. Now here is a song that everybody loves, dancing all night long."
)
CONVERGE_S = 3.0  # skip AEC3's first seconds when measuring ERLE
LEVELS = (0.10, 0.29, 0.58, 1.16)  # music RMS / voice RMS (AUDIT §5)
PRE_ROLL_S = 5.0  # background playing before the user speaks, as in real life
TAIL_S = 0.6
# Clean owner clips (base.en woke on them with no background) and negatives (incl. D54's).
WAKES = {
    "wake_clips_session2": [1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13],
    "wake_clips": [1, 2, 4, 5, 7, 10, 11, 12, 15, 17],
}
NEGATIVES = {
    "wake_clips_session2": list(range(15, 29)),
    "wake_clips": [13, 14, 16, 18, 19, 20, 21],
}
STOP_VOICES = ("Samantha", "Daniel", "Karen", "Rishi", "Moira")
STOP_PHRASES = ("Zoya, stop", "Zoya stop")
STOP_CHECK_AFTER_S = 0.3  # the stop spotter re-reads the last 2 s every 150 ms


def say(text: str, voice_name: str, folder: Path) -> np.ndarray:
    aiff, wav = folder / "say.aiff", folder / "say.wav"
    run = {"check": True, "timeout": SUBPROCESS_TIMEOUT_S}
    subprocess.run(["say", "-v", voice_name, "-o", aiff, text], **run)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", aiff, "-ar", str(RATE), wav], **run)
    return sf.read(wav, dtype="float32")[0]


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples**2)) + 1e-12)


def erle_db(raw: np.ndarray, cleaned: np.ndarray) -> float:
    return round(20 * np.log10(rms(raw) / rms(cleaned)), 1)


def music_file(folder: Path) -> Path:
    vocals = say(VOCALS, "Samantha", folder)
    t = np.arange(len(vocals) * 2) / RATE
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220, 277, 330)) * 0.05
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-((t % 0.5) * 20)) * 0.3
    song = (chord + kick + np.resize(vocals, len(t)) * 0.6).astype("f4")
    path = folder / "music.wav"
    sf.write(path, song / np.abs(song).max() * 0.8, RATE)
    return path


def osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S
    )
    return result.stdout.strip()


def play_sources(mark) -> dict:  # noqa: ANN001
    """Zoya's Polly voice through the mixer, then music from another process (via the tap)."""
    from zoya import speech

    spans = {}
    with tempfile.TemporaryDirectory() as folder:
        song = music_file(Path(folder))
        time.sleep(1.0)
        start = mark()
        speech.narrate(STORY)
        time.sleep(1.0)
        speech.wait_until_quiet()
        spans["tts"] = (start, mark())
        time.sleep(0.5)
        start = mark()
        subprocess.run(["afplay", song], check=True, timeout=SUBPROCESS_TIMEOUT_S)
        spans["music"] = (start, mark())
        time.sleep(0.5)
    return spans


def record(volume: int) -> int:
    """The live capture path (aec.LiveCanceller on a consumer thread) on the real speakers."""
    import queue
    import threading

    import sounddevice as sd

    from zoya import audio

    load_env()
    OUT.mkdir(parents=True, exist_ok=True)
    audio.engine()  # starts the tap too
    far_end = aec.reference()
    live = aec.LiveCanceller(far_end)
    blocks: queue.Queue = queue.Queue()
    raw, refs, cleaned, cost = [], [], [], []
    pair = live._far_end
    live._far_end = lambda count, end: refs.append(pair(count, end)) or refs[-1]

    def consume() -> None:
        while (item := blocks.get()) is not None:
            started = time.perf_counter()
            cleaned.append(live.process(*item))
            cost.append(time.perf_counter() - started)

    def on_audio(indata: np.ndarray, _frames, _time, _status) -> None:  # noqa: ANN001
        raw.append(indata[:, 0].copy())
        blocks.put((raw[-1], far_end.counts()))

    before = (
        osascript("output volume of (get volume settings)"),
        osascript("output muted of (get volume settings)"),
    )
    worker = threading.Thread(target=consume)
    worker.start()
    osascript(f"set volume output volume {volume} without output muted")
    try:
        with sd.InputStream(
            samplerate=RATE,
            channels=1,
            dtype="float32",
            blocksize=voice.VAD_BLOCK,
            callback=on_audio,
        ):
            spans = play_sources(lambda: len(raw) * voice.VAD_BLOCK / RATE)
    finally:
        osascript(f"set volume output volume {before[0]}")
        if before[1] == "true":
            osascript("set volume with output muted")
        blocks.put(None)
        worker.join()
    return save_recording(raw, refs, cleaned, cost, spans, live, volume)


def save_recording(raw, refs, cleaned, cost, spans, live, volume) -> int:  # noqa: ANN001
    delay = len(raw) - len(refs)  # the LiveCanceller's mic delay in blocks
    mic = np.concatenate(raw[: len(refs)])
    ref = np.concatenate(refs)
    out = np.concatenate(cleaned[delay:])
    for name, data in (("mic", mic), ("reference", ref), ("cancelled", out)):
        sf.write(OUT / f"{name}.wav", data, RATE)
    report = {
        "volume": volume,
        "spans_s": spans,
        "offsets_ms": {k: None if v is None else v * 1000 // RATE for k, v in live.offsets.items()},
    }
    for name, (begin, end) in spans.items():
        part = slice(int((begin + CONVERGE_S) * RATE), int(end * RATE))
        report[f"erle_{name}_db"] = erle_db(mic[part], out[part])
        report[f"echo_rms_{name}"] = round(rms(mic[part]), 4)
    block_s = voice.VAD_BLOCK / RATE
    report["aec_ms_per_block_median"] = round(float(np.median(cost)) * 1000, 3)
    report["aec_ms_per_block_p99"] = round(float(np.percentile(cost, 99)) * 1000, 3)
    report["aec_cpu_percent_of_one_core"] = round(float(np.mean(cost)) / block_s * 100, 2)
    report["added_latency_ms"] = round(delay * block_s * 1000 + 10)  # mic delay + ≤ 1 AEC frame
    (OUT / "record.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


# --- replay ----------------------------------------------------------------------------------


def load_clips(groups: dict[str, list[int]]) -> dict[str, np.ndarray]:
    return {
        f"{folder}/{n:03d}": sf.read(LOG_DIR / folder / f"{n:03d}.wav", dtype="float32")[0]
        for folder, numbers in groups.items()
        for n in numbers
    }


def cancel(mic: np.ndarray, ref: np.ndarray) -> np.ndarray:
    canceller = aec.Canceller()
    blocks = len(mic) // voice.VAD_BLOCK
    return np.concatenate(
        [
            canceller.process(
                mic[i * voice.VAD_BLOCK : (i + 1) * voice.VAD_BLOCK],
                ref[i * voice.VAD_BLOCK : (i + 1) * voice.VAD_BLOCK],
            )
            for i in range(blocks)
        ]
    )


def background(mic: np.ndarray, ref: np.ndarray, span: tuple, offset_s: float, seconds: float):
    """A window of recorded echo + its reference, looping inside the span."""
    begin, end = (int(s * RATE) for s in span)
    length = end - begin
    start = begin + int(offset_s * RATE) % max(1, length - int(seconds * RATE))
    window = slice(start, start + int(seconds * RATE))
    return mic[window], ref[window]


class Judge:
    def __init__(self) -> None:
        self.spot = voice.load_whisper(WAKE_MODEL, language="en", initial_prompt="Zoya")
        self.stt = voice.load_whisper(STT_MODEL_REPO, allowed_languages=voice.STT_LANGUAGES)

    def wakes(self, segment: np.ndarray) -> bool:
        """As VoiceLoop._on_segment_end: base.en wake unless turbo vetoes; turbo if long."""
        text = self.spot(segment[: int(WAKE_WINDOW_S * RATE)])
        if voice.is_wake(text):
            return not voice.vetoes_wake(self.stt(segment))
        return len(segment) / RATE >= voice.ONE_BREATH_MIN_S and voice.is_wake(self.stt(segment))

    def stops(self, window: np.ndarray) -> bool:
        return voice.is_stop(self.spot(window[-int(voice.STOP_WINDOW_S * RATE) :]))


def mix_trial(clip, level, echo, ref, aec_on) -> np.ndarray:
    """[PRE_ROLL_S background][clip + background][TAIL_S background] → the clip's segment."""
    scale = level * rms(clip) / rms(echo) if level else 0.0
    user = np.concatenate([np.zeros(int(PRE_ROLL_S * RATE)), clip, np.zeros(int(TAIL_S * RATE))])
    mic = (user[: len(echo)] + echo[: len(user)] * scale).astype("f4")
    heard = cancel(mic, ref[: len(mic)] * scale) if aec_on else mic
    begin = int(PRE_ROLL_S * RATE)
    return heard[begin : begin + len(clip)]


def replay() -> int:
    mic, _ = sf.read(OUT / "mic.wav", dtype="float32")
    ref, _ = sf.read(OUT / "reference.wav", dtype="float32")
    spans = json.loads((OUT / "record.json").read_text())["spans_s"]
    judge = Judge()
    wakes, negatives = load_clips(WAKES), load_clips(NEGATIVES)
    results: dict = {"wake": {}, "false_wake": {}, "stop": {}}
    seconds = (
        PRE_ROLL_S + TAIL_S + max(len(c) for c in [*wakes.values(), *negatives.values()]) / RATE
    )
    for source in ("music", "tts"):
        for level in LEVELS:
            for aec_on in (False, True):
                key = f"{source} {level:.2f} aec={'on' if aec_on else 'off'}"
                hits = [
                    judge.wakes(
                        mix_trial(
                            clip,
                            level,
                            *background(mic, ref, spans[source], i * 1.7, seconds),
                            aec_on,
                        )
                    )
                    for i, clip in enumerate(wakes.values())
                ]
                false = [
                    name
                    for i, (name, clip) in enumerate(negatives.items())
                    if judge.wakes(
                        mix_trial(
                            clip,
                            level,
                            *background(mic, ref, spans[source], i * 1.3, seconds),
                            aec_on,
                        )
                    )
                ]
                results["wake"][key] = f"{sum(hits)}/{len(hits)}"
                results["false_wake"][key] = false
                print(f"{key}: wakes {results['wake'][key]}, false {false}")
    results["stop"] = replay_stops(judge, mic, ref, spans["tts"])
    results["echo_alone_false_wakes"] = echo_alone(judge, mic, ref, spans)
    RESULTS.write_text(json.dumps(results, indent=1))
    print(json.dumps({k: results[k] for k in ("stop", "echo_alone_false_wakes")}, indent=1))
    return 0


def replay_stops(judge: Judge, mic, ref, span) -> dict:
    """ "Zoya, stop" over Zoya's own recorded speech at the real speaker volume."""
    with tempfile.TemporaryDirectory() as folder:
        phrases = [say(p, v, Path(folder)) for v in STOP_VOICES for p in STOP_PHRASES]
    target_rms = float(np.median([rms(c) for c in load_clips(WAKES).values()]))  # owner's level
    out = {}
    for aec_on in (False, True):
        hits = 0
        for i, phrase in enumerate(phrases):
            phrase = phrase * target_rms / rms(phrase)
            seconds = PRE_ROLL_S + len(phrase) / RATE + STOP_CHECK_AFTER_S
            echo, reference = background(mic, ref, span, i * 1.1, seconds)
            user = np.concatenate([np.zeros(int(PRE_ROLL_S * RATE)), phrase])
            user = np.pad(user, (0, len(echo) - len(user)))
            heard = cancel(user + echo, reference) if aec_on else (user + echo).astype("f4")
            hits += judge.stops(heard)
        out[f"aec={'on' if aec_on else 'off'}"] = f"{hits}/{len(phrases)}"
        print(f"stop over Zoya's speech, aec={'on' if aec_on else 'off'}: {hits}/{len(phrases)}")
    return out


def echo_alone(judge: Judge, mic, ref, spans) -> dict:
    """Music or Zoya's voice alone, 2.5 s windows: nothing may wake or stop."""
    out = {}
    for aec_on in (False, True):
        heard = cancel(mic, ref) if aec_on else mic
        fired = 0
        for begin, end in spans.values():
            for start in np.arange(begin + CONVERGE_S, end - WAKE_WINDOW_S, WAKE_WINDOW_S):
                window = heard[int(start * RATE) : int((start + WAKE_WINDOW_S) * RATE)]
                fired += judge.wakes(window) or judge.stops(window)
        out[f"aec={'on' if aec_on else 'off'}"] = fired
    return out


# --- barge-in replay (D62): AEC onset lowers the background; Whisper hears the raw mic ---

SPEECH_DROP_DELAY_S = 0.05  # mixer block + output/acoustic path before the echo gets quieter
DUCK_DELAY_S = 0.2  # osascript (~0.09–0.15 s measured) + acoustic path
STOP_CHECKS_S = (0.0, 0.15, 0.3, 0.45, 0.6)  # the stop spotter re-reads every 150 ms
TTS_LOUDNESS = (1.0, 2.0)  # recorded echo at 70% volume, and twice as loud
BARGE_IN_LEVELS = (0.29, 0.58, 1.16)


def barge_in_mic(user, echo, ref, gain: float, delay_s: float) -> tuple[np.ndarray, int | None]:
    """Block by block, as live: AEC → OnsetDetector → background × gain after delay_s.

    The live path cancels one mic block late (AEC_MIC_DELAY_BLOCKS); the recorded pair is already
    aligned, so that block is added to the onset time instead.
    """
    block = voice.VAD_BLOCK
    canceller, onset = aec.Canceller(), aec.OnsetDetector(voice.StreamingVad())
    mic = np.zeros(len(user) // block * block, np.float32)
    quiet_from = None
    for k in range(len(mic) // block):
        part = slice(k * block, (k + 1) * block)
        quieter = quiet_from is not None and k * block >= quiet_from
        g = gain if quieter else 1.0
        mic[part] = user[part] + echo[part] * g
        if onset(canceller.process(mic[part], ref[part] * g)) and quiet_from is None:
            quiet_from = (k + 1 + AEC_MIC_DELAY_BLOCKS) * block + int(delay_s * RATE)
    return mic, quiet_from


def barge_in_replay() -> int:
    mic, _ = sf.read(OUT / "mic.wav", dtype="float32")
    ref, _ = sf.read(OUT / "reference.wav", dtype="float32")
    spans = json.loads((OUT / "record.json").read_text())["spans_s"]
    judge = Judge()
    results = {
        "stop_over_tts": barge_in_stops(judge, mic, ref, spans["tts"]),
        "wake_over_music": barge_in_wakes(judge, mic, ref, spans["music"]),
        "onsets_per_min_echo_alone": onsets_alone(mic, ref, spans),
    }
    path = RESULTS.with_name("aec_barge_in_replay.json")
    path.write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))
    return 0


def barge_in_stops(judge: Judge, mic, ref, span) -> dict:
    """ "Zoya, stop" over Zoya's recorded speech: off vs barge-in; latency after the phrase."""
    with tempfile.TemporaryDirectory() as folder:
        phrases = [say(p, v, Path(folder)) for v in STOP_VOICES for p in STOP_PHRASES]
    target_rms = float(np.median([rms(c) for c in load_clips(WAKES).values()]))
    out = {}
    for loudness in TTS_LOUDNESS:
        for barge_in in (False, True):
            hits, latencies = 0, []
            for i, phrase in enumerate(phrases):
                phrase = phrase * target_rms / rms(phrase)
                end = int(PRE_ROLL_S * RATE) + len(phrase)
                seconds = PRE_ROLL_S + len(phrase) / RATE + max(STOP_CHECKS_S) + 0.1
                echo, reference = background(mic, ref, span, i * 1.1, seconds)
                user = np.pad(np.concatenate([np.zeros(int(PRE_ROLL_S * RATE)), phrase]), (0, 0))
                user = np.pad(user, (0, len(echo) - len(user)))
                gain = config.BARGE_IN_SPEECH_GAIN if barge_in else 1.0
                heard, _ = barge_in_mic(
                    user, echo * loudness, reference * loudness, gain, SPEECH_DROP_DELAY_S
                )
                for check in STOP_CHECKS_S:
                    if judge.stops(heard[: end + int(check * RATE)]):
                        hits += 1
                        latencies.append(round(check * 1000))
                        break
            key = f"loudness x{loudness:g} barge_in={'on' if barge_in else 'off'}"
            out[key] = {"stops": f"{hits}/{len(phrases)}", "phrase_end_to_detect_ms": latencies}
            print(f"stop {key}: {out[key]}", flush=True)
    return out


def barge_in_wakes(judge: Judge, mic, ref, span) -> dict:
    """The owner's "Hey Zoya" over music: off vs onset → system duck (+ osascript delay)."""
    wakes, negatives = load_clips(WAKES), load_clips(NEGATIVES)
    out = {}
    for level in BARGE_IN_LEVELS:
        for barge_in in (False, True):
            gain = DUCK_FRACTION if barge_in else 1.0
            hits = sum(
                barge_in_wake(judge, clip, level, mic, ref, span, i * 1.7, gain)
                for i, clip in enumerate(wakes.values())
            )
            false = [
                name
                for i, (name, clip) in enumerate(negatives.items())
                if barge_in_wake(judge, clip, level, mic, ref, span, i * 1.3, gain)
            ]
            key = f"music {level:.2f} barge_in={'on' if barge_in else 'off'}"
            out[key] = {"wakes": f"{hits}/{len(wakes)}", "false": false}
            print(f"wake {key}: {out[key]}", flush=True)
    return out


def barge_in_wake(judge, clip, level, mic, ref, span, offset_s, gain) -> bool:  # noqa: ANN001
    seconds = PRE_ROLL_S + TAIL_S + len(clip) / RATE
    echo, reference = background(mic, ref, span, offset_s, seconds)
    scale = level * rms(clip) / rms(echo)
    user = np.concatenate([np.zeros(int(PRE_ROLL_S * RATE)), clip, np.zeros(int(TAIL_S * RATE))])
    user = user[: len(echo)]
    heard, _ = barge_in_mic(
        user, echo[: len(user)] * scale, reference[: len(user)] * scale, gain, DUCK_DELAY_S
    )
    begin = int(PRE_ROLL_S * RATE)
    return judge.wakes(heard[begin : begin + len(clip)])


def onsets_alone(mic, ref, spans) -> dict:
    """Pumping guard: onsets on echo alone (no user), per minute, per source and loudness."""
    out = {}
    for name, (begin, end) in spans.items():
        part = slice(int(begin * RATE), int(end * RATE))
        for loudness in TTS_LOUDNESS:
            canceller, onset = aec.Canceller(), aec.OnsetDetector(voice.StreamingVad())
            echo, reference = mic[part] * loudness, ref[part] * loudness
            block = voice.VAD_BLOCK
            for k in range(len(echo) // block):
                window = slice(k * block, (k + 1) * block)
                onset(canceller.process(echo[window].astype("f4"), reference[window]))
            minutes = (end - begin) / 60
            out[f"{name} x{loudness:g}"] = round(onset.onsets / minutes, 1)
    return out


if __name__ == "__main__":
    sys.exit(
        record(int(sys.argv[2]) if len(sys.argv) > 2 else VOLUME)
        if sys.argv[1:2] == ["record"]
        else barge_in_replay() if sys.argv[1:2] == ["barge-in"] else replay()
    )
