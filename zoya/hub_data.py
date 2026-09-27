"""What the Hub shows: Zoya's own logs and memories, scrubbed like the problem report."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from zoya import config

HISTORY_MAX = 200
READ_LINES = 5000
HIDDEN = "Hidden for privacy"
UNFINISHED = "Didn't finish"
ANSWERED = "Answered"
ROUTE_DID = {"stop": "Stopped", "fast": ANSWERED, "orchestrator": ANSWERED}
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


def _did(record: dict[str, Any]) -> str:
    from zoya.overlay import step_label

    if record.get("ok") is False:
        return UNFINISHED
    step = record.get("tool") or record.get("skill")
    return step_label(str(step)) if step else ROUTE_DID.get(str(record.get("route")), ANSWERED)


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


def history(limit: int = HISTORY_MAX) -> list[dict[str, Any]]:
    confirms = _confirmations()
    entries = []
    for record in _records(config.TIMING_LOG):
        when = _when(record)
        if when is None or not record.get("command"):
            continue
        entry = {"at": when.isoformat(), "heard": shown(record["command"]), "did": _did(record)}
        if confirm := confirms.get(str(record.get("task_id"))):
            entry["confirm"] = confirm
        entries.append(entry)
    entries.sort(key=lambda e: e["at"], reverse=True)
    return entries[:limit]


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
