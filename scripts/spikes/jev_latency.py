"""Spike 2 — Jev p50/p95 by question count and state size. Run with --calls N."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

STATE_SIZES = {"small_500t": 500, "large_3000t": 3000}
QUESTION_COUNTS = (1, 3, 10)
TIMEOUT_S = 30
PACE_S = 1.0
RETRIES = 8
BACKOFF_S = 4.0
CHARS_PER_TOKEN = 4


CONTROL_LINE = (
    "Button: Send | Button: Cancel | TextField: To | TextField: Subject | "
    "StaticText: Draft saved | Button: Attach file | Checkbox: Notify me | "
)
QUESTION_BANK = [
    ("has_send", "There is a control that sends the message."),
    ("has_cancel", "There is a control that cancels."),
    ("has_subject", "There is a field for the subject line."),
    ("is_compose", "This window is a message composer."),
    ("has_attach", "There is a control that attaches a file."),
    ("is_modal", "This window is a modal dialog."),
    ("has_delete", "There is a control that deletes something."),
    ("has_payment", "This window asks for payment."),
    ("is_saved", "The draft has been saved."),
    ("has_notify", "There is a notification checkbox."),
]


def state_of(tokens: int) -> str:
    target = tokens * CHARS_PER_TOKEN
    return (CONTROL_LINE * (target // len(CONTROL_LINE) + 1))[:target]


def gateway_call(state: str, count: int) -> float:
    base = os.environ["AI_GATEWAY_BASE_URL"].rstrip("/")
    body = json.dumps(
        {
            "model": os.environ.get("JEV_MODEL", "typesafe-ai/jev"),
            "state": state,
            "questions": {
                k: {"type": "boolean", "instructions": i} for k, i in QUESTION_BANK[:count]
            },
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/evaluate",
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['AI_GATEWAY_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        response.read()
    return (time.perf_counter() - started) * 1000


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calls", type=int, default=30)
    calls = parser.parse_args().calls
    load_dotenv()

    rows, failures = [], []
    for size_name, tokens in STATE_SIZES.items():
        state = state_of(tokens)
        for count in QUESTION_COUNTS:
            samples = []
            for attempt in range(calls + 1):
                elapsed = None
                for retry in range(RETRIES):
                    try:
                        elapsed = gateway_call(state, count)
                        break
                    except urllib.error.HTTPError as error:
                        detail = error.read()[:160].decode(errors="replace")
                        if error.code != 429:
                            failures.append(f"{size_name}/{count}q: {error} {detail}")
                            break
                        time.sleep(BACKOFF_S * (retry + 1))
                    except (urllib.error.URLError, OSError) as error:
                        failures.append(f"{size_name}/{count}q: {error}")
                        break
                if elapsed is None:
                    failures.append(f"{size_name}/{count}q: gave up after {RETRIES} retries")
                    break
                if attempt:
                    samples.append(elapsed)
                time.sleep(PACE_S)
            if not samples:
                continue
            rows.append(
                {
                    "state": size_name,
                    "state_tokens_approx": tokens,
                    "questions": count,
                    "calls": len(samples),
                    "p50_ms": round(statistics.median(samples), 1),
                    "p95_ms": round(percentile(samples, 0.95), 1),
                    "min_ms": round(min(samples), 1),
                    "max_ms": round(max(samples), 1),
                }
            )

    out = Path(__file__).resolve().parents[2] / "logs/spikes/jev_latency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "failures": failures}, indent=2))
    print("| State | Questions | Calls | p50 ms | p95 ms | min | max |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r['state']} | {r['questions']} | {r['calls']} | "
            f"{r['p50_ms']} | {r['p95_ms']} | {r['min_ms']} | {r['max_ms']} |"
        )
    for f in failures:
        print(f"FAILED {f}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
