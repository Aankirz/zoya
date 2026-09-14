"""Task Manager × safety gate (D37, D61, §9.13): tasks never share or steal a confirmation.

Each test is a way a silent bug lets one task's "confirm" (or "stop") act on another task: a
purchase confirmed by a word meant for the presentation, a stop that cancels the grocery order,
a prompt spoken over the user.
"""

from __future__ import annotations

import contextvars
import threading
import time
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest

from zoya import orchestrator, safety, tasks
from zoya.tools import ToolError

ORDER = safety.Action("purchase", "Place order", "3 grocery items", "412 rupees")
WAIT_S = 2.0


@pytest.fixture(autouse=True)
def gate(monkeypatch):
    safety._reset_for_tests()
    tasks._reset_for_tests()
    record = {"prompts": [], "said": [], "audit": []}
    monkeypatch.setattr(safety, "CONFIRM_REPLY_TIMEOUT_S", 0.5)
    monkeypatch.setattr(safety, "ECHO_TAIL_S", 0.0)
    monkeypatch.setattr(safety, "TURN_POLL_S", 0.01)
    monkeypatch.setattr(tasks, "ANNOUNCE_POLL_S", 0.01)
    monkeypatch.setattr(safety, "_speaking", lambda: False)
    monkeypatch.setattr(safety, "_speak_prompt", lambda p: record["prompts"].append(p) or True)
    monkeypatch.setattr(safety, "_audit", lambda action, decision: record["audit"].append(decision))
    monkeypatch.setattr(safety, "_log_timing", lambda _record: None)
    from zoya import audio, speech

    monkeypatch.setattr(audio, "earcon", lambda _kind: None)
    monkeypatch.setattr(speech, "narrate", record["said"].append)
    yield record
    safety._reset_for_tests()
    tasks._reset_for_tests()


def _task(name: str, shared: bool = True) -> tasks.Task:
    task = tasks.Task(f"id-{name.replace(' ', '-')}", name, f"do the {name}", shared=shared)
    tasks._tasks[task.id] = task
    return task


def _in_task(task: tasks.Task | None, fn, *args):
    """Run fn in `task`'s context on a thread, as Strands runs tools. Returns thread, outcome."""
    outcome: dict = {}

    def run():
        if task is not None:
            tasks._current.set(task)
        try:
            outcome["result"] = fn(*args)
        except Exception as error:  # noqa: BLE001 — the test inspects it
            outcome["result"] = error

    thread = threading.Thread(target=contextvars.Context().run, args=(run,), daemon=True)
    thread.start()
    return thread, outcome


def _confirm(action=ORDER):
    safety.require_confirmation(action)
    return "confirmed"


def _wait(predicate, timeout=WAIT_S):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition never became true"
        time.sleep(0.005)


def _answer(channel, text):
    _wait(safety.awaiting_reply)
    return channel.reply(text, heard_from=time.monotonic())


# --- Tokens are bound to their task -------------------------------------------------------------


def test_a_token_minted_for_one_task_is_useless_to_another():
    grocery, presentation = _task("grocery order"), _task("presentation")
    channel = safety.claim_voice_channel()
    minted: dict = {}

    def mint():
        pending = safety._open(ORDER.summary())
        pending.spoken_hash = safety.summary_hash(ORDER.summary())
        pending.window_opened_at = time.monotonic()
        assert channel.reply("confirm", heard_from=time.monotonic())
        minted["token"] = pending.token_id
        safety._pending = None  # leave the token alive for the other task to try

    thread, _ = _in_task(grocery, mint)
    thread.join(WAIT_S)
    thread, outcome = _in_task(presentation, safety.consume_token, minted["token"], ORDER.summary())
    thread.join(WAIT_S)

    assert outcome["result"] is False


def test_the_same_token_works_for_its_own_task():
    grocery = _task("grocery order")
    channel = safety.claim_voice_channel()
    thread, outcome = _in_task(grocery, _confirm)

    _answer(channel, "confirm")
    thread.join(WAIT_S)

    assert outcome["result"] == "confirmed"


