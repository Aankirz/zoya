#!/usr/bin/env python3
"""Phase 0 — prove every provider/key actually works (docs/phases/phase-0-foundations.md).

Lists models on the OpenAI key, confirms the Fireworks fallback answers,
lists ElevenLabs voices, and pings Supermemory. One tiny call each. Never
prints a key.

Usage: python scripts/check_providers.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from zoya.config import FIREWORKS_BASE_URL

load_dotenv()


def _ok(label: str, detail: str) -> None:
    print(f"[ok]   {label}: {detail}")


def _fail(label: str, error: Exception) -> None:
    print(f"[FAIL] {label}: {type(error).__name__}: {error}")


def check_openai() -> bool:
    import openai

    try:
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        models = client.models.list().data
        _ok("OpenAI", f"{len(models)} models listed")
        return True
    except Exception as error:  # noqa: BLE001 — this script reports, never crashes silently
        _fail("OpenAI", error)
        return False


def check_fireworks() -> bool:
    import openai

    try:
        client = openai.OpenAI(api_key=os.environ["FIREWORKS_API_KEY"], base_url=FIREWORKS_BASE_URL)
        resp = client.chat.completions.create(
            model="accounts/fireworks/models/deepseek-v4-flash-0731",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            store=False,
        )
        _ok("Fireworks (fallback)", f"replied, finish_reason={resp.choices[0].finish_reason}")
        return True
    except Exception as error:  # noqa: BLE001
        _fail("Fireworks (fallback)", error)
        return False


def check_elevenlabs() -> bool:
    from elevenlabs.client import ElevenLabs

    try:
        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        voices = client.voices.search()
        _ok("ElevenLabs", f"{len(voices.voices)} voices listed")
        return True
    except Exception as error:  # noqa: BLE001
        _fail("ElevenLabs", error)
        return False


def check_supermemory() -> bool:
    from supermemory import Supermemory

    try:
        client = Supermemory(api_key=os.environ["SUPERMEMORY_API_KEY"])
        client.search.execute(q="ping", limit=1)
        _ok("Supermemory", "search reachable")
        return True
    except Exception as error:  # noqa: BLE001
        _fail("Supermemory", error)
        return False


def check_aws_polly() -> bool:
    import boto3
    from botocore.exceptions import ClientError

    try:
        session = boto3.Session(
            profile_name=os.environ.get("AWS_PROFILE"),
            region_name=os.environ.get("AWS_REGION", "ap-south-1"),
        )
        polly = session.client("polly")
        # ponytail: the `zoya` profile's login credential provider can throw a
        # transient ValidationException on first use in a fresh process; retry once.
        for attempt in range(2):
            try:
                voices = polly.describe_voices(LanguageCode="en-IN")["Voices"]
                break
            except ClientError:
                if attempt == 1:
                    raise
        _ok("AWS Polly", f"{len(voices)} en-IN voices listed")
        return True
    except Exception as error:  # noqa: BLE001
        _fail("AWS Polly", error)
        return False


def main() -> int:
    checks = [
        check_openai,
        check_fireworks,
        check_elevenlabs,
        check_supermemory,
        check_aws_polly,
    ]
    results = [check() for check in checks]
    print()
    if all(results):
        print("All providers reachable.")
        return 0
    print("Some providers failed — see [FAIL] lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
