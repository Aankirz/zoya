"""Record the web loop's element table on real pages, for offline tests (D126, D123).

    .venv/bin/python evals/harness/record_web.py

Only loads pages; nothing is clicked or typed. Page text is trimmed before it is saved.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya.config import load_env  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "web"
SETTLE_S = 4.0
TEXT_KEPT_CHARS = 1500
PAGES = {
    "search-results": "https://www.flipkart.com/search?q=wireless+mouse",
    "travel-search-form": "https://www.booking.com/",
    "marketplace-search": "https://www.ebay.com/sch/i.html?_nkw=mechanical+keyboard",
    "shop-product": "https://www.boat-lifestyle.com/products/airdopes-141",
    "video-channel": "https://www.youtube.com/@MrBeast",
    "encyclopedia": "https://en.wikipedia.org/wiki/Frank_Herbert",
}


def main() -> int:
    load_env()
    from zoya.agents import web_loop
    from zoya.tools import browser

    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in PAGES.items():
        try:
            browser.goto(url)
            time.sleep(SETTLE_S)
            state = web_loop.observe()
        except Exception as error:  # noqa: BLE001
            print(f"{name}: {type(error).__name__}: {error}")
            continue
        state["text"] = state["text"][:TEXT_KEPT_CHARS]
        state.pop("marker", None)
        (OUT / f"{name}.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        table = web_loop.element_table(state["actions"])
        counts = {op: len(t) for op, t in table.targets.items()}
        print(f"{name}: {len(state['actions'])} actions, {len(table.elements)} elements, {counts}")
    browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
