"""Login / CAPTCHA handoff (Flow 10, §12.1): Zoya never types passwords or OTPs.

`handoff_to_user` plays `blocked` then `attention` (mention.wav), tells the user what to do, emails
the trusted contact through SNS topic `zoya-alerts`, and remembers the task. The user signs in, then
says "done": the router resumes the task (`resume_command`) only while a handoff is pending. "done"
is never a confirmation: the voice loop hands replies to the safety gate first, and the gate only
mints a token for a clear "confirm" (tests/test_router_rules.py, tests/test_safety.py).

The email is a fixed sentence plus the page's host read from the browser, never page or model text
(§12.2). SNS Publish: https://docs.aws.amazon.com/sns/latest/api/API_Publish.html
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

from strands import tool

from zoya import aws, events, speech
from zoya.config import ALERTS_TOPIC_ARN

log = logging.getLogger(__name__)

HANDOFF_TTL_S = 15 * 60  # a sign-in left longer than this is forgotten: "done" is then just a word
REASONS = {"sign_in": "asking you to sign in", "captcha": "asking to check you're human"}

_lock = threading.Lock()
_pending: dict[str, object] = {}


def _current_host() -> str:
    from zoya.tools import browser

    try:
        return browser.on_page(lambda page: urlparse(page.url).netloc) or "a website"
    except Exception:  # noqa: BLE001 — the host only makes the message nicer
        return "a website"


def _alert(host: str, reason: str) -> None:
    try:
        sns = aws.client("sns")
        if sns is None:
            return
        sns.publish(
            TopicArn=ALERTS_TOPIC_ARN,
            Subject="Zoya needs help",
            Message=f"Zoya paused a task: {host} is {REASONS[reason]}. Nothing was bought or sent.",
        )
    except Exception as error:  # noqa: BLE001 — the user already heard it; the email is extra
        log.warning("SNS alert failed (%s)", aws._reason(error))


def pending_handoff() -> str | None:
    """The command waiting for the user's "done", if one is pending and fresh."""
    with _lock:
        if not _pending or time.monotonic() - float(_pending["at"]) > HANDOFF_TTL_S:
            _pending.clear()
            return None
        return str(_pending["command"])


def resume_command() -> str | None:
    """Consume the pending handoff: the text the brain gets instead of "done"."""
    command = pending_handoff()
    with _lock:
        _pending.clear()
    if command is None:
        return None
    return f"I've finished signing in. Continue the task: {command}"


@tool
def handoff_to_user(reason: str = "sign_in") -> str:
    """Hand the browser to the user for a sign-in, OTP or CAPTCHA page. Zoya never types those.

    Call it when a page asks for a password, OTP or CAPTCHA, then stop and wait: the task resumes
    when the user says "done".

    Args:
        reason: sign_in | captcha.
    """
    from zoya.orchestrator import current_command

    reason = reason if reason in REASONS else "sign_in"
    host = _current_host()
    with _lock:
        _pending.update(command=current_command(), at=time.monotonic())
    events.emit(events.EarconEvent("blocked"))
    events.emit(events.EarconEvent("attention"))
    speech.narrate(
        f"{host} is {REASONS[reason]}. I don't type passwords or codes. The browser is in front; "
        "say done when you've finished."
    )
    threading.Thread(target=_alert, args=(host, reason), daemon=True).start()
    return "The user was told and the trusted contact emailed. Stop now and wait for them."


TOOLS = [handoff_to_user]
