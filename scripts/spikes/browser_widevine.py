"""Spike 3.1 — Widevine and Spotify playback through agent-browser Chrome."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

TIMEOUT_S = 120
WIDEVINE_PROBE = """
(async () => {
  try {
    const access = await navigator.requestMediaKeySystemAccess('com.widevine.alpha', [{
      initDataTypes: ['cenc'],
      audioCapabilities: [{ contentType: 'audio/mp4; codecs="mp4a.40.2"' }],
    }]);
    return JSON.stringify({ widevine: true, keySystem: access.keySystem });
  } catch (error) {
    return JSON.stringify({ widevine: false, error: String(error) });
  }
})()
"""
PLAYING_PROBE = """
(() => {
  const media = [...document.querySelectorAll('audio,video')];
  return JSON.stringify({
    mediaElements: media.length,
    playing: media.some(m => !m.paused && m.currentTime > 0),
    currentTime: media.map(m => m.currentTime),
    nowPlaying: document.querySelector('[data-testid=now-playing-widget]')?.textContent ?? null,
  });
})()
"""


def run(args: list[str], profile: str | None, session: str) -> str:
    command = ["agent-browser", "--session", session, "--headed"]
    command += ["--args", "--autoplay-policy=no-user-gesture-required"]
    if profile:
        command += ["--profile", profile]
    result = subprocess.run(command + args, capture_output=True, text=True, timeout=TIMEOUT_S)
    return (result.stdout or result.stderr).strip()


def probe(profile: str | None) -> dict:
    session = f"widevine-{profile or 'bundled'}".replace(" ", "-")
    record: dict = {"profile": profile or "bundled Chrome for Testing"}
    try:
        record["open"] = run(["open", "https://open.spotify.com/"], profile, session)[:200]
        time.sleep(5)
        record["widevine_raw"] = run(["eval", WIDEVINE_PROBE], profile, session)[:400]
        record["url"] = run(["get", "url"], profile, session)[:200]
        record["signed_in"] = "login" not in record["url"].lower()
        run(["press", "Space"], profile, session)
        time.sleep(8)
        record["playback_raw"] = run(["eval", PLAYING_PROBE], profile, session)[:400]
    except subprocess.TimeoutExpired as error:
        record["error"] = f"timed out: {error}"
    finally:
        subprocess.run(
            ["agent-browser", "--session", session, "close"], capture_output=True, timeout=60
        )
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="Default")
    args = parser.parse_args()
    results = [probe(None), probe(args.profile)]
    out = Path(__file__).resolve().parents[2] / "logs/spikes/browser_widevine.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    for r in results:
        print(f"--- {r['profile']} ---")
        for key in ("url", "signed_in", "widevine_raw", "playback_raw", "error"):
            if key in r:
                print(f"  {key}: {r[key]}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
