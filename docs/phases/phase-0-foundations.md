# Phase 0 — Foundations (0–2h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-0-foundations` · **Depends on:** nothing

**Files this phase owns** (other agents must not edit them during this phase):
- `pyproject.toml`
- `zoya/config.py`
- `scripts/check_models.py`
- `scripts/check_regions.py`
- `.env (local only, never committed)`

**Goal:** every cloud service and macOS permission Zoya needs is proven to work on the demo Mac, before any product code exists.

**Build**
- Repo skeleton (§15.2), `pyproject.toml`, `.env.example`, Black/isort/Ruff configured.
- Enable Bedrock model access: Nova 2 Sonic, Claude Sonnet 5, Claude Haiku 4.5, Nova Micro, Nova 2 Lite, Nova Canvas.
- `scripts/check_models.py`: one tiny call to each model, prints latency per model.
- `scripts/check_regions.py`: round-trip time to candidate Bedrock regions → pick the nearest with all models (§13.5.4).
- AWS Budgets alarms at $25 / $50 / $75.
- Supermemory + Picovoice API keys in `.env`.
- Grant Microphone, Accessibility, Screen Recording to the terminal/Python that will run Zoya.
- Pick the sound pack: run `sounds/audition.sh`, choose `zen` or `soft` (§7.3).

**Not in this phase:** any agent, voice, or UI code.

**Doc sections:** §10, §13.5, §14.3, §15.

**Done when**
1. ☐ `check_models.py` gets a reply from all 6 models.
2. ☐ Region chosen and written into `config.py`, with measured latency noted.
3. ☐ Budget alarms visible in the AWS console.
4. ☐ `screencapture` and a test `pyautogui` click work without permission errors.
5. ☐ Sound pack chosen.

**Judge demo (30 s):** run `check_models.py` → "All six AWS models answer in X ms from region Y."