def test_a_decline_in_one_task_does_not_block_another():
    grocery, presentation = _task("grocery order"), _task("presentation")
    channel = safety.claim_voice_channel()
    thread, _ = _in_task(grocery, _confirm)
    _answer(channel, "cancel")
    thread.join(WAIT_S)

    thread, outcome = _in_task(presentation, safety.task_declined)
    thread.join(WAIT_S)

    assert outcome["result"] is False


def test_outside_any_task_with_several_running_nothing_is_asked(gate):
    _task("grocery order"), _task("presentation")
    safety.claim_voice_channel()

    with pytest.raises(ToolError):
        safety.require_confirmation(ORDER)
    assert gate["prompts"] == []


# --- One pending confirmation; the second waits its turn ----------------------------------------


def test_a_second_confirmation_waits_and_never_takes_the_first_ones_confirm(gate):
    grocery, presentation = _task("grocery order"), _task("presentation")
    channel = safety.claim_voice_channel()
    share = safety.Action("send", "email a link to deck.pptx", target="your sister")
    first, first_outcome = _in_task(grocery, _confirm)
    _wait(safety.awaiting_reply)
    second, second_outcome = _in_task(presentation, _confirm, share)
    _wait(lambda: presentation.status == "waiting_confirmation")

    _answer(channel, "confirm")  # heard while the grocery order was the one asking
    first.join(WAIT_S)

    assert first_outcome["result"] == "confirmed"
    _wait(lambda: len(gate["prompts"]) == 2)
    assert gate["prompts"][1].startswith("Presentation: ")
    assert "result" not in second_outcome  # still waiting for its own answer
    _answer(channel, "cancel")
    second.join(WAIT_S)
    assert isinstance(second_outcome["result"], safety.ConfirmationDeclined)


def test_the_prompt_names_the_task_and_waits_until_the_user_stops_talking(gate):
    grocery = _task("grocery order")
    talking = {"on": True}
    tasks.user_speaking = lambda: talking["on"]
    safety.claim_voice_channel()
    thread, _ = _in_task(grocery, _confirm)

    time.sleep(0.1)
    assert gate["prompts"] == []  # never over the user
    talking["on"] = False
    _wait(lambda: gate["prompts"])

    assert gate["prompts"][0].startswith("Grocery order: I'm about to place order")
    safety.cancel_pending(grocery.id)
    thread.join(WAIT_S)


# --- Stop is per task ----------------------------------------------------------------------------


def test_stopping_the_presentation_leaves_the_grocery_confirmation_waiting(gate):
    grocery, presentation = _task("grocery order"), _task("presentation")
    channel = safety.claim_voice_channel()
    thread, outcome = _in_task(grocery, _confirm)
    _wait(safety.awaiting_reply)

    said = tasks.stop("the presentation")

    assert said == "Stopped the presentation."
    assert presentation.cancel.is_set() and not grocery.cancel.is_set()
    assert safety.awaiting_reply() and "result" not in outcome
    _answer(channel, "confirm")
    thread.join(WAIT_S)
    assert outcome["result"] == "confirmed"


def test_stopping_one_task_never_confirms_another(gate):
    grocery, _presentation = _task("grocery order"), _task("presentation")
    safety.claim_voice_channel()
    thread, outcome = _in_task(grocery, _confirm)
    _wait(safety.awaiting_reply)

    tasks.stop("presentation")
    safety.cancel_pending(grocery.id)  # then the user stops the grocery order too
    thread.join(WAIT_S)

    assert isinstance(outcome["result"], safety.ConfirmationDeclined)
    assert "confirmed" not in gate["audit"]


def test_bare_stop_targets_the_task_whose_confirmation_is_waiting():
    grocery, presentation = _task("grocery order"), _task("presentation")
    tasks.mark_active(presentation)  # the presentation spoke last…
    safety.claim_voice_channel()
    thread, _ = _in_task(grocery, _confirm)
    _wait(safety.awaiting_reply)

    assert tasks.stop_target() is grocery  # …but "Zoya, stop" hears the one asking
    safety.cancel_pending(grocery.id)
    thread.join(WAIT_S)


def test_bare_stop_with_a_single_task_stops_it(monkeypatch):
    from zoya import speech

    monkeypatch.setattr(speech, "cancel", lambda: None)
    presentation = _task("presentation", shared=False)

    said = orchestrator.stop_task()

    assert presentation.cancel.is_set() and said == orchestrator.STOPPED_MESSAGE


