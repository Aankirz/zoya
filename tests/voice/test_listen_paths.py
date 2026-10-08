"""S1-Listen: voice-side paths that must never cancel work or swallow the user (L2, L5)."""

from tests.voice.sim import Reply, Sound, run_script

LONG_REPLY = Reply("Here is a long answer that keeps going for quite a while longer.", 0.5)


def test_push_to_talk_over_her_speech_cuts_speech_but_never_stops_a_task(monkeypatch):
    sounds = [
        Sound("tell me about Pune", 1.0, ptt=True),
        Sound("what time is it", 0.5, ptt=True, cue=0),
    ]
    trace, _loop = run_script(
        monkeypatch, sounds, replies={"Pune": LONG_REPLY}, running=["grocery order"]
    )
    assert trace.stops == []
    assert trace.dispatched == ["tell me about Pune", "what time is it"]
    assert trace.events("ptt_cut_speech")


QUESTION = Reply("Which colour would you like for the case?", 0.5)


def _answer_after_question(gap: float) -> list[Sound]:
    return [Sound("order a phone case", 1.0, ptt=True), Sound("the dark green one", gap, cue=0)]


def test_a_prompt_answer_is_kept_without_an_echo_canceller(monkeypatch):
    trace, _loop = run_script(
        monkeypatch, _answer_after_question(0.1), replies={"case": QUESTION}, aec_on=False
    )
    assert len(trace.dispatched) == 2 and "green" in trace.dispatched[1]


def test_her_own_echo_alone_is_never_taken_as_an_answer(monkeypatch):
    sounds = [Sound("order a phone case", 1.0, ptt=True)]
    for aec_on in (True, False):
        trace, _loop = run_script(monkeypatch, sounds, replies={"case": QUESTION}, aec_on=aec_on)
        assert trace.dispatched == ["order a phone case"]


def test_an_answer_over_her_question_starts_at_the_users_voice(monkeypatch):
    trace, _loop = run_script(monkeypatch, _answer_after_question(-0.2), replies={"case": QUESTION})
    assert len(trace.dispatched) == 2
    assert trace.dispatched[1].startswith("case?")
    assert trace.events("reply_over_speech")
