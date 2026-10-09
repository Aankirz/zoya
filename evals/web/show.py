"""Print a saved S4-Web run task by task: tools, Jev web steps, hand-backs, the final page.

.venv/bin/python evals/web/show.py LABEL [ID,ID]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.web.run import OUT_DIR  # noqa: E402

TEXT_CHARS = 300


def show(run: dict) -> None:
    mark = "PASS" if run["success"] else f"FAIL ({run['cause']})"
    print(
        f"== {run['id']} {mark} {run['seconds']}s lm={run['model_calls']} in={run['input_tokens']}"
    )
    print(f"   said: {' | '.join(run['said'])[:TEXT_CHARS]}")
    for asked in run["confirmations"]:
        print(f"   ASKED: {asked}")
    for tool in run["tools"]:
        print(f"   tool: {tool}")
    for loop in run["loops"]:
        print(f"   loop done={loop['done']} steps={loop['steps']} reason={loop['reason']!r}")
        for step in loop["decisions"]:
            print(
                f"     jev {step['operation']}@{step['operation_confidence']} "
                f"target {step['target']}@{step['target_confidence']} "
                f"elements={step['elements']} chars={step['state_chars']} {step['latency_ms']}ms"
            )
        for done in loop["history"]:
            print(f"     did: {done}")
    print(f"   page: {run['url']} | {run['title']}")
    print(f"   failed: {run['failed_checks']} {run['error']}")


def main() -> None:
    runs = json.loads((OUT_DIR / f"{sys.argv[1]}.json").read_text(encoding="utf-8"))
    wanted = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    for run in runs:
        if wanted is None or run["id"] in wanted:
            show(run)


if __name__ == "__main__":
    main()
