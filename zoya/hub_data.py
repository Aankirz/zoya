"""What the Hub shows: Zoya's own logs and memories, scrubbed like the problem report."""

from __future__ import annotations

import json
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zoya import config

HISTORY_MAX = 200
READ_LINES = 5000
HIDDEN = "Hidden for privacy"
WHY_UNKNOWN = "Something got in the way before I could finish. Try asking me again."
STOPPED = "Stopped"
APP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .&+-]{0,39}")
OPEN_WORDS = {"open", "launch", "start"}
STEP_APPS = {
    "amazon": "Safari",
    "browser": "Safari",
    "web": "Safari",
    "youtube": "Safari",
    "spotify": "Spotify",
    "set reminder": "Reminders",
    "share file": "Finder",
}
NOT_CONFIRMED = {
    "cancel": "Cancelled · you said stop",
    "stop": "Cancelled · you said stop",
    "timeout": "Cancelled · I didn't hear confirm",
    "changed": "Cancelled · the page changed",
}
OUTCOMES = {
    "amazon add to cart": "Added to cart",
    "amazon cart": "Checked the cart",
    "amazon place order": "Ordered",
    "amazon search": "Searched Amazon",
    "create document": "Wrote a document",
    "memory add": "Remembered",
    "memory search": "Remembered for you",
    "open app": "Opened the app",
    "set reminder": "Set a reminder",
    "share file": "Shared a file",
    "spotify play song": "Played music",
    "web search": "Searched the web",
    "youtube play video": "Played a video",
}
CONFIRM_FIELDS = ("action", "amount", "recipient_or_item", "decision")
PERMISSIONS = ("microphone", "accessibility", "screen", "automation")
SETTINGS_FILE = Path.home() / ".zoya" / "settings.json"
DEFAULT_SETTINGS: dict[str, Any] = {
    "largerText": False,
    "easierLetters": False,
    "pillPosition": "bottom",
    "launchAtLogin": False,
}
PLAN_TIMEOUT_S = 10.0
PLAN_MAX_BYTES = 4096


