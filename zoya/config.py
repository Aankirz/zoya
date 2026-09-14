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

# Fast-path tools.
AWS_CALL_TIMEOUT_S = 2
OSASCRIPT_TIMEOUT_S = 5
APP_LOOKUP_TIMEOUT_S = 2

# Apps run_applescript may address (§9.4 "allow-listed apps").
# ponytail: media + Notes only. System Events (keystrokes), Finder (files) and browsers
# (`do JavaScript` on logged-in pages) stay out until the safety gate (Phase 3) guards them.
APPLESCRIPT_ALLOWED_APPS = frozenset({"notes", "music", "spotify"})


def load_env() -> None:
    """Load .env from the repo root without overriding real environment variables."""
    load_dotenv(REPO_ROOT / ".env", override=False)


def aws_region() -> str:
    return os.environ.get("AWS_REGION") or DEFAULT_AWS_REGION
