from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from zoya import config
from zoya.safety import redact

REPORT_PHRASE = re.compile(
    r"\b(?:send|make|create|write)\s+(?:me\s+)?(?:a\s+|the\s+)?"
    r"(?:problem|bug|diagnostics?|error)\s+report\b",
    re.I,
)
DESKTOP = Path.home() / "Desktop"
LOG_TAIL_LINES = 2000
LOG_FILES = ("zoya.log", "zoya.log.1", "timing.log")
PERSONAL_FIELDS = frozenset(
    {
        "command",
        "content",
        "heard",
        "held_words",
        "partial",
        "recipient_or_item",
        "spoken",
        "text",
        "transcript",
    }
)
PERSONAL = "[personal]"
REDACTED = "[redacted]"
SECRET_NAME = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|DATABASE_URL|CREDENTIAL", re.I)
MIN_LITERAL_CHARS = 8
MODEL_ENV = ("MODEL_PROVIDER", "BRAIN_MODEL", "VISION_MODEL", "ROUTER_MODEL", "JEV_MODEL")
GIT_TIMEOUT_S = 3
STARTED = "Making a problem report."
SAVED = (
    "I've saved a problem report on your Desktop, called {name}. "
    "It has no passwords or keys in it. You can attach it to an email to us."
)
FAILED = "I couldn't make the problem report, because {reason}."


def is_report_phrase(text: str) -> bool:
    return bool(REPORT_PHRASE.search(text))


def _secret_literals() -> list[str]:
    values = [value for name, value in os.environ.items() if SECRET_NAME.search(name)]
    values.append(config.license_key())
    return sorted({v for v in values if len(v) >= MIN_LITERAL_CHARS}, key=len, reverse=True)


def _memory_literals() -> list[str]:
    try:
        items = json.loads(config.MEMORY_LOCAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    texts = [str(item.get("content", "")) for item in items if isinstance(item, dict)]
    return sorted({t for t in texts if len(t) >= MIN_LITERAL_CHARS}, key=len, reverse=True)


def _without_personal(line: str) -> str:
    try:
        record = json.loads(line)
    except ValueError:
        return line
    if not isinstance(record, dict):
        return line
    return json.dumps({k: PERSONAL if k in PERSONAL_FIELDS else v for k, v in record.items()})


def scrub(text: str, literals: list[str], memories: list[str]) -> str:
    for secret in literals:
        text = text.replace(secret, REDACTED)
    for memory in memories:
        text = text.replace(memory, PERSONAL)
    return redact("\n".join(_without_personal(line) for line in text.splitlines()))


def _tail(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-LOG_TAIL_LINES:])


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(config.REPO_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    try:
        zoya_version = version("zoya")
    except PackageNotFoundError:
        zoya_version = "unknown"
    return {
        "zoya": zoya_version,
        "commit": _git_commit(),
        "macos": platform.mac_ver()[0],
        "machine": platform.machine(),
        "python": platform.python_version(),
        "models": {name: os.environ.get(name, "") for name in MODEL_ENV},
        "speech_to_text": config.STT_MODEL_REPO,
        "wake_word": config.WAKE_MODEL,
        "memory_server": config.MEMORY_SERVER_VERSION,
        "memory_embeddings": config.MEMORY_EMBEDDING_MODEL,
        "voice": config.POLLY_VOICE_ID,
        "license": "present" if config.license_key() else "none",
        "relay_configured": bool(config.relay_url()),
    }


def _setup_state() -> dict:
    from zoya import first_run, permissions

    return {"setup": first_run.load_state(), "permissions": permissions.status()}


def _entries() -> dict[str, str]:
    entries = {
        name: _tail(config.LOG_DIR / name)
        for name in LOG_FILES
        if (config.LOG_DIR / name).is_file()
    }
    entries["versions.json"] = json.dumps(versions(), indent=2)
    entries["setup.json"] = json.dumps(_setup_state(), indent=2)
    return entries


def make_report(destination: Path = DESKTOP) -> Path:
    literals, memories = _secret_literals(), _memory_literals()
    stamp = datetime.now().strftime("%Y-%m-%d %H%M")
    path = destination / f"Zoya problem report {stamp}.zip"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, text in _entries().items():
            bundle.writestr(name, scrub(text, literals, memories))
    return path


def send_report() -> None:
    from zoya import speech

    speech.narrate(STARTED)
    try:
        path = make_report()
    except OSError as error:
        speech.narrate(FAILED.format(reason=error.strerror or "the file couldn't be written"))
        return
    speech.narrate(SAVED.format(name=path.stem))
