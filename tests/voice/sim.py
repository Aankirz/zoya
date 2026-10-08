"""Voice-loop simulator (S1-Listen): the real VoiceLoop decision logic on scripted sound.

A script is a list of `Sound`s on a timeline: what reached the microphone, who made it, and what
Whisper would hear. The simulator feeds 32 ms blocks to `VoiceLoop._on_block` on a fake clock,
with a fake VAD, fake spotter/STT (they read which sound each block belongs to), a fake echo
canceller for barge-in, and fake speech, audio, tasks and orchestrator. Nothing touches the
microphone, the speakers, the network or logs/. Every decision the loop makes is recorded in a
`Trace`: dispatched commands, stops, wakes, earcons, and each `_log_voice` record.

Model calls cost fake time (the loop thread is blocked meanwhile), so backlog behaves as live.
Speculative partials (D82) are off: they are read-only guesses that run on their own threads.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from types import SimpleNamespace

import numpy as np
import pytest

from zoya import aec, audio, events, orchestrator, overlay, safety, speculate, speech, tasks, voice
from zoya.router import RouteDecision

BLOCK = voice.VAD_BLOCK
BLOCK_S = voice.BLOCK_S
VOICE_LEVEL = 0.1
SILENCE_LEVEL = 0.0002
MARK = 1e-6  # per slot: sound number × MARK, then its block position × MARK
MARK_SLOTS = 2  # at most two sounds overlap in one block (the user over Zoya's echo)
SECONDS_PER_WORD = 0.32
MIN_SOUND_S = 0.35
ECHO_KEPT = 0.1  # what AEC3 leaves of Zoya's own voice (D62: ~20 dB)
USER_KEPT = 0.9
SPOT_COST_S = 0.03
STT_COST_S = 0.6
TURN_COST_S = 0.03
TAIL_S = 3.0
SPEAK_S_PER_WORD = 0.3
PTT_LEAD_S = 0.1
VOICED_CYCLE = 10
LEAD_IN_S = 10.0  # quiet room before the script: the loudness gate needs a background

USER, ZOYA, ROOM = "user", "zoya", "room"
LEVELS = {USER: VOICE_LEVEL, ZOYA: 0.03, ROOM: 0.05}  # her echo and a TV are quieter than the user


@dataclass(frozen=True)
class Sound:
    """Something the microphone hears. `text` is what turbo hears; `spot` what base.en hears."""

    text: str
    at: float
    speaker: str = USER
    seconds: float | None = None
    spot: str | None = None
    voiced: float = 1.0  # share of its blocks that read as speech (music: low)
    ptt: bool = False  # the push-to-talk keys are held for the whole sound
    cue: int | None = None  # `at` counts from the end of Zoya's cue-th reply (0 = her first)

    @property
    def length(self) -> float:
        if self.seconds is not None:
            return self.seconds
        return max(MIN_SOUND_S, len(self.text.split()) * SECONDS_PER_WORD)

    @property
    def end(self) -> float:
        return self.at + self.length


@dataclass(frozen=True)
class Reply:
    """What a dispatched command does: work for `after` seconds, then say `spoken`."""

    spoken: str = "Done."
    after: float = 0.5


@dataclass
class Trace:
    dispatched: list[str] = field(default_factory=list)
    stops: list[str] = field(default_factory=list)
    wakes: list[float] = field(default_factory=list)
    earcons: list[tuple[float, str]] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    said: list[str] = field(default_factory=list)
    ducked: bool = False  # other apps still ducked when the script ended
    ended_at: float = 0.0

    def events(self, name: str) -> list[dict]:
        return [record for record in self.log if record.get("event") == name]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def monotonic_ns(self) -> int:
        return int(self.now * 1e9)

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class SyncThread:
    """Runs the target at start(): background work becomes deterministic."""

    def __init__(self, target: Callable, args: tuple = (), **_kwargs) -> None:
        self._target, self._args = target, args

    def start(self) -> None:
        self._target(*self._args)


class FakeEngine:
    def __init__(self, sim: Simulator) -> None:
        self.sim = sim
        self.one_shot_at = -100.0
        self.speech_gain = 1.0

    def silence_all(self) -> None:
        self.sim.speaking_until = min(self.sim.speaking_until, self.sim.clock.now)

    def clear_speech(self) -> None:
        self.silence_all()

    def speech_pending(self) -> bool:
        return False

    def set_speech_gain(self, gain: float) -> None:
        self.speech_gain = gain


class FakeCanceller:
    """AEC3 stand-in: Zoya's echo keeps ECHO_KEPT of its level, anyone else USER_KEPT."""

    def __init__(self, sim: Simulator) -> None:
        self.sim = sim
        self.last_mic = np.zeros(0, np.float32)

    def process(self, block: np.ndarray, _counts: object) -> np.ndarray:
        self.last_mic = block
        speakers = {sound.speaker for sound, _position in self.sim.marks(block)}
        kept = ECHO_KEPT if speakers == {ZOYA} else USER_KEPT
        return block * kept

    def other_audio_playing(self) -> bool:
        return False


