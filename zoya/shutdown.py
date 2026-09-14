"""Stop and quit from outside the voice loop: the menu-bar item, Control + Shift + Esc, and the
"Zoya, quit" phrase all land here.

Stop ends the current work, like "Zoya, stop". Quit ends every task, says "Goodbye." and sends
Zoya SIGTERM, which main.py already turns into the Ctrl+C path (speech cut, volume restored;
the overlay child and Playwright's driver exit when their pipes to Zoya close). Neither ever
confirms or clicks anything: a waiting confirmation is cancelled with no token.
"""

from __future__ import annotations

import os
import re
import signal
import threading

GOODBYE = "Goodbye."
GOODBYE_TIMEOUT_S = 3.0  # quitting never hangs on a slow voice
QUIT_KEYS_LABEL = "Control + Shift + Esc"

_NAME = r"(?:hey\s+|ok\s+|okay\s+)?(?:zoya|zoyaa|soya)"
_POLITE = r"(?:please|now|right now|ji)"
_VERB = r"(?:quit|exit|shut\s*down|band\s+karo|bandh\s+karo|बंद\s+करो)"
# Whole utterance only: "music band karo" or "quit the app" is not quitting Zoya.
QUIT_RE = re.compile(rf"^(?:{_NAME}\s+)?(?:{_POLITE}\s+)?{_VERB}(?:\s+{_NAME})?(?:\s+{_POLITE})?$")

_quitting = threading.Lock()


def is_quit_phrase(text: str) -> bool:
    words = re.sub(r"[^\w\sऀ-ॿ]", " ", text.lower())
    return bool(QUIT_RE.match(" ".join(words.split())))


def stop() -> None:
    """The menu's Stop: the voice loop's "Zoya, stop" minus its listening state."""
    from zoya import audio, orchestrator

    said = orchestrator.stop_task()
    print(f"STOP (menu) — {said}", flush=True)
    audio.engine().silence_all()
    audio.earcon("stop")
    audio.restore()


def quit_zoya(say_goodbye: bool = True) -> None:
    """End every task, say goodbye, then SIGTERM ourselves. Safe to call twice, from any thread."""
    if not _quitting.acquire(blocking=False):
        return
    from zoya import orchestrator, safety, speech

    print("QUIT — Goodbye.", flush=True)
    orchestrator.stop_task("everything")
    orchestrator.stop_task()
    safety.cancel_pending()
    if say_goodbye:
        speech.say_and_wait(GOODBYE, GOODBYE_TIMEOUT_S)
    os.kill(os.getpid(), signal.SIGTERM)
