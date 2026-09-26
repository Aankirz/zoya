from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import numpy as np

from zoya import config, permissions, speech
from zoya.decisions import LOOPBACK_HOSTS

STATE_FILE = Path.home() / ".zoya" / "setup.json"
GRANTS_FILE = Path.home() / ".zoya" / "permissions.json"
STATE_MODE = 0o600
POLL_S = 1.0
FRESH_POLL_S = 3.0
REMIND_EVERY_S = 60.0
LISTEN_S = 45.0
SAY_TIMEOUT_S = 60.0
ECHO_TAIL_S = 0.6
END_SILENCE_S = 0.8
MIN_VOICED_S = 0.25
PRE_ROLL_BLOCKS = 10
HTTP_TIMEOUT_S = 10.0
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
REJECTED = (401, 403)
FRESH_CHECK = frozenset({"screen", "microphone"})
DIALOG_FIRST = frozenset({"microphone", "automation"})
LICENSE_SHAPE = re.compile(r"zoya_[A-Za-z0-9_-]{20,200}")
COPIED = re.compile(r"\b(cop(?:y|ied|ies)|done|ready|got it|ho gaya|kar liya)\b", re.I)

LABELS = {
    "accessibility": "Accessibility",
    "screen": "Screen Recording",
    "microphone": "Microphone",
    "automation": "Automation",
}
PURPOSE = {
    "accessibility": "Accessibility lets me read and press the buttons in your apps.",
    "screen": "Screen Recording lets me see your screen, so I can describe it to you.",
    "microphone": "The microphone lets me hear you.",
    "automation": "Automation lets me work inside other apps for you, starting with Notes.",
}
SWITCH = (
    "I've opened System Settings at {label}. Use VoiceOver to move into the list of apps and "
    "find {host}. Next to it is a switch that is off. Press Control Option Space to turn it on. "
    "macOS will then ask for your Mac's password or Touch ID. That request is from macOS, not me."
)
PROMPT_FIRST = "If a box appears first asking about {topic}, choose Open System Settings."
PROMPT_TOPIC = {"accessibility": "accessibility", "screen": "screen recording"}
AFTER_SWITCH = {
    "screen": "macOS may then offer to quit and reopen {host}. Choose Later. I'll restart myself.",
}
DIALOG = {
    "microphone": "A box is asking whether {host} may use the microphone. Choose Allow.",
    "automation": "A box is asking whether {host} may control Notes. Choose Allow.",
}
AUTOMATION_SWITCH = (
    "I've opened System Settings at Automation. Find {host} in the list. Under it is a switch "
    "for Notes. Press Control Option Space to turn it on."
)
INTRO = (
    "Hi, I'm Zoya. Before I can help, I need {count} things set up on this Mac: {items}. "
    "I'll talk you through each one. You can stop at any time, and I'll pick up where we left off."
)
WELCOME_BACK = "Welcome back. Let's carry on with setup."
REVOKED = "Something I need has been turned off: {items}. Let's turn it back on."
STEP = "Next: {label}. {purpose}"
GRANTED = "{label} is on. I checked."
WAITING = "I'm still waiting for {label} to be turned on."
RESTARTING = "{label} is on. macOS needs me to restart before I can use it. I'll be right back."
BACK = "I'm back, and {label} is working."
STILL_BLOCKED = (
    "{label} is turned on, but it still isn't working for me after a restart. "
    "Quit {host} with Command Q, open it again, and start me again."
)
KEY_INTRO = (
    "Next: your Zoya key. It's in the email we sent you when you signed up. "
    "Open that email, select the key, and copy it with Command C. Then say: I've copied it."
)
KEY_REMIND = "Whenever you're ready, copy your Zoya key from the email, then say: I've copied it."
NOT_A_KEY = (
    "What's on the clipboard doesn't look like a Zoya key. A Zoya key starts with the word "
    "zoya and an underscore. Copy the whole key from the email, then say: I've copied it."
)
KEY_INVALID = (
    "That key didn't work. Check that you copied the whole key from the latest email, then say: "
    "I've copied it. If it still fails, reply to that email and we'll send a new one."
)
KEY_UNREACHABLE = (
    "I couldn't reach Zoya's service to check your key. Check your internet connection, then say: "
    "I've copied it, and I'll try again."
)
KEY_SAVED = (
    "Your key works. I've saved it in your Mac's keychain and cleared it from the clipboard."
)
NO_RELAY = (
    "Zoya's service address isn't set up on this Mac yet, so I can't check a key. "
    "Simple commands, like opening an app, will still work."
)
DONE = "That's everything. I'm ready. Say Hey Zoya whenever you need me."
GOODBYE = "Goodbye. I'll pick up setup where we left off next time."