def test_an_ambiguous_stop_asks_which_task():
    _task("grocery order"), _task("medicine order")

    assert tasks.stop("the order") == "The grocery order or the medicine order?"
    assert not any(task.cancel.is_set() for task in tasks.running())


def test_stop_everything_stops_all_tasks():
    grocery, presentation = _task("grocery order"), _task("presentation")

    tasks.stop("everything")

    assert grocery.cancel.is_set() and presentation.cancel.is_set()


# --- Task-named answers ---------------------------------------------------------------------------


def test_a_reply_naming_another_task_is_not_an_answer():
    grocery, _presentation = _task("grocery order"), _task("presentation")

    assert tasks.answer_for("confirm the presentation", grocery.id) is None
    assert tasks.answer_for("cancel the presentation", grocery.id) is None


def test_a_reply_naming_the_waiting_task_is_its_answer():
    grocery, _presentation = _task("grocery order"), _task("presentation")

    assert safety.classify_reply(tasks.answer_for("confirm the grocery order", grocery.id)) == (
        "confirm"
    )
    assert tasks.answer_for("confirm", grocery.id) == "confirm"


# --- Limits: 3 tasks, one money cap per task ------------------------------------------------------


def test_a_fourth_task_is_offered_the_queue_and_starts_when_a_slot_frees():
    started, release = [], threading.Event()
    tasks.set_runner(lambda command: tasks.spawn(command, lambda t: started.append(t.name)))
    for command in ("make a presentation", "order groceries", "make an excel sheet"):
        assert tasks.spawn(command, lambda _t: release.wait(WAIT_S)) is not None

    assert tasks.spawn("remind me to drink water", lambda _t: None) is None
    assert tasks.answer_offer() == tasks.QUEUED_MESSAGE
    release.set()
    _wait(lambda: "reminder" in started)
    tasks.set_runner(lambda command: orchestrator.start_task(command))


def test_agents_of_one_task_share_one_cost_cap():
    task = _task("presentation")
    brain = orchestrator.TaskLimits("gpt-5.6-terra", cost_cap_usd=0.50)
    document = orchestrator.TaskLimits("gpt-5.6-terra", cost_cap_usd=0.50)

    def usage(tokens):
        metrics = SimpleNamespace(accumulated_usage={"inputTokens": tokens, "outputTokens": 0})
        return SimpleNamespace(agent=SimpleNamespace(event_loop_metrics=metrics))

    def run():
        brain._record(usage(150_000))  # $0.30
        document._check_limits(usage(150_000))  # its own $0.30 → task total $0.60

    thread, outcome = _in_task(task, run)
    thread.join(WAIT_S)

    assert isinstance(outcome["result"], orchestrator.TaskLimitExceeded)
    assert task.spent_usd == pytest.approx(0.60)


# --- Announcements --------------------------------------------------------------------------------


def test_announcements_wait_for_another_tasks_confirmation_and_carry_the_name(gate):
    grocery, presentation = _task("grocery order"), _task("presentation")
    safety.claim_voice_channel()
    thread, _ = _in_task(grocery, _confirm)
    _wait(safety.awaiting_reply)

    tasks.say("Ready, 6 slides.", presentation)
    time.sleep(0.1)
    assert gate["said"] == []  # the grocery order holds the floor
    safety.cancel_pending(grocery.id)
    thread.join(WAIT_S)

    _wait(lambda: "Presentation: Ready, 6 slides." in gate["said"])


def test_a_stopped_task_announces_nothing_more(gate):
    presentation = _task("presentation")
    presentation.cancel.set()

    tasks.say("Slide 4 done.", presentation)
    time.sleep(0.1)

    assert gate["said"] == []


def test_share_and_documents_are_registered_and_sending_is_never_free():
    assert safety.risk_of("share_file") == "guarded"
    assert safety.risk_of("document_agent") == "guarded"
    assert safety.risk_of("set_reminder") == "free"


