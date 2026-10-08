"""L4: how large-v3-turbo transcribes Hindi and Hinglish, and whether a documented option helps.

There is no recording of the owner speaking Hindi (logs hold text only), so this uses the
synthetic Indian voices already on disk: logs/voice_candidates/<voice>/NN.wav (sentences from
scripts/spikes/voice_candidates.py) and tests/evals/fixtures/commands (Polly, manifest.json).
Clips are read from ZOYA_CLIP_ROOT (default ~/Desktop/zoya/logs: a worktree reads the main
checkout's local clips).

Variants use only mlx_whisper.transcribe's documented keywords (`language`, `initial_prompt`):
https://github.com/ml-explore/mlx-examples/tree/main/whisper (mlx_whisper/transcribe.py).
Score: share of reference words heard, script-blind (Devanagari is romanised roughly first, for
scoring only), plus how often the router would need Amazon Translate (any Devanagari).

Usage: .venv/bin/python -u -m tests.evals.hinglish_stt
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import difflib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from tests.evals.spotter_compare import CLIP_ROOT  # noqa: E402
from zoya.config import STT_MODEL_REPO  # noqa: E402

RATE = 16000
MS_PER_S = 1000
FUZZY_MATCH = 0.75
SUBPROCESS_TIMEOUT_S = 30
CANDIDATES = CLIP_ROOT / "voice_candidates"
FIXTURES = Path(__file__).parent / "fixtures" / "commands"
RESULTS = Path(__file__).parent / "results" / "hinglish_stt.json"
SENTENCES = {
    5: "Theek hai, aapki behen ka birthday 12 March ko hai.",
    6: "Maine Rahul Verma ko WhatsApp pe message bhej diya.",
    10: "Aaj Noida mein 34 degree hai, shaam ko baarish ho sakti hai.",
    11: "Kesariya chala rahi hoon, Arijit Singh ka.",
    12: "1,249 ka order place karoon? Say confirm, or stop.",
    13: "Aapki meeting 4:30 baje hai, Riya ke saath.",
    1: "Notes is open.",
    7: "Your cart total is 1,249.50 rupees, with a delivery fee of 35 rupees.",
    9: "It's 31 degrees in Bengaluru, with a chance of rain after 4 PM.",
}
HINGLISH = {5, 6, 10, 11, 12, 13}
FIXTURE_HINGLISH = {"05", "06", "09", "14", "18"}
HINGLISH_PROMPT = "Haan, Spotify khol do aur mera playlist bajao. Mummy ko message bhejo."
VARIANTS = {
    "auto (current)": {},
    "language=hi": {"language": "hi"},
    "language=en": {"language": "en"},
    "auto + Hinglish prompt": {"initial_prompt": HINGLISH_PROMPT},
}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Rough romanisation for scoring only: consonants carry an inherent "a" that a matra replaces.
CONSONANTS = dict(
    zip(
        "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह",
        [
            "k",
            "kh",
            "g",
            "gh",
            "n",
            "ch",
            "chh",
            "j",
            "jh",
            "n",
            "t",
            "th",
            "d",
            "dh",
            "n",
            "t",
            "th",
            "d",
            "dh",
            "n",
            "p",
            "ph",
            "b",
            "bh",
            "m",
            "y",
            "r",
            "l",
            "v",
            "sh",
            "sh",
            "s",
            "h",
        ],
        strict=True,
    )
)
MATRAS = dict(
    zip(
        "ािीुूृेैोौॉॅ",
        ["a", "i", "ee", "u", "oo", "ri", "e", "ai", "o", "au", "o", "e"],
        strict=True,
    )
)
VOWELS = dict(
    zip("अआइईउऊएऐओऔ", ["a", "aa", "i", "ee", "u", "oo", "e", "ai", "o", "au"], strict=True)
)
NUKTA, VIRAMA, ANUSVARA, CHANDRABINDU = "़", "्", "ं", "ँ"
NUKTA_FORMS = {"ज": "z", "फ": "f", "ड": "r", "ढ": "rh", "क": "q", "ख": "kh", "ग": "g"}


def romanise(text: str) -> str:
    out: list[str] = []
    chars = list(text)
    for index, char in enumerate(chars):
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if char in CONSONANTS:
            sound = NUKTA_FORMS.get(char, CONSONANTS[char]) if following == NUKTA else None
            out.append(sound or CONSONANTS[char])
            after = chars[index + 2] if following == NUKTA and index + 2 < len(chars) else following
            if (
                after not in MATRAS
                and after != VIRAMA
                and after.strip()
                and DEVANAGARI.match(after)
            ):
                out.append("a")
        elif char in MATRAS:
            out.append(MATRAS[char])
        elif char in VOWELS:
            out.append(VOWELS[char])
        elif char in (ANUSVARA, CHANDRABINDU):
            out.append("n")
        elif char in (NUKTA, VIRAMA):
            continue
        else:
            out.append(char)
    return "".join(out)


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", romanise(text).lower().replace(",", ""))


def heard_share(reference: str, heard: str) -> float:
    wanted, got = tokens(reference), tokens(heard)
    hits = 0
    for word in wanted:
        match = difflib.get_close_matches(word, got, n=1, cutoff=FUZZY_MATCH)
        if match:
            hits += 1
            got.remove(match[0])
    return hits / max(1, len(wanted))


def load_mp3(path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as folder:
        wav = Path(folder) / "clip.wav"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", str(RATE), "-ac", "1", wav],
            check=True,
            timeout=SUBPROCESS_TIMEOUT_S,
        )
        return sf.read(wav, dtype="float32")[0]


def corpus() -> list[tuple[str, bool, str, np.ndarray]]:
    items = []
    for voice in sorted(p for p in CANDIDATES.iterdir() if p.is_dir()):
        for number, text in SENTENCES.items():
            path = voice / f"{number:02d}.wav"
            if path.exists():
                samples, rate = sf.read(path, dtype="float32")
                if rate == RATE and samples.ndim == 1:
                    items.append((f"{voice.name}/{number}", number in HINGLISH, text, samples))
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for name, text in manifest.items():
        stem = name.split(".")[0]
        items.append(
            (f"fixture/{stem}", stem in FIXTURE_HINGLISH, text, load_mp3(FIXTURES / f"{stem}.mp3"))
        )
    return items


def transcriber():
    import mlx.core as mx
    import mlx_whisper
    from mlx_whisper.load_models import load_model

    from zoya.setup_models import local_model_dir

    path = local_model_dir(STT_MODEL_REPO)
    load_model(path, dtype=mx.float16)

    def run(samples: np.ndarray, options: dict) -> tuple[str, str, float]:
        started = time.perf_counter()
        result = mlx_whisper.transcribe(
            samples,
            path_or_hf_repo=path,
            temperature=0.0,
            condition_on_previous_text=False,
            **options,
        )
        elapsed = (time.perf_counter() - started) * MS_PER_S
        return str(result.get("text", "")).strip(), str(result.get("language")), elapsed

    return run


def main() -> int:
    run = transcriber()
    items = corpus()
    summary, detail = {}, {}
    for variant, options in VARIANTS.items():
        rows = []
        for key, hinglish, reference, samples in items:
            text, language, ms = run(samples, options)
            rows.append(
                {
                    "clip": key,
                    "hinglish": hinglish,
                    "heard": text,
                    "language": language,
                    "share": round(heard_share(reference, text), 2),
                    "devanagari": bool(DEVANAGARI.search(text)),
                    "ms": round(ms),
                }
            )
        detail[variant] = rows
        for group, wanted in (("hinglish", True), ("english", False)):
            picked = [r for r in rows if r["hinglish"] is wanted]
            summary[f"{variant} / {group}"] = {
                "clips": len(picked),
                "heard_share": round(float(np.mean([r["share"] for r in picked])), 3),
                "needs_translate": sum(r["devanagari"] for r in picked),
                "p50_ms": round(float(np.median([r["ms"] for r in picked]))),
            }
        print(json.dumps({k: v for k, v in summary.items() if k.startswith(variant)}))
    RESULTS.write_text(
        json.dumps({"summary": summary, "detail": detail}, indent=1, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
