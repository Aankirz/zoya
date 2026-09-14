"""AWS glue for Phase 1: Secrets Manager, Translate, DynamoDB (STACK §8, D30, D35).

Every call is best-effort with a short timeout: an expired `aws login`, a
missing table or a network blip is logged and Zoya keeps working (keys fall
back to .env, text is routed untranslated, history is skipped).

D35: only the personal profile named by AWS_PROFILE is used. With no profile
set, AWS is disabled rather than silently picking up other credentials.

APIs (verified 2026-09-14):
- https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
- https://docs.aws.amazon.com/translate/latest/APIReference/API_TranslateText.html
- https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_PutItem.html
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from functools import cache
from typing import Any

from zoya.config import (
    AWS_CALL_TIMEOUT_S,
    PROVIDER_SECRET_ID,
    PROVIDER_SECRET_KEYS,
    TASK_HISTORY_TABLE,
    aws_region,
)

log = logging.getLogger(__name__)

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


_warned: set[str] = set()


def _warn_once(what: str, error: Exception) -> None:
    """One warning per service + reason per session: an expired login must not spam every task."""
    key = f"{what}:{_reason(error)}"
    if key not in _warned:
        _warned.add(key)
        log.warning("%s failed (%s) — continuing without it", what, _reason(error))


def _reason(error: Exception) -> str:
    """AWS error code when there is one ("ExpiredToken" → run `aws login`), else the class name."""
    code = getattr(error, "response", {}).get("Error", {}).get("Code")
    return code or type(error).__name__


@cache
def client(service: str, region: str | None = None) -> Any:
    """One reused client per service (§13.5.4). Returns None when AWS is disabled."""
    profile = os.environ.get("AWS_PROFILE")
    if not profile:
        log.warning("AWS_PROFILE not set — AWS services disabled (D35)")
        return None
    import boto3
    from botocore.config import Config

    config = Config(
        connect_timeout=AWS_CALL_TIMEOUT_S,
        read_timeout=AWS_CALL_TIMEOUT_S,
        retries={"max_attempts": 1},
    )
    session = boto3.Session(profile_name=profile)
    return session.client(service, region_name=region or aws_region(), config=config)


def load_provider_secrets() -> str:
    """Fill provider keys from Secrets Manager; keep .env values if it is unreachable.

    Returns where the keys came from, for the startup log (never the keys).
    """
    try:
        secrets = client("secretsmanager")
        if secrets is None:
            return ".env (AWS disabled)"
        raw = secrets.get_secret_value(SecretId=PROVIDER_SECRET_ID)["SecretString"]
        values = json.loads(raw)
    except Exception as error:  # noqa: BLE001 — fall back to .env, say why
        log.warning("Secrets Manager unavailable (%s) — using .env keys", _reason(error))
        return f".env (Secrets Manager: {_reason(error)})"
    loaded = [key for key in PROVIDER_SECRET_KEYS if values.get(key)]
    for key in loaded:
        os.environ[key] = values[key]
    return f"Secrets Manager {PROVIDER_SECRET_ID} ({len(loaded)} keys)"


def needs_translation(text: str) -> bool:
    """Whisper returns Hindi in Devanagari (D42); romanized Hinglish goes to the router as-is."""
    return bool(DEVANAGARI.search(text))


def translate_to_english(text: str) -> str | None:
    """Hindi (Devanagari) → English via Amazon Translate. None if unavailable."""
    try:
        translate = client("translate")
        if translate is None:
            return None
        response = translate.translate_text(
            Text=text, SourceLanguageCode="hi", TargetLanguageCode="en"
        )
        return response["TranslatedText"]
    except Exception as error:  # noqa: BLE001 — route the original text instead
        _warn_once("Amazon Translate (routing untranslated)", error)
        return None


def record_task(item: dict[str, str]) -> None:
    """Write one task-history row in the background so it never delays the fast path."""
    threading.Thread(target=_put_task, args=(item,), daemon=True).start()


def _put_task(item: dict[str, str]) -> None:
    try:
        dynamodb = client("dynamodb")
        if dynamodb is None:
            return
        dynamodb.put_item(
            TableName=TASK_HISTORY_TABLE,
            Item={key: {"S": value} for key, value in item.items()},
        )
    except Exception as error:  # noqa: BLE001 — history is nice-to-have
        _warn_once("DynamoDB task history write", error)
