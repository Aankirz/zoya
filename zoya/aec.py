"""Echo cancellation (D62): WebRTC AEC3 removes Zoya's own voice and other apps' audio from the mic.

Far end ("reference") = what Zoya's mixer plays + a Core Audio process tap of every other process
(Spotify, a browser tab, the macOS `say` fallback). The mic callback notes how far each reference
stream has got; the voice loop thread pairs and cancels in 10 ms frames, one mic block late. Audio
callbacks never wait more than REFERENCE_LOCK_TIMEOUT_S: missing reference = less cancellation.

APIs (verified against installed livekit 1.1.18 and pyobjc-framework-CoreAudio 12.2.2, 2026-09-14):
- livekit-rtc/livekit/rtc/apm.py https://github.com/livekit/python-sdks — AudioProcessingModule,
  process_reverse_stream / process_stream on exactly-10 ms int16 AudioFrames, set_stream_delay_ms.
- https://developer.apple.com/documentation/coreaudio/capturing-system-audio-with-core-audio-taps
  — CATapDescription → AudioHardwareCreateProcessTap → tap UID in a private aggregate device
  (macOS 14.2+, "System Audio Recording" permission). AudioDeviceCreateIOProcID reads it (ctypes:
  pyobjc's block variant returns an IOProcID that AudioDeviceStart rejects).
"""

from __future__ import annotations

import atexit
import ctypes as ct
import logging
import os
import threading
import uuid
from collections import deque
from functools import cache

import numpy as np

from zoya.config import (
    AEC_MIC_DELAY_BLOCKS,
    AEC_NOISE_SUPPRESSION,
    AEC_REANCHOR_S,
    AEC_TAP_START_TIMEOUT_S,
    MIC_SAMPLE_RATE_HZ,
    REFERENCE_LOCK_TIMEOUT_S,
    REFERENCE_MAX_S,
)

log = logging.getLogger(__name__)

FRAME = MIC_SAMPLE_RATE_HZ // 100  # AEC3 takes exactly 10 ms
INT16_MAX = 32767
MS_PER_S = 1000
REFERENCE_MAX = int(REFERENCE_MAX_S * MIC_SAMPLE_RATE_HZ)
REANCHOR_SAMPLES = int(AEC_REANCHOR_S * MIC_SAMPLE_RATE_HZ)
OFFSET_WINDOW_BLOCKS = 64  # ~2 s of mic blocks to find the on-time offset
PLAYBACK, TAP = "playback", "tap"
COREAUDIO = "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"


