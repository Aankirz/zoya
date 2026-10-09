"""Run the flow scenarios and print the table.

    .venv/bin/python -m evals.flows.run LABEL [--live-model] [--set dev,heldout,repro]
                                              [--only d01,h03] [--fresh N] [--scale 0.2]

Offline (default) uses the scripted brain and no network. --live-model uses the real router,
Jev and brain with every side-effect tool still faked. --fresh N asks the router model for N new
scenarios from the categories below and runs those instead, so QA never replays one sentence list.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.flows import sim  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[2] / "logs" / "flows"
CATEGORIES = {
    "chat": "small talk or a quick question for the assistant",
    "capability": "what the assistant can do",
    "open_app": "open a Mac app",
    "media": "pause, resume or skip what is playing",
    "setting": "change a Mac setting",
    "notes": "write a note with its text",
    "reminder": "a reminder with what and when",
    "timer": "a timer with a duration",
    "screen": "what is on the screen",
    "web_search": "look something up on the web",
    "play": "play a named song, artist or genre",
    "buy": "buy a named product",
    "buy_missing": "buy, with no product named",
    "post": "post given words on a social site",
    "post_missing": "post on a social site, with no words given",
    "message": "message a named person with the words to send",
    "message_missing": "message someone, missing the person or the words",
    "hinglish": "any request in Hinglish (Hindi in Latin letters)",
    "junk": "a fragment of speech that is not a request",
    "long": "a multi-step research task",
}
EXPECT = {
    "buy_missing": {"asks": True},
    "post_missing": {"asks": True},
    "message_missing": {"asks": True},
    "buy": {"asks": False, "acts": True},
    "post": {"asks": False, "acts": True},
    "message": {"asks": False, "acts": True},
    "junk": {"acts": False, "short": True},
    "chat": {"acts": None},
    "capability": {"acts": False},
}
FRESH_PROMPT = (
    "Write {n} different things a new user might say to a Mac voice assistant in their first "
    "week. Vary apps, sites, topics, phrasing, length and language (some Hinglish). Never name "
    "the same app or site twice. Spread them over these categories: {categories}. Do not reuse "
    "or lightly reword any of these earlier sentences: {used}."
)


USED_SENTENCES_MAX = 120


def used_sentences() -> str:
    """Every sentence an earlier fresh run already used, so the next run writes new ones."""
    used = []
    for report in sorted(OUT_DIR.glob("*.json")):
        turns = json.loads(report.read_text("utf-8")).get("turns", [])
        used += [turn["say"] for turn in turns if turn.get("set") == "fresh"]
    return json.dumps(used[-USED_SENTENCES_MAX:])


class FreshScenario(BaseModel):
    category: str = Field(description="One of the category keys")
    say: str = Field(description="Exactly what the user says")


class FreshBatch(BaseModel):
    scenarios: list[FreshScenario]


def fresh(n: int) -> list[dict[str, Any]]:
    from strands import Agent

    from zoya import config
    from zoya.models import get_model

    config.load_env()
    agent = Agent(model=get_model("router"), callback_handler=None)
    picked = random.sample(list(CATEGORIES), k=min(n, len(CATEGORIES)))
    prompt = FRESH_PROMPT.format(
        n=n, categories=json.dumps({k: CATEGORIES[k] for k in picked}), used=used_sentences()
    )
    batch = agent(prompt, structured_output_model=FreshBatch).structured_output
    return [_scenario(i, item) for i, item in enumerate(batch.scenarios[:n])]


def _scenario(index: int, item: FreshScenario) -> dict[str, Any]:
    category = item.category if item.category in CATEGORIES else "chat"
    expect = EXPECT.get(category, {"acts": None})
    script = category.removesuffix("_missing")
    return {
        "id": f"f{index:02d}",
        "set": "fresh",
        "category": script,
        "turns": [{"say": item.say, "expect": expect}],
    }


def _args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.flows.run")
    parser.add_argument("label")
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--set", default="dev,heldout,repro")
    parser.add_argument("--only", default="")
    parser.add_argument("--fresh", type=int, default=0)
    parser.add_argument("--scale", type=float, default=1.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    scenarios = fresh(args.fresh) if args.fresh else sim.load(tuple(args.set.split(",")))
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only.split(",")]
    simulator = sim.Simulator(live=args.live_model, scale=args.scale)
    turns: list[sim.Turn] = []
    with simulator.installed():
        for scenario in scenarios:
            turns += simulator.run(scenario)
            print(sim.table(turns[-len(scenario["turns"]) :]).splitlines()[-1], flush=True)
    report = sim.save(turns, args.label, OUT_DIR)
    print(json.dumps(sim.summary(turns)))
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
