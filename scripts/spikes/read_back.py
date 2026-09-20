"""Can Zoya read a results page back without site-specific code? (v2 Phase D2 item 1)

    .venv/bin/python scripts/spikes/read_back.py

Opens each search URL in Zoya's own Chrome, extracts the page's repeated lists structurally
(`zoya/page_items.py`), asks Jev which list holds what the user asked for, and records the five
lines Zoya would speak. The family pick is graded automatically against the expected path shape;
the names and prices are written out verbatim so every wrong one can be listed.
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

OUT = LOG_DIR / "spikes" / "read_back.json"
SNAPSHOT_DIR = LOG_DIR / "spikes" / "snapshots"
SETTLE_S = 4.0
PACING_S = 2.0

CASES = [
    ("flipkart", "https://www.flipkart.com/search?q=wireless+mouse", "wireless mouse", "/p/"),
    ("ebay", "https://www.ebay.com/sch/i.html?_nkw=wireless+mouse", "wireless mouse", "/itm/"),
    ("bandcamp", "https://bandcamp.com/search?q=lofi", "lofi albums", "bandcamp"),
    ("goodreads", "https://www.goodreads.com/search?q=dune", "books called dune", "/book/"),
    ("imdb", "https://www.imdb.com/find/?q=dune", "dune films", "/title/"),
    ("youtube", "https://www.youtube.com/results?search_query=lofi+beats", "lofi beats", "/watch"),
    (
        "booking",
        "https://www.booking.com/searchresults.html"
        "?ss=Goa&checkin=2026-10-17&checkout=2026-10-19&group_adults=2",
        "hotels in Goa for two",
        "/hotel/",
    ),
    (
        "amazon",
        "https://www.amazon.in/s?k=wireless+mouse",
        "wireless mouse",
        "/dp/",
    ),
]


def look(url: str) -> tuple[str, str]:
    from zoya.tools import browser

    title = browser.goto(url)
    time.sleep(SETTLE_S)
    return title, browser._agent_browser("snapshot", "--compact", "--urls")


def run_case(name: str, url: str, goal: str, want: str) -> dict:
    title, snapshot = look(url)
    (SNAPSHOT_DIR / f"read_back_{name}.txt").write_text(snapshot)
    found = page_items.families(snapshot)
    started = time.monotonic()
    chosen, confidence = page_items.choose(goal, title, found)
    jev_ms = round((time.monotonic() - started) * 1000)
    lines = page_items.read_back(chosen).splitlines() if chosen else []
    items = chosen.items[: page_items.MAX_SPOKEN_ITEMS] if chosen else []
    return {
        "site": name,
        "goal": goal,
        "families": [f.key for f in found],
        "chose": chosen.key if chosen else None,
        "want_contains": want,
        "right": bool(chosen and want in chosen.key),
        "confidence": round(confidence, 3),
        "jev_ms": jev_ms,
        "spoken": lines,
        "priced": sum(1 for item in items if item.price),
        "ads": sum(1 for item in items if item.ad),
        "items": len(chosen.items) if chosen else 0,
    }


def main() -> None:
    load_env()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for name, url, goal, want in CASES:
        try:
            runs.append(run_case(name, url, goal, want))
        except Exception as error:  # noqa: BLE001 — a site that refuses is a result, not a crash
            runs.append({"site": name, "goal": goal, "error": f"{type(error).__name__}: {error}"})
        print(json.dumps(runs[-1], ensure_ascii=False)[:400], flush=True)
        time.sleep(PACING_S)
    answered = [r for r in runs if "error" not in r]
    right = [r for r in answered if r["right"]]
    summary = {
        "cases": len(runs),
        "answered": len(answered),
        "family_correct": len(right),
        "family_accuracy": round(len(right) / len(answered), 3) if answered else 0.0,
        "spoken_five": sum(1 for r in right if len(r["spoken"]) == page_items.MAX_SPOKEN_ITEMS),
        "priced_of_five": sum(r["priced"] for r in right),
        "confidence_p50": (
            round(statistics.median([r["confidence"] for r in right]), 3) if right else 0.0
        ),
        "jev_ms_p50": (
            round(statistics.median([r["jev_ms"] for r in answered])) if answered else 0
        ),
    }
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
