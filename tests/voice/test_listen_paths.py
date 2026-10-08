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
