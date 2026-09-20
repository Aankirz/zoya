"""Spike 3.3 — capture agent-browser snapshots for amazon.in, flipkart.com, open.spotify.com."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

SITES = {
    "amazon.in": "https://www.amazon.in/s?k=wireless+mouse",
    "flipkart.com": "https://www.flipkart.com/search?q=wireless%20mouse",
    "open.spotify.com": "https://open.spotify.com/search/ravyn%20lenae/tracks",
}
TIMEOUT_S = 180
SETTLE_S = 8
SESSION = "zoya-snapshots"


def run(args: list[str], profile: str | None) -> str:
    command = ["agent-browser", "--session", SESSION, "--headed"]
    if profile:
        command += ["--profile", profile]
    result = subprocess.run(command + args, capture_output=True, text=True, timeout=TIMEOUT_S)
    return result.stdout or result.stderr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None)
    profile = parser.parse_args().profile
    out_dir = Path(__file__).resolve().parents[2] / "logs/spikes/snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, url in SITES.items():
        run(["open", url], profile)
        time.sleep(SETTLE_S)
        snapshot = run(["snapshot", "-i", "-c"], profile)
        path = out_dir / f"{name}.txt"
        path.write_text(snapshot)
        print(f"{name}: {len(snapshot)} chars, {len(snapshot.splitlines())} lines -> {path}")
    subprocess.run(["agent-browser", "--session", SESSION, "close"], capture_output=True)


if __name__ == "__main__":
    main()
