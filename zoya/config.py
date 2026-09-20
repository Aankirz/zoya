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
    "TINYFISH_API_KEY",
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
SCREENSHOT_JPEG_QUALITY = 0.8  # readable text at a fraction of a PNG's bytes
BROWSER_PROFILE_DIR = Path.home() / ".zoya" / "chrome-profile"  # D11 dedicated profile
BROWSER_ACTION_TIMEOUT_S = 15.0  # every Playwright call (navigation, click, read)
BROWSER_TEXT_MAX_CHARS = 6000  # page text handed to the brain

# --- Phase 4: browser, shopping, memory, harness (§9.7, §9.8, §9.12) ----------------------------

SKILLS_DIR = REPO_ROOT / "zoya" / "skills"
# Brain prompt-prefix cache (OpenAI prompt caching; verified live 2026-09-14: the second call with
# the same key read 1,836 of 1,839 prompt tokens from cache). One key per skill prompt.
PROMPT_CACHE_KEY_PREFIX = "zoya-v1"
PROMPT_CACHE_TTL = "30m"
LEARNED_PICKS_FILE = LOG_DIR / "learned_picks.json"  # command → skill action the router model chose
LEARNED_PICK_TTL_S = 7 * 24 * 3600
RESULT_CACHE_MAX_ITEMS = 256
TINYFISH_SEARCH_URL = "https://api.search.tinyfish.ai"
TINYFISH_FETCH_URL = "https://api.fetch.tinyfish.ai"
WEB_SEARCH_TIMEOUT_S = 10.0
WEB_FETCH_TIMEOUT_S = 25.0  # the API's own per-URL budget is set 5 s lower
WEB_RESULTS_MAX = 6
WEB_FETCH_MAX_CHARS = 5000  # per page handed to the brain
WEB_CACHE_TTL_S = 10 * 60
MEMORY_USER_TAG = "user_owner"  # §9.8: one Supermemory container per user
MEMORY_TABLE = "zoya-memory"  # DynamoDB pk (S) + sk (S): "memory#<user>" / "order#<user>"
MEMORY_LOCAL_FILE = Path.home() / ".zoya" / "memory.json"  # fallback copy, never secrets
MEMORY_TIMEOUT_S = 6.0
MEMORY_SEARCH_LIMIT = 5
ALERTS_TOPIC_ARN = "arn:aws:sns:ap-south-1:567487920371:zoya-alerts"  # trusted contact (Flow 10)
PLACES_MAX_RESULTS = 3
LOGIN_SITES = (
    "https://www.amazon.in/",
    "https://www.youtube.com/",
    "https://open.spotify.com/",
    "https://mail.google.com/",
)
# Done-when #5 test run only (coordinator): `python -m zoya.main --order-limit 300` sets this env
# var; above that payable total Zoya never asks to confirm. Unset = no limit.
ORDER_LIMIT_ENV = "ZOYA_ORDER_LIMIT_RUPEES"

# --- Echo cancellation for laptop speakers ------------------------------------------------------

# D62, zoya/aec.py: WebRTC AEC3 with Zoya's playback + a tap of other apps as
# the reference, so "Hey Zoya" / "Zoya, stop" work over music and her own voice on laptop speakers.
AEC_ENABLED = True  # barge-in detector only, never in front of Whisper (D62); False = pre-D62 loop
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
ONSET_MIN_KEPT = 0.4  # cancelled/raw level: leftover echo ~0.1, the user over Zoya ~0.8 (D62)
OTHER_AUDIO_MIN_RMS = 0.003  # tap reference above this = another app is playing: duck it too
BARGE_IN_SPEECH_GAIN = 10 ** (-20 / 20)  # Zoya keeps talking, 20 dB quieter
BARGE_IN_HOLD_S = 2.5  # restore this long after the user's last voiced block, if no stop/wake


def load_env() -> None:
    """Load .env from the repo root without overriding real environment variables."""
    load_dotenv(REPO_ROOT / ".env", override=False)


def aws_region() -> str:
    return os.environ.get("AWS_REGION") or DEFAULT_AWS_REGION


# --- Phase 5: computer use (§9.4, §9.6, D23) ---------------------------------------------------

