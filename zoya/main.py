"""Hands-free Zoya (Phase 2): wake word, push-to-talk, earcons, streamed speech.

Usage:
  python -m zoya.main                         # "Hey Zoya" + push-to-talk (hold fn + Shift)
  python -m zoya.main --no-wake               # push-to-talk only (Done-when #5)
  python -m zoya.main --test-wake             # print wake/stop detections + timings, run nothing
  python -m zoya.main --test-wake --record-clips  # also save each utterance to logs/wake_clips/
  python -m zoya.main --disable-tts polly     # Polly off → ElevenLabs → macOS voice (#7)
Every stage's timing is printed and appended to logs/timing.log. Ctrl+C quits.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

from zoya.config import DISABLE_TTS_ENV, TIMING_LOG, load_env


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m zoya.main", description=__doc__)
    parser.add_argument("--no-wake", action="store_true", help="push-to-talk only")
    parser.add_argument("--test-wake", action="store_true", help="detect and time; run nothing")
    parser.add_argument(
        "--record-clips", action="store_true", help="with --test-wake: save logs/wake_clips/*.wav"
    )
    parser.add_argument("--disable-tts", default="", help="comma list: polly,elevenlabs")
    return parser.parse_args(argv)


def _start(args: argparse.Namespace):  # noqa: ANN202 — returns VoiceLoop, imported lazily
    started = time.monotonic()
    from zoya import audio, aws
    from zoya.__main__ import _warm_up
    from zoya.orchestrator import setup_tracing
    from zoya.voice import VoiceLoop

    print(f"keys: {aws.load_provider_secrets()}")
    print(f"tracing: {setup_tracing()}")
    audio.engine()
    _warm_up()
    loop = VoiceLoop(
        wake_enabled=not args.no_wake, test_wake=args.test_wake, record_clips=args.record_clips
    )
    print(f"ready in {time.monotonic() - started:.1f} s — timing log: {TIMING_LOG}")
    return loop


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    load_env()
    if args.disable_tts:
        os.environ[DISABLE_TTS_ENV] = args.disable_tts
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("zoya.speech").setLevel(logging.INFO)  # tts engine + first-chunk timing
    logging.getLogger("botocore.credentials").setLevel(logging.CRITICAL)

    from zoya import audio, speech

    loop = _start(args)
    from zoya.voice import push_to_talk_label

    keys = push_to_talk_label()
    wake = f"off — hold {keys} to talk" if args.no_wake else f'say "Hey Zoya", or hold {keys}'
    print(f"Listening ({wake}). Ctrl+C quits.")
    audio.earcon("listening")
    stop_event = threading.Event()
    try:
        loop.run(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        speech.cancel()  # Ctrl+C means quit now, even mid-sentence
        audio.restore_blocking()  # never leave the Mac ducked, even after a crash
    return 0


if __name__ == "__main__":
    sys.exit(main())