def _lines(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return list(deque(handle, maxlen=READ_LINES))
    except OSError:
        return []


def _records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in _lines(path):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def shown(text: object) -> str:
    from zoya import diagnostics, safety
    from zoya.tools.memory import secret_reason

    clean = " ".join(str(text or "").split())
    for secret in diagnostics._secret_literals():
        clean = clean.replace(secret, "")
    if secret_reason(clean):
        return HIDDEN
    return safety.redact(clean)


def _step(record: dict[str, Any]) -> str:
    step = str(record.get("tool") or record.get("skill") or "")
    return step.removeprefix("using ").replace("_", " ").strip()


def app_name(record: dict[str, Any]) -> str | None:
    step = _step(record)
    if step != "open app":
        return next((app for prefix, app in STEP_APPS.items() if step.startswith(prefix)), None)
    words = shown(record.get("command")).split()
    opened = next((i for i, word in enumerate(words) if word.lower() in OPEN_WORDS), None)
    name = " ".join(words[opened + 1 :]).strip(".?!") if opened is not None else ""
    return name.title() if APP_NAME.fullmatch(name) else None


def _outcome(record: dict[str, Any], app: str | None) -> str | None:
    if record.get("route") == "stop":
        return STOPPED
    step = _step(record)
    if step == "open app" and app:
        return f"Opened {app}"
    return OUTCOMES.get(step)


def _confirmed(outcome: str | None, confirm: dict[str, str]) -> str:
    decision = confirm.get("decision")
    if decision != "confirmed":
        return NOT_CONFIRMED.get(str(decision), "Cancelled")
    parts = [outcome or "Done", confirm.get("amount", ""), "you said confirm"]
    return " · ".join(part for part in parts if part)


def _confirmations() -> dict[str, dict[str, str]]:
    return {
        str(r["task_id"]): {field: shown(r.get(field, "")) for field in CONFIRM_FIELDS}
        for r in _records(config.CONFIRMATION_LOG)
        if r.get("task_id")
    }


def _when(record: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(record.get("at"))).astimezone()
    except ValueError:
        return None


def record_said(task_id: str, text: str) -> None:
    line = {"at": datetime.now(UTC).isoformat(timespec="milliseconds"), "task_id": task_id}
    try:
        config.SAID_LOG.parent.mkdir(parents=True, exist_ok=True)
        with config.SAID_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line | {"said": shown(text)}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _said() -> dict[str, str]:
    return {str(r["task_id"]): str(r.get("said", "")) for r in _records(config.SAID_LOG)}


def _entry(record: dict[str, Any], said: str, confirm: dict[str, str] | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"heard": shown(record["command"]), "said": said, "times": 1}
    app = app_name(record)
    entry = entry | {"app": app} if app else entry
    outcome = _outcome(record, app)
    if record.get("ok") is False and outcome != STOPPED:
        return entry | {"failed": True, "why": said or WHY_UNKNOWN, "said": ""}
    if confirm:
        return entry | {"confirm": confirm, "outcome": _confirmed(outcome, confirm)}
    return entry | {"outcome": outcome} if outcome else entry


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ("heard", "outcome", "failed", "confirm")
    return a["at"][:10] == b["at"][:10] and all(a.get(k) == b.get(k) for k in keys)


def _collapsed(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for entry in entries:
        if kept and _same(kept[-1], entry):
            kept[-1] = kept[-1] | {"times": kept[-1]["times"] + 1}
        else:
            kept.append(entry)
    return kept


def history(limit: int = HISTORY_MAX) -> list[dict[str, Any]]:
    confirms, said = _confirmations(), _said()
    entries = []
    for order, record in enumerate(_records(config.TIMING_LOG)):
        when = _when(record)
        if when is None or not record.get("command"):
            continue
        task = str(record.get("task_id"))
        entry = _entry(record, said.get(task, ""), confirms.get(task))
        entries.append((when, order, {"at": when.isoformat()} | entry))
    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    return _collapsed([e[2] for e in entries])[:limit]


def today() -> list[dict[str, Any]]:
    day = datetime.now().astimezone().date()
    return [e for e in history() if datetime.fromisoformat(e["at"]).date() == day]


def parse_plan(body: object) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    used, cap, month = body.get("usedCents"), body.get("capCents"), body.get("month")
    numbers = all(
        isinstance(v, int | float) and not isinstance(v, bool) and v >= 0 for v in (used, cap)
    )
    if not numbers or not isinstance(month, str):
        return None
    return {"month": month, "usedCents": used, "capCents": cap}


def memories() -> list[dict[str, str]]:
    items = [r for r in _records_json(config.MEMORY_LOCAL_FILE) if r.get("id") and r.get("content")]
    return [
        {"id": str(i["id"]), "at": str(i.get("at", "")), "content": shown(i["content"])}
        for i in reversed(items)
    ]


def _records_json(path: Path) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in loaded if isinstance(item, dict)] if isinstance(loaded, list) else []


def setup() -> dict[str, Any]:
    from zoya import first_run

    try:
        grants = json.loads(first_run.GRANTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        grants = {}
    return {
        "permissions": {name: grants.get(name) is True for name in PERMISSIONS},
        "license": bool(config.license_key()),
        "version": config.app_version(),
    }


def settings() -> dict[str, Any]:
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    saved = saved if isinstance(saved, dict) else {}
    return {key: saved.get(key, default) for key, default in DEFAULT_SETTINGS.items()}


def save_setting(key: str, value: object) -> dict[str, Any]:
    updated = settings() | {key: value}
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    return updated


def plan() -> dict[str, Any] | None:
    import urllib.error
    import urllib.request

    from zoya import first_run

    key, url = config.license_key(), first_run._license_url()
    if not key or not url:
        return None
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=PLAN_TIMEOUT_S) as response:
            return parse_plan(json.loads(response.read(PLAN_MAX_BYTES)))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def clear_history() -> int:
    cleared = len(history(limit=READ_LINES))
    for path in (config.TIMING_LOG, config.CONFIRMATION_LOG, config.SAID_LOG):
        if path.exists():
            path.write_text("", encoding="utf-8")
    return cleared
