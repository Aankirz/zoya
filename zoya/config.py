"""Shared settings (docs/phases/phase-1-brain-fast-actions.md "Contracts first").

Secrets and account-specific values live in .env (loaded by `load_env`); every
other setting is a named constant here. Later phases add keys append-only.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --- Phase 0 -------------------------------------------------------------------

# Spending limits (STACK §7, phase-0 brief "Set spending limits").
OPENAI_MONTHLY_BUDGET_USD = 15.0
PER_TASK_COST_CAP_USD = 0.50

# Fireworks is OpenAI-compatible; verified against
# https://docs.fireworks.ai/api-reference/post-chatcompletions (2026-09-14).
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

# --- Phase 1 -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
TIMING_LOG = LOG_DIR / "timing.log"

DEFAULT_AWS_REGION = "ap-south-1"  # D30

# Price per 1M tokens (input, output), verified 2026-09-14 (STACK §7). Unknown
# models fall back to the most expensive known price so the cap errs safe.
MODEL_PRICES_USD_PER_1M = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
}
UNKNOWN_MODEL_PRICE_USD_PER_1M = (4.00, 20.00)

# Bounded autonomy (§9.3, §12.1).
MAX_TOOL_CALLS_PER_TASK = 40

# AWS Secrets Manager: one JSON secret holding provider keys (STACK §8).
PROVIDER_SECRET_ID = "zoya/providers"
PROVIDER_SECRET_KEYS = (
    "OPENAI_API_KEY",
    "FIREWORKS_API_KEY",
    "ELEVENLABS_API_KEY",
    "SUPERMEMORY_API_KEY",
)

# Amazon DynamoDB task history (STACK §8). Partition key: task_id (S).
TASK_HISTORY_TABLE = "zoya-task-history"

# Voice (D33, D41). Polly neural PCM supports 8000/16000 Hz.
POLLY_VOICE_ID = "Kajal"
POLLY_ENGINE = "neural"
POLLY_LANGUAGE_CODE = "en-IN"
SPEECH_SAMPLE_RATE_HZ = 16000
ELEVENLABS_MODEL_ID = "eleven_flash_v2_5"
MACOS_FALLBACK_VOICE = "Rishi"  # en_IN voice installed on the demo Mac

# OpenAI SDK defaults are a 600 s timeout with 2 retries (openai/_constants.py), so one stuck
# request could block ~30 min. Router calls are short structured answers; brain calls stream.
MODEL_TIMEOUT_S = {"router": 10.0, "brain": 60.0, "vision": 60.0}
MODEL_MAX_RETRIES = 1

# Fast-path tools.
AWS_CALL_TIMEOUT_S = 2
OSASCRIPT_TIMEOUT_S = 5
APP_LOOKUP_TIMEOUT_S = 2

# --- Phase 2 -------------------------------------------------------------------

SOUNDS_DIR = REPO_ROOT / "sounds"
AUDIO_SAMPLE_RATE_HZ = 48000  # earcons are built at this rate (scripts/build_sounds.sh)
AUDIO_BLOCK_SIZE = 480  # 10 ms mixer blocks → stop silences within one block
LOOP_DUCK_GAIN = 10 ** (-18 / 20)  # working loop −18 dB under speech (§9.10)
DUCK_FRACTION = 0.3  # other apps' audio drops to 30% of the volume while Zoya listens
DUCK_STATE_FILE = LOG_DIR / "duck_state.json"  # pre-duck volume, so a killed run can be undone

# TTS bounds. ElevenLabs SDK default timeout is 240 s (elevenlabs/client.py).
ELEVENLABS_TIMEOUT_S = 5.0
POLLY_CHUNK_BYTES = 3200  # 100 ms of 16 kHz int16
SAY_TIMEOUT_S = 30.0
SPEECH_DRAIN_MARGIN_S = 2.0  # wait for playback at most audio length + this
DISABLE_TTS_ENV = "ZOYA_DISABLE_TTS"  # e.g. "polly" or "polly,elevenlabs" (Done-when #7)

# Listening (§9.1, D19, D48). Silero VAD v6 runs on 512-sample blocks at 16 kHz.
MIC_SAMPLE_RATE_HZ = 16000
VAD_BLOCK = 512
VAD_THRESHOLD = 0.5
PRE_ROLL_S = 0.3
WAKE_END_SILENCE_S = 0.3  # a wake-only phrase ends after this
COMMAND_END_SILENCE_S = 0.5  # STACK §2: a turn ends after ~0.5 s silence (fallback rule)
# Smart Turn v3.2 end-of-turn model (pipecat, BSD-2: third_party/LICENSE-smart-turn.txt), 8 MB
# ONNX downloaded at startup, never committed: https://huggingface.co/pipecat-ai/smart-turn-v3
# "complete" after TURN_CHECK_SILENCE_S ends the turn early; otherwise the 0.5 s rule applies.
ENDPOINT_MODE = "smart_turn"  # "silence" = the fixed COMMAND_END_SILENCE_S rule only
SMART_TURN_REPO = "pipecat-ai/smart-turn-v3"
SMART_TURN_FILE = "smart-turn-v3.2-cpu.onnx"
SMART_TURN_SHA256 = "2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f"
TURN_CHECK_SILENCE_S = 0.2
TURN_COMPLETE_PROBABILITY = 0.5
TURN_WINDOW_S = 8  # the model reads the last 8 s
# Every local model, pinned: repo → (revision, {file: sha256}). Downloaded once by
# `python -m zoya.setup_models`; at runtime Zoya is offline for models (AUDIT §6).
MODEL_PINS = {
    "mlx-community/whisper-base.en-mlx": (
        "aa0678c3466ed62c5c6114ec600a0e1f96820089",
        {"weights.npz": "b6c8ee500656e04e8e57c2949a5253f0dda002ba36cd1561846574dbcf01132e"},
    ),
    "mlx-community/whisper-large-v3-turbo": (
        "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb",
        {"weights.safetensors": "951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6"},
    ),
    "pipecat-ai/smart-turn-v3": (
        "f766f81d3cfdf7737ac64aad813d91bbfd56bf93",
        {"smart-turn-v3.2-cpu.onnx": SMART_TURN_SHA256},
    ),
}
PARTIAL_EVERY_S = 0.15  # re-check for "Zoya, stop" this often while Zoya talks or works
PARTIAL_MIN_S = 0.35
WAKE_WINDOW_S = 2.5  # the name must come in the first 3 words: spot only this much audio
MAX_UTTERANCE_S = 15.0  # bounds every Whisper call
AFTER_WAKE_WAIT_S = 6.0  # "Hey Zoya" … pause … command; other audio stays ducked meanwhile
ECHO_TAIL_S = 0.6  # ignore wake words this long after Zoya stops talking (Done-when #2)
MIC_READ_TIMEOUT_S = 1.0
WAKE_MODEL = "mlx-community/whisper-base.en-mlx"  # D51: ~30 ms/call on GPU vs ~250 ms CPU
SPOTTER_ENGINE = "mlx"  # "faster-whisper" = D19's CPU spotter, if mlx misbehaves on stage
STT_MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
PTT_POLL_S = 0.03
# Hold to talk; press while Zoya talks to interrupt. Owner's other app uses Control + Option.
# Names: fn, shift, control, option, command.
PUSH_TO_TALK_KEYS = ("fn", "shift")
TASK_JOIN_TIMEOUT_S = 90.0
WEATHER_TIMEOUT_S = 3.0  # per Open-Meteo call (D50)

# --- Phase 3: safety gate (§9.9, §12, D7) ------------------------------------------------------

CONFIRM_TOKEN_TTL_S = 60.0  # a voice-issued token is dead after this
CONFIRM_REPLY_TIMEOUT_S = 20.0  # no answer → re-prompt once → auto-cancel (silence ≠ consent)
CONFIRM_PROMPTS = 2  # the first ask + one re-prompt
CONFIRM_SPEAK_TIMEOUT_S = 30.0  # bound on speaking one summary
WARNING_EARCON_GAP_S = 0.6  # warning.wav is 0.53 s; played twice before every summary
CONFIRMATION_AUDIT_TABLE = "zoya-confirmations"  # partition key: confirmation_id (S)
CONFIRMATION_LOG = LOG_DIR / "confirmations.log"  # local copy of the audit log
SCREEN_CAPTURE_TIMEOUT_S = 3.0  # ScreenCaptureKit completion handlers (D23)
REKOGNITION_TIMEOUT_S = 6.0  # DetectText on a ~1 MB screenshot
SCREENSHOT_JPEG_QUALITY = 0.8  # Rekognition image bytes limit is 5 MB
BROWSER_PROFILE_DIR = Path.home() / ".zoya" / "chrome-profile"  # D11 dedicated profile
BROWSER_ACTION_TIMEOUT_S = 15.0  # every Playwright call (navigation, click, read)
BROWSER_TEXT_MAX_CHARS = 6000  # page text handed to the brain

# --- Echo cancellation for laptop speakers ------------------------------------------------------

# D62, zoya/aec.py: WebRTC AEC3 with Zoya's playback + a tap of other apps as
# the reference, so "Hey Zoya" / "Zoya, stop" work over music and her own voice on laptop speakers.
AEC_ENABLED = False  # never in front of Whisper (replay: it lowered wakes); barge-in detector only
AEC_NOISE_SUPPRESSION = False
AEC_TAP_START_TIMEOUT_S = 3.0
REFERENCE_LOCK_TIMEOUT_S = 0.002  # audio callbacks never wait longer than this
REFERENCE_MAX_S = 2.0  # reference kept per source; the loop thread may lag behind a turbo call
AEC_MIC_DELAY_BLOCKS = 1  # the tap trails the mic by up to ~30 ms: mic waits one 32 ms block
AEC_REANCHOR_S = 0.03  # a source's offset moving more than this (clock drift) re-anchors it
# Barge-in (D62): user voice onset in the echo-cancelled mic → Zoya's voice drops within one 10 ms
# mixer block and other apps duck, so Whisper hears "stop" / "Hey Zoya" on the raw mic.
BARGE_IN_ONSET_BLOCKS = 2  # consecutive voiced 32 ms blocks = the user is talking
ONSET_MIN_RMS = 0.005  # same floor as the voice loop's MIN_SPEECH_RMS
OTHER_AUDIO_MIN_RMS = 0.003  # tap reference above this = another app is playing: duck it too
BARGE_IN_SPEECH_GAIN = 10 ** (-20 / 20)  # Zoya keeps talking, 20 dB quieter
BARGE_IN_HOLD_S = 2.5  # restore this long after the user's last voiced block, if no stop/wake


def load_env() -> None:
    """Load .env from the repo root without overriding real environment variables."""
    load_dotenv(REPO_ROOT / ".env", override=False)


def aws_region() -> str:
    return os.environ.get("AWS_REGION") or DEFAULT_AWS_REGION
