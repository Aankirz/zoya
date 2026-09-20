"""Does the spoken confirmation name what is really about to happen? (v2 Phase D2 item 2)

    .venv/bin/python scripts/spikes/say_before.py

For each flow: open the page, find the control that would be pressed, build the summary exactly
as `browser.click_ref` would -- Guard 2's risky label plus the subject Jev picks out of the names
the page prints around that control -- and print the sentence. Nothing is clicked (D96).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import page_items, safety  # noqa: E402
from zoya.config import LOG_DIR, load_env  # noqa: E402

OUT = LOG_DIR / "spikes" / "say_before.json"
SNAPSHOT_DIR = LOG_DIR / "spikes" / "snapshots"
SETTLE_S = 4.0

CASES = [
    {
        "name": "youtube-subscribe",
        "url": "https://www.youtube.com/@MrBeast",
        "control": "subscribe",
        "want": "mrbeast",
    },
    {
        "name": "booking-reserve",
        "url": "https://www.booking.com/hotel/in/lotus-candolim.html"
        "?checkin=2026-10-17&checkout=2026-10-19&group_adults=2",
        "control": "reserve",
        "want": "lotus",
    },
    {
        "name": "amazon-cart-buy",
        "url": "https://www.amazon.in/gp/cart/view.html",
        "control": "proceed to buy",
        "want": "cart",
    },
    {
        "name": "amazon-cart-delete",
        "url": "https://www.amazon.in/gp/cart/view.html",
        "control": "delete",
        "want": "power",
    },
    {
        "name": "x-post",
        "url": "https://x.com/compose/post",
        "prep": [["click", "div[role=textbox]"], ["keyboard", "type", "testing Zoya my assistant"]],
        "control": "post",
        "want": "testing zoya",
    },
]


PRESSABLE = {"button", "link", "menuitem", "tab", "checkbox", "radio"}
CONTROL_NAME_MAX = 60


def find_control(snapshot: str, wanted: str) -> tuple[str, str] | None:
    """The smallest pressable control whose own name carries the word, never its wrapper."""
    from zoya.tools import browser

    hits = [
        node
        for node in browser.parse_refs(snapshot).values()
        if (node.role in PRESSABLE or node.clickable)
        and wanted in node.name.casefold()
        and len(node.name) <= CONTROL_NAME_MAX
    ]
    if not hits:
        return None
    best = min(hits, key=lambda node: (node.role not in PRESSABLE, len(node.name)))
    return best.ref, best.identity()


def run_case(case: dict) -> dict:
    from zoya.tools import browser

    title = browser.goto(case["url"])
    time.sleep(SETTLE_S)
    for command in case.get("prep", []):
        try:
            browser._agent_browser(*command)
        except Exception as error:  # noqa: BLE001 — a prep step that fails is reported, not fatal
            return {"name": case["name"], "error": f"prep {command[0]}: {error}"}
        time.sleep(1.0)
    snapshot = browser.snapshot()
    (SNAPSHOT_DIR / f"say_before_{case['name']}.txt").write_text(snapshot)
    found = find_control(snapshot, case["control"])
    if found is None:
        return {"name": case["name"], "error": f"no control matching {case['control']!r}"}
    ref, identity = found
    target = browser._ref_probe(ref, identity)
    risky = safety.click_risk(target.facts)
    full = browser._agent_browser("snapshot", "--compact", "--urls")
    subjects = page_items.subject_candidates(full, ref, title)
    started = time.monotonic()
    name, confidence = page_items.subject(
        risky.say if risky else "press it", identity, title, subjects
    )
    jev_ms = round((time.monotonic() - started) * 1000)
    action = safety.Action(
        risky.kind if risky else "tool",
        risky.say if risky else "press it",
        target=name or target.host,
    )
    return {
        "name": case["name"],
        "control": identity,
        "risk": risky.kind if risky else None,
        "say": risky.say if risky else None,
        "candidates": [s.name for s in subjects],
        "subject": name,
        "from_page": bool(name),
        "confidence": round(confidence, 3),
        "jev_ms": jev_ms,
        "summary": action.summary(),
        "want": case["want"],
        "right": bool(name) and case["want"] in name.casefold(),
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
        print(json.dumps(runs[-1], ensure_ascii=False)[:500], flush=True)
    answered = [r for r in runs if "error" not in r]
    named = [r for r in answered if r["from_page"]]
    summary = {
        "flows": len(runs),
        "reached": len(answered),
        "named_from_page": len(named),
        "correct": sum(1 for r in named if r["right"]),
        "wrong": [r["summary"] for r in named if not r["right"]],
        "fell_back_to_host": [r["summary"] for r in answered if not r["from_page"]],
        "jev_ms_p50": round(statistics.median([r["jev_ms"] for r in answered])) if answered else 0,
    }
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
