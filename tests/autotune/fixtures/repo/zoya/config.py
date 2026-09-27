"""A synthetic zoya/config.py for the autotune surface tests."""

MODEL_PRICES = {
    "model-a": (0.20, 1.20),
}

# Bounded autonomy.
MAX_TOOL_CALLS_PER_TASK = 40

MAX_FAILED_ATTEMPTS = 3  # consecutive failed actions, then give up

BRAIN_PLANNING_REASONING_EFFORT = "high"
BRAIN_STEP_REASONING_EFFORT = "none"

JEV_STEP_CONFIDENCE = 0.70
COMPUTER_MAX_JEV_STEPS = 12
WEB_RENDER_WAIT_S = 4.0
WEB_MAX_STEPS = 25
