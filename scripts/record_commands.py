#!/usr/bin/env python3
"""Record the 20 Phase 0 STT benchmark commands on this Mac (owner-run).

For each phrase: shows the text, waits for Enter, records 5 seconds, saves
a WAV to tests/evals/fixtures/commands/ and writes manifest.json mapping
each file to its expected text. Needs Microphone permission for Terminal.

Usage: python scripts/record_commands.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import sounddevice as sd
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "evals"))
from commands_data import TARGET_COMMANDS  # noqa: E402

OUT_DIR = Path(__file__).parent.parent / "tests" / "evals" / "fixtures" / "commands"
SAMPLE_RATE = 16000
DURATION_S = 5


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}

    for i, command in enumerate(TARGET_COMMANDS):
        phrase = command["text"]
        filename = f"{i:02d}.wav"
        print(f"\n[{i + 1}/{len(TARGET_COMMANDS)}] Say: {phrase!r}")
        input("Press Enter to start recording (5s)...")
        audio = sd.rec(int(DURATION_S * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
        sd.wait()
        sf.write(OUT_DIR / filename, audio, SAMPLE_RATE)
        manifest[filename] = phrase
        print(f"  saved {filename}")

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nDone. {len(manifest)} clips + manifest.json saved to {OUT_DIR}")
    print("Run: python tests/evals/stt_benchmark.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
