#!/usr/bin/env python3
"""Phase 0 benchmark — voice (docs/STACK.md §4/§8, phase-0 brief).

1. Amazon Polly `Kajal` (neural, en-IN) time-to-first-audio on 5 Zoya
   sentences incl. Hinglish — the already-decided primary voice (D33).
2. ElevenLabs `Tara` (the one Indian voice this plan allows, D31)
   time-to-first-byte on the same 5 sentences, for the fallback comparison.
3. A Whisper pipeline smoke test using the Polly audio as input.

Item 3 is NOT the real Phase 0 "Done when" Whisper benchmark — that one
needs 20 commands *recorded by the owner on this Mac* (word accuracy on
names/amounts, real accent/Hinglish). This only proves mlx-whisper /
faster-whisper run end-to-end on this machine; see the printed note.

Usage: python tests/evals/voice_benchmark.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RESULTS_DIR = Path(__file__).parent / "results"
AUDIO_DIR = RESULTS_DIR / "audio"

# 5 Zoya sentences incl. Hinglish (STACK §4 "Voice" row).
SENTENCES = [
    "Hi, I'm Zoya. How can I help you today?",
    "Your order total is two thousand eight hundred and forty seven rupees.",
    "Aapka Swiggy order pandrah minute mein aa jayega.",
    "I've set a reminder for six pm to call Priya.",
    "Zoya ruk gayi hai, bataiye aage kya karna hai.",
]


def bench_polly() -> list[dict]:
    import boto3
    from botocore.exceptions import ClientError

    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "ap-south-1"),
    )
    polly = session.client("polly")
    # ponytail: the `zoya` profile's login credential provider can throw a
    # transient ValidationException on first use in a fresh process; warm it up.
    for attempt in range(2):
        try:
            polly.describe_voices(LanguageCode="en-IN")
            break
        except ClientError:
            if attempt == 1:
                raise

    rows = []
    for i, sentence in enumerate(SENTENCES):
        t0 = time.monotonic()
        resp = polly.synthesize_speech(
            Text=sentence,
            OutputFormat="mp3",
            VoiceId="Kajal",
            Engine="neural",
            LanguageCode="en-IN",
        )
        first_byte = resp["AudioStream"].read(4096)
        ttfa = round(time.monotonic() - t0, 3)
        rest = resp["AudioStream"].read()
        path = AUDIO_DIR / f"polly_kajal_{i}.mp3"
        path.write_bytes(first_byte + rest)
        rows.append({"sentence": sentence, "time_to_first_audio_s": ttfa, "file": str(path)})
    return rows


def bench_elevenlabs(voice_id: str = "Be3X8pg7kLN4vyyMC3QN") -> list[dict]:
    """voice_id defaults to Tara — the only Indian voice this ElevenLabs plan allows (D31)."""
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    rows = []
    for i, sentence in enumerate(SENTENCES):
        t0 = time.monotonic()
        chunks = client.text_to_speech.convert(
            voice_id=voice_id,
            text=sentence,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        )
        first_chunk = next(chunks)
        ttfb = round(time.monotonic() - t0, 3)
        audio = first_chunk + b"".join(chunks)
        path = AUDIO_DIR / f"elevenlabs_tara_{i}.mp3"
        path.write_bytes(audio)
        rows.append({"sentence": sentence, "time_to_first_byte_s": ttfb, "file": str(path)})
    return rows


def whisper_smoke_test() -> list[dict]:
    """Transcribe the Polly clips with mlx-whisper as an end-to-end pipeline check."""
    import mlx_whisper

    rows = []
    for i, sentence in enumerate(SENTENCES):
        path = AUDIO_DIR / f"polly_kajal_{i}.mp3"
        if not path.exists():
            continue
        t0 = time.monotonic()
        result = mlx_whisper.transcribe(
            str(path), path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
        )
        latency = round(time.monotonic() - t0, 3)
        rows.append(
            {
                "expected": sentence,
                "transcribed": result["text"].strip(),
                "latency_s": latency,
            }
        )
    return rows


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Polly Kajal (neural, en-IN) — {len(SENTENCES)} sentences...")
    polly_rows = bench_polly()
    avg_polly = round(sum(r["time_to_first_audio_s"] for r in polly_rows) / len(polly_rows), 3)
    print(f"  avg time-to-first-audio: {avg_polly}s")

    print(f"ElevenLabs Tara (flash v2.5) — {len(SENTENCES)} sentences...")
    try:
        eleven_rows = bench_elevenlabs()
        avg_eleven = round(
            sum(r["time_to_first_byte_s"] for r in eleven_rows) / len(eleven_rows), 3
        )
        print(f"  avg time-to-first-byte: {avg_eleven}s")
    except Exception as error:  # noqa: BLE001
        eleven_rows, avg_eleven = [], None
        print(f"  [FAIL] {type(error).__name__}: {error}")

    print("\nWhisper smoke test (mlx-whisper large-v3-turbo on the Polly clips)...")
    whisper_rows = whisper_smoke_test()
    for row in whisper_rows:
        print(f"  expected: {row['expected'][:50]!r}")
        print(f"  heard:    {row['transcribed'][:50]!r}  ({row['latency_s']}s)")

    result = {
        "polly_kajal": {"avg_time_to_first_audio_s": avg_polly, "rows": polly_rows},
        "elevenlabs_tara": {"avg_time_to_first_byte_s": avg_eleven, "rows": eleven_rows},
        "whisper_smoke_test": whisper_rows,
    }
    out_path = RESULTS_DIR / "voice_benchmark.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out_path}")
    print(
        "\nNOTE: the real Phase 0 Whisper pass bar (>=90% word-correct on names/amounts, "
        "<=0.5s/command, English+Hinglish) needs 20 commands recorded by the owner on this "
        "Mac (docs/phases/phase-0-foundations.md) — the smoke test above only proves the "
        "pipeline runs end-to-end on synthetic audio."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
