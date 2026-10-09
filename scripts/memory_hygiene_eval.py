"""S3-Memory measurements on fresh scenarios (tests/fixtures/memory_hygiene/).

    uv run python scripts/memory_hygiene_eval.py live dev
    uv run python scripts/memory_hygiene_eval.py inline held_out
    uv run python scripts/memory_hygiene_eval.py live held_out_2 --judge rules+jev
    uv run python scripts/memory_hygiene_eval.py inline held_out --picker jev

Nothing reads or writes ~/.zoya/memory.json: the stores are lists in memory. The Jev judges and
picker send only the fact, or the request and the candidate memory lines, to Jev.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from zoya import memory_rules
from zoya.tools import memory

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "memory_hygiene"
MS_PER_S = 1000
EVAL_INLINE_MAX = 40
HELPS_QUESTION = "Would knowing this remembered fact help Zoya do this request: {line!r}?"
JEV_HELPS_THRESHOLD = 0.5


def _load(name: str, split: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))[split]


def _timed(call: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - started) * MS_PER_S


JUDGES = {
    "rules": lambda text: memory_rules.live_reason(text) is not None,
    "jev": lambda text: memory._live_by_jev(text),
    "rules+jev": lambda text: memory.live_fact(text) is not None,
}


def live(split: str, name: str) -> dict[str, Any]:
    data = _load("live_facts", split)
    judge = JUDGES[name]
    report: dict[str, Any] = {"split": split, "judge": name}
    latencies = []
    for kind in ("stable", "changing"):
        wrong = []
        for text in data[kind]:
            is_live, ms = _timed(lambda text=text: judge(text))
            latencies.append(ms)
            if is_live != (kind == "changing"):
                wrong.append(text)
        report[f"{kind}_total"] = len(data[kind])
        report[f"{kind}_wrong"] = wrong
    report["p50_ms"] = round(statistics.median(latencies), 3)
    report["max_ms"] = round(max(latencies), 3)
    return report


def _jev_pick(request: str, lines: list[str], limit: int) -> list[str]:
    from typesafe_sdk import Noul

    from zoya import decisions

    questions = {
        f"m{i}": Noul(instructions=HELPS_QUESTION.format(line=line)) for i, line in enumerate(lines)
    }
    answers = decisions.ask(f"The user asked Zoya: {request!r}", questions)
    if not answers:
        raise SystemExit(f"Jev unavailable: {answers.reason}")
    scored = sorted(((answers.noul(f"m{i}"), i) for i in range(len(lines))), reverse=True)
    return [lines[i] for score, i in scored[:limit] if score >= JEV_HELPS_THRESHOLD]


PICKERS = {
    "local": lambda request, items, _lines: memory.relevant_block(request, items),
    "jev": lambda request, _items, lines: "\n".join(
        _jev_pick(request, lines, memory.MEMORY_SEARCH_LIMIT)
    ),
}


def inline(split: str, picker: str) -> dict[str, Any]:
    data = _load("inline_selection", split)
    items = [{"category": c, "content": t} for c, t in data["store"]]
    lines = [t for _, t in data["store"]]
    before_hits, after_hits, before_ms, after_ms, misses = 0, 0, [], [], []
    for request, expected in data["requests"]:
        wanted = [lines[i - 1] for i in expected]
        before, ms = _timed(lambda: memory.profile_block(memory._profile_lines(items)))
        before_ms.append(ms)
        before_hits += any(line in before for line in wanted)
        picks, ms = _timed(lambda r=request: PICKERS[picker](r, items, lines))
        after = before + "\n" + picks
        after_ms.append(before_ms[-1] + ms)
        hit = any(line in after for line in wanted)
        after_hits += hit
        if not hit:
            misses.append(request)
    total = len(data["requests"])
    return {
        "split": split,
        "picker": picker,
        "store": len(lines),
        "requests": total,
        "before_hit": f"{before_hits}/{total}",
        "after_hit": f"{after_hits}/{total}",
        "before_p50_ms": round(statistics.median(before_ms), 3),
        "after_p50_ms": round(statistics.median(after_ms), 3),
        "after_max_ms": round(max(after_ms), 3),
        "misses": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["live", "inline"])
    parser.add_argument("split", choices=["dev", "held_out", "held_out_2"])
    parser.add_argument("--judge", choices=sorted(JUDGES), default="rules")
    parser.add_argument("--picker", choices=sorted(PICKERS), default="local")
    args = parser.parse_args()
    load_dotenv()
    memory.MEMORY_INLINE_MAX = EVAL_INLINE_MAX
    if args.what == "live":
        result = live(args.split, args.judge)
    else:
        result = inline(args.split, args.picker)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
