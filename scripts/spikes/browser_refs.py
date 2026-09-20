"""v2 Phase C item 2 — the ref substrate, live: latency, Widevine, and Guard 2 rejecting a ref.

Run: .venv/bin/python scripts/spikes/browser_refs.py
Writes logs/spikes/browser_refs.json and prints the Guard 2 rejections (Done-when #7).
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from typing import Any

from zoya.config import LOG_DIR
from zoya.tools import ToolError
from zoya.tools.browser import (
    _agent_browser,
    _chrome,
    _ref_probe,
    click_ref,
    goto,
    parse_refs,
    snapshot,
)

OUT = LOG_DIR / "spikes" / "browser_refs.json"
CALLS = 20
WIDEVINE_JS = (
    "navigator.requestMediaKeySystemAccess('com.widevine.alpha', [{initDataTypes:['cenc'],"
    "videoCapabilities:[{contentType:'video/mp4;codecs=\"avc1.42E01E\"'}]}])"
    ".then(k => k.keySystem).catch(e => e.name)"
)


def percentiles(call: Callable[[], Any]) -> dict[str, float]:
    call()
    samples = []
    for _ in range(CALLS):
        started = time.monotonic()
        call()
        samples.append((time.monotonic() - started) * 1000)
    ordered = sorted(samples)
    return {
        "p50": round(statistics.median(ordered), 1),
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 1),
        "min": round(ordered[0], 1),
        "max": round(ordered[-1], 1),
    }


def guard_2_rejections(stale_ref: str, live_ref: str, approved: str) -> dict[str, str]:
    """Done-when #7: a ref that is gone, and a ref whose name is not the one that was approved."""
    found: dict[str, str] = {"approved_identity": approved}
    for case, ref, claim in (
        ("stale ref", stale_ref, approved),
        ("mismatched ref", live_ref, 'button "Place order"'),
    ):
        try:
            click_ref(ref, claim)
            found[case] = "NOT REJECTED — Guard 2 let it through"
        except ToolError as refused:
            found[case] = str(refused)
        print(f"{case}: {found[case]}")
    return found


def main() -> int:
    port = _chrome()
    print(f"Chrome on CDP port {port}")
    goto("example.com")
    print(f"agent-browser sees: {_agent_browser('get', 'url').strip()}")
    widevine = _agent_browser("eval", WIDEVINE_JS).strip()
    print(f"widevine: {widevine}")
    stale = next(iter(parse_refs(snapshot())))
    goto("https://www.iana.org/help/example-domains")
    live = snapshot()
    print(live[:400])
    target = next(node for node in parse_refs(live).values() if node.name)

    report = {
        "cdp_port": port,
        "widevine": widevine,
        "snapshot_ms": percentiles(snapshot),
        "guard_2_probe_ms": percentiles(lambda: _ref_probe(target.ref, target.identity())),
        "guard_2": guard_2_rejections(stale, target.ref, target.identity()),
    }
    started = time.monotonic()
    clicked = click_ref(target.ref, target.identity())
    report["click_ref_ms"] = round((time.monotonic() - started) * 1000, 1)
    report["click_ref_said"] = clicked
    print(json.dumps(report, indent=2))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
