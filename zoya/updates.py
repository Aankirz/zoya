from __future__ import annotations

import re
import threading
from pathlib import Path

from zoya import config

LAST_VERSION_FILE = Path.home() / ".zoya" / "version"
QUESTION = "There's a new version of me. Should I update now?"
UPDATING = "Updating now. I'll be back in about a minute."
LATER = "Okay, I'll ask again another day."
UPDATED = "I've updated myself to version {version}."
INSTALL = "install"
DISMISS = "later"
_WAKE = r"(?:(?:hey\s+|ok\s+|okay\s+)?(?:zoya|zoyaa|soya)\s+)?"
_POLITE = r"(?:\s+(?:please|now|ji))*"
YES = re.compile(
    rf"^{_WAKE}(?:yes|yeah|yep|sure|ok|okay|haan|han|go ahead|do it|update(?: yourself)?)"
    rf"(?:\s+(?:update|do it))?{_POLITE}$"
)
NO = re.compile(rf"^{_WAKE}(?:no|nope|not now|later|nahi|na|don't|do not)(?:\s+update)?{_POLITE}$")

_lock = threading.Lock()
_offered = False


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s']", " ", text.lower()).split())


def reply_for(text: str) -> str:
    spoken = _words(text)
    if YES.match(spoken):
        return INSTALL
    if NO.match(spoken):
        return DISMISS
    return ""


def offer() -> None:
    global _offered
    from zoya import audio, speech

    with _lock:
        _offered = True
    audio.earcon("attention")
    speech.narrate(QUESTION)


def answer(text: str) -> bool:
    global _offered
    with _lock:
        if not _offered:
            return False
        choice = reply_for(text)
        if not choice:
            return False
        _offered = False
    from zoya import overlay, speech

    overlay.send({"update": choice})
    speech.narrate(UPDATING if choice == INSTALL else LATER)
    return True


def announce_if_updated() -> None:
    current = config.app_version()
    try:
        previous = LAST_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        previous = ""
    if previous == current:
        return
    LAST_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_VERSION_FILE.write_text(current, encoding="utf-8")
    if previous:
        from zoya import speech

        speech.narrate(UPDATED.format(version=current))