def test_names_for_spoken_commands():
    assert tasks.name_for("Make a 6-slide presentation on renewable energy") == "presentation"
    assert tasks.name_for("order my usual groceries from Amazon") == "grocery order"
    assert tasks.name_for("make an Excel sheet of my monthly expenses") == "spreadsheet"


def test_money_parser_used_for_sheet_totals():
    from zoya.tools.office import to_number

    assert to_number("₹1,200.50") == Decimal("1200.50")
    assert to_number("Rs 300") == Decimal("300")
    assert to_number("rent") is None


# --- Voice loop: task-named replies and stops (D61) ----------------------------------------


@pytest.fixture
def loop(monkeypatch):
    from zoya import audio, voice

    instance = object.__new__(voice.VoiceLoop)
    instance.confirmations = SimpleNamespace(replies=[])
    instance.confirmations.reply = lambda text, heard_from: instance.confirmations.replies.append(
        text
    )
    instance.recent = []
    instance.ptt, instance.segment, instance.pre_roll = None, None, []
    monkeypatch.setattr(audio, "earcon", lambda _kind: None)
    monkeypatch.setattr(voice, "_log_voice", lambda _record: None)
    return instance


def _segment():
    from zoya import voice

    return voice.Segment([], time.monotonic(), woke_at=time.monotonic())


def test_voice_reply_naming_another_task_never_reaches_the_confirmation(loop, monkeypatch):
    grocery, presentation = _task("grocery order"), _task("presentation")
    monkeypatch.setattr(safety, "pending_task_id", lambda: grocery.id)

    loop._confirmation_reply(_segment(), "confirm the presentation")

    assert loop.confirmations.replies == []
    assert not grocery.cancel.is_set() and not presentation.cancel.is_set()


def test_voice_cancel_naming_another_task_stops_that_task_not_the_waiting_one(loop, monkeypatch):
    grocery, presentation = _task("grocery order"), _task("presentation")
    monkeypatch.setattr(safety, "pending_task_id", lambda: grocery.id)

    loop._confirmation_reply(_segment(), "cancel the presentation")

    assert loop.confirmations.replies == []
    assert presentation.cancel.is_set() and not grocery.cancel.is_set()


def test_voice_confirm_naming_the_waiting_task_is_passed_on(loop, monkeypatch):
    grocery, _presentation = _task("grocery order"), _task("presentation")
    monkeypatch.setattr(safety, "pending_task_id", lambda: grocery.id)

    loop._confirmation_reply(_segment(), "confirm the grocery order")

    assert loop.confirmations.replies == ["confirm"]


def test_spoken_stop_with_a_task_name_is_a_named_stop():
    from zoya import voice

    _task("presentation")

    assert voice.stop_name("Zoya, stop the presentation") == "presentation"
    assert voice.stop_name("Zoya, stop everything") == "everything"
    assert voice.stop_name("Zoya, stop") == ""
    assert voice.stop_name("stop the music") == ""  # not a task: stays a media command


def test_a_stop_naming_no_running_task_never_becomes_a_bare_stop(loop, monkeypatch):
    grocery = _task("grocery order")
    from zoya import audio

    monkeypatch.setattr(
        orchestrator, "stop_task", lambda name="": tasks.stop(name) if name else tasks.stop_last()
    )
    monkeypatch.setattr(audio, "engine", lambda: SimpleNamespace(silence_all=lambda: None))
    monkeypatch.setattr(audio, "restore", lambda: None)
    loop._end_barge_in = lambda: None

    loop._stop(time.monotonic(), "Zoya, stop the presentation", partial=False)

    assert not grocery.cancel.is_set()  # the presentation had already stopped


def test_push_to_talk_with_tasks_running_cuts_speech_but_stops_no_task(loop, monkeypatch):
    import numpy as np

    from zoya import audio, speech, voice

    presentation = _task("presentation")
    stopped = []
    monkeypatch.setattr(voice, "push_to_talk_held", lambda: True)
    monkeypatch.setattr(voice.VoiceLoop, "_zoya_busy", lambda self: True)
    monkeypatch.setattr(safety, "awaiting_reply", lambda: False)
    monkeypatch.setattr(orchestrator, "stop_task", lambda *a: stopped.append(a))
    monkeypatch.setattr(speech, "cancel", lambda: stopped.append("speech"))
    monkeypatch.setattr(audio, "engine", lambda: SimpleNamespace(silence_all=lambda: None))
    monkeypatch.setattr(audio, "duck", lambda: None)

    loop._push_to_talk(time.monotonic(), np.zeros(512, dtype="float32"))

    assert stopped == ["speech"] and not presentation.cancel.is_set()


