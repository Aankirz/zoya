"""Task Manager (§9.13, D10): up to 3 voice tasks at once, each with its own name, step and stop.

Strands does the per-task work. Every task runs its own orchestrator `Agent` (AUDIT B6) with its
own `cancel_signal` (strands 1.55.1 agent/agent.py `Agent.__call__`, `_link_cancel_signal`), and the
`StepTracker` hook (hooks/events.py `BeforeToolCallEvent`) keeps the spoken step and the resource
class. Sub-agents inherit the stop: `_AgentAsTool.stream` forwards the parent's cancel signal
(agent/_agent_as_tool.py). Docs: https://strandsagents.com/docs/user-guide/concepts/agents/hooks/ ,
https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/

Custom, because Strands has no equivalent: the registry and the 3-task limit, spoken task names,
the announcement queue that waits for the user to stop talking, and GUI pause/resume. Swarm/Graph
don't fit: these are independent user requests, not nodes of one workflow sharing a result.

The current task travels in a ContextVar. Strands copies the context into its event-loop thread
(strands/_async.py `run_async` → `contextvars.copy_context`) and into sync tools (tools/decorator.py
`asyncio.to_thread`), so safety.py binds a confirmation to the task that asked without passing ids
through every tool.
"""

from __future__ import annotations

import contextvars
import difflib
import logging
import queue
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from zoya import events
from zoya.config import (
    ANNOUNCE_POLL_S,
    GUI_PAUSE_MAX_S,
    MAX_TASKS,
    RESOURCE_WAIT_MAX_S,
    SAME_SPEAKER_WINDOW_S,
)

log = logging.getLogger(__name__)

Resource = Literal["background", "browser", "gui"]
FULL_MESSAGE = "I'm already doing three things. Want me to queue this or stop one?"
QUEUED_MESSAGE = "Okay, I'll start it as soon as one finishes."
IDLE_MESSAGE = "Nothing is running."
NAME_MATCH_RATIO = 0.6
COUNT_WORDS = {1: "One thing", 2: "Two things", 3: "Three things"}
ALL_WORDS = {"all", "everything", "all tasks", "every task", "sab", "sab kuch"}
FILLER = re.compile(r"\b(?:hey|hi|ok|okay|the|my|a|an|task|please|zoya)\b|[^\w\s]", re.I)

# Spoken names: the first rule that matches the command. Otherwise its first three words.
NAME_RULES = [
    (re.compile(r"\b(?:presentation|slides?|deck|ppt|powerpoint|keynote)\b", re.I), "presentation"),
    (re.compile(r"\bgrocer", re.I), "grocery order"),
    (re.compile(r"\b(?:order|buy|cart|checkout)\b", re.I), "order"),
    (re.compile(r"\b(?:excel|spreadsheet|sheet)\b", re.I), "spreadsheet"),
    (re.compile(r"\b(?:word|resume|document|doc|pdf|report)\b", re.I), "document"),
    (re.compile(r"\bremind", re.I), "reminder"),
    (re.compile(r"\b(?:e-?mail|mail|inbox)\b", re.I), "email"),
    (re.compile(r"\bsettings?\b", re.I), "settings change"),
]
NAME_WORDS = 3

# Tool name → resource class. Everything else is background (no screen, no browser page).
GUI_TOOLS = {"computer_task", "click", "type_text", "key", "scroll", "ax_press", "run_shortcut"}
BROWSER_PREFIXES = ("browser_", "amazon_", "youtube_", "spotify_")


@dataclass(eq=False)
class Task:
    id: str
    name: str
    command: str
    resource: Resource = "background"
    status: str = "running"  # running | waiting_confirmation | waiting_browser | paused
    step: str = "starting"
    shared: bool = False  # another task ran alongside: every announcement carries the name
    spent_usd: float = 0.0  # all agents of this task together (orchestrator.TaskLimits)
    cancel: threading.Event = field(default_factory=threading.Event)
    paused_by: set[str] = field(default_factory=set)  # foreground task ids holding a GUI pause

    def spoken_name(self) -> str:
        return self.name[:1].upper() + self.name[1:]


_current: contextvars.ContextVar[Task | None] = contextvars.ContextVar("zoya_task", default=None)
_changed = threading.Condition()  # guards everything below; notified on any task change
_tasks: dict[str, Task] = {}
_waiting: deque[str] = deque()  # commands queued for a free slot
_offer = ""  # the 4th command, until the user says "queue it" or stops one
_last_active = ""  # task id that last spoke or asked
_runner: Callable[[str], None] | None = None  # starts a command as a task (set by orchestrator)
_announcements: queue.Queue[tuple[Task, str]] = queue.Queue()
_announcer: threading.Thread | None = None
_last_spoken: tuple[str, float] = ("", 0.0)

