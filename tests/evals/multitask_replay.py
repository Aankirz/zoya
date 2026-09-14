"""Phase 6 Done-when #2, #3, #4, #6 (and #5 by voice) through the real voice loop, with no GUI.

Real: VoiceLoop (Silero VAD, Whisper spotter + turbo), router, Task Manager, brain, document_agent
writing real files, the safety gate and its voice channel. Synthetic: the user (macOS `say` fed
block by block, as tests/evals/safety_replay.py does) and the grocery order: a stand-in long
browser-class task (Phase 4's Amazon flow is still being built) that takes steps, then asks the
real `safety.require_confirmation` for "3 grocery items, 412 rupees". Zoya's speech is recorded
with its timing instead of played, so the run is silent and no other session's mic hears it.

Usage: .venv/bin/python -u tests/evals/multitask_replay.py [scenario ...]
Scenarios: together (#2 #4 + confirm), stop_one (#3), fourth (#6). An eval, not a pytest.
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"  # pinned models from the cache only (AUDIT §6)

import json  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))

from safety_replay import Mic, wait_until  # noqa: E402

from zoya import audio, aws, events, orchestrator, safety, speech, tasks, voice  # noqa: E402
from zoya.config import REPO_ROOT, load_env  # noqa: E402

RESULTS = REPO_ROOT / "tests" / "evals" / "results" / "multitask_replay.json"
GROCERY_STEPS = ["searching for milk", "adding milk to the cart", "adding bread to the cart"]
STEP_S = 4.0
WORDS_PER_S = 3.0  # simulated playback speed of recorded speech
TIMEOUT_S = 180.0
QUIET_S = 6.0  # D53: the 10 s loudness median must fall back to room noise between utterances
ORDER = safety.Action("purchase", "Place order", "3 grocery items", "412 rupees")

said: list[dict] = []
grocery_outcome: dict = {}


def record_speech() -> None:
    """Speech is timed, not played: each sentence 'plays' for words / WORDS_PER_S seconds."""

    def speak_now(text: str, generation: int | None = None) -> str:
        generation = speech._generation if generation is None else generation
        started = time.monotonic()
        said.append({"text": text, "at": started})
        deadline = started + len(text.split()) / WORDS_PER_S
        while time.monotonic() < deadline:
            speech._check(generation)
            time.sleep(0.02)
        return "recorded"

    speech.speak_now = speak_now


def stand_in_grocery(command: str, pre: dict | None = None) -> orchestrator.CommandResult:
    """A long browser-class task: steps, then the real confirmation gate, inside its task."""
    task = tasks.current()
    task.resource = "browser"
    safety.begin_task(task.id)
    decision = orchestrator.RouteDecision("orchestrator", text=command)
    try:
        for step in GROCERY_STEPS:
            tasks.set_step(step)
            if task.cancel.wait(STEP_S):
                raise orchestrator.TaskCancelled
        safety.require_confirmation(ORDER)
        grocery_outcome["result"] = "placed"
        tasks.say("Order placed.")
        spoken, ok = "Order placed.", True
    except (safety.ConfirmationDeclined, orchestrator.TaskCancelled) as stopped:
        grocery_outcome["result"] = type(stopped).__name__
        spoken, ok = str(stopped) or orchestrator.STOPPED_MESSAGE, False
    return orchestrator.CommandResult(task.id, decision, spoken, ok, {})


def patch_grocery() -> None:
    real = orchestrator.handle_command

    def handle_command(text: str, pre_timings: dict | None = None):
        if "grocer" in text.lower():
            return stand_in_grocery(text, pre_timings)
        return real(text, pre_timings)

    orchestrator.handle_command = handle_command


def quiet(timeout: float = 60.0) -> None:
    wait_until(lambda: not speech.is_speaking(), timeout)
    time.sleep(QUIET_S)


heard: list[str] = []
HEARD_WAIT_S = 10.0
COMMAND_ATTEMPTS = 3


def command(mic: Mic, text: str) -> None:
    """Say a command like a user would: if it landed on Zoya's own speech (echo protection ignores
    it) and nothing was heard, wait for quiet and say it again."""
    for _ in range(COMMAND_ATTEMPTS):
        before = len(heard)
        quiet()
        mic.say(text)
        if wait_until(lambda count=before: len(heard) > count, HEARD_WAIT_S):
            return
    print(f"never heard: {text!r}")


def spoken_since(start: float) -> list[str]:
    return [f'{s["at"] - start:6.1f}s {s["text"]}' for s in said if s["at"] >= start]


def together(mic: Mic) -> dict:
    """Presentation + grocery order at once; "what's running?"; the confirmation waits for the
    user to stop talking and names the task; "confirm" places only the order."""
    start = time.monotonic()
    grocery_outcome.clear()
    command(mic, "Hey Zoya, make a 6-slide presentation on renewable energy for my class.")
    quiet()
    command(mic, "Hey Zoya, order my usual groceries.")
    quiet()
    command(mic, "Hey Zoya, what's running?")
    quiet()
    status = next((s["text"] for s in said if s["at"] >= start and "things" in s["text"]), None)
    # Talk right when the order is about to ask: the prompt must wait until we're done.
    wait_until(
        lambda: tasks.find("grocery order")
        and tasks.find("grocery order")[0].step == GROCERY_STEPS[-1],
        TIMEOUT_S,
    )
    user_talk_started = time.monotonic()
    mic.say("I am just thinking out loud about what to cook tonight, maybe some dal and rice.")
    user_talk_ended = time.monotonic()
    wait_until(safety.awaiting_reply, TIMEOUT_S)
    prompt = next((s for s in said if "about to place order" in s["text"]), None)
    time.sleep(0.8)
    mic.say("Confirm.")
    wait_until(lambda: grocery_outcome.get("result"), TIMEOUT_S)
    wait_until(lambda: not tasks.running(), TIMEOUT_S)
    quiet()
    return {
        "scenario": "together",
        "status_reply": status,
        "prompt": prompt["text"] if prompt else None,
        "prompt_started_after_user_stopped_s": (
            round(prompt["at"] - user_talk_ended, 2) if prompt else None
        ),
        "user_talked_s": round(user_talk_ended - user_talk_started, 2),
        "user_talk_ended_at_s": round(user_talk_ended - start, 1),
        "grocery": grocery_outcome.get("result"),
        "spoken": spoken_since(start),
        "files": sorted(p.name for p in (Path.home() / "Documents" / "Zoya").glob("*.pptx")),
        "pass": bool(
            status
            and "presentation" in status.lower()
            and "grocery order" in status.lower()
            and prompt
            and prompt["text"].startswith("Grocery order:")
            and prompt["at"] >= user_talk_ended
            and grocery_outcome.get("result") == "placed"
        ),
    }


def stop_one(mic: Mic) -> dict:
    """ "Stop the presentation" stops only that task; the order still reaches its confirmation."""
    start = time.monotonic()
    grocery_outcome.clear()
    cancelled: list[str] = []
    events.subscribe(
        events.TASK, lambda e: cancelled.append(e.task_id) if e.status == "cancelled" else None
    )
    command(mic, "Hey Zoya, make a 6-slide presentation about the history of cricket.")
    quiet()
    command(mic, "Hey Zoya, order my usual groceries.")
    quiet()
    names = {t.id: t.name for t in tasks.running()}
    mic.say("Zoya, stop the presentation.")  # the stop spotter, not a dispatched command
    quiet()
    still = [t.name for t in tasks.running()]
    wait_until(safety.awaiting_reply, TIMEOUT_S)
    time.sleep(0.8)
    mic.say("Cancel.")
    wait_until(lambda: not tasks.running(), TIMEOUT_S)
    quiet()
    stopped_names = [names.get(i) for i in cancelled]
    return {
        "scenario": "stop_one",
        "running_after_stop": still,
        "cancelled": stopped_names,
        "grocery": grocery_outcome.get("result"),
        "spoken": spoken_since(start),
        "pass": stopped_names == ["presentation"]
        and still == ["grocery order"]
        and grocery_outcome.get("result") == "ConfirmationDeclined",
    }


def fourth(mic: Mic) -> dict:
    """A 4th task → "queue it or stop one?"; "queue it" starts it when a slot frees."""
    start = time.monotonic()
    commands = [
        "Hey Zoya, make a 6-slide presentation on the solar system.",
        "Hey Zoya, make an Excel sheet of my monthly expenses with a total.",
        "Hey Zoya, order my usual groceries.",
        "Hey Zoya, make a Word doc with a packing list for a trip to Goa.",
    ]
    for text in commands:
        command(mic, text)
    offered = any(tasks.FULL_MESSAGE in t for t in spoken_since(start))  # "…s <text>"
    command(mic, "Hey Zoya, queue it.")
    quiet()
    queued = any(tasks.QUEUED_MESSAGE in t for t in spoken_since(start))
    wait_until(safety.awaiting_reply, TIMEOUT_S)
    time.sleep(0.8)
    mic.say("Cancel.")
    wait_until(lambda: not tasks.running(), TIMEOUT_S * 2)
    quiet()
    docs = sorted(p.name for p in (Path.home() / "Documents" / "Zoya").glob("*packing*"))
    return {
        "scenario": "fourth",
        "offered": offered,
        "queued": queued,
        "packing_list_made_after_slot_freed": docs,
        "spoken": spoken_since(start),
        "pass": offered and queued and bool(docs),
    }


SCENARIOS = {"together": together, "stop_one": stop_one, "fourth": fourth}


def main() -> int:
    load_env()
    print(f"keys: {aws.load_provider_secrets()}")
    audio.duck = audio.restore = lambda: None  # leave the Mac's volume alone
    audio.engine()
    record_speech()
    patch_grocery()
    loop = voice.VoiceLoop()
    real_dispatch = loop._dispatch
    loop._dispatch = lambda text, *rest: (heard.append(text), real_dispatch(text, *rest))
    mic = Mic(loop)
    time.sleep(4)  # background loudness history
    outcomes = []
    for name in sys.argv[1:] or list(SCENARIOS):
        outcome = SCENARIOS[name](mic)
        print(json.dumps(outcome, ensure_ascii=False, indent=1), flush=True)
        outcomes.append(outcome)
    mic.stop.set()
    RESULTS.write_text(json.dumps(outcomes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if all(o["pass"] for o in outcomes) else 1


if __name__ == "__main__":
    threading.excepthook = lambda args: print(f"thread error: {args.exc_value!r}")
    sys.exit(main())
