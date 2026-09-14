"""Constants that never change per-request (docs/phases/phase-0-foundations.md).

Secrets and account-specific values live in .env; anything else lives here.
"""

# Spending limits (STACK §7, phase-0 brief "Set spending limits").
OPENAI_MONTHLY_BUDGET_USD = 15.0
PER_TASK_COST_CAP_USD = 0.50

# Fireworks is OpenAI-compatible; verified against
# https://docs.fireworks.ai/api-reference/post-chatcompletions (2026-09-14).
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
