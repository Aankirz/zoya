#!/usr/bin/env python3
"""Router eval (§17.1b), Phase 1: Zoya's real router against 40 utterances.

Replaces the Phase 0 generic tool-calling benchmark (kept in git history and
tests/evals/results/router_eval_<model>.json). Two passes over the same set:

- `system`: route() as shipped — Translate → rules → ROUTER_MODEL.
- `model`:  route(use_rules=False) — every utterance goes to ROUTER_MODEL, so the
  model's own accuracy is measured, not the rules'.

Pass bar: >= 95% correct route + tool (+ key args) for each pass. p90 latency is
recorded (§17.1b asks < 500 ms; D44 already shows the model can't, which is why
the rules carry the fast path). No tool is executed.

Usage: python tests/evals/router_eval.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from zoya.config import load_env

load_env()

from zoya.router import RouteDecision, route  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"
PASS_BAR = 0.95
P90 = 0.9

# (utterance, expected route, expected tool, arg substrings that must appear, case-insensitive)
Case = tuple[str, str, str | None, dict[str, str]]
UTTERANCES: list[Case] = [
    ("open Spotify", "fast", "open_app", {"app_name": "spotify"}),
    ("Hey Zoya, open WhatsApp please", "fast", "open_app", {"app_name": "whatsapp"}),
    ("uh, open the, the Notes app", "fast", "open_app", {"app_name": "notes"}),
    ("Can you launch Safari", "fast", "open_app", {"app_name": "safari"}),
    ("Spotify khol do", "fast", "open_app", {"app_name": "spotify"}),
    ("Mail khol do zara", "fast", "open_app", {"app_name": "mail"}),
    ("Chrome open kardo", "fast", "open_app", {"app_name": "chrome"}),
    ("स्पॉटिफाई खोलो", "fast", "open_app", {"app_name": "spotify"}),
    ("Could you bring up Calculator for me", "fast", "open_app", {"app_name": "calculator"}),
    ("open youtube.com", "fast", "open_url", {"url": "youtube.com"}),
    ("go to amazon.in", "fast", "open_url", {"url": "amazon.in"}),
    ("wikipedia.org khol do", "fast", "open_url", {"url": "wikipedia"}),
    ("write a note: buy milk", "fast", "notes_create", {"body": "milk"}),
    (
        "Take a note that the plumber comes Monday morning",
        "fast",
        "notes_create",
        {"body": "plumber"},
    ),
    ("note down call mom at 7", "fast", "notes_create", {"body": "mom"}),
    ("doodh lena hai note kar lo", "fast", "notes_create", {"body": ""}),
    ("एक नोट लिखो: दूध खरीदना है", "fast", "notes_create", {"body": "milk"}),
    (
        "Jot down that my locker code is at the front desk",
        "fast",
        "notes_create",
        {"body": "locker"},
    ),
    ("add fix the tap to my plumber note", "fast", "notes_append", {"note_name": "plumber"}),
    ("search my notes for plumber", "fast", "notes_search", {"query": "plumber"}),
    (
        "Do I have any notes about the electricity bill",
        "fast",
        "notes_search",
        {"query": "electric"},
    ),
    ("what time is it", "fast", "get_time", {}),
    ("time kya hua", "fast", "get_time", {}),
    ("What's today's date", "fast", "get_time", {}),
    ("set volume to 40", "fast", "set_volume", {"level": "40"}),
    ("turn the volume up", "fast", "volume_up", {}),
    ("awaaz kam karo", "fast", "volume_down", {}),
    ("mute", "fast", "mute", {}),
    ("Zoya stop", "stop", None, {}),
    ("Ruk jao Zoya", "stop", None, {}),
    ("Plan a trip and book a hotel", "orchestrator", None, {}),
    ("Open Amazon and search for running shoes", "orchestrator", None, {}),
    ("What's the weather in Bangalore today", "orchestrator", None, {}),
    ("Remind me to call Priya at 6pm", "orchestrator", None, {}),
    ("Message Rohan that I'm running late", "orchestrator", None, {}),
    ("What's on my screen right now", "orchestrator", None, {}),
    ("Amazon pe mera usual grocery order kar do", "orchestrator", None, {}),
    ("Make me a presentation about solar energy", "orchestrator", None, {}),
    ("Read my latest email from Karthik", "orchestrator", None, {}),
    ("Find the cheapest flight to Delhi next Friday", "orchestrator", None, {}),
]


def score(expected: Case, decision: RouteDecision) -> bool:
    _, expected_route, expected_tool, expected_args = expected
    if decision.route != expected_route or decision.tool != expected_tool:
        return False
    return all(
        substring.lower() in str(decision.args.get(key, "")).lower()
        for key, substring in expected_args.items()
        if substring
    )


def run_pass(use_rules: bool) -> dict[str, Any]:
    rows = []
    # "stop" never reaches a model: it is a local kill switch (§12.1), so the model-only
    # pass skips those cases instead of scoring the model on a route it can't return.
    cases = UTTERANCES if use_rules else [case for case in UTTERANCES if case[1] != "stop"]
    for case in cases:
        started = time.monotonic()
        decision = route(case[0], use_rules=use_rules)
        latency_ms = round((time.monotonic() - started) * 1000)
        rows.append(
            {
                "utterance": case[0],
                "expected": {"route": case[1], "tool": case[2]},
                "actual": {
                    "route": decision.route,
                    "tool": decision.tool,
                    "args": decision.args,
                    "source": decision.source,
                },
                "latency_ms": latency_ms,
                "correct": score(case, decision),
            }
        )
    latencies = sorted(row["latency_ms"] for row in rows)
    correct = sum(row["correct"] for row in rows)
    return {
        "total": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows), 4),
        "answered_by_rules": sum(row["actual"]["source"] == "rules" for row in rows),
        "median_latency_ms": statistics.median(latencies),
        "p90_latency_ms": latencies[int(P90 * (len(latencies) - 1))],
        "rows": rows,
    }


def main() -> int:
    model_id = os.environ["ROUTER_MODEL"]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"router_model": model_id}
    failed = False
    for name, use_rules in (("system", True), ("model", False)):
        print(f"[{name}] utterances (rules={'on' if use_rules else 'off'})...")
        summary = run_pass(use_rules)
        result[name] = summary
        mark = "PASS" if summary["accuracy"] >= PASS_BAR else "FAIL"
        failed |= mark == "FAIL"
        print(
            f"  [{mark}] {summary['correct']}/{summary['total']} ({summary['accuracy']:.1%}), "
            f"rules answered {summary['answered_by_rules']}, "
            f"median {summary['median_latency_ms']} ms, p90 {summary['p90_latency_ms']} ms"
        )
        for row in summary["rows"]:
            if not row["correct"]:
                print(f"    miss: {row['utterance']!r} → {row['actual']}")
    out_path = RESULTS_DIR / f"router_eval_phase1_{model_id}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"results → {out_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
