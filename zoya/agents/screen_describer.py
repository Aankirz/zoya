"""screen_describer (§6 Flow 5, §9.5): "What's on my screen?" for a blind user.

A tool-less Strands Agent on VISION_MODEL (Phase 0 benchmark; D36 store=False via models.py). One
screenshot of the display under the frontmost window, Zoya's windows excluded; the app name comes
from the system, not the pixels. A fresh agent per call with a byte-identical system prompt, so
OpenAI's prefix cache applies. The screenshot stays in memory only.

Strands multimodal input: https://strandsagents.com/docs/user-guide/concepts/agents/prompts/
(ContentBlock list with {"image": {"format", "source": {"bytes"}}}; strands/models/openai.py
format_request_message_content turns it into an image_url data URI).
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent, tool

from zoya import screen
from zoya.prompts import SCREEN_DESCRIBER_PROMPT
from zoya.tools.computer import log_stage

MS_PER_S = 1000


def describe_image(
    image: bytes, app: str, question: str = "", image_format: str = "jpeg"
) -> tuple[str, dict[str, Any]]:
    """(spoken description, usage) for one screenshot."""
    from zoya.models import get_model

    agent = Agent(
        model=get_model("vision"),
        system_prompt=SCREEN_DESCRIBER_PROMPT,
        callback_handler=None,
        trace_attributes={"zoya.component": "screen_describer"},
    )
    ask = question.strip() or "What's on my screen?"
    result = agent(
        [
            {"text": f"Frontmost app: {app or 'unknown'}.\nUser: {ask}"},
            {"image": {"format": image_format, "source": {"bytes": image}}},
        ]
    )
    return str(result).strip(), agent.event_loop_metrics.accumulated_usage


@tool
def describe_screen(question: str = "") -> str:
    """Look at the screen and describe it for the user: the app, any dialog or error first, then
    the main content with exact amounts and names. Say the description to the user as it is.

    Args:
        question: The user's question about the screen, if any, e.g. "what's the total?".
    """
    started = time.monotonic()
    shot = screen.capture_display()
    captured = time.monotonic()
    text, usage = describe_image(shot.jpeg, shot.app, question)
    log_stage(
        "describe_screen",
        capture_ms=round((captured - started) * MS_PER_S),
        vision_ms=round((time.monotonic() - captured) * MS_PER_S),
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        cached_tokens=usage.get("cacheReadInputTokens", 0),
        pixel_scale=shot.pixel_scale,
    )
    return text


TOOLS = [describe_screen]
