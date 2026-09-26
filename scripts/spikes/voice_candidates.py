"""P2 spike: the same 10 Zoya sentences in every candidate voice, judged by ear (D33).

Writes logs/voice_candidates/<candidate>/NN.wav and appends one row per sentence to
logs/voice_candidates/measurements.jsonl; `--table` turns the rows into README.md.

  .venv/bin/python scripts/spikes/voice_candidates.py --engine polly
  .venv/bin/python scripts/spikes/voice_candidates.py --engine say
  <venv with pyobjc-framework-AVFoundation> scripts/spikes/voice_candidates.py --engine avspeech
  <venv with mlx-audio 0.5.6> scripts/spikes/voice_candidates.py --engine kokoro
  .venv/bin/python scripts/spikes/voice_candidates.py --table

Time to first audio (ttfa): polly = request → first PCM chunk (streamed, as Zoya plays it);
say = the whole sentence rendered to a file (what a `say -o` engine would wait for);
avspeech = utterance → first non-empty buffer; kokoro = text → first generated segment, model
already loaded. Memory: peak resident set of the process doing the synthesis, less its baseline.
"""

from __future__ import annotations

import argparse
import html
import json
import resource
import statistics
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "logs" / "voice_candidates"
ROWS = OUT / "measurements.jsonl"

SENTENCES = [
    "Notes is open.",
    "I'm about to place order for Amul Taaza Toned Milk, 1 litre, total 2,847 rupees.",
    "I didn't hear confirm, so I cancelled. Nothing was done.",
    "You've used this month's allowance for bigger tasks. Simple commands still work.",
    "Theek hai, aapki behen ka birthday 12 March ko hai.",
    "Maine Rahul Verma ko WhatsApp pe message bhej diya.",
    "Your cart total is 1,249.50 rupees, with a delivery fee of 35 rupees.",
    "Calling Priya Sharma and Aniruddha Iyer now.",
    "It's 31 degrees in Bengaluru, with a chance of rain after 4 PM.",
    "Aaj Noida mein 34 degree hai, shaam ko baarish ho sakti hai.",
]
SAY_VOICES = {
    "macos-rishi": "Rishi",
    "macos-lekha": "Lekha",
    "macos-aman-enhanced": "com.apple.voice.Aman.premium",
    "macos-tara-enhanced": "com.apple.voice.Tara.premium",
}
AVSPEECH_VOICES = {
    "avspeech-aman-enhanced": "com.apple.voice.Aman.premium",
    "avspeech-tara-enhanced": "com.apple.voice.Tara.premium",
}
KOKORO_REPO = "mlx-community/Kokoro-82M-bf16"
KOKORO_REVISION = "a71e4d38b236d968966a2002c4c895dbd12b1c3c"
KOKORO_VOICES = {
    "kokoro-af_heart": ("af_heart", "a"),
    "kokoro-bf_emma": ("bf_emma", "b"),
    "kokoro-hf_alpha": ("hf_alpha", "a"),
    "kokoro-hf_beta": ("hf_beta", "a"),
    "kokoro-hm_omega": ("hm_omega", "a"),
}
POLLY_RATE_HZ = 16000
SAY_FORMAT = "LEI16@22050"
AVSPEECH_TIMEOUT_S = 30.0
INT16_MAX = 32767


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


def _write_wav(path: Path, pcm: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm)


def _record(candidate: str, index: int, ttfa_ms: float, memory_mb: float, note: str = "") -> None:
    row = {
        "candidate": candidate,
        "sentence": index + 1,
        "ttfa_ms": round(ttfa_ms),
        "memory_mb": round(memory_mb),
        "note": note,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with ROWS.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row) + "\n")
    print(row, flush=True)


def run_polly() -> None:
    sys.path.insert(0, str(REPO))
    from zoya import aws
    from zoya.config import POLLY_ENGINE, POLLY_LANGUAGE_CODE, POLLY_VOICE_ID, load_env

    load_env()
    polly = aws.client("polly")
    for index, text in enumerate(SENTENCES):
        started = time.monotonic()
        response = polly.synthesize_speech(
            Text=text,
            VoiceId=POLLY_VOICE_ID,
            Engine=POLLY_ENGINE,
            LanguageCode=POLLY_LANGUAGE_CODE,
            OutputFormat="pcm",
            SampleRate=str(POLLY_RATE_HZ),
        )
        chunks = response["AudioStream"].iter_chunks(3200)
        first = next(chunks)
        ttfa = (time.monotonic() - started) * 1000
        pcm = first + b"".join(chunks)
        _write_wav(OUT / "polly-kajal" / f"{index + 1:02}.wav", pcm, POLLY_RATE_HZ)
        _record("polly-kajal", index, ttfa, 0, "cloud; nothing resident on the Mac")


