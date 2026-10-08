"""S1-Listen: voice-side paths that must never cancel work or swallow the user (L2, L5)."""

from tests.voice.sim import Reply, Simulator, Sound, run_script, simulated

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


CHATTER = [
    "so the idea is you just talk to it",
    "and it goes off and does the thing",
    "I've been using it all week honestly",
    "the trick is the little pill at the bottom",
    "we built the whole thing in a month",
    "you can see it thinking right there",
    "anyway it's pretty fast most of the time",
    "my friend tried it yesterday and loved it",
]


def _storm() -> tuple[list[Sound], dict[str, Reply]]:
    """The Oct 7 pattern: the owner talks to a room for a minute, wakes Zoya once, and answers
    her question over its last words while still chatting."""
    sounds = [Sound(line, 0.5 + 6.0 * i) for i, line in enumerate(CHATTER[:3])]
    sounds += [Sound("Hey Zoya", 19.0), Sound("tweet something about Bangalore", 20.6)]
    sounds += [Sound(line, 26.0 + 6.0 * i) for i, line in enumerate(CHATTER[3:5])]
    sounds += [Sound("say the weather is lovely this week", -0.3, cue=0)]
    sounds += [Sound(line, 2.0 + 6.0 * i, cue=1) for i, line in enumerate(CHATTER[5:])]
    replies = {
        "Bangalore": Reply("What exact text would you like to tweet?", 14.0),
        "lovely": Reply("Posted.", 1.0),
    }
    return sounds, replies


def test_the_barge_in_storm_replay(monkeypatch):
    sounds, replies = _storm()
    trace, loop = run_script(monkeypatch, sounds, replies=replies)
    assert len(trace.dispatched) == 2
    assert "Bangalore" in trace.dispatched[0] and "lovely" in trace.dispatched[1]
    assert trace.stops == []
    assert len(trace.events("barge_in")) >= len(CHATTER)
    assert not trace.ducked


def test_chatter_after_a_wake_does_not_hold_the_music_down(monkeypatch):
    sounds = [Sound("Hey Zoya", 1.0)]
    sounds += [Sound(line, 2.6 + 6.0 * i) for i, line in enumerate(CHATTER)]
    sim_trace, loop = run_script(monkeypatch, sounds)
    assert sim_trace.dispatched == []
    assert sim_trace.events("not_for_me")
    assert not sim_trace.ducked and loop.awaiting_command_until < sim_trace.ended_at


def test_an_onset_that_changes_nothing_holds_nothing(monkeypatch):
    sim = Simulator([Sound("hello", 1.0)])
    with simulated(sim, monkeypatch) as loop:
        loop._barge_in(sim.clock.now, other_audio=False)
        assert loop.barge_in_until == 0.0
        sim.speaking_until = sim.clock.now + 1.0
        loop._barge_in(sim.clock.now, other_audio=False)
        assert loop.barge_in_until > sim.clock.now


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