def load_state() -> dict:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    STATE_FILE.chmod(STATE_MODE)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def say(text: str) -> None:
    print(f"ZOYA: {text}", flush=True)
    speech.say_and_wait(text, SAY_TIMEOUT_S)


def own_keys_work() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return False
    request = urllib.request.Request(OPENAI_MODELS_URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S):
            return True
    except urllib.error.HTTPError as error:
        return error.code not in REJECTED
    except (urllib.error.URLError, TimeoutError):
        return True


def key_needed(state: dict) -> bool:
    if config.license_key():
        return False
    has_own_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return not (has_own_key and state.get("finished")) and not own_keys_work()


def _license_url() -> str:
    base = config.relay_url()
    parsed = urllib.parse.urlparse(base)
    secure = parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS
    )
    return f"{base}/v1/license" if base and secure else ""


def validate_license(key: str) -> str:
    request = urllib.request.Request(_license_url(), headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S):
            return "valid"
    except urllib.error.HTTPError as error:
        return "invalid" if error.code == 401 else "unreachable"
    except (urllib.error.URLError, TimeoutError):
        return "unreachable"


def _read_clipboard() -> tuple[str, int]:
    from AppKit import NSPasteboard, NSPasteboardTypeString

    board = NSPasteboard.generalPasteboard()
    return str(board.stringForType_(NSPasteboardTypeString) or ""), board.changeCount()


def _clear_clipboard(change_count: int) -> None:
    from AppKit import NSPasteboard

    board = NSPasteboard.generalPasteboard()
    if board.changeCount() == change_count:
        board.clearContents()


@cache
def _transcriber():  # noqa: ANN202
    from zoya.config import WAKE_MODEL
    from zoya.voice import load_whisper

    return load_whisper(WAKE_MODEL, language="en")


def _record(timeout_s: float) -> np.ndarray | None:
    import sounddevice as sd

    from zoya.config import MIC_SAMPLE_RATE_HZ, VAD_BLOCK, VAD_THRESHOLD
    from zoya.voice import StreamingVad

    vad, block_s = StreamingVad(), VAD_BLOCK / MIC_SAMPLE_RATE_HZ
    kept: list[np.ndarray] = []
    voiced = silent = 0
    deadline = time.monotonic() + timeout_s
    with sd.InputStream(samplerate=MIC_SAMPLE_RATE_HZ, channels=1, dtype="float32") as stream:
        while time.monotonic() < deadline:
            block = stream.read(VAD_BLOCK)[0][:, 0].copy()
            kept.append(block)
            if vad(block) >= VAD_THRESHOLD:
                voiced, silent = voiced + 1, 0
            elif voiced:
                silent += 1
                if silent * block_s >= END_SILENCE_S:
                    break
            else:
                kept = kept[-PRE_ROLL_BLOCKS:]
    return np.concatenate(kept) if voiced * block_s >= MIN_VOICED_S else None


def hear(timeout_s: float = LISTEN_S) -> str:
    time.sleep(ECHO_TAIL_S)
    samples = _record(timeout_s)
    heard = _transcriber()(samples) if samples is not None else ""
    print(f"HEARD {heard!r}", flush=True)
    return heard


def _restart(name: str, state: dict) -> None:
    say(RESTARTING.format(label=LABELS[name]))
    save_state({**state, "restarting_for": name})
    sys.stdout.flush()
    permissions.release_automation_target()
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])


def _instructions(name: str) -> str:
    host = permissions.host_app()
    if name == "automation":
        return AUTOMATION_SWITCH.format(host=host)
    topic = PROMPT_TOPIC.get(name)
    parts = [
        PROMPT_FIRST.format(topic=topic) if topic else "",
        SWITCH.format(label=LABELS[name], host=host),
        AFTER_SWITCH.get(name, "").format(host=host),
    ]
    return " ".join(part for part in parts if part)


def _show_pane(name: str) -> None:
    permissions.open_pane(name)
    say(_instructions(name))