class Simulator:
    def __init__(
        self,
        sounds: list[Sound],
        replies: dict[str, Reply] | None = None,
        echo: bool = True,
        aec_on: bool = True,
        spot_cost_s: float = SPOT_COST_S,
        stt_cost_s: float = STT_COST_S,
        running: list[str] | None = None,
    ) -> None:
        self.sounds = [replace(s, at=s.at + LEAD_IN_S) for s in sounds if s.cue is None]
        self.cued = [sound for sound in sounds if sound.cue is not None]
        self.replies_spoken = 0
        self.replies = replies or {}
        self.echo, self.aec_on = echo, aec_on
        self.spot_cost_s, self.stt_cost_s = spot_cost_s, stt_cost_s
        self.clock = Clock()
        self.trace = Trace()
        self.speaking_until = -1.0
        self.pending: list[tuple[float, Callable[[], None]]] = []
        self.engine = FakeEngine(self)
        self.ducked = False
        self.running = [
            SimpleNamespace(id=f"t{i}", name=n, shared=False) for i, n in enumerate(running or [])
        ]

    # --- fake audio --------------------------------------------------------------------

    def marks(self, block: np.ndarray) -> list[tuple[Sound, int]]:
        """The sounds mixed into this block, with each one's block position."""
        found = []
        for slot in range(0, MARK_SLOTS * 2, 2):
            number = round(float(block[slot]) / MARK)
            if 0 < number <= len(self.sounds):
                found.append((self.sounds[number - 1], round(float(block[slot + 1]) / MARK)))
        return found

    def _block(self, start: float) -> np.ndarray:
        block = np.full(BLOCK, SILENCE_LEVEL, np.float32)
        block[: MARK_SLOTS * 2] = 0.0
        playing = [(n, s) for n, s in enumerate(self.sounds, 1) if s.at <= start < s.end]
        for slot, (number, sound) in enumerate(playing[:MARK_SLOTS]):
            position = int((start - sound.at) / BLOCK_S)
            block[slot * 2], block[slot * 2 + 1] = number * MARK, position * MARK
        if playing:
            block[MARK_SLOTS * 2 :] = sum(LEVELS[s.speaker] for _n, s in playing[:MARK_SLOTS])
        return block

    def is_voiced(self, block: np.ndarray) -> bool:
        return any(
            position % VOICED_CYCLE < sound.voiced * VOICED_CYCLE
            for sound, position in self.marks(block)
        )

    def vad(self, block: np.ndarray) -> float:
        return 0.9 if self.is_voiced(block) else 0.05

    def heard(self, samples: np.ndarray, spot: bool) -> str:
        """Words of each sound in proportion to the blocks of it in `samples`, in order."""
        seen: dict[Sound, list[int]] = {}
        for block in samples[: len(samples) // BLOCK * BLOCK].reshape(-1, BLOCK):
            for sound, position in self.marks(block):
                seen.setdefault(sound, []).append(position)
        parts = []
        for sound, positions in seen.items():
            text = sound.spot if spot and sound.spot is not None else sound.text
            parts.append(_span(text, min(positions), max(positions), sound.length))
        return " ".join(part for part in parts if part)

    def spot(self, samples: np.ndarray) -> str:
        self.clock.now += self.spot_cost_s
        return self.heard(samples, spot=True)

    def stt(self, samples: np.ndarray) -> str:
        self.clock.now += self.stt_cost_s
        return self.heard(samples, spot=False)

    def turn(self, _samples: np.ndarray) -> bool:
        self.clock.now += TURN_COST_S
        return True

    # --- fake world --------------------------------------------------------------------

    def speak(self, text: str) -> None:
        self.trace.said.append(text)
        start = max(self.clock.now, self.speaking_until)
        length = max(MIN_SOUND_S, len(text.split()) * SPEAK_S_PER_WORD)
        self.speaking_until = start + length
        if self.echo:
            self.sounds.append(Sound(text, start, ZOYA, seconds=length))
        for sound in [s for s in self.cued if s.cue == self.replies_spoken]:
            self.sounds.append(replace(sound, at=self.speaking_until + sound.at, cue=None))
        self.replies_spoken += 1

    def start_task(self, text: str, pre: dict, on_done: Callable | None = None) -> SimpleNamespace:
        self.trace.dispatched.append(text)
        reply = next((r for key, r in self.replies.items() if key.lower() in text.lower()), Reply())
        task = SimpleNamespace(id=f"t{len(self.trace.dispatched)}", name=text, shared=False)
        self.running.append(task)

        def finish() -> None:
            if task in self.running:
                self.running.remove(task)
            self.speak(reply.spoken)
            decision = RouteDecision("orchestrator", text=text)
            if on_done:
                on_done(orchestrator.CommandResult(task.id, decision, reply.spoken, True, {}))

        self.pending.append((self.clock.now + reply.after, finish))
        return task

    def stop_task(self, name: str = "") -> str:
        self.trace.stops.append(name)
        self.running.clear()
        self.speaking_until = self.clock.now
        return orchestrator.STOPPED_MESSAGE

    def earcon(self, name: str) -> None:
        self.trace.earcons.append((self.clock.now, name))
        self.engine.one_shot_at = self.clock.now

    def ptt_held(self) -> bool:
        now = self.clock.now
        return any(s.ptt and s.at - PTT_LEAD_S <= now < s.end + PTT_LEAD_S for s in self.sounds)

    def log(self, record: dict) -> None:
        self.trace.log.append({"t": round(self.clock.now, 3), **record})
        if record.get("event") == "wake":
            self.trace.wakes.append(self.clock.now)

    # --- run ---------------------------------------------------------------------------

    def run(self, loop: voice.VoiceLoop, until: float | None = None) -> Trace:
        end = until if until is not None else max(s.end for s in self.sounds) + TAIL_S
        index = 0
        while index * BLOCK_S < end:
            arrival = (index + 1) * BLOCK_S
            self.clock.now = max(self.clock.now, arrival)
            for due, action in sorted(self.pending, key=lambda item: item[0]):
                if due <= self.clock.now:
                    self.pending.remove((due, action))
                    action()
            block = self._block(index * BLOCK_S)
            if loop.canceller:
                loop._listen_for_barge_in(arrival, block, None)
            loop._on_block(arrival, block)
            index += 1
            if until is None:
                end = max(end, max(s.end for s in self.sounds) + TAIL_S)
        self.trace.ducked, self.trace.ended_at = self.ducked, self.clock.now
        return self.trace


def _span(text: str, first: int, last: int, length: float) -> str:
    words = text.split()
    blocks = max(1, math.ceil(length / BLOCK_S))
    start = math.floor(first / blocks * len(words))
    stop = math.ceil((last + 1) / blocks * len(words))
    return " ".join(words[start:stop])


@contextmanager
def simulated(sim: Simulator, monkeypatch: pytest.MonkeyPatch) -> Iterator[voice.VoiceLoop]:
    """Patch the loop's world for `sim` and yield a fresh VoiceLoop wired to it."""
    patches = {
        (voice, "time"): sim.clock,
        (voice.threading, "Thread"): SyncThread,
        (voice, "_log_voice"): sim.log,
        (voice, "_report"): lambda *_a, **_k: None,
        (voice, "push_to_talk_held"): sim.ptt_held,
        (voice.VoiceLoop, "_speculate"): lambda _loop, _segment: None,
        (audio, "earcon"): sim.earcon,
        (audio, "duck"): lambda: setattr(sim, "ducked", True),
        (audio, "restore"): lambda: setattr(sim, "ducked", False),
        (audio, "is_ducked"): lambda: sim.ducked,
        (audio, "engine"): lambda: sim.engine,
        (speech, "is_speaking"): lambda: sim.clock.now < sim.speaking_until,
        (speech, "narrate"): sim.speak,
        (speech, "cancel"): sim.engine.silence_all,
        (speech, "reset_timing"): lambda: None,
        (orchestrator, "start_task"): sim.start_task,
        (orchestrator, "stop_task"): sim.stop_task,
        (orchestrator, "task_status"): lambda name="": "Nothing is running.",
        (tasks, "running"): lambda: list(sim.running),
        (speculate, "prepare"): lambda _text: 0,
        (speculate, "discard"): lambda: None,
        (speculate, "peek"): lambda _text: None,
        (events, "emit"): lambda _event: None,
        (overlay, "level"): lambda _block: None,
        (voice.decisions, "ask"): lambda *_a, **_k: None,
        (voice.updates, "answer"): lambda _text: False,
    }
    for (target, name), value in patches.items():
        monkeypatch.setattr(target, name, value)
    monkeypatch.setattr(safety, "_channel", None)
    monkeypatch.setattr(tasks, "user_speaking", tasks.user_speaking)
    models = voice.Models(sim.vad, sim.spot, sim.stt, sim.turn)
    loop = voice.VoiceLoop(models=models)
    if sim.aec_on:
        loop.canceller = FakeCanceller(sim)
        loop.onset = aec.OnsetDetector(sim.vad)
    yield loop


def run_script(
    monkeypatch: pytest.MonkeyPatch, sounds: list[Sound], **options: object
) -> tuple[Trace, voice.VoiceLoop]:
    sim = Simulator(sounds, **options)
    with simulated(sim, monkeypatch) as loop:
        return sim.run(loop), loop