# The voice loop sets this: True while the user is talking. Announcements never talk over them.
user_speaking: Callable[[], bool] = lambda: False  # noqa: E731


def current() -> Task | None:
    return _current.get()


def running() -> list[Task]:
    with _changed:
        return list(_tasks.values())


# --- Lifecycle ----------------------------------------------------------------------------------


def name_for(command: str) -> str:
    for pattern, name in NAME_RULES:
        if pattern.search(command):
            return name
    return " ".join(FILLER.sub(" ", command).split()[:NAME_WORDS]).lower() or "task"


def _unique(name: str) -> str:
    taken = {task.name for task in _tasks.values()}
    number = 2
    candidate = name
    while candidate in taken:
        candidate, number = f"{name} {number}", number + 1
    return candidate


def spawn(command: str, run: Callable[[Task], None]) -> Task | None:
    """Start `command` as a task on its own thread. None when three are running: the command is
    kept as the offer until the user says "queue it" or stops one (§9.13 limits)."""
    global _offer
    with _changed:
        if len(_tasks) >= MAX_TASKS:
            _offer = command
            return None
        task = Task(uuid.uuid4().hex[:12], _unique(name_for(command)), command)
        if _tasks:
            task.shared = True
            for other in _tasks.values():
                other.shared = True
        _tasks[task.id] = task
        _pause_gui_tasks(task)
    threading.Thread(
        target=_run, args=(task, run), name=f"zoya-task-{task.id}", daemon=True
    ).start()
    return task


def _run(task: Task, run: Callable[[Task], None]) -> None:
    _current.set(task)  # a new thread starts with an empty context
    try:
        run(task)
    except Exception:  # noqa: BLE001 — handle_command already speaks failures; never kill the loop
        log.exception("task %s crashed", task.name)
    finally:
        _finish(task)


def _finish(task: Task) -> None:
    with _changed:
        _tasks.pop(task.id, None)
        for other in _tasks.values():
            other.paused_by.discard(task.id)
        next_command = _waiting.popleft() if _waiting and len(_tasks) < MAX_TASKS else ""
        _changed.notify_all()
    if next_command and _runner is not None:
        _runner(next_command)


def set_runner(runner: Callable[[str], None]) -> None:
    global _runner
    _runner = runner


def answer_offer() -> str:
    """ "Queue it": the 4th command waits for a free slot."""
    global _offer
    with _changed:
        if not _offer:
            return "There's nothing waiting to be queued."
        _waiting.append(_offer)
        _offer = ""
    events.emit(events.EarconEvent("queued"))
    return QUEUED_MESSAGE


def has_offer() -> bool:
    with _changed:
        return bool(_offer)


# --- Voice controls: what's running, status, stop -----------------------------------------------


def _describe(task: Task) -> str:
    step = {
        "waiting_confirmation": "waiting for your confirm",
        "waiting_browser": "waiting for the browser",
        "paused": "paused while you use the Mac",
    }.get(task.status, task.step)
    return f"{task.spoken_name()}: {step}."


def list_tasks() -> str:
    tasks = running()
    if not tasks:
        return IDLE_MESSAGE
    parts = [f"{COUNT_WORDS.get(len(tasks), f'{len(tasks)} things')}."]
    parts += [_describe(task) for task in tasks]
    with _changed:
        if _waiting:
            parts.append(f"Queued: {len(_waiting)}.")
    return " ".join(parts)


def find(query: str) -> list[Task]:
    """Fuzzy match on the spoken name, then on the command ("the order" → "grocery order")."""
    wanted = " ".join(FILLER.sub(" ", query.lower()).split())
    if not wanted:
        return []
    tasks = running()
    exact = [t for t in tasks if t.name == wanted]
    if exact:
        return exact
    by_words = [t for t in tasks if set(wanted.split()) & set(t.name.split())]
    if by_words:
        return by_words
    return [
        t
        for t in tasks
        if difflib.SequenceMatcher(None, wanted, t.name).ratio() >= NAME_MATCH_RATIO
        or wanted in t.command.lower()
    ]


def task_status(query: str = "") -> str:
    if not query.strip():
        return list_tasks()
    matches = find(query)
    if len(matches) == 1:
        return _describe(matches[0])
    return _which(matches) if matches else f"Nothing called {query.strip()} is running."


def _which(matches: list[Task]) -> str:
    return "The " + " or the ".join(task.name for task in matches) + "?"


