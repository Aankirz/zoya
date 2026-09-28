"""D136 voice spike: Llama-to-SNAC TTS models on this Mac, judged by ear.

Veena (maya-research/Veena) and Svara-TTS v1 (kenpath/svara-tts-v1), both Apache-2.0, are 3B
Llamas that emit SNAC 24 kHz audio codes (the Orpheus recipe). The Llama runs on MLX (mlx-lm)
and the SNAC decoder on torch MPS. Writes logs/voice_candidates/<model>-<speaker>-<weights>/NN.wav
and appends rows to logs/voice_candidates/measurements.jsonl.

  scripts/spikes/.venv/bin/python scripts/spikes/voice_llm_tts.py --model veena --quantize q4
  scripts/spikes/.venv/bin/python scripts/spikes/voice_llm_tts.py --model veena --weights q4

Time to first audio (ttfa): text -> first 4 SNAC frames (341 ms of audio) generated and
decoded, model loaded and warm; the chunk a streaming player starts on (Svara's own server
uses the same 4-frame window). Real-time factor (rtf): whole-sentence generate + decode time
over audio duration (< 1 is faster than real time). Memory: MLX peak + torch MPS driver memory.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(HERE / ".venv" / "hf"))

import mlx.core as mx  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from mlx_lm import load, stream_generate  # noqa: E402
from mlx_lm.convert import convert  # noqa: E402
from mlx_lm.sample_utils import make_logits_processors, make_sampler  # noqa: E402
from snac import SNAC  # noqa: E402
from voice_candidates import OUT, ROWS, SENTENCES, _write_wav  # noqa: E402

SNAC_REPO = "hubertsiuzdak/snac_24khz"
QUANTIZED_DIR = HERE / ".venv" / "mlx"

BOS = 128000
END_OF_TURN = 128009
START_OF_SPEECH = 128257
END_OF_SPEECH = 128258
START_OF_HUMAN = 128259
END_OF_HUMAN = 128260
START_OF_AI = 128261
END_OF_AI = 128262
SVARA_AUDIO_MARKER = 156939
AUDIO_BASE = 128266
CODEBOOK = 4096
FRAME = 7
FIRST_CHUNK_FRAMES = 4
SAMPLE_RATE = 24000
SEED = 7
MB = 1024 * 1024


@dataclass(frozen=True)
class Model:
    repo: str
    revision: str
    speakers: tuple[str, ...]
    temperature: float
    top_p: float
    repetition_penalty: float
    max_tokens: int


MODELS = {
    "veena": Model(
        "maya-research/Veena",
        "8b770f9e69e6b35ef320d4cd70a99a4ab6dd022f",
        ("kavya", "maitri", "vinaya"),
        0.4,
        0.9,
        1.05,
        700,
    ),
    "svara": Model(
        "kenpath/svara-tts-v1",
        "db8a02fc1e4eab827ff6dda5bed3b56d4d2dd51e",
        ("Hindi (Female)", "English (Female)"),
        0.75,
        0.9,
        1.1,
        2048,
    ),
}


def weights_path(name: str, weights: str) -> str:
    if weights == "bf16":
        from huggingface_hub import snapshot_download

        return snapshot_download(MODELS[name].repo, revision=MODELS[name].revision)
    return str(QUANTIZED_DIR / f"{name}-{weights}")


def quantize(name: str, weights: str) -> None:
    bits = int(weights.removeprefix("q"))
    source = weights_path(name, "bf16")
    convert(source, mlx_path=weights_path(name, weights), quantize=True, q_bits=bits)


def prompt_tokens(name: str, tokenizer, speaker: str, text: str) -> list[int]:  # noqa: ANN001
    if name == "veena":
        body = tokenizer.encode(f"<spk_{speaker}> {text}", add_special_tokens=False)
        return [START_OF_HUMAN, *body, END_OF_HUMAN, START_OF_AI, START_OF_SPEECH]
    body = tokenizer.encode(f"{speaker}: {text}", add_special_tokens=False)
    return [BOS, START_OF_HUMAN, SVARA_AUDIO_MARKER, *body, END_OF_HUMAN, END_OF_TURN] + [
        START_OF_AI,
        START_OF_SPEECH,
    ]


def decode(snac: SNAC, codes: list[int]) -> np.ndarray:
    usable = codes[: len(codes) // FRAME * FRAME]
    levels: list[list[int]] = [[], [], []]
    for i in range(0, len(usable), FRAME):
        f = [usable[i + k] - AUDIO_BASE - k * CODEBOOK for k in range(FRAME)]
        levels[0].append(f[0])
        levels[1] += [f[1], f[4]]
        levels[2] += [f[2], f[3], f[5], f[6]]
    device = next(snac.parameters()).device
    tensors = [torch.tensor(level, dtype=torch.int32, device=device)[None] for level in levels]
    with torch.no_grad():
        return snac.decode(tensors).squeeze().clamp(-1, 1).cpu().numpy()


def is_audio_code(token: int, position: int) -> bool:
    band = AUDIO_BASE + (position % FRAME) * CODEBOOK
    return band <= token < band + CODEBOOK


def synthesize(
    name: str, model, tokenizer, snac: SNAC, speaker: str, text: str
):  # noqa: ANN001, ANN201
    spec = MODELS[name]
    mx.random.seed(SEED)
    sampler = make_sampler(temp=spec.temperature, top_p=spec.top_p)
    processors = make_logits_processors(repetition_penalty=spec.repetition_penalty)
    max_tokens = min(int(len(text) * 1.3) * FRAME + 21, spec.max_tokens)
    started = time.monotonic()
    ttfa = None
    codes: list[int] = []
    prompt = prompt_tokens(name, tokenizer, speaker, text)
    for step in stream_generate(
        model,
        tokenizer,
        prompt,
        max_tokens=max_tokens,
        sampler=sampler,
        logits_processors=processors,
    ):
        if step.token in (END_OF_SPEECH, END_OF_AI):
            break
        if is_audio_code(step.token, len(codes)):
            codes.append(step.token)
        if ttfa is None and len(codes) == FIRST_CHUNK_FRAMES * FRAME:
            decode(snac, codes)
            ttfa = time.monotonic() - started
    audio = decode(snac, codes)
    return audio, (ttfa if ttfa is not None else time.monotonic() - started)


def memory_mb() -> float:
    return (mx.get_peak_memory() + torch.mps.driver_allocated_memory()) / MB


def slug(speaker: str) -> str:
    return speaker.lower().replace(" (", "_").replace(")", "")


def record(
    candidate: str, index: int, ttfa_s: float, rtf: float, audio_s: float, note: str
) -> None:
    row = {
        "candidate": candidate,
        "sentence": index + 1,
        "ttfa_ms": round(ttfa_s * 1000),
        "memory_mb": round(memory_mb()),
        "rtf": round(rtf, 2),
        "audio_s": round(audio_s, 2),
        "note": note,
    }
    with ROWS.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row) + "\n")
    print(row, flush=True)


def run(name: str, weights: str, speakers: list[str]) -> None:
    started = time.monotonic()
    model, tokenizer = load(weights_path(name, weights))
    snac = SNAC.from_pretrained(SNAC_REPO).eval().to("mps")
    print(f"{name} {weights} + snac loaded in {time.monotonic() - started:.1f} s", flush=True)
    note = f"MLX {weights} Llama + SNAC on MPS, first {FIRST_CHUNK_FRAMES} frames"
    for speaker in speakers:
        candidate = f"{name}-{slug(speaker)}-{weights}"
        synthesize(name, model, tokenizer, snac, speaker, "Warming up.")
        ttfas = []
        for index, text in enumerate(SENTENCES):
            started = time.monotonic()
            audio, ttfa = synthesize(name, model, tokenizer, snac, speaker, text)
            elapsed = time.monotonic() - started
            audio_s = len(audio) / SAMPLE_RATE
            pcm = (audio * 32767).astype("<i2").tobytes()
            _write_wav(OUT / candidate / f"{index + 1:02}.wav", pcm, SAMPLE_RATE)
            record(candidate, index, ttfa, elapsed / max(audio_s, 1e-3), audio_s, note)
            ttfas.append(ttfa)
        print(f"{candidate}: ttfa p50 {statistics.median(ttfas) * 1000:.0f} ms", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--weights", choices=["bf16", "q8", "q4"])
    parser.add_argument("--quantize", choices=["q8", "q4"])
    parser.add_argument("--speakers", nargs="+")
    args = parser.parse_args()
    if args.quantize:
        quantize(args.model, args.quantize)
    if args.weights:
        run(args.model, args.weights, args.speakers or list(MODELS[args.model].speakers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
