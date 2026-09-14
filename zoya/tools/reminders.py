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
    REMINDER_MAX_DAYS,
    REMINDER_ROLE_ARN,
    REMINDER_SCHEDULE_GROUP,
    REMINDER_TIMEZONE,
)
from zoya.tools import ToolError

log = logging.getLogger(__name__)
CLOCK = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)
HOURS_PER_HALF_DAY = 12
MAX_TEXT_CHARS = 200


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


def _schedule_email(when: datetime, text: str) -> bool:
    scheduler = aws.client("scheduler")
    if scheduler is None:
        return False
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
        return True
    except Exception as error:  # noqa: BLE001 — the spoken reminder is still set
        log.warning("reminder email schedule failed (%s)", aws._reason(error))
        return False


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
    timer = threading.Timer((when - now).total_seconds(), _speak, args=(clean,))
    timer.daemon = True
    timer.start()
    emailed = _schedule_email(when, clean)
    spoken_time = when.strftime("%-I:%M %p")
    email = "and email you" if emailed else "but I couldn't set the email copy"
    return f"Okay, I'll remind you to {clean} at {spoken_time}, {email}."


TOOLS = [set_reminder]
