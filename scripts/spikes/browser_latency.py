"""Spike 3.2 — agent-browser snapshot and click round-trip latency from Python."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import time
from pathlib import Path

CALL_TIMEOUT_S = 60
SESSION = "zoya-spike"


REF_PATTERN = re.compile(r"^\s*-\s*(searchbox|button)\b.*?\[ref=(e\d+)\]", re.MULTILINE)


def run(args: list[str], profile: str | None) -> tuple[str, float]:
    command = ["agent-browser", "--session", SESSION]
    if profile:
        command += ["--profile", profile]
    started = time.perf_counter()
    result = subprocess.run(command + args, capture_output=True, text=True, timeout=CALL_TIMEOUT_S)
    elapsed = (time.perf_counter() - started) * 1000
    return (result.stdout or result.stderr), elapsed


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def summarise(name: str, samples: list[float]) -> dict:
    return {
        "command": name,
        "calls": len(samples),
        "p50_ms": round(statistics.median(samples), 1),
        "p95_ms": round(percentile(samples, 0.95), 1),
        "min_ms": round(min(samples), 1),
        "max_ms": round(max(samples), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://en.wikipedia.org/wiki/Accessibility")
    parser.add_argument("--calls", type=int, default=30)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    run(["open", args.url], args.profile)
    run(["snapshot", "-i"], args.profile)

    snapshot_ms, snapshot_out = [], ""
    for _ in range(args.calls):
        snapshot_out, elapsed = run(["snapshot", "-i"], args.profile)
        snapshot_ms.append(elapsed)

    refs = REF_PATTERN.findall(snapshot_out)
    click_ms, clicked = [], refs[0][1] if refs else None
    if clicked:
        run(["click", f"@{clicked}"], args.profile)
        for _ in range(args.calls):
            _out, elapsed = run(["click", f"@{clicked}"], args.profile)
            click_ms.append(elapsed)

    rows = [summarise("snapshot -i", snapshot_ms)]
    if click_ms:
        rows.append(summarise(f"click @{clicked}", click_ms))

    out = Path(__file__).resolve().parents[2] / "logs/spikes/browser_latency.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"url": args.url, "profile": args.profile, "rows": rows}, indent=2))
    print(f"url={args.url} profile={args.profile or 'bundled Chrome for Testing'}")
    print("| Command | Calls | p50 ms | p95 ms | min | max |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| `{r['command']}` | {r['calls']} | {r['p50_ms']} | "
            f"{r['p95_ms']} | {r['min_ms']} | {r['max_ms']} |"
        )
    if not click_ms:
        print("No @ref found in the snapshot — click not measured.")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