# --- share_file is a SEND: always asked, file and recipient named, on every call path ------------


@pytest.fixture
def shareable(tmp_path, monkeypatch):
    from zoya.tools import office, share

    monkeypatch.setattr(office, "DOCUMENTS_DIR", tmp_path)
    monkeypatch.setattr(share, "SHARE_CONTACTS", ("sister",))
    sent = []
    monkeypatch.setattr(share, "_upload", lambda file: sent.append(file.name) or "https://link")
    monkeypatch.setattr(share, "_publish", lambda *args: sent.append("email"))
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"x")
    return share, deck, sent


def test_share_file_called_directly_asks_naming_file_and_recipient(gate, shareable):
    share, deck, sent = shareable
    channel = safety.claim_voice_channel()
    thread, outcome = _in_task(None, share.share_file, str(deck), "my sister")

    _answer(channel, "confirm")
    thread.join(WAIT_S)

    assert gate["prompts"] == [
        "I'm about to email a link to deck.pptx to your sister. Say confirm, or cancel."
    ]
    assert sent == ["deck.pptx", "email"] and outcome["result"].startswith("Sent your sister")


def test_share_file_without_confirm_sends_nothing(gate, shareable):
    share, deck, sent = shareable
    channel = safety.claim_voice_channel()
    thread, outcome = _in_task(None, share.share_file, str(deck), "sister")

    _answer(channel, "cancel")
    thread.join(WAIT_S)

    assert sent == [] and isinstance(outcome["result"], safety.ConfirmationDeclined)


def test_share_file_through_an_agent_direct_tool_call_still_asks(gate, shareable):
    from strands import Agent

    share, deck, sent = shareable
    safety.claim_voice_channel()  # nobody answers: silence cancels
    agent = Agent(
        tools=[share.share_file], hooks=[safety.ConfirmationGate()], callback_handler=None
    )

    thread, _ = _in_task(None, lambda: agent.tool.share_file(path=str(deck), recipient="sister"))
    thread.join(WAIT_S * 2)

    assert sent == [] and len(gate["prompts"]) == 2  # asked, re-prompted, cancelled
    assert all("deck.pptx" in p and "your sister" in p for p in gate["prompts"])


def test_share_file_to_an_unknown_contact_is_refused_before_asking(gate, shareable):
    share, deck, sent = shareable
    safety.claim_voice_channel()

    with pytest.raises(ToolError):
        share.share_file(str(deck), "neighbour")
    assert gate["prompts"] == [] and sent == []


def test_share_file_outside_zoya_documents_is_refused(gate, shareable, tmp_path_factory):
    share, _deck, sent = shareable
    secret = tmp_path_factory.mktemp("home") / "id_rsa"
    secret.write_text("key")

    with pytest.raises(ToolError):
        share.share_file(str(secret), "sister")
    assert gate["prompts"] == [] and sent == []


def test_partial_stop_waits_for_a_task_name_once_tasks_shared_the_floor(loop, monkeypatch):
    from zoya import voice

    _task("grocery order", shared=True)  # the presentation already finished
    spotted = []
    monkeypatch.setattr(voice.VoiceLoop, "_zoya_busy", lambda self: True)
    loop._spot = lambda samples: spotted.append(1) or "Zoya, stop"
    loop.recent = [np.zeros(voice.VAD_BLOCK, "f4")] * 40
    loop.last_stop_check = loop.last_stop_at = 0.0
    now = time.monotonic()
    loop.last_voice_at = now  # still talking: "…the presentation" may follow

    loop._check_stop(now)

    assert spotted == []


@pytest.mark.parametrize("heard", ["queue it", "Cue it!", "yes, queue that"])
def test_queue_it_as_transcribed(heard):
    from zoya import voice
    from zoya.router import clean_command

    assert voice.QUEUE_IT.match(clean_command(heard))