def _say_once(voice: str, text: str, target: Path) -> tuple[float, float]:
    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = subprocess.run(
        ["/usr/bin/time", "-l", "say", "-v", voice, f"--data-format={SAY_FORMAT}"]
        + ["-o", str(target), text],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = (time.monotonic() - started) * 1000
    rss = next(
        int(line.split()[0]) for line in result.stderr.splitlines() if "maximum resident" in line
    )
    return elapsed, rss / (1024 * 1024)


def run_say() -> None:
    for candidate, voice in SAY_VOICES.items():
        for index, text in enumerate(SENTENCES):
            path = OUT / candidate / f"{index + 1:02}.wav"
            ttfa, rss = _say_once(voice, text, path)
            _record(candidate, index, ttfa, rss, "whole sentence rendered to a file")


def _avspeech_first_buffer(synth, voice, text: str, path: Path) -> float:  # noqa: ANN001
    import AVFoundation
    import numpy as np
    from Foundation import NSDate, NSRunLoop

    utterance = AVFoundation.AVSpeechUtterance.speechUtteranceWithString_(text)
    utterance.setVoice_(voice)
    state = {"first": None, "pcm": [], "rate": 0, "done": threading.Event()}
    started = time.monotonic()

    def on_buffer(buffer) -> None:  # noqa: ANN001
        frames = buffer.frameLength()
        if frames == 0:
            state["done"].set()
            return
        if state["first"] is None:
            state["first"] = time.monotonic()
        state["rate"] = int(buffer.format().sampleRate())
        floats = bytes(buffer.floatChannelData()[0].as_buffer(frames))
        samples = np.clip(np.frombuffer(floats, "<f4"), -1, 1)
        state["pcm"].append((samples * INT16_MAX).astype("<i2").tobytes())

    synth.writeUtterance_toBufferCallback_(utterance, on_buffer)
    deadline = time.monotonic() + AVSPEECH_TIMEOUT_S
    while not state["done"].is_set() and time.monotonic() < deadline:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.01))
    _write_wav(path, b"".join(state["pcm"]), state["rate"])
    return ((state["first"] or time.monotonic()) - started) * 1000


def run_avspeech() -> None:
    import AVFoundation

    baseline = _peak_rss_mb()
    synth = AVFoundation.AVSpeechSynthesizer.alloc().init()
    for candidate, identifier in AVSPEECH_VOICES.items():
        voice = AVFoundation.AVSpeechSynthesisVoice.voiceWithIdentifier_(identifier)
        _avspeech_first_buffer(synth, voice, "Warming up.", OUT / "warmup.wav")
        for index, text in enumerate(SENTENCES):
            path = OUT / candidate / f"{index + 1:02}.wav"
            ttfa = _avspeech_first_buffer(synth, voice, text, path)
            _record(candidate, index, ttfa, _peak_rss_mb() - baseline, "streamed buffers")


def run_kokoro() -> None:
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model

    baseline = _peak_rss_mb()
    started = time.monotonic()
    model = load_model(KOKORO_REPO, revision=KOKORO_REVISION)
    print(f"kokoro loaded in {time.monotonic() - started:.1f} s", flush=True)
    for candidate, (voice, lang) in KOKORO_VOICES.items():
        list(model.generate(text="Warming up.", voice=voice, lang_code=lang))
        for index, text in enumerate(SENTENCES):
            started = time.monotonic()
            segments = model.generate(text=text, voice=voice, lang_code=lang)
            first = next(segments)
            ttfa = (time.monotonic() - started) * 1000
            audio = np.concatenate([np.array(s.audio) for s in [first, *segments]])
            pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
            _write_wav(OUT / candidate / f"{index + 1:02}.wav", pcm, model.sample_rate)
            memory = max(_peak_rss_mb() - baseline, mx.get_peak_memory() / (1024 * 1024))
            _record(candidate, index, ttfa, memory, f"voice {voice}, G2P lang '{lang}'")


