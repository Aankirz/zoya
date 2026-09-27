"""Phase H item 4: the router's skill pick, as a typed Jev Choice against the router model.

    .venv/bin/python evals/harness/jev_vs_model.py

The pick is a pure choice (D86 allows it); the arguments stay with the model. Jev replaces the
model's pick only if its accuracy at JEV_STEP_CONFIDENCE is at least the model's (D95); below the
threshold the model keeps it (D90). Writes logs/harness/jev_vs_model.json.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run  # noqa: E402

from zoya import decisions, harness, router  # noqa: E402
from zoya.config import JEV_STEP_CONFIDENCE, load_env  # noqa: E402

NONE = "none"
NONE_CRITERION = "none of these: anything else, such as a website, a question or several steps"
QUESTION = "Which of these skills does the user's command belong to?"
STATE = "The user said to their voice assistant: {text!r}"
LABELLED: list[tuple[str, str]] = [
    ("write a note that the plumber comes monday", "notes"),
    ("add eggs to my shopping note", "notes"),
    ("do I have any notes about the electricity bill", "notes"),
    ("jot down call mom at seven", "notes"),
    ("doodh lena hai note kar lo", "notes"),
    ("pause the music", "media"),
    ("skip this song", "media"),
    ("turn it down a bit", "media"),
    ("go back to the previous track", "media"),
    ("awaaz kam karo", "media"),
    ("what's the weather in Pune", "weather"),
    ("is it going to rain in Mumbai today", "weather"),
    ("how hot is it in Delhi right now", "weather"),
    ("mausam kaisa hai Bangalore mein", "weather"),
    ("remember that my sister's name is Riya", "memory"),
    ("what do you remember about my usual groceries", "memory"),
    ("keep in mind I'm vegetarian", "memory"),
    ("no, I meant Rahul Verma, remember that", "memory"),
    ("search flipkart for a wireless mouse", NONE),
    ("book a table for two at a cafe nearby", NONE),
    ("make me a presentation about solar energy", NONE),
    ("who won the match yesterday", NONE),
    ("open the settings and turn on dark mode", NONE),
    ("find hotels in Goa for next weekend", NONE),
]


def choices() -> dict[str, str]:
    skills = {name: skill.description for name, skill in harness.catalog().items()}
    return {**skills, NONE: NONE_CRITERION}


def ask_jev(text: str) -> tuple[str, float, int]:
    from typesafe_sdk import Choice

    answers = decisions.ask(
        STATE.format(text=text), {"skill": Choice(instructions=QUESTION, criteria=choices())}
    )
    pick = answers.pick("skill") if answers else None
    if pick is None:
        return "", 0.0, answers.latency_ms
    return pick.name, pick.confidence, answers.latency_ms


def ask_model(text: str) -> tuple[str, int]:
    started = time.monotonic()
    choice = router.ask_router_model(text)
    skill = choice.skill if choice.route == "skill" and choice.skill else NONE
    return skill, round((time.monotonic() - started) * 1000)


def summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    answered = [r for r in rows if r[key]["pick"]]
    return {
        "accuracy": round(sum(r[key]["right"] for r in rows) / len(rows), 3),
        "answered": len(answered),
        "p50_ms": statistics.median(r[key]["ms"] for r in rows),
        "cents": round(sum(r[key]["cents"] for r in rows), 4),
    }


def measure(text: str, expected: str) -> dict[str, Any]:
    row: dict[str, Any] = {"text": text, "expected": expected}
    for key, ask in (("jev", ask_jev), ("model", ask_model)):
        run.meter.run = run.Run(text, key, text)
        if key == "jev":
            pick, confidence, ms = ask(text)
            pick = pick if confidence >= JEV_STEP_CONFIDENCE else ""
        else:
            pick, ms = ask(text)
            confidence = 1.0
        spent = run.meter.run.cents
        run.meter.run = None
        row[key] = {
            "pick": pick,
            "confidence": round(confidence, 3),
            "right": pick == expected,
            "ms": ms,
            "cents": spent,
        }
    return row


def main() -> int:
    load_env()
    run.meter = run.Meter()
    run.install_meters()
    decisions.warm()
    rows = [measure(text, expected) for text, expected in LABELLED]
    result = {"threshold": JEV_STEP_CONFIDENCE, "jev": summary(rows, "jev")}
    result["model"] = summary(rows, "model")
    result["switch"] = result["jev"]["accuracy"] >= result["model"]["accuracy"]
    run.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (run.OUT_DIR / "jev_vs_model.json").write_text(
        json.dumps({**result, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
