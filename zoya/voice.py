"""Hands-free voice loop (§9.1, STACK §2, D19, D48).

Mic → Silero VAD (always on) → Whisper base.en checks each finished utterance for "Hey Zoya"
and, while Zoya talks or works, the last 2 s every 150 ms for "Zoya, stop" (D51: base.en runs
on the Apple GPU via mlx, ~30 ms a call) → after wake, record until ~0.5 s silence →
mlx-whisper large-v3-turbo → router → task. Push-to-talk (fn + Shift by default) records from
key-down. While Zoya talks, only the stop spotter listens (echo protection).

APIs (verified against the installed packages, 2026-09-14):
- https://github.com/SYSTRAN/faster-whisper — Silero VAD v6 ONNX ships in faster_whisper/assets;
  driven block by block with carried state as in https://github.com/snakers4/silero-vad
  (512 samples + 64 context at 16 kHz). WhisperModel.transcribe for the CPU spotter switch.
- https://github.com/ml-explore/mlx-examples/tree/main/whisper — mlx_whisper.transcribe(ndarray,
  path_or_hf_repo, initial_prompt, language, temperature, condition_on_previous_text).
- Quartz CGEventSourceFlagsState — modifier keys, no event tap or Input Monitoring needed.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from zoya import audio, orchestrator, speech
from zoya.config import (
    AFTER_WAKE_WAIT_S,
    COMMAND_END_SILENCE_S,
    ECHO_TAIL_S,
    ENDPOINT_MODE,
    LOG_DIR,
    MAX_UTTERANCE_S,
    MIC_READ_TIMEOUT_S,
    MIC_SAMPLE_RATE_HZ,
    PARTIAL_EVERY_S,
    PARTIAL_MIN_S,
    PRE_ROLL_S,
    PUSH_TO_TALK_KEYS,
    SMART_TURN_FILE,
    SMART_TURN_REPO,
    SMART_TURN_SHA256,
    SPOTTER_ENGINE,
    STT_MODEL_REPO,
    TIMING_LOG,
    TURN_CHECK_SILENCE_S,
    TURN_COMPLETE_PROBABILITY,
    TURN_WINDOW_S,
    VAD_BLOCK,
    VAD_THRESHOLD,
    WAKE_END_SILENCE_S,
    WAKE_MODEL,
    WAKE_WINDOW_S,
)
from zoya.router import STOP, clean_command

log = logging.getLogger(__name__)

MS_PER_S = 1000
BLOCK_S = VAD_BLOCK / MIC_SAMPLE_RATE_HZ
VAD_CONTEXT = 64
VAD_STATE_SHAPE = (1, 1, 128)
STOP_WINDOW_S = 2.0  # spot "stop" in the last 2 s of mic audio, across utterance boundaries
WARM_UP_S = 1.0
TURN_NORM_EPS = 1e-7
CLIPS_DIR = LOG_DIR / "wake_clips"
BACKGROUND_WINDOW_S = 10.0
BACKGROUND_MIN_S = 3.0  # too little history: the utterance itself would count as background
SPEECH_OVER_BACKGROUND = 2.0  # the user's voice must be ≥ 2× (+6 dB) the background loudness
MIN_SPEECH_RMS = 0.005
ONE_BREATH_MIN_S = 1.2  # longer utterances get a turbo wake check if base.en misses the name
FIRST_WORD_WAIT_S = 5.0
FIRST_WORD_POLL_S = 0.02
STOP_COOLDOWN_S = 2.0
# After Zoya answers, listen this long without "Hey Zoya" (§9.1 conversation timeout; GPT-Voice
# style follow-ups; pipecat's wake-phrase strategy keeps 10 s).
FOLLOW_UP_WINDOW_S = 8.0

# --- Parsers (tested: tests/test_voice_spotter.py) ------------------------------------

# Lenient "Zoya" (§7.1): zoya, zoia, zooeya, zoa, zoea, zoyah — not soya, sonia, zoe.
NAME = re.compile(r"^z(?:oo?e?y|oi|oe|o)ah?$")
# Whisper sometimes merges the greeting: "Hizoya", "Hezoya".
MERGED_WAKE = re.compile(r"^(?:hey|hi|he|hay|ok|okay)z(?:oo?e?y|oi|oe|o)ah?$")
WORD = re.compile(r"[a-z]+|[\u0900-\u097F]+")
# large-v3-turbo writes Hinglish in Devanagari (D42): "ज़ोया, स्पॉटिफ़ाई खोल दो".
DEVANAGARI_NAME = re.compile(r"^(?:ज़|ज़|ज)ोया$")
WAKE_NAME_WORDS = 3
# Only greetings may come before the name: "I bought soya milk" transcribes as "I bought
# Zoya milk" even on the whole clip (Phase 2 test), so "name anywhere in 3 words" isn't enough.
# "here"/"he's" (→ "he", "s"): how base.en heard the owner's real "Hey Zoya" (Phase 2 voice test).
GREETINGS = {"hey", "hi", "hay", "he", "here", "hear", "s", "hello", "ok", "okay", "oh", "a", "हे"}
# Whisper's classic outputs on near-silence (seen live: "you", "ん", "예소야").
HALLUCINATIONS = {
    *("you", "thank you", "thanks for watching", "bye", "so", "okay"),
    *("um", "uh", "hmm", "mm", "ah", "er"),  # fillers: owner's live run sent "um" to the brain
}
SUPPORTED_SCRIPT = re.compile(r"[A-Za-z\u0900-\u097F]")  # Latin or Devanagari (D42)
LATIN_ACCENT = re.compile(r"[\u0300-\u036f]")
# Not "soya": turbo wrote real "Hey Zoya" as "Hey, Soya." (replay) and "Soya!" (owner live run).
SOUND_ALIKES = {"zoe", "joya", "sonia", "sonya", "so", "siri", "सोनिया", "ज़ो"}
STOP_WORDS = {"stop", "cancel", "quiet", "ruko", "ruk", "bas", "chup"}
MAX_STOP_PHRASE_WORDS = 6
STATUS = re.compile(r"\bwhat(?:'s| is| are you)\s+(?:running|doing|working on)\b", re.I)


def words(text: str) -> list[str]:
    # Strip Latin accents only ("Zoëa" → "zoea"); Devanagari marks are letters, keep them.
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not LATIN_ACCENT.match(c))
    return WORD.findall(plain.lower())


def vetoes_wake(turbo_text: str) -> bool:
    """large-v3-turbo heard a different name where "Zoya" was: "Zoe is coming", "Joya!", "हे सोनिया".

    base.en with the "Zoya" prompt turned those into wakes (owner's run: 4/12 false). Requiring
    turbo to hear "Zoya" too would drop real wakes 13 → 6 (it hears "He's aware"), so turbo may
    only veto. ponytail: a list fitted to 4 real negatives; extend it from new false wakes.
    """
    first = words(turbo_text)[:WAKE_NAME_WORDS]
    if any(is_name(word) or MERGED_WAKE.match(word) for word in first):
        return False  # turbo heard the name too: "Hey Zoya, so what's the weather" stays a wake
    return any(word in SOUND_ALIKES for word in first)


def is_name(word: str) -> bool:
    return bool(NAME.match(word) or DEVANAGARI_NAME.match(word))


def is_wake(text: str) -> bool:
    """A Zoya-like name within the first 3 words, with only greetings before it (D19, D51)."""
    spoken = words(text)[:WAKE_NAME_WORDS]
    for index, word in enumerate(spoken):
        if is_name(word) or MERGED_WAKE.match(word):
            return all(earlier in GREETINGS for earlier in spoken[:index])
    return False


def after_wake(text: str) -> str:
    """The words after the wake name: "Here Zoya, open Spotify" → "open spotify"."""
    spoken = words(text)
    for index, word in enumerate(spoken[:WAKE_NAME_WORDS]):
        if is_name(word) or MERGED_WAKE.match(word):
            return " ".join(spoken[index + 1 :])
    return ""


def is_usable_command(text: str) -> bool:
    """Drop Whisper hallucinations and scripts Zoya can't route (Japanese/Korean on noise)."""
    command = clean_command(text)
    if not command or not SUPPORTED_SCRIPT.search(command):
        return False
    return " ".join(words(command)) not in HALLUCINATIONS


def is_stop(text: str) -> bool:
    """ "Zoya, stop" / "stop Zoya" / "Zoya ruko": the name AND a stop word in a short phrase.

    Requiring the name keeps Zoya's own speech ("Okay, stopped.") from stopping her.
    """
    spoken = words(text)
    if not spoken or len(spoken) > MAX_STOP_PHRASE_WORDS:
        return False
    return any(is_name(w) for w in spoken) and any(w in STOP_WORDS for w in spoken)


def is_stop_command(text: str) -> bool:
    """A captured command that means stop ("Hey Zoya … stop", router STOP phrases)."""
    return is_stop(text) or bool(STOP.match(clean_command(text)))


# --- Models -----------------------------------------------------------------------------


class StreamingVad:
    """Silero VAD v6 (bundled with faster-whisper) with state carried across 32 ms blocks."""

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._session = get_vad_model().session
        self._h = np.zeros(VAD_STATE_SHAPE, dtype=np.float32)
        self._c = np.zeros(VAD_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros(VAD_CONTEXT, dtype=np.float32)

    def __call__(self, block: np.ndarray) -> float:
        batch = np.concatenate([self._context, block])[None, :]
        out, self._h, self._c = self._session.run(
            None, {"input": batch, "h": self._h, "c": self._c}
        )
        self._context = block[-VAD_CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])


def load_whisper(repo: str, **options: str) -> Callable[[np.ndarray], str]:
    """An mlx-whisper transcriber, loaded and warmed now (the first call is slow, D48)."""
    import mlx.core as mx
    import mlx_whisper
    from mlx_whisper.load_models import load_model
    from mlx_whisper.transcribe import ModelHolder

    from zoya.setup_models import local_model_dir

    # A local path: mlx-whisper would otherwise ask the Hub for a revision (startup hang, AUDIT §6).
    model = load_model(local_model_dir(repo), dtype=mx.float16)  # transcribe()'s default fp16

    def transcribe(samples: np.ndarray) -> str:
        # ponytail: mlx-whisper 0.4.3 caches ONE model, so alternating base.en and turbo reloaded
        # weights every call (+350 ms spot, turbo 0.6 → 1.3 s). Hand it ours; re-check on upgrade.
        ModelHolder.model, ModelHolder.model_path = model, repo
        result = mlx_whisper.transcribe(
            samples,
            path_or_hf_repo=repo,
            temperature=0.0,  # no temperature fallback re-runs: keeps each call bounded
            condition_on_previous_text=False,
            **options,
        )
        return str(result.get("text", "")).strip()

    transcribe(np.zeros(int(WARM_UP_S * MIC_SAMPLE_RATE_HZ), dtype=np.float32))
    return transcribe


def load_smart_turn() -> Callable[[np.ndarray], bool] | None:
    """Smart Turn v3.2: is this pause the end of the user's turn? ~31 ms on CPU (owner's clips).

    Features: faster-whisper's Whisper log-mel extractor with padding=0 matches pipecat's
    vendored one exactly (max diff 0.0), after zero-mean unit-variance waveform normalisation as
    in pipecat local_smart_turn_v3.py. Returns None (fixed-silence endpointing) if unavailable.
    """
    import hashlib

    import onnxruntime as ort
    from faster_whisper.feature_extractor import FeatureExtractor

    from zoya.setup_models import local_model_dir

    try:
        path = f"{local_model_dir(SMART_TURN_REPO)}/{SMART_TURN_FILE}"
        with open(path, "rb") as model_file:
            if hashlib.sha256(model_file.read()).hexdigest() != SMART_TURN_SHA256:
                raise ValueError("Smart Turn model checksum mismatch")
    except Exception as error:  # noqa: BLE001 — endpointing still works on the silence rule
        log.warning(
            "Smart Turn unavailable (%s) — using %.1f s silence", error, COMMAND_END_SILENCE_S
        )
        return None
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(path, sess_options=options)
    features = FeatureExtractor(feature_size=80, chunk_length=TURN_WINDOW_S)
    window = TURN_WINDOW_S * MIC_SAMPLE_RATE_HZ

    def is_complete(samples: np.ndarray) -> bool:
        audio8 = np.pad(samples[-window:], (max(0, window - len(samples)), 0)).astype(np.float32)
        audio8 = (audio8 - audio8.mean()) / np.sqrt(audio8.var() + TURN_NORM_EPS)
        mel = features(audio8, padding=0)[None]
        probability = float(session.run(None, {"input_features": mel})[0][0][0])
        log.debug("smart turn p=%.2f", probability)
        return probability > TURN_COMPLETE_PROBABILITY

    is_complete(np.zeros(MIC_SAMPLE_RATE_HZ, dtype=np.float32))  # warm up
    return is_complete


def load_cpu_spotter() -> Callable[[np.ndarray], str]:
    """D19's original spotter: faster-whisper base.en int8 on CPU (~250 ms/call). Stage fallback."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base.en", device="cpu", compute_type="int8")

    def transcribe(samples: np.ndarray) -> str:
        segments, _ = model.transcribe(
            samples, language="en", initial_prompt="Zoya", beam_size=1, vad_filter=False
        )
        return " ".join(segment.text for segment in segments).strip()

    transcribe(np.zeros(int(WARM_UP_S * MIC_SAMPLE_RATE_HZ), dtype=np.float32))
    return transcribe


def push_to_talk_label() -> str:
    return " + ".join(key.capitalize() if key != "fn" else "fn" for key in PUSH_TO_TALK_KEYS)


def push_to_talk_held() -> bool:
    import Quartz

    masks = {
        "fn": Quartz.kCGEventFlagMaskSecondaryFn,
        "shift": Quartz.kCGEventFlagMaskShift,
        "control": Quartz.kCGEventFlagMaskControl,
        "option": Quartz.kCGEventFlagMaskAlternate,
        "command": Quartz.kCGEventFlagMaskCommand,
    }
    wanted = 0
    for key in PUSH_TO_TALK_KEYS:
        wanted |= masks[key]
    flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateHIDSystemState)
    return flags & wanted == wanted


# --- Listener ---------------------------------------------------------------------------


@dataclass
class Segment:
    blocks: list[np.ndarray]
    last_voice_at: float
    turn_complete: bool | None = None  # Smart Turn verdict for the current pause
    woke_at: float | None = None  # set once "Zoya" was heard in this segment
    awaited: bool = False  # captured in the "Hey Zoya" … pause … command window
    began_while_busy: bool = False  # started during Zoya's speech: likely her own echo

    @property
    def seconds(self) -> float:
        return len(self.blocks) * BLOCK_S

    def samples(self, head_s: float = MAX_UTTERANCE_S) -> np.ndarray:
        return np.concatenate(self.blocks[: max(1, int(head_s / BLOCK_S))])

    def tail(self, seconds: float) -> np.ndarray:
        return np.concatenate(self.blocks[-max(1, int(seconds / BLOCK_S)) :])


class VoiceLoop:
    def __init__(
        self, wake_enabled: bool = True, test_wake: bool = False, record_clips: bool = False
    ) -> None:
        self.wake_enabled = wake_enabled
        self.test_wake = test_wake
        self.record_clips = record_clips
        self.vad = StreamingVad()
        self.spot = (
            load_cpu_spotter()
            if SPOTTER_ENGINE == "faster-whisper"
            else load_whisper(WAKE_MODEL, language="en", initial_prompt="Zoya")
        )
        self.stt = load_whisper(STT_MODEL_REPO)  # multilingual: Hinglish → Devanagari (D42)
        self.turn = load_smart_turn() if ENDPOINT_MODE == "smart_turn" else None
        self.mic: queue.Queue[tuple[float, np.ndarray]] = queue.Queue()
        self.pre_roll: deque[np.ndarray] = deque(maxlen=int(PRE_ROLL_S / BLOCK_S))
        self.recent: deque[np.ndarray] = deque(maxlen=int(STOP_WINDOW_S / BLOCK_S))
        self.last_voice_at = 0.0
        self.loudness: deque[float] = deque(maxlen=int(BACKGROUND_WINDOW_S / BLOCK_S))
        self.last_stop_check = 0.0
        self.last_stop_at = 0.0
        self.follow_up_pending = False
        self.utterances = 0
        self.segment: Segment | None = None
        self.awaiting_command_until = 0.0  # "Hey Zoya" … pause … command
        self.ptt: Segment | None = None
        self.task: threading.Thread | None = None
        self.last_spoke_at = 0.0

    # --- main loop ---------------------------------------------------------------------

    def run(self, stop_event: threading.Event) -> None:
        import sounddevice as sd

        def on_audio(indata: np.ndarray, _frames, _time, _status) -> None:  # noqa: ANN001
            self.mic.put((time.monotonic(), indata[:, 0].copy()))

        with sd.InputStream(
            samplerate=MIC_SAMPLE_RATE_HZ,
            channels=1,
            dtype="float32",
            blocksize=VAD_BLOCK,
            callback=on_audio,
        ):
            while not stop_event.is_set():
                try:
                    arrival, block = self.mic.get(timeout=MIC_READ_TIMEOUT_S)
                except queue.Empty:
                    continue
                self._on_block(arrival, block)

    def _on_block(self, arrival: float, block: np.ndarray) -> None:
        voiced = self._user_voice(block)
        self.recent.append(block)
        if voiced:
            self.last_voice_at = arrival
        if speech.is_speaking():
            self.last_spoke_at = time.monotonic()
        self._check_stop(arrival)
        if self.follow_up_pending and not self._zoya_busy():
            self._open_follow_up()
        if audio.is_ducked() and self._idle_since_wake():
            audio.restore()
        if self._push_to_talk(arrival, block):
            return
        if self.segment is None:
            self.pre_roll.append(block)
            if voiced:
                self.segment = Segment([*self.pre_roll, block], arrival)
                self.segment.began_while_busy = self._zoya_busy()
                if time.monotonic() < self.awaiting_command_until:
                    self.segment.woke_at = time.monotonic()  # already awake: this is the command
                    self.segment.awaited = True
            return
        self.segment.blocks.append(block)
        if voiced:
            self.segment.last_voice_at = arrival
            self.segment.turn_complete = None  # speaking again: a new pause gets a new verdict
        if self._segment_ended(self.segment, arrival):
            ended, self.segment = self.segment, None
            self.pre_roll.clear()
            self._on_segment_end(ended)

    def _user_voice(self, block: np.ndarray) -> bool:
        """VAD speech that is also clearly louder than the background.

        Silero calls music vocals and radio "speech", so with Spotify playing an utterance never
        ended and ran to MAX_UTTERANCE_S (owner's live run: wake → command gaps of 7–13 s, music
        stayed ducked). ponytail: median loudness of the last 10 s as the background; a TV
        talking at the user's own level still defeats it — AEC/source separation is the upgrade.
        """
        loudness = float(np.sqrt(np.mean(block**2)))
        warmed_up = len(self.loudness) * BLOCK_S >= BACKGROUND_MIN_S
        background = float(np.median(self.loudness)) if warmed_up else 0.0
        self.loudness.append(loudness)
        loud_enough = loudness >= max(background * SPEECH_OVER_BACKGROUND, MIN_SPEECH_RMS)
        return loud_enough and self.vad(block) >= VAD_THRESHOLD

    def _segment_ended(self, segment: Segment, arrival: float) -> bool:
        silence = arrival - segment.last_voice_at
        if segment.seconds >= MAX_UTTERANCE_S:
            return True
        if segment.woke_at is None:
            return silence >= WAKE_END_SILENCE_S
        if self.turn and silence >= TURN_CHECK_SILENCE_S and segment.turn_complete is None:
            segment.turn_complete = self.turn(segment.tail(TURN_WINDOW_S))
        # Smart Turn can only end a command sooner; "incomplete" falls back to the 0.5 s rule.
        return bool(segment.turn_complete) or silence >= COMMAND_END_SILENCE_S

    # --- spotting: "stop" always, the wake word only when Zoya is quiet ----------------------

    def _zoya_busy(self) -> bool:
        recently_spoke = time.monotonic() - self.last_spoke_at < ECHO_TAIL_S
        return speech.is_speaking() or recently_spoke or self._task_running()

    def _check_stop(self, arrival: float) -> None:
        """While Zoya talks or works, re-read the last 2 s every 150 ms (false stops fail safe)."""
        now = time.monotonic()
        if not self._zoya_busy() or now - self.last_stop_check < PARTIAL_EVERY_S:
            return
        if (
            arrival - self.last_voice_at > STOP_WINDOW_S
            or len(self.recent) * BLOCK_S < PARTIAL_MIN_S
        ):
            return
        self.last_stop_check = now
        if now - self.last_stop_at < STOP_COOLDOWN_S:
            return  # Zoya saying "Okay, stopped." must not stop her again
        text = self._spot(np.concatenate(self.recent))
        if is_stop(text):  # name AND stop word in one window: echo alone rarely has both
            self._stop(self.last_voice_at, text, partial=True)

    def _spot(self, samples: np.ndarray) -> str:
        started = time.monotonic()
        text = self.spot(samples)
        log.debug("spot %d ms: %r", (time.monotonic() - started) * MS_PER_S, text)
        return text

    def _on_segment_end(self, segment: Segment) -> None:
        if segment.woke_at is not None:
            self._command(segment)
            return
        if self._zoya_busy() or segment.began_while_busy or not self.wake_enabled:
            return  # echo protection (Done-when #2): only the stop spotter listens now
        # Whole utterance only: partial audio makes Whisper hallucinate the "Zoya" prompt.
        text = self._spot(segment.samples(WAKE_WINDOW_S))
        if not words(text) and segment.seconds < ONE_BREATH_MIN_S:
            return  # the wake chime or a click heard back: not an utterance
        self.utterances += 1
        if self.record_clips:
            _save_clip(self.utterances, segment.samples())
        if is_stop(text):
            self._stop(segment.last_voice_at, text, partial=False)
        elif is_wake(text):
            self._wake(segment, text)  # chime now (< 500 ms); turbo can still veto
            full, _ = self._transcribe(segment)
            if vetoes_wake(full):
                self._veto(full)
            elif self.test_wake:
                return  # score every utterance on its own
            elif after_wake(text) or after_wake(full):
                self._command(segment, transcript=full)  # "Hey Zoya, open Spotify" in one breath
            else:
                self._await_command()  # "Hey Zoya" … pause … command
        elif segment.seconds >= ONE_BREATH_MIN_S and is_wake(full := self._transcribe(segment)[0]):
            # base.en misses the name inside a long sentence (owner's live run); turbo's transcript
            # is the command itself, so a real command pays nothing extra.
            self._wake(segment, full)
            if not self.test_wake:
                self._command(segment, transcript=full)
        elif self.test_wake:
            print(f"#{self.utterances} no wake — heard {text!r}")

    def _veto(self, heard: str) -> None:
        self.awaiting_command_until = 0.0
        audio.restore()
        print(f"#{self.utterances} VETO — turbo heard {heard!r}, not Zoya")
        _log_voice({"event": "wake_veto"})

    def _open_follow_up(self) -> None:
        """Zoya finished answering: the next sentence needs no wake word for a few seconds."""
        self.follow_up_pending = False
        self.awaiting_command_until = time.monotonic() + FOLLOW_UP_WINDOW_S
        print(f"LISTENING for a follow-up ({FOLLOW_UP_WINDOW_S:.0f} s, no wake word needed)")

    def _on_task_done(self, result: orchestrator.CommandResult) -> None:
        stopped = result.decision.route == "stop" or result.spoken == orchestrator.STOPPED_MESSAGE
        self.follow_up_pending = not stopped

    def _await_command(self) -> None:
        self.awaiting_command_until = time.monotonic() + AFTER_WAKE_WAIT_S

    def _idle_since_wake(self) -> bool:
        waiting = time.monotonic() < self.awaiting_command_until
        capturing = self.segment is not None and self.segment.woke_at is not None
        return not (waiting or capturing or self.ptt is not None)

    def _wake(self, segment: Segment, text: str) -> None:
        segment.woke_at = time.monotonic()
        audio.earcon("listening")
        audio.duck()  # Wispr Flow's "mute music while dictating": other audio drops while we listen
        after_end = round((segment.woke_at - segment.last_voice_at) * MS_PER_S)
        print(f"#{self.utterances} WAKE {after_end} ms after the phrase ended — heard {text!r}")
        _log_voice({"event": "wake", "phrase_end_to_earcon_ms": after_end, "heard": text})

    def _stop(self, voice_end_at: float, text: str, partial: bool) -> None:
        stopped_at = time.monotonic()
        was_busy = self._zoya_busy()
        orchestrator.stop_task()
        audio.engine().silence_all()
        audio.earcon("stop")
        after_end = round((stopped_at - voice_end_at) * MS_PER_S)
        self.segment = None
        self.recent.clear()  # don't hear the same "stop" twice
        self.last_stop_at = time.monotonic()
        self.follow_up_pending = False
        self.utterances = 0
        self.awaiting_command_until = 0.0
        audio.restore()
        print(f"STOP {after_end} ms after last voice (partial={partial}) — heard {text!r}")
        _log_voice(
            {
                "event": "stop",
                "partial": partial,
                "busy": was_busy,
                "last_voice_to_silence_ms": after_end,
            }
        )

    # --- push-to-talk ----------------------------------------------------------------------

    def _push_to_talk(self, arrival: float, block: np.ndarray) -> bool:
        held = push_to_talk_held()
        if self.ptt is None and not held:
            return False
        if self.ptt is None:
            if self._zoya_busy():
                orchestrator.stop_task()  # pressing the keys interrupts Zoya, like Wispr's fn key
                audio.engine().silence_all()
            self.ptt = Segment([*self.pre_roll, block], arrival, woke_at=time.monotonic())
            self.segment = None
            audio.earcon("listening")
            audio.duck()
            print("PUSH-TO-TALK down")
            return True
        self.ptt.blocks.append(block)
        if held and self.ptt.seconds < MAX_UTTERANCE_S:
            return True
        ended, self.ptt = self.ptt, None
        ended.last_voice_at = arrival
        print("PUSH-TO-TALK up")
        self._command(ended)
        return True

    # --- commands ---------------------------------------------------------------------------

    def _task_running(self) -> bool:
        return self.task is not None and self.task.is_alive()

    def _transcribe(self, segment: Segment) -> tuple[str, int]:
        started = time.monotonic()
        text = self.stt(segment.samples())
        return text, round((time.monotonic() - started) * MS_PER_S)

    def _command(self, segment: Segment, transcript: str | None = None) -> None:
        endpoint_ms = round((time.monotonic() - segment.last_voice_at) * MS_PER_S)
        audio.restore()
        audio.earcon("heard")
        audio.earcon("working")
        speech.reset_timing()
        text, stt_ms = (transcript, 0) if transcript is not None else self._transcribe(segment)
        print(f"HEARD {text!r} (endpoint {endpoint_ms} ms, stt {stt_ms} ms)")
        if not is_usable_command(text):
            audio.engine().silence_all()  # end the working loop
            if not segment.awaited:
                self._await_command()  # woke (or keys pressed) but no words yet: keep listening
                audio.duck()
            # Junk inside the wait window (music, the chime) must not use up the wake.
            return
        self.awaiting_command_until = 0.0
        self._dispatch(text, segment.last_voice_at, {"endpoint_ms": endpoint_ms, "stt_ms": stt_ms})

    def _dispatch(self, text: str, speech_end_at: float, pre: dict[str, int]) -> None:
        if not is_usable_command(text):
            audio.engine().silence_all()  # nothing heard: end the working loop quietly
            return
        if is_stop_command(text):
            self._stop(speech_end_at, text, partial=False)
            return
        if STATUS.search(text):
            audio.earcon("success")
            speech.narrate(orchestrator.task_status())
            return
        if self._task_running():
            audio.earcon("error")
            speech.narrate("I'm still on the last task. Say Zoya, stop, to cancel it.")
            return

        def on_done(result: orchestrator.CommandResult) -> None:
            self._on_task_done(result)
            _report(result, speech_end_at, pre)

        self.task = orchestrator.start_task(text, pre, on_done=on_done)


def _report(result: orchestrator.CommandResult, speech_end_at: float, pre: dict[str, int]) -> None:
    done_ms = round((time.monotonic() - speech_end_at) * MS_PER_S)
    deadline = time.monotonic() + FIRST_WORD_WAIT_S  # fast replies are spoken after "done"
    while speech.first_audio_at is None and time.monotonic() < deadline:
        time.sleep(FIRST_WORD_POLL_S)
    first = speech.first_audio_at
    first_word_ms = round((first - speech_end_at) * MS_PER_S) if first else None
    print(
        f"DONE route={result.decision.route} tool={result.decision.tool} ok={result.ok} "
        f"speech_end→done {done_ms} ms, first word {first_word_ms} ms, stages {result.timings_ms}"
    )
    print(f"  zoya: {result.spoken}")
    _log_voice(
        {
            "event": "command",
            "task_id": result.task_id,
            "route": result.decision.route,
            "ok": result.ok,
            "speech_end_to_done_ms": done_ms,
            "speech_end_to_first_word_ms": first_word_ms,
            **pre,
        }
    )


def _save_clip(number: int, samples: np.ndarray) -> None:
    """Owner-approved tuning clips; logs/ is git-ignored and nothing is uploaded."""
    import soundfile as sf

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    sf.write(CLIPS_DIR / f"{number:03d}.wav", samples, MIC_SAMPLE_RATE_HZ)


def _log_voice(record: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    line = {"at": datetime.now(UTC).isoformat(timespec="milliseconds"), "voice": True, **record}
    with TIMING_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")
