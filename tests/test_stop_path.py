""" "Stop" path (D37, §11.3): the flag halts the brain, speech is dropped, streamed text splits."""

import pytest

from zoya import orchestrator, speech
from zoya.orchestrator import SentenceStream


class FakeEngine:
    cleared = False

    def clear_speech(self):
        self.cleared = True

    def speech_pending(self):
        return False


@pytest.fixture
def engine(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(speech.audio, "engine", lambda: fake)
    return fake


def test_stop_task_sets_flag_and_drops_queued_speech(engine, monkeypatch):
    monkeypatch.setattr(speech, "_worker", object())  # don't start the real speech worker
    speech.narrate("A sentence that must never be spoken.")

    orchestrator.stop_task()

    assert orchestrator._cancel.is_set()
    assert speech._queue.empty()
    assert engine.cleared
    orchestrator._cancel.clear()


def test_cancelled_generation_stops_a_sentence_mid_stream():
    generation = speech._generation
    speech._generation += 1

    with pytest.raises(speech.Cancelled):
        speech._check(generation)


def test_no_sentence_is_spoken_after_stop(engine, monkeypatch):
    spoken = []
    monkeypatch.setattr(speech, "narrate", spoken.append)
    handler = orchestrator._speak_stream(SentenceStream())
    orchestrator._cancel.set()

    handler(data="Tokyo is the capital of Japan. ")

    assert spoken == []
    orchestrator._cancel.clear()


def test_cancelled_run_is_reported_as_stopped_not_success(monkeypatch):
    class CancelledAgent:
        messages = []
        event_loop_metrics = type("M", (), {"accumulated_usage": {}})()

        def __call__(self, command, cancel_signal):
            cancel_signal.set()
            return type("Result", (), {"stop_reason": "cancelled"})()

    monkeypatch.setattr(orchestrator, "build_orchestrator", lambda **_: CancelledAgent())
    decision = orchestrator.RouteDecision("orchestrator", text="tell me a story")

    spoken, ok = orchestrator._execute(decision, {})

    assert (spoken, ok) == (orchestrator.STOPPED_MESSAGE, False)
    assert orchestrator._conversation == []
    orchestrator._cancel.clear()


def test_sentence_stream_speaks_first_sentence_before_the_rest_arrives():
    stream = SentenceStream()

    assert stream.feed("Tokyo is the capital") == []
    assert stream.feed(" of Japan. It has about 14") == ["Tokyo is the capital of Japan."]
    assert stream.feed(".2 million people") == []  # "14.2" is not a sentence end
    assert stream.flush() == "It has about 14.2 million people"
    assert stream.flush() == ""
