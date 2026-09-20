"""Hands-free Zoya (Phase 2): wake word, push-to-talk, earcons, streamed speech.

Usage:
  python -m zoya.main                         # "Hey Zoya" + push-to-talk (hold fn + Shift)
  python -m zoya.main --no-wake               # push-to-talk only (Done-when #5)
  python -m zoya.main --test-wake             # print wake/stop detections + timings, run nothing
  python -m zoya.main --test-wake --record-clips  # also save each utterance to logs/wake_clips/
  python -m zoya.main --disable-tts polly     # Polly off → ElevenLabs → macOS voice (#7)
  python -m zoya.main --page http://127.0.0.1:8765/place_order.html  # open a page in Zoya's browser
  python -m zoya.main --login                 # sign in once: Amazon.in, YouTube, Spotify, Gmail
  python -m zoya.main --order-limit 300       # Done-when #5 test run: never offer a bigger order
  python -m zoya.main --overlay               # stage overlay: presence, captions, action ring
Every stage's timing is printed and appended to logs/timing.log. Quit: Control + Shift + Esc,
the Zoya menu-bar item, or Ctrl+C.
"""

from __future__ import annotations

import os

# Before any Hugging Face / mlx import: models load from the local cache only. A Hub revision check
# over a black-holed IPv6 route hung startup forever (AUDIT §6). Download: zoya.setup_models.
os.environ["HF_HUB_OFFLINE"] = "1"

import argparse  # noqa: E402
import logging  # noqa: E402
import signal  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from zoya.config import DISABLE_TTS_ENV, TIMING_LOG, load_env  # noqa: E402


def _raise_interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt  # the finally in main() restores the volume


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m zoya.main", description=__doc__)
    parser.add_argument("--no-wake", action="store_true", help="push-to-talk only")
    parser.add_argument("--test-wake", action="store_true", help="detect and time; run nothing")
    parser.add_argument(
        "--record-clips", action="store_true", help="with --test-wake: save logs/wake_clips/*.wav"
    )
    parser.add_argument("--disable-tts", default="", help="comma list: polly,elevenlabs")
    parser.add_argument("--page", default="", help="open this page in Zoya's browser (Phase 3)")
    parser.add_argument("--login", action="store_true", help="open the Zoya profile to sign in")
    parser.add_argument("--overlay", action="store_true", help="stage overlay for judges (§9.11)")
    parser.add_argument("--order-limit", default="", help="rupees; bigger orders are never offered")
    return parser.parse_args(argv)


def _warm_jev() -> None:
    """Jev's TLS connection, opened before the first question rather than on the voice path.

    Unconditional: `_warm_browser` is skipped when --page is given, and the first call of a
    process was measured at 948-1,034 ms against ~424 ms once a connection is open.
    """
    from zoya import decisions

    decisions.warm()


def _warm_browser() -> None:
    """§9.7: the skill catalogue, trigger index and Playwright driver at startup; Chrome itself
    opens on first use (browser.warm)."""
    from zoya import harness
    from zoya.tools import ToolError, browser

    harness.trigger_index()
    try:
        browser.warm()
    except ToolError as error:
        print(f"Zoya's browser didn't start: {error}")


def _start(args: argparse.Namespace):  # noqa: ANN202 — returns VoiceLoop, imported lazily
    started = time.monotonic()
    from zoya import audio, aws
    from zoya.__main__ import _warm_up
    from zoya.orchestrator import setup_tracing
    from zoya.voice import VoiceLoop

    print(f"keys: {aws.load_provider_secrets()}")
    print(f"tracing: {setup_tracing()}")
    from zoya import overlay

    print(f"overlay: {overlay.start(presence=args.overlay)}")  # menu-bar Stop / Quit always
    audio.engine()
    _warm_up()
    threading.Thread(target=_warm_jev, name="zoya-jev-warm", daemon=True).start()
    if not args.page:  # --page launches it right away below
        threading.Thread(target=_warm_browser, name="zoya-browser-warm", daemon=True).start()
    loop = VoiceLoop(
        wake_enabled=not args.no_wake, test_wake=args.test_wake, record_clips=args.record_clips
    )
    if args.page:
        from zoya.tools import ToolError
        from zoya.tools.browser import browser_open

        try:
            print(browser_open(url=args.page))
        except ToolError as error:
            print(f"Couldn't open {args.page}: {error}")
    print(f"ready in {time.monotonic() - started:.1f} s — timing log: {TIMING_LOG}")
    return loop


def open_login_sites() -> int:
    """Onboarding (D60): normal Chrome on the Zoya profile, so Google allows the sign-in and the
    cookies land in the real keychain that Zoya's Playwright launch reads (coordinator)."""
    import subprocess

    from zoya.config import BROWSER_PROFILE_DIR, LOGIN_SITES

    command = [
        "open",
        "-na",
        "Google Chrome",
        "--args",
        f"--user-data-dir={BROWSER_PROFILE_DIR}",
        *LOGIN_SITES,
    ]
    result = subprocess.run(command, stdin=subprocess.DEVNULL, timeout=10, check=False)
    print("Sign in to each tab, then quit that Chrome window (Cmd+Q) before starting Zoya.")
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.login:
        return open_login_sites()
    load_env()
    if args.order_limit:
        from zoya.config import ORDER_LIMIT_ENV

        os.environ[ORDER_LIMIT_ENV] = args.order_limit
    if args.disable_tts:
        os.environ[DISABLE_TTS_ENV] = args.disable_tts
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("zoya.speech").setLevel(logging.INFO)  # tts engine + first-chunk timing
    logging.getLogger("botocore.credentials").setLevel(logging.CRITICAL)

    from zoya import audio, speech
    from zoya.setup_models import ModelsMissing

    audio.restore_after_kill()  # before anything else: undo a previous run killed while ducked
    for quit_signal in (signal.SIGTERM, signal.SIGHUP):  # kill / terminal closed → same as Ctrl+C
        signal.signal(quit_signal, _raise_interrupt)
    try:
        loop = _start(args)
    except ModelsMissing as missing:
        print(f"Zoya can't start: {missing}")
        return 1
    from zoya.shutdown import QUIT_KEYS_LABEL
    from zoya.voice import push_to_talk_label

    keys = push_to_talk_label()
    wake = f"off — hold {keys} to talk" if args.no_wake else f'say "Hey Zoya", or hold {keys}'
    print(f"Listening ({wake}). Quit: {QUIT_KEYS_LABEL}, the menu bar, or Ctrl+C.")
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
