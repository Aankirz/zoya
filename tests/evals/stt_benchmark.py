#!/usr/bin/env python3
"""Phase 0 benchmark — Amazon Transcribe vs local Whisper (STACK §4/§8).

Reads tests/evals/fixtures/commands/*.wav + manifest.json (see
scripts/record_commands.py) and grades both engines on whether each
command's names/amounts `keywords` survive transcription, plus latency.
Pass bar: >= 90% word-correct on names/amounts, <= 0.5s/command for Whisper.

If no real recordings exist yet, synthesizes a Polly smoke-test set from the
same 20 commands (tests/evals/commands_data.py) — NOT a substitute for the
real benchmark on the owner's voice; see the printed warning.

Amazon Transcribe here uses a **batch** job (boto3, no extra streaming SDK —
`amazon-transcribe` pins awscrt~=0.26.1 and breaks the `zoya` AWS profile's
login credential provider, which needs a newer awscrt; see docs/AUDIT.md).
Batch jobs need audio in S3: set S3_RESULTS_BUCKET, or this half is skipped.

Usage: python tests/evals/stt_benchmark.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from commands_data import TARGET_COMMANDS  # noqa: E402

CLIPS_DIR = Path(__file__).parent / "fixtures" / "commands"
RESULTS_DIR = Path(__file__).parent / "results"
MANIFEST_PATH = CLIPS_DIR / "manifest.json"


def _keywords_present(transcript: str, keyword_groups: list[list[str]]) -> tuple[int, int]:
    """Each group is a set of acceptable surface forms; one match counts as a hit."""
    transcript_lower = transcript.lower()
    hits = sum(
        1 for group in keyword_groups if any(form.lower() in transcript_lower for form in group)
    )
    return hits, len(keyword_groups)


def ensure_smoke_test_clips() -> bool:
    """Synthesize Polly audio for TARGET_COMMANDS if no real recordings exist.

    Returns True if this is a synthetic smoke-test set (not real owner audio).
    """
    if MANIFEST_PATH.exists():
        return False

    import boto3
    from botocore.exceptions import ClientError

    print("No real recordings found — synthesizing a Polly smoke-test set instead.")
    print("(This only proves the pipeline runs; it is NOT the real benchmark — ")
    print(" record the real 20 commands with: python scripts/record_commands.py)\n")

    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "ap-south-1"),
    )
    polly = session.client("polly")
    for attempt in range(2):  # warm up the login credential provider (transient on first use)
        try:
            polly.describe_voices(LanguageCode="en-IN")
            break
        except ClientError:
            if attempt == 1:
                raise

    manifest = {}
    for i, command in enumerate(TARGET_COMMANDS):
        filename = f"{i:02d}.mp3"
        resp = polly.synthesize_speech(
            Text=command["text"],
            OutputFormat="mp3",
            VoiceId="Kajal",
            Engine="neural",
            LanguageCode="en-IN",
        )
        (CLIPS_DIR / filename).write_bytes(resp["AudioStream"].read())
        manifest[filename] = command["text"]
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return True


def run_whisper(clips: dict[str, str]) -> list[dict[str, Any]]:
    import mlx_whisper

    rows = []
    for filename, expected_text in clips.items():
        t0 = time.monotonic()
        result = mlx_whisper.transcribe(
            str(CLIPS_DIR / filename), path_or_hf_repo="mlx-community/whisper-large-v3-turbo"
        )
        latency = round(time.monotonic() - t0, 3)
        keywords = next(c["keywords"] for c in TARGET_COMMANDS if c["text"] == expected_text)
        hits, total = _keywords_present(result["text"], keywords)
        rows.append(
            {
                "file": filename,
                "expected": expected_text,
                "transcribed": result["text"].strip(),
                "keyword_hits": hits,
                "keyword_total": total,
                "latency_s": latency,
            }
        )
    return rows


def run_transcribe(clips: dict[str, str]) -> list[dict[str, Any]] | None:
    import boto3

    bucket = os.environ.get("S3_RESULTS_BUCKET")
    if not bucket:
        print("S3_RESULTS_BUCKET not set — skipping Amazon Transcribe (batch jobs need S3 input).")
        return None

    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE"),
        region_name=os.environ.get("AWS_REGION", "ap-south-1"),
    )
    s3 = session.client("s3")
    transcribe = session.client("transcribe")
    rows = []
    for filename, expected_text in clips.items():
        key = f"stt-benchmark/{uuid.uuid4().hex}-{filename}"
        s3.upload_file(str(CLIPS_DIR / filename), bucket, key)
        job_name = f"zoya-stt-{uuid.uuid4().hex[:12]}"
        media_format = filename.rsplit(".", 1)[-1]

        t0 = time.monotonic()
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode="en-IN",
            Media={"MediaFileUri": f"s3://{bucket}/{key}"},
            MediaFormat=media_format,
            OutputBucketName=bucket,
        )
        for _ in range(60):  # up to ~2 min per clip
            job = transcribe.get_transcription_job(TranscriptionJobName=job_name)[
                "TranscriptionJob"
            ]
            if job["TranscriptionJobStatus"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(2)
        latency = round(time.monotonic() - t0, 3)

        if job["TranscriptionJobStatus"] != "COMPLETED":
            rows.append(
                {"file": filename, "expected": expected_text, "error": job.get("FailureReason")}
            )
            continue

        # Private bucket: the TranscriptFileUri is unsigned, so read it through the S3 client.
        output = s3.get_object(Bucket=bucket, Key=f"{job_name}.json")
        transcript_json = json.loads(output["Body"].read())
        transcript = transcript_json["results"]["transcripts"][0]["transcript"]
        keywords = next(c["keywords"] for c in TARGET_COMMANDS if c["text"] == expected_text)
        hits, total = _keywords_present(transcript, keywords)
        rows.append(
            {
                "file": filename,
                "expected": expected_text,
                "transcribed": transcript,
                "keyword_hits": hits,
                "keyword_total": total,
                "latency_s": latency,
            }
        )
    return rows


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if "keyword_hits" in r]
    total_hits = sum(r["keyword_hits"] for r in scored)
    total_keywords = sum(r["keyword_total"] for r in scored)
    return {
        "keyword_accuracy": round(total_hits / total_keywords, 4) if total_keywords else None,
        "avg_latency_s": (
            round(sum(r["latency_s"] for r in scored) / len(scored), 3) if scored else None
        ),
        "rows": rows,
    }


def main() -> int:
    is_smoke_test = ensure_smoke_test_clips()
    clips = json.loads(MANIFEST_PATH.read_text())

    print(f"Running Whisper (mlx-whisper large-v3-turbo) on {len(clips)} clips...")
    whisper_summary = _summarize(run_whisper(clips))
    print(
        f"  keyword accuracy: {whisper_summary['keyword_accuracy']:.1%}, "
        f"avg latency: {whisper_summary['avg_latency_s']}s"
    )

    print("Running Amazon Transcribe...")
    transcribe_rows = run_transcribe(clips)
    transcribe_summary = _summarize(transcribe_rows) if transcribe_rows else None
    if transcribe_summary:
        print(
            f"  keyword accuracy: {transcribe_summary['keyword_accuracy']:.1%}, "
            f"avg latency: {transcribe_summary['avg_latency_s']}s"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "is_smoke_test": is_smoke_test,
        "note": (
            "Synthetic Polly audio, not the owner's real voice — not the real Phase 0 pass/fail."
            if is_smoke_test
            else "Real owner recordings."
        ),
        "whisper": whisper_summary,
        "amazon_transcribe": transcribe_summary,
    }
    out_path = RESULTS_DIR / "stt_benchmark.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved: {out_path}")
    if is_smoke_test:
        print(
            "\nNOTE: this ran on synthetic Polly audio. Record the real 20 commands with "
            "`python scripts/record_commands.py` and rerun for the real STACK §4 pass bar "
            "(>=90% keyword accuracy, <=0.5s/command)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
