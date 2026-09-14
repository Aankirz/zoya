"""Provider adapter for Strands models (docs/STACK.md §3, D34, D36).

One function picks the model for MODEL_PROVIDER so agent code never touches
provider details. Model IDs come from .env, chosen by the Phase 0 benchmark.

D36 (mandatory): every OpenAI request is sent with store=False — Zoya's
requests carry screenshots, voice commands and personal data. Verified
against the installed SDK: strands/models/openai.py spreads `params` (which
we set to {"store": False}) straight into the Chat Completions request body.
"""

from __future__ import annotations

import os

from strands.models import BedrockModel, Model
from strands.models.openai import OpenAIModel

from zoya.config import FIREWORKS_BASE_URL

Role = str  # "brain" | "vision" | "router"

_ROLE_ENV = {
    "brain": "BRAIN_MODEL",
    "vision": "VISION_MODEL",
    "router": "ROUTER_MODEL",
}


def _model_id(role: Role) -> str:
    env_var = _ROLE_ENV[role]
    model_id = os.environ.get(env_var, "")
    if not model_id:
        raise RuntimeError(f"{env_var} is not set in .env — run the Phase 0 benchmark first")
    return model_id


def get_model(role: Role = "brain", provider: str | None = None) -> Model:
    """Return the Strands model for `role` on `provider` (default: MODEL_PROVIDER).

    Args:
        role: "brain" (planning/tools), "vision" (screen understanding), or "router".
        provider: "openai" | "fireworks" | "bedrock". Defaults to the MODEL_PROVIDER env var.
    """
    provider = provider or os.environ.get("MODEL_PROVIDER", "openai")
    model_id = _model_id(role)

    if provider == "openai":
        return OpenAIModel(
            client_args={"api_key": os.environ["OPENAI_API_KEY"]},
            model_id=model_id,
            params={"store": False},  # D36 — never relax this.
        )

    if provider == "fireworks":
        return OpenAIModel(
            client_args={
                "api_key": os.environ["FIREWORKS_API_KEY"],
                "base_url": FIREWORKS_BASE_URL,
            },
            model_id=model_id,
        )

    if provider == "bedrock":
        return BedrockModel(
            model_id=model_id, region_name=os.environ.get("AWS_REGION", "ap-south-1")
        )

    raise ValueError(
        f"Unknown MODEL_PROVIDER: {provider!r} (expected openai | fireworks | bedrock)"
    )
