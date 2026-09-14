#!/usr/bin/env python3
"""Phase 0 benchmark — screen understanding (docs/STACK.md §4, phase-0 brief).

10 screenshots covering checkout totals, popups, errors, chat and login
screens. Pass bar: zero misread amounts/names.

Screenshots are generated locally with known ground truth (rather than
scraping a real, logged-in Amazon account, which is out of scope until
Phase 4 — docs/phases/phase-4-browser-shopping-memory.md) so accuracy can be
graded exactly instead of by eye.

Usage: python tests/evals/screen_benchmark.py [model_id]
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "screens"
RESULTS_DIR = Path(__file__).parent / "results"
SIZE = (900, 560)


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _card(title: str, lines: list[tuple[str, int, str]], bg: str = "#ffffff") -> Image.Image:
    """lines: (text, font_size, color)."""
    img = Image.new("RGB", SIZE, bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, SIZE[0], 60], fill="#1a1a2e")
    draw.text((24, 16), title, font=_font(28), fill="white")
    y = 100
    for text, size, color in lines:
        draw.text((32, y), text, font=_font(size), fill=color)
        y += size + 22
    return img


# Each fixture: (filename, ground_truth {"amount": ..., "name": ...}, question, image builder)
FIXTURES: list[dict[str, Any]] = [
    {
        "file": "checkout_total.png",
        "question": "What is the order total shown on this checkout screen?",
        "truth": {"amount": "₹2,847"},
        "build": lambda: _card(
            "Amazon.in — Checkout",
            [
                ("Items (3): ₹2,499", 22, "black"),
                ("Delivery: ₹49", 22, "black"),
                ("Discount: -₹101", 22, "#2e7d32"),
                ("Order Total: ₹2,847", 30, "black"),
                ("Deliver to: Priya Nair, Bangalore 560034", 20, "#555"),
            ],
        ),
    },
    {
        "file": "popup_confirm_delete.png",
        "question": "What does this popup dialog say, and what are the button options?",
        "truth": {"amount": None, "name": None, "keyword": "delete"},
        "build": lambda: _card(
            "Confirm",
            [
                ("Delete this photo? This cannot be undone.", 24, "black"),
                ("[ Cancel ]        [ Delete ]", 26, "#c62828"),
            ],
        ),
    },
    {
        "file": "error_dialog.png",
        "question": "What is the exact error message shown?",
        "truth": {"amount": None, "name": None, "keyword": "network connection was lost"},
        "build": lambda: _card(
            "Error",
            [
                ("Could not send message.", 26, "#c62828"),
                ("The network connection was lost.", 24, "black"),
                ("[ Try Again ]", 24, "#1a1a2e"),
            ],
        ),
    },
    {
        "file": "whatsapp_message.png",
        "question": "Who sent the latest message, and what does it say?",
        "truth": {"amount": None, "name": "Rohan Mehta", "keyword": "pick up milk"},
        "build": lambda: _card(
            "WhatsApp",
            [
                ("Rohan Mehta", 24, "#075e54"),
                ("Can you pick up milk on your way home?", 22, "black"),
                ("10:42 AM", 18, "#888"),
            ],
        ),
    },
    {
        "file": "login_page.png",
        "question": "What fields does this login form ask for?",
        "truth": {"amount": None, "name": None, "keyword": "password"},
        "build": lambda: _card(
            "Sign in",
            [
                ("Email address", 22, "#555"),
                ("[__________________________]", 22, "black"),
                ("Password", 22, "#555"),
                ("[__________________________]", 22, "black"),
                ("[ Sign in ]", 24, "#1a1a2e"),
            ],
        ),
    },
    {
        "file": "reminder_card.png",
        "question": "What is the reminder text and what time is it set for?",
        "truth": {"amount": None, "name": None, "keyword": "6:00 pm", "keyword2": "medicine"},
        "build": lambda: _card(
            "Reminder",
            [
                ("Take evening medicine", 26, "black"),
                ("Today at 6:00 PM", 24, "#555"),
            ],
        ),
    },
    {
        "file": "bank_transfer_confirm.png",
        "question": "How much money is being transferred, and to whom?",
        "truth": {"amount": "₹15,000", "name": "Ankit Sharma"},
        "build": lambda: _card(
            "Confirm Transfer",
            [
                ("To: Ankit Sharma", 24, "black"),
                ("Account ending 4821", 20, "#555"),
                ("Amount: ₹15,000", 30, "black"),
                ("[ Cancel ]        [ Confirm ]", 24, "#c62828"),
            ],
        ),
    },
    {
        "file": "delivery_address.png",
        "question": "What name and address is the delivery going to?",
        "truth": {"amount": None, "name": "Sneha Reddy"},
        "build": lambda: _card(
            "Delivery Address",
            [
                ("Sneha Reddy", 26, "black"),
                ("221 MG Road, Indiranagar", 22, "black"),
                ("Bangalore, Karnataka 560038", 22, "black"),
                ("Phone: +91 98765 43210", 20, "#555"),
            ],
        ),
    },
    {
        "file": "discount_applied.png",
        "question": "What discount code was applied and how much was saved?",
        "truth": {"amount": "₹300", "keyword": "FESTIVE"},
        "build": lambda: _card(
            "Cart",
            [
                ("Promo code FESTIVE applied", 24, "#2e7d32"),
                ("You saved ₹300", 26, "black"),
                ("New total: ₹4,199", 24, "black"),
            ],
        ),
    },
    {
        "file": "cart_summary.png",
        "question": "How many items are in the cart and what is the subtotal?",
        "truth": {"amount": "₹6,198", "keyword": "4 items"},
        "build": lambda: _card(
            "Your Cart",
            [
                ("4 items", 24, "black"),
                ("Subtotal: ₹6,198", 28, "black"),
                ("[ Proceed to Checkout ]", 24, "#1a1a2e"),
            ],
        ),
    },
]


def ensure_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for spec in FIXTURES:
        path = FIXTURES_DIR / spec["file"]
        if not path.exists():
            spec["build"]().save(path)


def _image_to_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def grade(truth: dict[str, Any], answer: str) -> bool:
    answer_lower = answer.lower()
    for expected in truth.values():
        if not expected:
            continue
        if expected.lower() not in answer_lower:
            return False
    return True


def run_benchmark(model_id: str) -> dict[str, Any]:
    import openai

    ensure_fixtures()
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    rows = []
    correct = 0
    for spec in FIXTURES:
        image_uri = _image_to_data_uri(FIXTURES_DIR / spec["file"])
        t0 = time.monotonic()
        resp = client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": spec["question"]},
                        {"type": "image_url", "image_url": {"url": image_uri}},
                    ],
                }
            ],
            max_completion_tokens=150,
            store=False,
        )
        latency = round(time.monotonic() - t0, 3)
        answer = resp.choices[0].message.content or ""
        ok = grade(spec["truth"], answer)
        correct += ok
        rows.append(
            {
                "file": spec["file"],
                "question": spec["question"],
                "truth": spec["truth"],
                "answer": answer,
                "correct": ok,
                "latency_s": latency,
            }
        )

    return {
        "model_id": model_id,
        "total": len(FIXTURES),
        "correct": correct,
        "accuracy": round(correct / len(FIXTURES), 4),
        "rows": rows,
    }


PAGES_DIR = Path(__file__).parent / "fixtures" / "pages"

# 3 scripted click tasks (STACK §4 "Computer-use loop"). Each page exposes a
# #success element the script flips via JS once the *correct* button is
# clicked, so pass/fail is read from the DOM, not guessed from a screenshot.
COMPUTER_USE_TASKS = [
    {"page": "cookie_banner.html", "task": "Accept the cookie banner."},
    {"page": "add_to_cart.html", "task": "Add the item to your cart."},
    {"page": "close_popup.html", "task": "Close the subscribe popup."},
]


def run_computer_use_benchmark(model_id: str) -> dict[str, Any]:
    """3 short click loops: screenshot -> model names the button -> Playwright clicks it.

    Clicks by visible text (not pixel coordinates) per docs/ZOYA_TECHNICAL_DOC.md
    §9.7's "prefer DOM over pixels" guidance; coordinate-based clicking with
    per-display scaling is a Phase 5 concern (docs/AUDIT.md B10).
    """
    import openai
    from playwright.sync_api import sync_playwright

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for spec in COMPUTER_USE_TASKS:
            page = browser.new_page()
            page.goto((PAGES_DIR / spec["page"]).absolute().as_uri())
            screenshot_uri = "data:image/png;base64," + base64.b64encode(page.screenshot()).decode(
                "ascii"
            )

            t0 = time.monotonic()
            resp = client.chat.completions.create(
                model=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Task: {spec['task']} Reply with ONLY the exact visible "
                                    "text of the single button to click."
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": screenshot_uri}},
                        ],
                    }
                ],
                max_completion_tokens=20,
                store=False,
            )
            latency = round(time.monotonic() - t0, 3)
            button_text = (resp.choices[0].message.content or "").strip().strip('"').strip("'")

            clicked = False
            try:
                page.get_by_text(button_text, exact=False).first.click(timeout=2000)
                clicked = True
            except Exception:  # noqa: BLE001 — recorded as a failed task, not a crash
                pass

            success = page.locator("#success").is_visible() if clicked else False
            rows.append(
                {
                    "page": spec["page"],
                    "task": spec["task"],
                    "model_said_click": button_text,
                    "clicked": clicked,
                    "success": success,
                    "latency_s": latency,
                }
            )
            page.close()
        browser.close()

    complete = sum(r["success"] for r in rows)
    return {"model_id": model_id, "total": len(rows), "complete": complete, "rows": rows}


def main() -> int:
    model_id = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.6-terra"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Running screen understanding eval on {model_id} ({len(FIXTURES)} screenshots)...")
    result = run_benchmark(model_id)
    out_path = RESULTS_DIR / f"screen_benchmark_{model_id}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"  {model_id}: {result['correct']}/{result['total']} correct -> {out_path}")
    for row in result["rows"]:
        if not row["correct"]:
            print(f"  MISREAD [{row['file']}]: {row['answer'][:120]}")
    mark = "PASS" if result["correct"] == result["total"] else "FAIL"
    print(f"[{mark}] zero-misread pass bar")

    print(f"\nRunning computer-use loop on {model_id} ({len(COMPUTER_USE_TASKS)} tasks)...")
    cu_result = run_computer_use_benchmark(model_id)
    cu_path = RESULTS_DIR / f"computer_use_{model_id}.json"
    cu_path.write_text(json.dumps(cu_result, indent=2, ensure_ascii=False))
    print(f"  {model_id}: {cu_result['complete']}/{cu_result['total']} tasks complete -> {cu_path}")
    cu_mark = "PASS" if cu_result["complete"] >= 2 else "FAIL"
    print(f"[{cu_mark}] >= 2/3 pass bar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
