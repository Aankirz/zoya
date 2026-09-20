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
    # Only what the user heard is kept, marked interrupted, so "continue" works (owner's run).
    last_reply = orchestrator._conversation[-1][1]["content"][0]["text"]
    assert last_reply.endswith("[interrupted by the user]")
    orchestrator._conversation.clear()
    orchestrator._cancel.clear()


def test_sentence_stream_speaks_first_sentence_before_the_rest_arrives():
    stream = SentenceStream()

    assert stream.feed("Tokyo is the capital") == []
    assert stream.feed(" of Japan. It has about 14") == ["Tokyo is the capital of Japan."]
    assert stream.feed(".2 million people") == []  # "14.2" is not a sentence end
    assert stream.flush() == "It has about 14.2 million people"
    assert stream.flush() == ""


def test_unknown_app_falls_back_to_the_brain_instead_of_failing(monkeypatch):
    from zoya.tools import ToolError

    def missing_app(_decision):
        raise ToolError("I can't find YouTube MrBeast on this Mac.")

    monkeypatch.setattr(orchestrator, "run_fast_tool", missing_app)
    monkeypatch.setattr(orchestrator, "run_orchestrator", lambda text, timings: f"brain: {text}")
    decision = orchestrator.RouteDecision(
        "fast", "open_app", {"app_name": "YouTube MrBeast"}, text="open YouTube MrBeast"
    )
    timings = {}

    assert orchestrator._execute(decision, timings) == ("brain: open YouTube MrBeast", True)
    assert orchestrator.OPEN_APP_FALLBACK in timings


# --- Phase B: Jev widens "stop", and can never narrow it (D81) ---------------------------------


STOP_PHRASES = ("Zoya stop", "Zoya, stop it now", "Zoya ruk jao", "Zoya bas", "Zoya cancel that")


def test_the_regex_catches_stop_with_no_model_and_no_network(monkeypatch):
    from zoya import voice

    def unreachable(*_args, **_kwargs):
        raise AssertionError("the offline stop path asked the network")

    monkeypatch.setattr(voice.decisions, "ask", unreachable)
    assert all(voice.is_stop(phrase) for phrase in STOP_PHRASES)
    assert all(voice.is_stop_command(phrase) for phrase in STOP_PHRASES)


def test_jev_is_never_asked_about_a_stop_the_regex_already_caught(monkeypatch):
    from zoya import voice

    asked = []
    monkeypatch.setattr(voice.VoiceLoop, "_spot", lambda self, samples: "Zoya stop")
    monkeypatch.setattr(voice.VoiceLoop, "_stop", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(voice.VoiceLoop, "_ask_jev_stop", lambda self, *args: asked.append(args))
    loop = voice.VoiceLoop.__new__(voice.VoiceLoop)
    loop.last_voice_at = 0.0
    loop.recent = [__import__("numpy").zeros(512, dtype="float32")] * 40
    loop.last_stop_check = -100.0
    loop.last_stop_at = -100.0
    monkeypatch.setattr(voice.VoiceLoop, "_zoya_busy", lambda self: True)
    monkeypatch.setattr(voice.tasks, "running", lambda: [])
    voice.VoiceLoop._check_stop(loop, 0.1)
    assert asked == []


def test_a_jev_stop_only_fires_while_there_is_something_to_stop(monkeypatch):
    from zoya import voice

    stopped = []
    monkeypatch.setattr(
        voice.VoiceLoop, "_stop", lambda self, *args, **kwargs: stopped.append((args, kwargs))
    )

    loop = voice.VoiceLoop.__new__(voice.VoiceLoop)
    loop.jev_stop = (1.0, "Zoya that's enough")
    monkeypatch.setattr(voice.VoiceLoop, "_zoya_busy", lambda self: False)
    voice.VoiceLoop._take_jev_stop(loop)
    assert stopped == []

    loop.jev_stop = (1.0, "Zoya that's enough")
    monkeypatch.setattr(voice.VoiceLoop, "_zoya_busy", lambda self: True)
    voice.VoiceLoop._take_jev_stop(loop)
    assert stopped == [((1.0, "Zoya that's enough"), {"partial": True})]


def test_an_unreachable_jev_never_raises_into_the_voice_loop(monkeypatch):
    from zoya import voice

    monkeypatch.setattr(
        voice.decisions, "ask", lambda *a, **k: voice.decisions.unavailable("offline")
    )
    loop = voice.VoiceLoop.__new__(voice.VoiceLoop)
    loop.jev_stop, loop.jev_stop_asked = None, False
    voice.VoiceLoop._jev_stop_answer(loop, "Zoya that's enough", 1.0)
    assert loop.jev_stop is None
    assert loop.jev_stop_asked is False
