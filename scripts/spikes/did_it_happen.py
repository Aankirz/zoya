"""Can Zoya tell, from the page, that what she did actually happened? (v2 Phase D2 item 3)

    .venv/bin/python scripts/spikes/did_it_happen.py

Only reversible actions are run (D75, D96): add to cart, play, open, navigate. Each case
snapshots before and after, diffs the two structurally, and asks Jev which change shows the
action happened. The last cases press something inert on purpose: the answer there must be that
the page shows nothing, not a success nobody can see.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import page_items  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402

OUT = LOG_DIR / "spikes" / "did_it_happen.json"
SNAPSHOT_DIR = LOG_DIR / "spikes" / "snapshots"
SETTLE_S = 4.0
AFTER_S = 3.0

CASES = [
    {
        "name": "amazon-add-to-cart",
        "url": "https://www.amazon.in/dp/B0BTYCRJSS",
        "control": "add to cart",
        "expect": True,
    },
    {
        "name": "wikipedia-navigate",
        "url": "https://en.wikipedia.org/wiki/Dune_(novel)",
        "control": "frank herbert",
        "want": "Frank Herbert",
        "expect": True,
    },
    {
        "name": "youtube-play",
        "url": "https://www.youtube.com/results?search_query=lofi+beats",
        "control": "lofi",
        "expect": True,
    },
    {
        "name": "duckduckgo-open-result",
        "url": "https://duckduckgo.com/?q=frank+herbert+dune",
        "control": "wikipedia",
        "expect": True,
    },
    {
        "name": "wikipedia-not-pressed",
        "url": "https://en.wikipedia.org/wiki/Dune_(novel)",
        "control": "frank herbert",
        "press": False,
        "expect": False,
    },
]

PRESSABLE = {"button", "link", "menuitem", "tab"}


def find_control(snapshot: str, wanted: str) -> tuple[str, str] | None:
    from zoya.tools import browser

    hits = [
        node
        for node in browser.parse_refs(snapshot).values()
        if (node.role in PRESSABLE or node.clickable) and wanted in node.name.casefold()
    ]
    if not hits:
        return None
    best = min(hits, key=lambda node: (node.role not in PRESSABLE, len(node.name)))
    return best.ref, best.name


def run_case(case: dict) -> dict:
    from zoya.tools import browser

    browser.goto(case["url"])
    time.sleep(SETTLE_S)
    before = browser._agent_browser("snapshot", "--compact", "--urls")
    url_before, _title = browser.ref_page_state()
    found = find_control(browser.snapshot(), case["control"])
    if found is None:
        return {"name": case["name"], "error": f"no control matching {case['control']!r}"}
    ref, was = found
    if case.get("press", True):
        browser._agent_browser("click", f"@{ref}")
    time.sleep(AFTER_S)
    after = browser._agent_browser("snapshot", "--compact", "--urls")
    (SNAPSHOT_DIR / f"did_{case['name']}_before.txt").write_text(before)
    (SNAPSHOT_DIR / f"did_{case['name']}_after.txt").write_text(after)
    now = browser.parse_refs(after).get(ref)
    url_after, title_after = browser.ref_page_state()
    went_to = (title_after or url_after) if url_after != url_before else ""
    changes = page_items.changes(before, after, ref, was, now.name if now else "", went_to)
    started = time.monotonic()
    shown, confidence = page_items.happened(f'pressed the control "{was}"', was, changes)
    return {
        "name": case["name"],
        "pressed": was,
        "clicked": case.get("press", True),
        "changes": [c.said for c in changes],
        "shown": shown,
        "claims_success": bool(shown),
        "expect": case["expect"],
        "right": bool(shown) == case["expect"],
        "confidence": round(confidence, 3),
        "jev_ms": round((time.monotonic() - started) * 1000),
    }


def main() -> None:
    load_env()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for case in CASES:
        try:
            runs.append(run_case(case))
        except Exception as error:  # noqa: BLE001
            runs.append({"name": case["name"], "error": f"{type(error).__name__}: {error}"})
        print(json.dumps(runs[-1], ensure_ascii=False)[:600], flush=True)
    answered = [r for r in runs if "error" not in r]
    summary = {
        "cases": len(runs),
        "reached": len(answered),
        "correct": sum(1 for r in answered if r["right"]),
        "false_success": [r["name"] for r in answered if r["claims_success"] and not r["expect"]],
        "missed": [r["name"] for r in answered if not r["claims_success"] and r["expect"]],
        "jev_ms_p50": round(statistics.median([r["jev_ms"] for r in answered])) if answered else 0,
    }
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