def stop(query: str) -> str:
    """ "Stop the presentation" stops only that task; "stop everything" stops all. Stopping one
    task never touches another task's confirmation (safety.cancel_pending is task-scoped)."""
    if " ".join(query.lower().split()) in ALL_WORDS:
        with _changed:
            _waiting.clear()
        stopped = [_stop_one(task) for task in running()]
        return "Stopped everything." if stopped else IDLE_MESSAGE
    matches = find(query)
    if len(matches) > 1:
        return _which(matches)
    if not matches:
        return f"Nothing called {query.strip()} is running."
    _queue_offer_after_stop()
    return f"Stopped the {_stop_one(matches[0])}."


def _queue_offer_after_stop() -> None:
    """ "Queue it or stop one?" → "stop the presentation": the waiting command takes the slot."""
    if has_offer():
        answer_offer()


def _stop_one(task: Task) -> str:
    from zoya import safety

    task.cancel.set()
    safety.cancel_pending(task.id)
    events.emit(events.TaskEvent(task.id, "cancelled", task.command, "orchestrator"))
    return task.name


def stop_target() -> Task | None:
    """ "Zoya, stop" with no name: the task whose confirmation is waiting, else the one that last
    spoke or acted, else the newest (§9.13 voice controls)."""
    from zoya import safety

    tasks = {task.id: task for task in running()}
    for task_id in (safety.pending_task_id(), _last_active):
        if task_id in tasks:
            return tasks[task_id]
    return list(tasks.values())[-1] if tasks else None


def stop_last() -> str:
    task = stop_target()
    if task is None:
        return ""
    name = _stop_one(task)
    return f"Stopped the {name}." if task.shared else ""  # alone: the caller says "Okay, stopped."


# --- Steps, resources, spend --------------------------------------------------------------------


def set_step(step: str) -> None:
    task = current()
    if task is not None and step:
        task.step = step


def set_status(status: str, task: Task | None = None) -> None:
    task = task or current()
    if task is None:
        return
    with _changed:
        task.status = status
        _changed.notify_all()


def mark_active(task: Task | None = None) -> None:
    global _last_active
    task = task or current()
    if task is not None:
        _last_active = task.id


def add_spend(usd: float) -> float:
    """Add this agent's new spend to its task; returns the task's total (0 without a task)."""
    task = current()
    if task is None:
        return 0.0
    with _changed:
        task.spent_usd += usd
        return task.spent_usd


def resource_of(tool_name: str) -> Resource:
    if tool_name in GUI_TOOLS:
        return "gui"
    if tool_name.startswith(BROWSER_PREFIXES):
        return "browser"
    return "background"


def _wait(ready: Callable[[], bool], task: Task, limit_s: float) -> bool:
    """Wait (under _changed) until `ready`, the task is stopped, or `limit_s` passes."""
    deadline = time.monotonic() + limit_s
    while not ready():
        left = deadline - time.monotonic()
        if task.cancel.is_set() or left <= 0:
            return False
        _changed.wait(min(left, ANNOUNCE_POLL_S))
    return True


def claim(tool_name: str) -> str:
    """Before a tool runs: record its class. One browser task drives the Zoya Chrome page at a time
    (ponytail: Phase 4 has one shared Playwright page; per-task pages are the upgrade), so a second
    browser task waits. A foreground command that turns out to be background lifts its GUI pause.
    Returns a refusal for the model, or ""."""
    task = current()
    if task is None:
        return ""
    wanted = resource_of(tool_name)
    with _changed:
        if wanted != "gui":
            _lift_pause_by(task)
        if wanted == "browser" and task.resource != "browser":
            free = _wait(lambda: not _others_with(task, "browser"), task, RESOURCE_WAIT_MAX_S)
            if not free:
                return "The browser is busy with another task. Tell the user and stop."
        if wanted != "background":
            task.resource = wanted
    return ""


def _others_with(task: Task, resource: Resource) -> list[Task]:
    return [t for t in _tasks.values() if t is not task and t.resource == resource]


# --- GUI pause / resume (§9.13 "the user always wins the foreground") ---------------------------


def _pause_gui_tasks(new: Task) -> None:
    """Called under _changed when a new command starts: GUI tasks pause at their next step."""
    for task in _tasks.values():
        if task is not new and task.resource == "gui":
            task.paused_by.add(new.id)
            announce("Pausing while I do that.", task)


def _lift_pause_by(foreground: Task) -> None:
    for task in _tasks.values():
        task.paused_by.discard(foreground.id)
    _changed.notify_all()


def gui_checkpoint(lock: threading.Lock) -> bool:
    """Computer agent, before every step. If a user command paused this task: give up the GUI lock,
    wait until the command is done (at most GUI_PAUSE_MAX_S), take the lock back. True = resumed,
    the screen may have changed. Raises TimeoutError if the lock can't be taken back."""
    task = current()
    if task is None or not task.paused_by:
        return False
    lock.release()
    set_status("paused", task)
    try:
        with _changed:
            _wait(lambda: not task.paused_by, task, GUI_PAUSE_MAX_S)
            task.paused_by.clear()
        deadline = time.monotonic() + GUI_PAUSE_MAX_S
        while not lock.acquire(timeout=ANNOUNCE_POLL_S):
            if time.monotonic() > deadline:
                raise TimeoutError("the screen is still in use")
    finally:
        set_status("running", task)
    return True