SCREENSHOT_MAX_WIDTH = 1280  # ~1280×800 ≈ 1.3k image tokens; captured at point size or smaller
SCREEN_PIXEL_DELTA = 24  # a pixel "changed" when a colour channel moved more than this
SCREEN_CHANGED_FRACTION = 0.02  # >2% of pixels near the target changed → the action did something
CHANGE_BOX_PX = 60  # half-size of the region compared around a click point
ACTION_SETTLE_S = 0.6  # wait before the verify screenshot after a click, key or typing
KEEP_SCREENSHOTS = 2  # older screenshots leave the computer agent's context (§9.3)
MAX_FAILED_ATTEMPTS = 3  # consecutive failed actions → give up honestly (Done-when #4)
CURSOR_MOVED_BY_USER_PT = 8.0  # the pointer moved this far since Zoya's last action → user wins
AX_MESSAGING_TIMEOUT_S = 1.0  # per AX call into an app (AXUIElementSetMessagingTimeout)
AX_READ_MAX_ITEMS = 250  # elements listed by ax_read
AX_READ_TOKEN_BUDGET = 2000
AX_CHARS_PER_TOKEN = 3
AX_WINDOWS_WAIT_S = 2.0
AX_WINDOWS_POLL_S = 0.1
AX_TREE_SETTLE_S = 3.0
OCR_CROP_HALF_WIDTH_PT = 240  # OCR backstop crop around a native target: 480×160 pt
OCR_CROP_HALF_HEIGHT_PT = 80
AX_MAX_ANCESTORS = 12  # Guard 2 walks this far up for the pressable control; cut short → asks
AX_INNER_LABEL_NODES = 24  # descendants searched for an unnamed row's own text
AX_INNER_LABEL_MAX = 2
AX_WALK_DEADLINE_S = 2.0  # whole-tree walk bound
AX_NEARBY_MAX_CHARS = 2000  # sibling text used to spot a price next to a button
TYPE_CHUNK_CHARS = 16  # UTF-16 units per unicode keyboard event
SHORTCUTS_TIMEOUT_S = 20.0  # `shortcuts run` bound
TEXTRACT_TIMEOUT_S = 15.0  # AnalyzeDocument on one page
DOCUMENT_MAX_PAGES = 5  # pages read aloud per document (sync Textract: 1 page per call)
DOCUMENT_RENDER_DPI = 150  # Textract needs ≥ 15 px text height; 8 pt at 150 DPI qualifies
DOCUMENT_TEXT_MAX_CHARS = 6000
COMPUTER_FLOWS_FILE = LOG_DIR / "computer_flows.json"  # intent + app → steps that worked (harness)
COMPUTER_FLOW_TTL_S = 7 * 24 * 3600  # same lifetime as Phase 4's learned picks

# --- Phase 6: multitasking, documents, reminders (§9.13, STACK §8–9) ---------------------------

MAX_TASKS = 3  # D10: a 4th → "queue it or stop one?"
ANNOUNCE_POLL_S = 0.05  # how often a waiting announcement / confirmation checks for its turn
SAME_SPEAKER_WINDOW_S = 8.0  # a task speaking again within this skips repeating its name
GUI_PAUSE_MAX_S = 120.0  # a GUI task paused for a user command resumes after this at the latest
RESOURCE_WAIT_MAX_S = 300.0  # a second browser task waits this long for the page
CONFIRM_TURN_WAIT_S = 120.0  # a confirmation waits this long for another task's / the user's turn
USER_QUIET_S = 0.8  # the user counts as talking until this long after their last voiced block
DOCUMENTS_DIR = Path.home() / "Documents" / "Zoya"  # document_agent output (STACK §9)
DOCUMENT_READ_ROOTS = tuple(Path.home() / name for name in ("Documents", "Downloads", "Desktop"))
OFFICE_MAX_PARTS = 40  # slides or sections per file
OFFICE_MAX_ROWS = 500
OFFICE_TEXT_MAX_CHARS = 4000  # one read-back handed to the model
OPEN_APP_TIMEOUT_S = 10.0  # `open -b` bound
# Sharing ("send it to my sister"): private S3 object + pre-signed GET link, emailed by SNS.
# Private, public access blocked, objects expire after 1 day (owner-created at the end visit).
SHARE_BUCKET = "zoya-shared-567487920371-ap-south-1"
SHARE_PREFIX = ""
SHARE_LINK_TTL_S = 3600
SHARE_TOPIC_ARN = "arn:aws:sns:ap-south-1:567487920371:zoya-shares"  # one filtered sub per contact
SHARE_CONTACTS: tuple[str, ...] = ("sister",)  # confirmed zoya-shares subscriptions
SHARE_TEST_ENV = "ZOYA_SHARE_TEST_TO_OWNER"  # =1: links go to the owner's zoya-alerts email
S3_UPLOAD_TIMEOUT_S = 20.0
# Reminders (STACK §8): a local timer speaks; EventBridge Scheduler emails via SNS.
REMINDER_SCHEDULE_GROUP = "zoya-reminders"
REMINDER_ROLE_ARN = "arn:aws:iam::567487920371:role/zoya-scheduler-sns"  # D67, owner-created
REMINDER_TIMEZONE = "Asia/Kolkata"
REMINDER_MAX_DAYS = 30
REMINDER_MAX_PER_TASK = 5  # new reminders one command may set (a hijacked model can't fan out)
REMINDER_MAX_ACTIVE = 20  # spoken reminders waiting at once