def _begin(name: str) -> bool:
    say(STEP.format(label=LABELS[name], purpose=PURPOSE[name]))
    permissions.request(name)
    if name in DIALOG_FIRST and not permissions.denied(name):
        say(DIALOG[name].format(host=permissions.host_app()))
        return False
    _show_pane(name)
    return True


def _wait_for(name: str) -> str:
    pane_shown = _begin(name)
    remind_at = time.monotonic() + REMIND_EVERY_S
    fresh_at = time.monotonic() + FRESH_POLL_S
    while not permissions.granted(name):
        now = time.monotonic()
        if name in FRESH_CHECK and now >= fresh_at:
            if permissions.granted_fresh(name):
                return "restart"
            fresh_at = now + FRESH_POLL_S
        if not pane_shown and permissions.denied(name):
            _show_pane(name)
            pane_shown, remind_at = True, time.monotonic() + REMIND_EVERY_S
        elif now >= remind_at:
            say(WAITING.format(label=LABELS[name]))
            if pane_shown:
                _show_pane(name)
            else:
                permissions.request(name)
            remind_at = time.monotonic() + REMIND_EVERY_S
        time.sleep(POLL_S)
    return "granted"


def grant(name: str, state: dict) -> None:
    if _wait_for(name) == "restart":
        if state.get("restarting_for") == name:
            say(STILL_BLOCKED.format(label=LABELS[name], host=permissions.host_app()))
            raise SystemExit(0)
        _restart(name, state)
    say(GRANTED.format(label=LABELS[name]))
    save_state({**state, "restarting_for": ""})


def _heard_copied() -> bool:
    from zoya.shutdown import is_quit_phrase

    heard = hear()
    if is_quit_phrase(heard):
        say(GOODBYE)
        raise SystemExit(0)
    if not heard:
        say(KEY_REMIND)
    return bool(COPIED.search(heard))


def _try_clipboard() -> bool:
    key, change_count = _read_clipboard()
    key = key.strip()
    if not LICENSE_SHAPE.fullmatch(key):
        say(NOT_A_KEY)
        return False
    verdict = validate_license(key)
    if verdict != "valid":
        say(KEY_INVALID if verdict == "invalid" else KEY_UNREACHABLE)
        return False
    config.save_license_key(key)
    _clear_clipboard(change_count)
    say(KEY_SAVED)
    return True


def license_step(state: dict) -> None:
    if not _license_url():
        say(NO_RELAY)
        return
    say(KEY_INTRO)
    while not (_heard_copied() and _try_clipboard()):
        pass
    save_state({**load_state(), "license": "keychain"})


def _items(missing: list[str], key: bool) -> list[str]:
    items = [LABELS[name] for name in missing]
    return [*items, "your Zoya key"] if key else items


def _greet(state: dict, missing: list[str], key: bool) -> None:
    restarting = state.get("restarting_for", "")
    items = _items(missing, key)
    if restarting and restarting not in missing:
        say(BACK.format(label=LABELS[restarting]))
        return
    if not state.get("introduced"):
        spoken = ", ".join(items[:-1]) + f", and {items[-1]}" if len(items) > 1 else items[0]
        say(INTRO.format(count=len(items), items=spoken))
        return
    say(REVOKED.format(items=", ".join(items)) if state.get("finished") else WELCOME_BACK)


def run() -> None:
    try:
        _run()
    finally:
        permissions.release_automation_target()


def record_grants(missing: list[str]) -> None:
    checked = {
        "version": config.app_version(),
        "checked_at": _now(),
        "granted": {name: name not in missing for name in permissions.PERMISSIONS},
    }
    GRANTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GRANTS_FILE.write_text(json.dumps(checked, indent=2), encoding="utf-8")


def _run() -> None:
    state = load_state()
    missing = [name for name in permissions.PERMISSIONS if not permissions.granted(name)]
    record_grants(missing)
    key = key_needed(state)
    if not missing and not key and not state.get("restarting_for"):
        if not state.get("finished"):
            save_state({**state, "finished": _now()})
        return
    _greet(state, missing, key)
    restarting = state.get("restarting_for", "")
    state = {
        **state,
        "introduced": state.get("introduced") or _now(),
        "restarting_for": restarting if restarting in missing else "",
    }
    save_state(state)
    for name in missing:
        grant(name, state)
        state = load_state()
    if key:
        license_step(state)
    save_state({**load_state(), "restarting_for": "", "finished": _now()})
    say(DONE)
