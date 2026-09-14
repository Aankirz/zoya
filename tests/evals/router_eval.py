#!/usr/bin/env python3
"""Phase 0 benchmark — tool calling (docs/STACK.md §4, phase-0 brief).

40 router/tool utterances (English, Hinglish, names). Pass bar: >= 95%
correct tool + args. Tests each ROUTER_MODEL candidate and records raw
results to tests/evals/results/router_eval_<model>.json so the model choice
in docs/DECISIONS.md is evidence-based, not guessed.

Usage: python tests/evals/router_eval.py [model_id ...]
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"

# The tools Zoya's router chooses between (docs/ZOYA_TECHNICAL_DOC.md examples:
# "Open Spotify", "what's the weather", "read my latest email", reminders, search).
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a named application.",
            "parameters": {
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder for a time.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "time": {"type": "string"}},
                "required": ["text", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a chat message to a contact.",
            "parameters": {
                "type": "object",
                "properties": {"contact": {"type": "string"}, "text": {"type": "string"}},
                "required": ["contact", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Describe what is currently on screen.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Stop whatever Zoya is doing right now.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# (utterance, expected_tool, required arg substrings to look for, case-insensitive)
UTTERANCES: list[tuple[str, str, dict[str, str]]] = [
    ("Hey Zoya, open Spotify", "open_app", {"app_name": "spotify"}),
    ("Spotify khol do", "open_app", {"app_name": "spotify"}),
    ("Open WhatsApp please", "open_app", {"app_name": "whatsapp"}),
    ("Can you launch Safari", "open_app", {"app_name": "safari"}),
    ("Mail khol do zara", "open_app", {"app_name": "mail"}),
    ("Open the Notes app", "open_app", {"app_name": "notes"}),
    ("Start Keynote for me", "open_app", {"app_name": "keynote"}),
    ("Chrome open kardo", "open_app", {"app_name": "chrome"}),
    ("What's the weather today", "get_weather", {"location": ""}),
    ("Bangalore mein aaj mausam kaisa hai", "get_weather", {"location": "bangalore"}),
    ("Is it going to rain in Mumbai tomorrow", "get_weather", {"location": "mumbai"}),
    ("What's the temperature outside right now", "get_weather", {"location": ""}),
    ("Weather in Delhi batao", "get_weather", {"location": "delhi"}),
    ("Remind me to call Priya at 6pm", "set_reminder", {"text": "priya", "time": "6"}),
    ("Set a reminder to take medicine at 9 pm", "set_reminder", {"text": "medicine", "time": "9"}),
    (
        "Mujhe kal subah 8 baje yaad dilana doctor appointment ke liye",
        "set_reminder",
        {"time": "8"},
    ),
    ("Remind me to pay the electricity bill tomorrow", "set_reminder", {"text": "electricity"}),
    (
        "Set a reminder for the team meeting at 3pm",
        "set_reminder",
        {"text": "meeting", "time": "3"},
    ),
    ("Message Rohan and tell him I'm running late", "send_message", {"contact": "rohan"}),
    ("Mummy ko message bhejo ki main ghar aa raha hoon", "send_message", {"contact": "mummy"}),
    ("Send a WhatsApp to Ananya saying happy birthday", "send_message", {"contact": "ananya"}),
    ("Text Karthik that the meeting is postponed", "send_message", {"contact": "karthik"}),
    ("Send Sneha a message asking if she's free tonight", "send_message", {"contact": "sneha"}),
    ("Search the web for the best biryani near me", "search_web", {"query": "biryani"}),
    ("Google what time the Bangalore airport opens", "search_web", {"query": "airport"}),
    ("Look up the population of India", "search_web", {"query": "population"}),
    ("Paas mein sabse achha coffee shop dhundo", "search_web", {"query": "coffee"}),
    ("Find me a recipe for butter chicken", "search_web", {"query": "butter chicken"}),
    ("What's on my screen right now", "read_screen", {}),
    ("Can you describe what's showing on the display", "read_screen", {}),
    ("Screen par kya hai bata do", "read_screen", {}),
    ("Read out what's on this page", "read_screen", {}),
    ("Zoya stop", "stop", {}),
    ("Stop, cancel that", "stop", {}),
    ("Ruk jao Zoya", "stop", {}),
    ("Cancel what you're doing right now", "stop", {}),
    ("Rukiye, mat kijiye", "stop", {}),
    ("Open Amazon and search for running shoes", "open_app", {"app_name": "amazon"}),
    ("Set a reminder to water the plants every morning", "set_reminder", {"text": "plants"}),
    ("Message my sister that I'll be home by 8", "send_message", {"contact": "sister"}),
]


def _client(model_id: str):
    import openai

    return openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"]), model_id


def run_one(client, model_id: str, utterance: str) -> dict[str, Any]:
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": "You are Zoya's router. Call exactly one tool for the user's command.",
            },
            {"role": "user", "content": utterance},
        ],
        tools=TOOLS,
        tool_choice="required",
        max_completion_tokens=200,
        reasoning_effort="none",  # function tools need this on gpt-5.6.* in Chat Completions
        store=False,
    )
    latency = time.monotonic() - t0
    call = resp.choices[0].message.tool_calls[0] if resp.choices[0].message.tool_calls else None
    return {
        "tool": call.function.name if call else None,
        "args": json.loads(call.function.arguments) if call else {},
        "latency_s": round(latency, 3),
    }


def score(expected_tool: str, expected_args: dict[str, str], actual: dict[str, Any]) -> bool:
    if actual["tool"] != expected_tool:
        return False
    for key, substring in expected_args.items():
        if not substring:
            continue
        value = str(actual["args"].get(key, "")).lower()
        if substring.lower() not in value:
            return False
    return True


def run_benchmark(model_id: str) -> dict[str, Any]:
    client, model_id = _client(model_id)
    rows = []
    correct = 0
    for utterance, expected_tool, expected_args in UTTERANCES:
        try:
            actual = run_one(client, model_id, utterance)
        except Exception as error:  # noqa: BLE001 — record and keep going
            actual = {"tool": None, "args": {}, "latency_s": None, "error": str(error)}
        ok = score(expected_tool, expected_args, actual)
        correct += ok
        rows.append(
            {"utterance": utterance, "expected": expected_tool, "actual": actual, "correct": ok}
        )

    result = {
        "model_id": model_id,
        "total": len(UTTERANCES),
        "correct": correct,
        "accuracy": round(correct / len(UTTERANCES), 4),
        "avg_latency_s": round(sum(r["actual"]["latency_s"] or 0 for r in rows) / len(rows), 3),
        "rows": rows,
    }
    return result


def main() -> int:
    candidates = sys.argv[1:] or ["gpt-5.6-luna", "gpt-5.6-terra"]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for model_id in candidates:
        print(f"Running router eval on {model_id} ({len(UTTERANCES)} utterances)...")
        result = run_benchmark(model_id)
        out_path = RESULTS_DIR / f"router_eval_{model_id}.json"
        out_path.write_text(json.dumps(result, indent=2))
        print(
            f"  {model_id}: {result['correct']}/{result['total']} "
            f"({result['accuracy']:.1%}), avg latency {result['avg_latency_s']}s -> {out_path}"
        )
        summary.append((model_id, result["accuracy"], result["avg_latency_s"]))

    print("\nSummary (pass bar >= 95%):")
    for model_id, accuracy, latency in summary:
        mark = "PASS" if accuracy >= 0.95 else "FAIL"
        print(f"  [{mark}] {model_id}: {accuracy:.1%} accuracy, {latency}s avg latency")
    return 0


if __name__ == "__main__":
    sys.exit(main())