# --- Phase B (v2): Jev decisions (D74, D81, D82) -----------------------------------------------

# Phase A measured Jev at ~550–600 ms p50 and 660–1050 ms p95 from this Mac, with one 6.5 s
# outlier. The timeout cuts the tail before it reaches the voice loop; the deadline bounds the
# whole call including backoff, so at most one retry fits on the voice path.
JEV_TIMEOUT_S = 1.5
JEV_DEADLINE_S = 3.0
JEV_BACKOFF_S = 0.25
JEV_RETRY_STATUS = (408, 429, 500, 502, 503, 504)

# --- Phase B (v2): scoped brain reasoning (D80a) -----------------------------------------------

# The brain runs on the OpenAI Responses API, which accepts function tools and a reasoning effort
# in the same request (D43's Chat Completions restriction does not apply there). Reasoning bills
# as output tokens the user pays (D78), so only the first model call of a task — the plan — gets
# it; every later cycle in the same task drops back to no reasoning.
BRAIN_PLANNING_REASONING_EFFORT = "high"
BRAIN_STEP_REASONING_EFFORT = "none"

# Rule-miss routing (Phase B item 3). Measured on 30 rule-miss commands on this Mac: Jev was
# right 28 times at confidence 0.54–1.00 and wrong twice at 0.38 and 0.64. 0.70 sits in the gap
# — it rejects both wrong answers and the two least certain right ones, which ROUTER_MODEL then
# takes. Every decision acted on in that run was correct.
JEV_ROUTE_CONFIDENCE = 0.70

# Jev widening "stop" (Phase B item 4). Measured on this Mac over 11 stop paraphrases the regex
# misses and 8 commands that only sound like one: stops answered 0.87–0.97, non-stops 0.03–0.53.
# 0.70 sits in that gap with 0.17 either side. The regex still runs first and offline, and Jev
# can never veto a stop it caught.
JEV_STOP_NOUL = 0.70

# Speculation (Phase B item 2). A prepared route older than the TTL is stale — the app or the
# page it was decided against may have moved on. The wait is what end-of-speech spends on a Jev
# call that started during the utterance but has not landed yet; beyond it, routing normally is
# faster than waiting.
SPECULATION_EVERY_S = 0.3
SPECULATION_TTL_S = 10.0
SPECULATION_WAIT_S = 0.25
# The gateway 429s after roughly 28 sustained calls (Phase A). At the cadence above, a 15 s
# utterance could start 50 preparations; a command worth speculating on is settled long before
# the eighth.
SPECULATION_MAX_PER_UTTERANCE = 8

# --- Phase C (v2): the Jev step loop (D81, D82) -------------------------------------------------

JEV_STEP_CONFIDENCE = 0.70
JEV_STEP_NOUL = 0.70
COMPUTER_MAX_JEV_STEPS = 12
COMPUTER_TRANSIENT_RETRIES = 2

# --- Phase C (v2): Chrome over CDP, agent-browser refs (D83, D84) ------------------------------

# D83: Zoya launches Chrome itself so it owns the switches, then agent-browser and Playwright both
# attach over CDP. agent-browser's own launch hard-codes --disable-component-update (Widevine dies)
# and --use-mock-keychain (the owner's saved cookies stay hidden), and `--args` only appends, so the
# browser cannot be agent-browser's to launch (Phase A §3.1). Chrome 136+ also refuses
# --remote-debugging-port on the default profile dir, so BROWSER_PROFILE_DIR stays dedicated.
# https://developer.chrome.com/blog/remote-debugging-port
CHROME_BINARY = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CDP_HOST = "127.0.0.1"
CDP_READY_TIMEOUT_S = 20.0  # bound on waiting for /json/version after launching Chrome
CDP_POLL_S = 0.1
CDP_PROBE_TIMEOUT_S = 1.0  # per /json/version probe
CHROME_SHUTDOWN_TIMEOUT_S = 5.0  # SIGTERM to Zoya's Chrome child, then SIGKILL

# agent-browser 0.38.1. `--cdp <port|url>` and `--session <name>` are global flags that come before
# the command: `agent-browser --session zoya --cdp 9222 snapshot -i` (README "CDP Mode").
AGENT_BROWSER_BIN = "agent-browser"
AGENT_BROWSER_SESSION = "zoya"
AGENT_BROWSER_TIMEOUT_S = 20.0  # bound on one agent-browser subprocess

AX_ACTION_SETTLE_S = 0.3
