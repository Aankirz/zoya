"""D136 voice spike: a rough intelligibility check for every candidate, by round-trip ASR.

Transcribes each clip with Whisper large-v3-turbo (forced to English, so Hinglish comes back in
Latin script) and scores word overlap with the text that was spoken. It catches skipped words,
babble and truncation; it says nothing about warmth or accent. Writes asr_check.json.

  .venv/bin/python scripts/spikes/voice_asr_check.py
"""

from __future__ import annotations

import difflib
import json
import re
import statistics
import sys

import mlx_whisper
from voice_candidates import OUT, SENTENCES

WHISPER_REPO = "mlx-community/whisper-large-v3-turbo"
NUMBER_WORDS = {"₹": " rupees ", ",": "", ":": " "}


def words(text: str) -> list[str]:
    for symbol, spoken in NUMBER_WORDS.items():
        text = text.replace(symbol, spoken)
    return re.findall(r"[a-z0-9]+", text.lower())


def score(expected: str, heard: str) -> float:
    return difflib.SequenceMatcher(None, words(expected), words(heard)).ratio()


def main() -> int:
    results: dict[str, dict] = {}
    for folder in sorted(p for p in OUT.iterdir() if p.is_dir()):
        clips = {}
        for index, text in enumerate(SENTENCES):
            clip = folder / f"{index + 1:02}.wav"
            if not clip.exists():
                continue
            heard = mlx_whisper.transcribe(str(clip), path_or_hf_repo=WHISPER_REPO, language="en")[
                "text"
            ].strip()
            clips[index + 1] = {"heard": heard, "score": round(score(text, heard), 2)}
        if clips:
            mean = statistics.mean(c["score"] for c in clips.values())
            hinglish = [clips[i]["score"] for i in (5, 6, 10, 11, 12, 13) if i in clips]
            results[folder.name] = {
                "mean": round(mean, 2),
                "hinglish_mean": round(statistics.mean(hinglish), 2) if hinglish else None,
                "clips": clips,
            }
            print(folder.name, results[folder.name]["mean"], results[folder.name]["hinglish_mean"])
    (OUT / "asr_check.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
