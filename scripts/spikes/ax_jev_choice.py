"""Spike 4 — one Jev Choice question against a live window's accessibility control list."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import AppKit
import ApplicationServices as AS
import tiktoken
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya.tools.ax import (
    PRESSABLE_ROLES,
    TEXT_ROLES,
    listed_elements,
)

JEV_CONTEXT_TOKENS = 32_000
MESSAGING_TIMEOUT_S = 2.0
SETTLE_S = 3.0
WALK_CAP = 4000
MAX_OPTIONS = 60
TIMEOUT_S = 30


TARGETS = [
    ("Mail", {"Mail"}, "the button that sends the message"),
    ("Notes", {"Notes"}, "the control that creates a new note"),
    ("System Settings", {"System Settings"}, "the search field"),
    ("Visual Studio Code", {"Code", "Visual Studio Code"}, "the control that opens the sidebar"),
    ("Calendar", {"Calendar"}, "the control that moves to today"),
]


def activate(app: str, names: set[str]) -> object | None:
    subprocess.run(["open", "-a", app], capture_output=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for r in AppKit.NSWorkspace.sharedWorkspace().runningApplications():
            if r.activationPolicy() != AppKit.NSApplicationActivationPolicyRegular:
                continue
            if str(r.localizedName()) in names and r.isFinishedLaunching():
                r.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
                time.sleep(SETTLE_S)
                element = AS.AXUIElementCreateApplication(r.processIdentifier())
                AS.AXUIElementSetMessagingTimeout(element, MESSAGING_TIMEOUT_S)
                AS.AXUIElementSetAttributeValue(element, "AXManualAccessibility", True)
                AS.AXUIElementSetAttributeValue(element, "AXEnhancedUserInterface", True)
                time.sleep(SETTLE_S)
                return AS.AXUIElementCreateApplication(r.processIdentifier())
        time.sleep(0.5)
    return None


def controls(app_element: object) -> list[tuple[str, str]]:
    pressable, other, seen = [], [], set()
    for role, name, _element in listed_elements(app_element):
        if not name or (role, name) in seen:
            continue
        seen.add((role, name))
        (pressable if role in PRESSABLE_ROLES or role in TEXT_ROLES else other).append((role, name))
    return pressable + other


def serialise(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"c{i}: {role.removeprefix('AX')} “{name}”" for i, (role, name) in enumerate(items, 1)
    )


def tokens(text: str) -> int:

    return len(tiktoken.get_encoding("cl100k_base").encode(text))


def ask(state: str, options: dict[str, str], question: str) -> tuple[dict, float]:
    base = os.environ["AI_GATEWAY_BASE_URL"].rstrip("/")
    body = json.dumps(
        {
            "model": os.environ.get("JEV_MODEL", "typesafe-ai/jev"),
            "state": state,
            "questions": {
                "which": {
                    "type": "choice",
                    "instructions": f"Which control is {question}?",
                    "criteria": options,
                }
            },
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/evaluate",
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['AI_GATEWAY_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        payload = json.loads(response.read())
    return payload, (time.perf_counter() - started) * 1000


def probe(app: str, names: set[str], question: str) -> dict:
    element = activate(app, names)
    if element is None:
        return {"app": app, "error": "did not come to front"}
    items = controls(element)
    state = serialise(items)
    record = {
        "app": app,
        "question": question,
        "controls": len(items),
        "state_tokens": tokens(state),
        "fits_32k": tokens(state) < JEV_CONTEXT_TOKENS,
        "options_offered": min(len(items), MAX_OPTIONS),
    }
    if not items:
        record["error"] = "no named controls"
        return record
    options = {
        f"c{i}": f"{role.removeprefix('AX')} labelled {name!r}"
        for i, (role, name) in enumerate(items[:MAX_OPTIONS], 1)
    }
    try:
        payload, latency_ms = ask(state, options, question)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as error:
        detail = getattr(error, "read", lambda: b"")()[:200].decode(errors="replace")
        record["error"] = f"{error} {detail}"
        return record
    answer = payload.get("answers", payload).get("which", {})
    probabilities = answer.get("probabilities", {})
    choice = answer.get("choice")
    index = int(choice[1:]) - 1 if isinstance(choice, str) and choice[1:].isdigit() else None
    record |= {
        "choice": choice,
        "chose": items[index] if index is not None and index < len(items) else None,
        "confidence": probabilities.get(choice),
        "top_probabilities": dict(sorted(probabilities.items(), key=lambda kv: -kv[1])[:5]),
        "latency_ms": round(latency_ms, 1),
    }
    return record


def main() -> None:
    load_dotenv()
    results = [probe(app, names, question) for app, names, question in TARGETS]
    out = Path(__file__).resolve().parents[2] / "logs/spikes/ax_jev_choice.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print("| App | Controls | State tokens | Fits 32k | Asked for | Chose | Confidence | ms |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        if "error" in r and "choice" not in r:
            print(
                f"| {r['app']} | {r.get('controls', '')} | {r.get('state_tokens', '')} | "
                f"{r.get('fits_32k', '')} | {r.get('question', '')} | _{r['error'][:60]}_ | | |"
            )
            continue
        print(
            f"| {r['app']} | {r['controls']} | {r['state_tokens']} | "
            f"{'yes' if r['fits_32k'] else 'NO'} | {r['question']} | "
            f"{r['chose']} | {r['confidence']} | {r['latency_ms']} |"
        )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