NOTES = """
## Notes

- **polly-kajal** is today's voice. After P2 it can come through the relay (`polly-relay`), which
  needs no AWS profile on the Mac: 122–179 ms to the first chunk through local `wrangler dev`,
  metered at $16 per 1M characters (a 100-character sentence is 0.16 cents).
- **macos-*** voices: `say` cannot write to a pipe, so a mixer-routed macOS voice waits for the
  whole sentence (the ttfa above). Played straight to the speakers, as today's fallback is,
  `say` starts sooner. Aman and Tara are the enhanced voices already installed on this Mac;
  AVSpeechSynthesizer in Zoya's Python process does not list them (only compact Rishi), so they
  are reachable only through `say`. The Siri voice (Akash) is not reachable at all.
- **kokoro-***: Kokoro-82M (Apache-2.0) via mlx-audio 0.5.6. The weights take 312 MB; the process
  grows about 700 MB once it speaks (its text front-end loads spaCy and torch); memory above is
  the transient MLX peak on the longest sentence. Hinglish and any word outside its English
  dictionary go through espeak-ng, which is GPL-3.0. Its Hindi voices (hf_*, hm_*) were run
  with the English front-end, since Zoya's Hinglish is written in Latin script.
- Not rendered: **Indic Parler-TTS** (ai4bharat, Apache-2.0, 0.9B) is gated on Hugging Face;
  **rumik-oss-1** (3B, Indic and Hinglish) is CC-BY-NC-4.0, so it cannot ship in a paid app.
"""


def write_table() -> None:
    rows = [json.loads(line) for line in ROWS.read_text(encoding="utf-8").splitlines()]
    by_candidate: dict[str, list[dict]] = {}
    for row in rows:
        by_candidate.setdefault(row["candidate"], []).append(row)
    lines = [
        "# Voice candidates (P2, D33): the owner picks by ear",
        "",
        "Every folder holds the same 10 sentences, 01.wav to 10.wav:",
        "",
        *[f"{i + 1}. {text}" for i, text in enumerate(SENTENCES)],
        "",
        "| candidate | ttfa p50 ms | ttfa max ms | peak memory MB | how measured |",
        "|---|---|---|---|---|",
    ]
    for candidate, items in by_candidate.items():
        ttfas = [row["ttfa_ms"] for row in items]
        lines.append(
            f"| {candidate} | {round(statistics.median(ttfas))} | {max(ttfas)} | "
            f"{max(row['memory_mb'] for row in items)} | {items[0]['note']} |"
        )
    (OUT / "README.md").write_text("\n".join(lines) + "\n" + NOTES, encoding="utf-8")
    _write_listening_page(list(by_candidate))
    print((OUT / "README.md").read_text(encoding="utf-8"))


def _write_listening_page(candidates: list[str]) -> None:
    head = "".join(f"<th>{html.escape(name)}</th>" for name in candidates)
    rows = "".join(
        f"<tr><td>{index + 1}. {html.escape(text)}</td>"
        + "".join(
            f'<td><audio controls preload="none" src="{name}/{index + 1:02}.wav"></audio></td>'
            for name in candidates
        )
        + "</tr>"
        for index, text in enumerate(SENTENCES)
    )
    page = (
        '<!doctype html><meta charset="utf-8"><title>Zoya voice candidates</title>'
        "<style>body{font:14px system-ui;margin:16px}"
        "td,th{padding:4px;border-bottom:1px solid #ddd;vertical-align:middle}"
        "audio{width:120px}</style>"
        f"<h1>Zoya voice candidates</h1><p>Pick by ear (D33). Details: README.md</p>"
        f"<table><tr><th>sentence</th>{head}</tr>{rows}</table>"
    )
    (OUT / "index.html").write_text(page, encoding="utf-8")


ENGINES = {
    "polly": run_polly,
    "say": run_say,
    "avspeech": run_avspeech,
    "kokoro": run_kokoro,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=sorted(ENGINES))
    parser.add_argument("--table", action="store_true")
    args = parser.parse_args()
    if args.engine:
        ENGINES[args.engine]()
    if args.table:
        write_table()
    return 0


if __name__ == "__main__":
    sys.exit(main())
