from __future__ import annotations

import copy
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
from types import TracebackType

from zoya.config import LOG_DIR, MACOS_FALLBACK_VOICE, SAY_TIMEOUT_S
from zoya.safety import redact

APP_LOG = LOG_DIR / "zoya.log"
APP_LOG_MAX_BYTES = 2_000_000
APP_LOG_BACKUPS = 2
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(threadName)s]: %(message)s"
CONSOLE_FORMAT = "%(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
SPEAK_TIMEOUT_S = 12.0
SPOKEN_GAP_S = 20.0
SUPERVISED_ENV = "ZOYA_SUPERVISED"
RESTARTED_ENV = "ZOYA_RESTARTED_AFTER_CRASH"

MAIN_RESTARTING = (
    "Something went wrong inside me, so I have to restart. I'll be back in a few seconds."
)
MAIN_STOPPING = (
    "Something went wrong inside me, so I have to stop. Start me again when you're ready."
)
BACKGROUND = (
    "Something went wrong in the background. I've noted it for the problem report, "
    "and I'm carrying on."
)
TASK = "The {name} task ran into a problem and stopped. Everything else still works."
RESTARTED = "I stopped unexpectedly a moment ago, so I restarted myself. I'm ready again."

log = logging.getLogger(__name__)
_last_spoken = 0.0
_spoken_lock = threading.Lock()


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, tracebacks: bool) -> None:
        super().__init__(fmt, datefmt=LOG_DATE_FORMAT)
        self.tracebacks = tracebacks

    def format(self, record: logging.LogRecord) -> str:
        if not self.tracebacks:
            record = copy.copy(record)
            record.exc_info, record.exc_text, record.stack_info = None, None, None
        return redact(super().format(record))


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    to_file = logging.handlers.RotatingFileHandler(
        APP_LOG, maxBytes=APP_LOG_MAX_BYTES, backupCount=APP_LOG_BACKUPS, encoding="utf-8"
    )
    to_file.setFormatter(RedactingFormatter(LOG_FORMAT, tracebacks=True))
    to_console = logging.StreamHandler()
    to_console.setFormatter(RedactingFormatter(CONSOLE_FORMAT, tracebacks=False))
    logging.basicConfig(level=logging.WARNING, handlers=[to_file, to_console], force=True)


def say_directly(text: str) -> None:
    command = ["say", "-v", MACOS_FALLBACK_VOICE, text]
    try:
        subprocess.run(command, capture_output=True, timeout=SAY_TIMEOUT_S, check=True)
    except (subprocess.SubprocessError, OSError):
        subprocess.run(["say", text], capture_output=True, timeout=SAY_TIMEOUT_S, check=False)


def speak(text: str, always: bool = False) -> None:
    global _last_spoken
    with _spoken_lock:
        if not always and time.monotonic() - _last_spoken < SPOKEN_GAP_S:
            return
        _last_spoken = time.monotonic()
    print(f"ZOYA: {text}", flush=True)
    try:
        from zoya import speech

        speech.say_and_wait(text, SPEAK_TIMEOUT_S)
    except Exception:  # noqa: BLE001
        say_directly(text)


def supervised() -> bool:
    return os.environ.get(SUPERVISED_ENV) == "1"


def _main_thread_crash(
    kind: type[BaseException], error: BaseException, trace: TracebackType | None
) -> None:
    if issubclass(kind, KeyboardInterrupt):
        sys.__excepthook__(kind, error, trace)
        return
    log.critical("Zoya stopped on an unhandled error", exc_info=(kind, error, trace))
    speak(MAIN_RESTARTING if supervised() else MAIN_STOPPING, always=True)


def _thread_crash(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit:
        return
    thread = args.thread.name if args.thread else "unknown"
    log.error(
        "thread %s crashed", thread, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )
    speak(BACKGROUND)


def task_crashed(name: str) -> None:
    log.exception("task %s crashed", name)
    speak(TASK.format(name=name), always=True)


def install() -> None:
    configure_logging()
    sys.excepthook = _main_thread_crash
    threading.excepthook = _thread_crash


def announce_restart() -> None:
    if os.environ.pop(RESTARTED_ENV, "") == "1":
        speak(RESTARTED, always=True)
