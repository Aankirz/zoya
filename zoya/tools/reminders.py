"""Reminders (STACK §8, Phase 6 Done-when #5c): "remind me in 2 minutes to drink water".

Two copies, so a reminder isn't lost if one path fails:
- **Spoken:** a local timer inside Zoya. When it fires it goes through the Task Manager's
  announcement queue ("Reminder: drink water"), so it never talks over the user or over a
  confirmation. ponytail: in memory only; reminders set before a restart are not spoken (the
  email still arrives). A persisted schedule is the upgrade.
- **Email:** a one-time EventBridge Scheduler schedule, `at(yyyy-mm-ddThh:mm:ss)` in
  REMINDER_TIMEZONE, whose templated SNS Publish target sends to the owner's zoya-alerts topic,
  then deletes itself (ActionAfterCompletion=DELETE). Scheduler fires within the minute.
  Docs: https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html (one-time),
  https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-templated.html (SNS),
  https://docs.aws.amazon.com/scheduler/latest/APIReference/API_CreateSchedule.html
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from strands import tool

from zoya import aws, events, tasks
from zoya.config import (
    ALERTS_TOPIC_ARN,
    REMINDER_MAX_ACTIVE,
    REMINDER_MAX_DAYS,
    REMINDER_MAX_PER_TASK,
    REMINDER_ROLE_ARN,
    REMINDER_SCHEDULE_GROUP,
    REMINDER_TIMEZONE,
)
from zoya.tools import ToolError

log = logging.getLogger(__name__)
CLOCK = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)
HOURS_PER_HALF_DAY = 12
MAX_TEXT_CHARS = 200
TOO_MANY_FOR_TASK = f"I can set at most {REMINDER_MAX_PER_TASK} reminders at a time."
TOO_MANY_ACTIVE = f"You already have {REMINDER_MAX_ACTIVE} reminders waiting."
_timers: list[threading.Timer] = []
_per_task: dict[str, int] = {}
_lock = threading.Lock()


def reminder_time(now: datetime, in_minutes: float, at_time: str) -> datetime:
    """Parser (tested): minutes from now, or the next "21:00" / "9 pm" / "9:30am" after now."""
    if in_minutes and at_time.strip():
        raise ToolError("Give either minutes from now or a clock time, not both.")
    if in_minutes:
        if in_minutes <= 0:
            raise ToolError("The reminder has to be in the future.")
        when = now + timedelta(minutes=in_minutes)
    else:
        match = CLOCK.match(at_time)
        if not match:
            raise ToolError("Tell me when, like in 10 minutes or at 9 pm.")
        hour, minute = int(match[1]), int(match[2] or 0)
        if match[3]:
            if not 1 <= hour <= HOURS_PER_HALF_DAY:
                raise ToolError("That time doesn't exist.")
            hour = hour % HOURS_PER_HALF_DAY + (
                HOURS_PER_HALF_DAY if match[3].lower() == "pm" else 0
            )
        if hour > 23 or minute > 59:
            raise ToolError("That time doesn't exist.")
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
    if when - now > timedelta(days=REMINDER_MAX_DAYS):
        raise ToolError(f"I can set reminders up to {REMINDER_MAX_DAYS} days ahead.")
    return when


def _speak(text: str) -> None:
    events.emit(events.EarconEvent("attention"))
    tasks.announce(text, tasks.Task(f"reminder-{uuid.uuid4().hex[:6]}", "reminder", text))


EMAIL_SET = "and email you"
EMAIL_OFF = "but email reminders are off because AWS is off"
EMAIL_NOT_SET_UP = "but email reminders aren't set up yet, so only I will say it"
EMAIL_FAILED = "but I couldn't set the email copy"


def _schedule_email(when: datetime, text: str) -> str:
    """Create the one-time email schedule; returns the spoken clause for how that went."""
    scheduler = aws.client("scheduler")
    if scheduler is None:
        return EMAIL_OFF
    try:
        scheduler.create_schedule(
            Name=f"zoya-reminder-{uuid.uuid4().hex[:16]}",
            GroupName=REMINDER_SCHEDULE_GROUP,
            ScheduleExpression=f"at({when.strftime('%Y-%m-%dT%H:%M:%S')})",
            ScheduleExpressionTimezone=REMINDER_TIMEZONE,
            FlexibleTimeWindow={"Mode": "OFF"},
            ActionAfterCompletion="DELETE",
            Target={
                "Arn": ALERTS_TOPIC_ARN,
                "RoleArn": REMINDER_ROLE_ARN,
                "Input": f"Reminder from Zoya: {text}",
            },
        )
        return EMAIL_SET
    except Exception as error:  # noqa: BLE001 — the spoken reminder is still set
        log.warning("reminder email schedule failed (%s)", aws._reason(error))
        code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
        # No schedule group / role yet (created by the owner, D67), or no permission for them.
        missing = code in {
            "ResourceNotFoundException",
            "AccessDeniedException",
            "ValidationException",
        }
        return EMAIL_NOT_SET_UP if missing else EMAIL_FAILED


@tool
def set_reminder(text: str, in_minutes: float = 0, at_time: str = "") -> str:
    """Remind the user later: Zoya says it out loud and emails it. Give in_minutes OR at_time.

    Args:
        text: What to remind about, e.g. "drink water".
        in_minutes: Minutes from now, e.g. 2.
        at_time: A clock time today or tomorrow, e.g. "21:00" or "9 pm".
    """
    clean = " ".join(text.split())[:MAX_TEXT_CHARS]
    if not clean:
        raise ToolError("What should I remind you about?")
    now = datetime.now(ZoneInfo(REMINDER_TIMEZONE))
    when = reminder_time(now, in_minutes, at_time)
    _start_timer((when - now).total_seconds(), clean)
    email = _schedule_email(when, clean)
    return f"Okay, I'll remind you to {clean} at {when.strftime('%-I:%M %p')}, {email}."


def _start_timer(delay_s: float, text: str) -> None:
    """Named caps (§12.1 bounded autonomy): per command and in total, checked before anything."""
    from zoya import safety

    key = safety.current_task_id()
    with _lock:
        _timers[:] = [timer for timer in _timers if timer.is_alive()]
        if _per_task.get(key, 0) >= REMINDER_MAX_PER_TASK:
            raise ToolError(TOO_MANY_FOR_TASK)
        if len(_timers) >= REMINDER_MAX_ACTIVE:
            raise ToolError(TOO_MANY_ACTIVE)
        timer = threading.Timer(delay_s, _speak, args=(text,))
        timer.daemon = True
        timer.start()
        _timers.append(timer)
        _per_task[key] = _per_task.get(key, 0) + 1


TOOLS = [set_reminder]
