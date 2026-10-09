"""S4-Web item 5 (D164): two-stage tool choice, measured before it is adopted.

    .venv/bin/python evals/web/tool_choice.py RUN_LABEL [RUN_LABEL ...]

1. From saved runs: right-tool-first (the brain's first tool reaches the named site) and
   needless tool calls (every call beyond the fewest that finish a site task).
2. Live: Jev picks the first tool from the brain's whole tool list for every fresh command, with
   its latency, as the stage that would sit in front of the brain.
Writes logs/web/tool_choice.json.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.web.run import OUT_DIR, load_tasks  # noqa: E402
from zoya import decisions, harness  # noqa: E402
from zoya.config import load_env  # noqa: E402

SITE_TOOLS = {"browser_task", "browser_open", "open_url", "web_fetch"}
FEWEST_CALLS = 2
QUESTION = "Which tool should the assistant call first to carry out the user's command?"
STATE = "The user said to their voice assistant: {text!r}"
DESCRIPTION_CHARS = 160


def first_tool(run: dict[str, Any]) -> str:
    named = [t.split(" ", 1)[0] for t in run["tools"] if not t.startswith(("narrate", "skills"))]
    return named[0] if named else ""


def from_runs(labels: list[str]) -> dict[str, Any]:
    runs = [r for label in labels for r in json.loads((OUT_DIR / f"{label}.json").read_text())]
    calls = [len([t for t in r["tools"] if not t.startswith("narrate")]) for r in runs]
    return {
        "tasks": len(runs),
        "right_tool_first": sum(first_tool(r) in SITE_TOOLS for r in runs),
        "needless_calls_total": sum(max(0, n - FEWEST_CALLS) for n in calls),
        "needless_calls_median": statistics.median(max(0, n - FEWEST_CALLS) for n in calls),
    }


def tool_criteria() -> dict[str, str]:
    tools = harness.all_tools()
    return {
        name: " ".join((tool.tool_spec.get("description") or name).split())[:DESCRIPTION_CHARS]
        for name, tool in sorted(tools.items())
    }


def jev_first_tool(commands: list[str]) -> dict[str, Any]:
    from typesafe_sdk import Choice

    criteria = tool_criteria()
    picks = []
    for text in commands:
        answers = decisions.ask(
            STATE.format(text=text), {"tool": Choice(instructions=QUESTION, criteria=criteria)}
        )
        pick = answers.pick("tool") if answers else None
        picks.append(
            {
                "command": text,
                "tool": pick.name if pick else "",
                "confidence": round(pick.confidence, 2) if pick else 0.0,
                "latency_ms": answers.latency_ms,
            }
        )
    latencies = [p["latency_ms"] for p in picks]
    return {
        "tools_offered": len(criteria),
        "right_first": sum(p["tool"] in SITE_TOOLS for p in picks),
        "asked": len(picks),
        "latency_p50_ms": statistics.median(latencies),
        "picks": picks,
    }


def main() -> None:
    load_env()
    from zoya import aws

    aws.load_provider_secrets()
    decisions.warm()
    commands = [t["command"] for name in ("dev", "heldout") for t in load_tasks(name, "")]
    result = {"brain": from_runs(sys.argv[1:]), "jev": jev_first_tool(commands)}
    (OUT_DIR / "tool_choice.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    summary = {k: v for k, v in result["jev"].items() if k != "picks"}
    print(json.dumps({"brain": result["brain"], "jev": summary}, indent=1))


if __name__ == "__main__":
    main()
