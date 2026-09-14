#!/usr/bin/env python3
"""Phase 0 benchmark — brain latency (docs/STACK.md §4, phase-0 brief).

Streams brain-style prompts and records time to first token and time to
first complete sentence. Pass bar: prefer <= 1s to first sentence.

Uses the same request shape zoya/models.py sends in production (store=False,
reasoning_effort="none" — D43) so the numbers are representative.

Usage: python tests/evals/brain_latency.py [model_id ...]
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"

SENTENCE_END = re.compile(r"[.!?](?:\s|$)")

# Representative brain prompts (docs/ZOYA_TECHNICAL_DOC.md examples).
PROMPTS = [
    "What's the weather like in Bangalore today, and should I carry an umbrella?",
    "I just added a running shoe to my cart for 2499 rupees. "
    "Should I check for a discount code first?",
    "Summarize in two sentences: the user wants a reminder to call their mother at 6pm "
    "and to also check today's cricket score.",
]


def stream_once(client, model_id: str, prompt: str) -> dict[str, Any]:
    t0 = time.monotonic()
    first_token_at: float | None = None
    first_sentence_at: float | None = None
    text = ""

    stream = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        store=False,
        reasoning_effort="none",
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        if first_token_at is None:
            first_token_at = time.monotonic()
        text += delta
        if first_sentence_at is None and SENTENCE_END.search(text):
            first_sentence_at = time.monotonic()

    return {
        "prompt": prompt,
        "time_to_first_token_s": round((first_token_at or time.monotonic()) - t0, 3),
        "time_to_first_sentence_s": round((first_sentence_at or time.monotonic()) - t0, 3),
        "response": text.strip(),
    }


def run_benchmark(model_id: str) -> dict[str, Any]:
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    rows = [stream_once(client, model_id, prompt) for prompt in PROMPTS]
    return {
        "model_id": model_id,
        "avg_time_to_first_token_s": round(
            sum(r["time_to_first_token_s"] for r in rows) / len(rows), 3
        ),
        "avg_time_to_first_sentence_s": round(
            sum(r["time_to_first_sentence_s"] for r in rows) / len(rows), 3
        ),
        "rows": rows,
    }


def main() -> int:
    candidates = sys.argv[1:] or ["gpt-5.6-luna", "gpt-5.6-terra"]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for model_id in candidates:
        print(f"Streaming {len(PROMPTS)} brain prompts on {model_id}...")
        result = run_benchmark(model_id)
        out_path = RESULTS_DIR / f"brain_latency_{model_id}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        mark = "PASS" if result["avg_time_to_first_sentence_s"] <= 1.0 else "FAIL"
        print(
            f"  {model_id}: first token {result['avg_time_to_first_token_s']}s, "
            f"first sentence {result['avg_time_to_first_sentence_s']}s "
            f"[{mark} <=1s bar] -> {out_path}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
