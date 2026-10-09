"""Compare two first checks for a missing detail: zoya/clarify.py's rules against one Jev Choice.

    .venv/bin/python -m evals.flows.jev_clarify [--set heldout]

Every scenario turn with an `asks` expectation is a case. Reports p50 latency and wrong asks
(asked although the detail was given) and wrong acts (did not ask although it was missing).
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

from typesafe_sdk import Choice

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.flows import sim  # noqa: E402

STATE = "A user said to their voice assistant: {text!r}"
QUESTION = "Does the request contain everything its action needs?"
CRITERIA = {
    "complete": "nothing needed is missing, or the request is not a post, message, buy or reminder",
    "missing_words": "a post or message with no words to send",
    "missing_recipient": "a message with no person to send it to",
    "missing_item": "a buy or add-to-cart with no product named",
    "missing_reminder": "a reminder with nothing to be reminded about",
}


def cases(sets: tuple[str, ...]) -> list[tuple[str, bool]]:
    found = []
    for scenario in sim.load(sets):
        for turn in scenario["turns"]:
            expect = turn.get("expect") or {}
            if expect.get("asks") is not None:
                found.append((turn["say"], bool(expect["asks"])))
    return found


def rules(text: str) -> bool:
    from zoya.clarify import missing_detail

    return missing_detail(text) is not None


def jev(text: str) -> bool:
    from zoya import decisions

    answers = decisions.ask(
        STATE.format(text=text), {"slot": Choice(instructions=QUESTION, criteria=CRITERIA)}
    )
    pick = answers.pick("slot") if answers else None
    return pick is not None and pick.name != "complete"


def score(name: str, check, found: list[tuple[str, bool]]) -> str:
    times, wrong_asks, wrong_acts = [], 0, 0
    for text, should_ask in found:
        started = time.monotonic()
        asked = check(text)
        times.append((time.monotonic() - started) * 1000)
        wrong_asks += asked and not should_ask
        wrong_acts += should_ask and not asked
    p50 = statistics.median(times)
    return f"| {name} | {len(found)} | {p50:.0f} | {wrong_asks} | {wrong_acts} |"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="heldout")
    args = parser.parse_args()
    from zoya import config

    config.load_env()
    found = cases(tuple(args.set.split(",")))
    print("| check | cases | p50 ms | wrong asks | wrong acts |\n|---|---|---|---|---|")
    print(score("rules (zoya/clarify.py)", rules, found))
    print(score("Jev Choice", jev, found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