class StepTracker(HookProvider):
    """Strands hook on every task agent: the step "what's running?" reads, and resource claims."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        name = str(event.tool_use.get("name", ""))
        if name != "narrate":
            set_step(f"using {name.replace('_', ' ')}")
            _overlay_step(name.replace("_", " "), acting=True)
        refusal = claim(name)
        if refusal:
            event.cancel_tool = refusal

    def after_tool(self, _event: AfterToolCallEvent) -> None:
        task = current()
        _overlay_step(task.step if task else "", acting=False)


def _overlay_step(step: str, acting: bool) -> None:
    """Stage overlay (Phase 7): acting while a tool runs, thinking with the step between tools;
    the task's name only when several run."""
    task = current()
    name = task.spoken_name() if task and len(running()) > 1 else ""
    extra = {"tool": step, "task": name} if acting else {"task": name}
    events.emit(events.OverlayEvent(step, "working", extra))


# --- Announcements: named, queued, never over the user -------------------------------------------


def say(text: str, task: Task | None = None) -> None:
    """What a task says. Alone: straight to speech (streaming stays fast). With other tasks: the
    announcement queue, prefixed with the task's name, after the user stops talking."""
    from zoya import speech

    task = task or current()
    if not text.strip():
        return
    if task is None or not task.shared:
        mark_active(task)
        speech.narrate(text)
        return
    announce(text, task)


def announce(text: str, task: Task) -> None:
    global _announcer
    _announcements.put((task, text))
    if _announcer is None:
        _announcer = threading.Thread(target=_announce_loop, name="zoya-announce", daemon=True)
        _announcer.start()


def my_turn(task_id: str = "") -> bool:
    """The floor is free: the user isn't talking and no other task's confirmation waits."""
    from zoya import safety

    pending = safety.pending_task_id()
    return not user_speaking() and (pending is None or pending == task_id)


def wait_for_turn(task_id: str, stopped: Callable[[], bool], limit_s: float) -> bool:
    deadline = time.monotonic() + limit_s
    while not my_turn(task_id):
        if stopped() or time.monotonic() > deadline:
            return False
        time.sleep(ANNOUNCE_POLL_S)
    return True


def _announce_loop() -> None:
    global _last_spoken
    from zoya import speech

    while True:
        task, text = _announcements.get()
        if task.cancel.is_set():
            continue  # a stopped task says nothing more; the stop already said so
        while not my_turn(
            task.id
        ):  # ponytail: waits as long as the user talks; it blocks no caller
            time.sleep(ANNOUNCE_POLL_S)
        same = (
            _last_spoken[0] == task.id
            and time.monotonic() - _last_spoken[1] < SAME_SPEAKER_WINDOW_S
        )
        speech.narrate(text if same else f"{task.spoken_name()}: {text}")
        _last_spoken = (task.id, time.monotonic())
        mark_active(task)


def _reset_for_tests() -> None:
    global _offer, _last_active, _last_spoken, user_speaking
    with _changed:
        _tasks.clear()
        _waiting.clear()
        _offer, _last_active, _last_spoken = "", "", ("", 0.0)
    user_speaking = lambda: False  # noqa: E731


# --- Task-named confirmation answers (§9.2 answer_confirmation(task, decision)) ------------------

NAME_ARTICLES = re.compile(r"\b(?:the|my|for|on)\b", re.I)


def named_tasks(text: str) -> list[Task]:
    """Running tasks named in `text`, longest names first ("grocery order" before "order")."""
    lowered = f" {' '.join(text.lower().split())} "
    found = []
    for task in sorted(running(), key=lambda t: len(t.name), reverse=True):
        if f" {task.name} " in lowered:
            found.append(task)
            lowered = lowered.replace(f" {task.name} ", " ")
    return found


def answer_for(text: str, pending_id: str | None) -> str | None:
    """A reply to the waiting confirmation, with the pending task's name removed ("confirm the
    grocery order" → "confirm"). None when it names any other task: it is not an answer to this
    confirmation, and must never confirm or cancel it."""
    named = named_tasks(text)
    if any(task.id != pending_id for task in named):
        return None
    reply = f" {' '.join(text.lower().split())} "
    for task in named:
        reply = reply.replace(f" {task.name} ", " ")
    return " ".join(NAME_ARTICLES.sub(" ", reply).split()) if named else text