def to_mic_rate(samples: np.ndarray, rate: int, carry: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mono float32 at `rate` → MIC_SAMPLE_RATE_HZ. Integer ratios average (a cheap anti-alias)."""
    if rate == MIC_SAMPLE_RATE_HZ:
        return samples, carry
    if rate % MIC_SAMPLE_RATE_HZ:  # e.g. a 44.1 kHz output device
        count = int(len(samples) * MIC_SAMPLE_RATE_HZ / rate)
        positions = np.arange(count) * rate / MIC_SAMPLE_RATE_HZ
        return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32), carry
    step = rate // MIC_SAMPLE_RATE_HZ
    joined = np.concatenate([carry, samples])
    whole = len(joined) // step * step
    return joined[:whole].reshape(-1, step).mean(axis=1), joined[whole:]


class Reference:
    """Far-end audio at the mic rate: per source, the last REFERENCE_MAX_S and a count of samples.

    Sources arrive in 10 ms chunks with ~15 ms jitter, so a FIFO popped by 32 ms mic blocks kept
    underrunning and scrambled the reference (live ERLE 2 dB). Instead the reader addresses samples
    by their position in each source's contiguous stream.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rings = {PLAYBACK: np.zeros(0, np.float32), TAP: np.zeros(0, np.float32)}
        self._carry = {PLAYBACK: np.zeros(0, np.float32), TAP: np.zeros(0, np.float32)}
        self.fed = {PLAYBACK: 0, TAP: 0}

    def feed(self, source: str, samples: np.ndarray, rate: int) -> None:
        down, self._carry[source] = to_mic_rate(samples, rate, self._carry[source])
        if not self._lock.acquire(timeout=REFERENCE_LOCK_TIMEOUT_S):
            return  # never stall an audio callback: a dropped chunk shifts that source; re-anchored
        try:
            self._rings[source] = np.concatenate([self._rings[source], down])[-REFERENCE_MAX:]
            self.fed[source] += len(down)
        finally:
            self._lock.release()

    def counts(self) -> dict[str, int]:
        """Called from the mic callback: plain ints, no copy."""
        return dict(self.fed)

    def read(self, source: str, start: int, count: int) -> np.ndarray | None:
        """Samples [start, start + count) of a source's stream, or None if not held."""
        if not self._lock.acquire(timeout=REFERENCE_LOCK_TIMEOUT_S):
            return None
        try:
            ring, fed = self._rings[source], self.fed[source]
            first = fed - len(ring)
            if start < first or start + count > fed:
                return None
            return ring[start - first : start - first + count].copy()
        finally:
            self._lock.release()


class LiveCanceller:
    """Pairs mic blocks with the reference and cancels, one mic block late (AEC_MIC_DELAY_BLOCKS).

    Measured on the MacBook speakers: the tap delivers other apps' audio up to ~30 ms after the mic
    hears it, so the mic waits one 32 ms block; with that both sources cancel ~24 dB. Per source,
    offset = samples fed − mic samples seen; jitter only makes chunks late, so the running maximum
    is the on-time offset. It is re-anchored (and logged) only when it moves > REANCHOR_S.
    """

    def __init__(self, reference: Reference) -> None:
        self._reference = reference
        self._canceller = Canceller()
        self._mic_seen = 0
        self._pending: deque[tuple[np.ndarray, int]] = deque()
        self._recent = {source: deque(maxlen=OFFSET_WINDOW_BLOCKS) for source in reference.fed}
        self.offsets: dict[str, int | None] = dict.fromkeys(reference.fed)

    def process(self, mic: np.ndarray, counts: dict[str, int]) -> np.ndarray:
        self._mic_seen += len(mic)
        for source, fed in counts.items():
            self._track(source, fed - self._mic_seen)
        self._pending.append((mic, self._mic_seen))
        if len(self._pending) <= AEC_MIC_DELAY_BLOCKS:
            return np.zeros(len(mic), np.float32)  # the first block of a run: silence, once
        late, mic_end = self._pending.popleft()
        return self._canceller.process(late, self._far_end(len(late), mic_end))

    def _track(self, source: str, offset: int) -> None:
        self._recent[source].append(offset)
        on_time, current = max(self._recent[source]), self.offsets[source]
        if current is None or abs(on_time - current) > REANCHOR_SAMPLES:
            self.offsets[source] = on_time
            log.info("aec %s offset %+d ms", source, on_time * MS_PER_S // MIC_SAMPLE_RATE_HZ)

    def _far_end(self, count: int, mic_end: int) -> np.ndarray:
        total = np.zeros(count, np.float32)
        for source, offset in self.offsets.items():
            if offset is None:
                continue
            piece = self._reference.read(source, mic_end + offset - count, count)
            if piece is not None:
                total += piece
        return total


class Canceller:
    """AEC3 over blocks of any size; one 10 ms frame of priming keeps every output block full."""

    def __init__(self) -> None:
        from livekit import rtc

        self._rtc = rtc
        self._apm = rtc.AudioProcessingModule(
            echo_cancellation=True, noise_suppression=AEC_NOISE_SUPPRESSION, high_pass_filter=True
        )
        self._apm.set_stream_delay_ms(0)  # AEC3's own delay estimator aligns (measured 30–500 ms)
        self._mic = np.zeros(0, np.float32)
        self._ref = np.zeros(0, np.float32)
        self._out = np.zeros(FRAME, np.float32)

    def process(self, mic: np.ndarray, ref: np.ndarray) -> np.ndarray:
        self._mic = np.concatenate([self._mic, mic])
        self._ref = np.concatenate([self._ref, ref])
        frames = len(self._mic) // FRAME
        cleaned = [self._frame(index) for index in range(frames)]
        self._mic, self._ref = self._mic[frames * FRAME :], self._ref[frames * FRAME :]
        self._out = np.concatenate([self._out, *cleaned])
        block, self._out = self._out[: len(mic)], self._out[len(mic) :]
        return block

    def _frame(self, index: int) -> np.ndarray:
        part = slice(index * FRAME, (index + 1) * FRAME)
        mic = self._int16_frame(self._mic[part])
        try:
            self._apm.process_reverse_stream(self._int16_frame(self._ref[part]))
            self._apm.process_stream(mic)
        except RuntimeError as error:  # pass the mic through rather than lose the user's voice
            log.warning("echo cancellation failed (%s)", error)
            return self._mic[part]
        return np.frombuffer(mic.data, dtype=np.int16).astype(np.float32) / INT16_MAX

    def _int16_frame(self, samples: np.ndarray):  # noqa: ANN202 — livekit AudioFrame
        pcm = (np.clip(samples, -1.0, 1.0) * INT16_MAX).astype("<i2").tobytes()
        return self._rtc.AudioFrame(pcm, MIC_SAMPLE_RATE_HZ, 1, FRAME)


# --- Core Audio process tap: other apps' output as reference ------------------------------------


class _AudioBuffer(ct.Structure):
    _fields_ = [
        ("mNumberChannels", ct.c_uint32),
        ("mDataByteSize", ct.c_uint32),
        ("mData", ct.c_void_p),
    ]


class _AudioBufferList(ct.Structure):
    _fields_ = [("mNumberBuffers", ct.c_uint32), ("mBuffers", _AudioBuffer * 1)]


class _PropertyAddress(ct.Structure):
    _fields_ = [("mSelector", ct.c_uint32), ("mScope", ct.c_uint32), ("mElement", ct.c_uint32)]


_IOProc = ct.CFUNCTYPE(
    ct.c_int32,
    ct.c_uint32,
    ct.c_void_p,
    ct.POINTER(_AudioBufferList),
    ct.c_void_p,
    ct.c_void_p,
    ct.c_void_p,
    ct.c_void_p,
)


def _property(object_id: int, selector: int, value, qualifier=None) -> None:  # noqa: ANN001
    import CoreAudio

    lib = ct.CDLL(COREAUDIO)
    address = _PropertyAddress(
        selector,
        CoreAudio.kAudioObjectPropertyScopeGlobal,
        CoreAudio.kAudioObjectPropertyElementMain,
    )
    size = ct.c_uint32(ct.sizeof(value))
    qualifier_size = ct.sizeof(qualifier) if qualifier is not None else 0
    qualifier_ptr = ct.byref(qualifier) if qualifier is not None else None
    status = lib.AudioObjectGetPropertyData(
        ct.c_uint32(object_id),
        ct.byref(address),
        ct.c_uint32(qualifier_size),
        qualifier_ptr,
        ct.byref(size),
        ct.byref(value),
    )
    if status:
        raise OSError(f"AudioObjectGetPropertyData {selector} → {status}")


class Tap:
    """A mono tap of every process except Zoya, read through a private aggregate device."""

    def __init__(self, reference: Reference) -> None:
        import CoreAudio

        self._reference = reference
        self._lib = ct.CDLL(COREAUDIO)
        self._lib.AudioDeviceCreateIOProcID.argtypes = [
            ct.c_uint32,
            _IOProc,
            ct.c_void_p,
            ct.POINTER(ct.c_void_p),
        ]
        for name in ("AudioDeviceStart", "AudioDeviceStop", "AudioDeviceDestroyIOProcID"):
            getattr(self._lib, name).argtypes = [ct.c_uint32, ct.c_void_p]
        ourselves = ct.c_uint32()
        _property(
            CoreAudio.kAudioObjectSystemObject,
            CoreAudio.kAudioHardwarePropertyTranslatePIDToProcessObject,
            ourselves,
            ct.c_int32(os.getpid()),
        )
        description = CoreAudio.CATapDescription.alloc().initMonoGlobalTapButExcludeProcesses_(
            [ourselves.value] if ourselves.value else []
        )
        description.setPrivate_(True)
        description.setMuteBehavior_(CoreAudio.CATapUnmuted)
        status, self._tap = CoreAudio.AudioHardwareCreateProcessTap(description, None)
        if status:
            raise OSError(f"AudioHardwareCreateProcessTap → {status}")
        # pyobjc exposes the dictionary keys as bytes; CFDictionary needs str keys.
        aggregate = {
            "name": "Zoya echo reference",
            "uid": f"zoya-aec-{uuid.uuid4()}",
            "private": True,
            "tapautostart": True,
            "taps": [{"uid": description.UUID().UUIDString(), "drift": True}],
        }
        status, self._device = CoreAudio.AudioHardwareCreateAggregateDevice(aggregate, None)
        if status:
            CoreAudio.AudioHardwareDestroyProcessTap(self._tap)
            raise OSError(f"AudioHardwareCreateAggregateDevice → {status}")
        rate = ct.c_double()
        _property(self._device, CoreAudio.kAudioDevicePropertyNominalSampleRate, rate)
        self.rate = int(rate.value)
        self._callback = _IOProc(self._on_audio)  # keep a reference: Core Audio calls it later
        self._proc = ct.c_void_p()
        status = self._lib.AudioDeviceCreateIOProcID(
            self._device, self._callback, None, ct.byref(self._proc)
        )
        if status or self._lib.AudioDeviceStart(self._device, self._proc):
            self.close()
            raise OSError(f"tap IOProc failed to start ({status})")

    def _on_audio(
        self, _device, _now, buffers, _in_time, _out, _out_time, _client
    ) -> int:  # noqa: ANN001
        buffer = buffers.contents.mBuffers[0]
        if buffer.mData and buffer.mDataByteSize:
            count = buffer.mDataByteSize // ct.sizeof(ct.c_float)
            pointer = ct.cast(buffer.mData, ct.POINTER(ct.c_float))
            self._reference.feed(TAP, np.ctypeslib.as_array(pointer, (count,)).copy(), self.rate)
        return 0

    def close(self) -> None:
        import CoreAudio

        if self._proc:
            self._lib.AudioDeviceStop(self._device, self._proc)
            self._lib.AudioDeviceDestroyIOProcID(self._device, self._proc)
            self._proc = ct.c_void_p()
        CoreAudio.AudioHardwareDestroyAggregateDevice(self._device)
        CoreAudio.AudioHardwareDestroyProcessTap(self._tap)


@cache
def reference() -> Reference:
    """The shared far end; starts the tap once (bounded). No tap: only Zoya's voice cancels."""
    shared = Reference()
    started: list[Tap] = []

    def start() -> None:
        try:
            started.append(Tap(shared))
        except Exception as error:  # noqa: BLE001 — Zoya's own voice still cancels without the tap
            log.warning("system audio tap unavailable (%s): only Zoya's voice is cancelled", error)

    worker = threading.Thread(target=start, name="zoya-tap", daemon=True)
    worker.start()
    worker.join(AEC_TAP_START_TIMEOUT_S)
    if started:
        atexit.register(started[0].close)
        log.info("system audio tap running at %d Hz", started[0].rate)
    elif worker.is_alive():
        log.warning("system audio tap took > %.0f s to start: skipped", AEC_TAP_START_TIMEOUT_S)
    return shared
