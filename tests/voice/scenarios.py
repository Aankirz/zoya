"""Scripted listening scenarios for the voice-loop simulator (S1-Listen).

Two sets. DEV is what the fixes were built against. HELDOUT was written in the same commit,
before any fix, and is only run and reported, never tuned to (owner, 2026-10-09). Transcripts
from the owner's real logs appear only in DEV, each as the minimal repro of the bug it proves.

Each case says what must be dispatched (one substring per dispatched command, in order; setup
commands included) and how many stops must happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tests.voice.sim import ROOM, Reply, Sound

WAKE_AT = 1.0
COMMAND_AFTER_WAKE_S = 1.6
SETUP = "what's the weather in Pune"
SETUP_REPLY = Reply("It is twenty eight degrees in Pune right now.", after=0.5)
FOLLOW_UP_GAP_S = 1.0
ANSWER_GAP_S = 0.8
OVERLAP_S = -0.3
SPLIT_PAUSE_S = 1.2


@dataclass(frozen=True)
class Case:
    name: str
    sounds: list[Sound]
    dispatched: list[str]
    stops: int = 0
    replies: dict[str, Reply] = field(default_factory=dict)
    running: list[str] = field(default_factory=list)


def ptt(text: str, at: float = WAKE_AT) -> Sound:
    return Sound(text, at, ptt=True)


def after_wake(text: str, wake: str = "Hey Zoya", speaker: str = "user") -> list[Sound]:
    """ "Hey Zoya" … pause … then `text` in the after-wake window."""
    return [Sound(wake, WAKE_AT), Sound(text, WAKE_AT + COMMAND_AFTER_WAKE_S, speaker)]


def one_breath(text: str) -> list[Sound]:
    return [Sound(text, WAKE_AT)]


def follow_up(text: str, speaker: str = "user") -> list[Sound]:
    """A first command answered by Zoya (no question), then `text` with no wake word."""
    return [ptt(SETUP), Sound(text, FOLLOW_UP_GAP_S, speaker, cue=0)]


def answer(question: str, *parts: tuple[str, float]) -> tuple[list[Sound], dict[str, Reply]]:
    """A first command that Zoya answers with `question`; parts start (gap) after the previous
    part ends, or after her question for the first part (a negative gap talks over it)."""
    sounds = [ptt("help me with something")]
    at = 0.0
    for text, gap in parts:
        sounds.append(Sound(text, at + gap, cue=0))
        at += gap + Sound(text, 0).length
    return sounds, {"help me with something": Reply(question, after=0.5)}


def _answer_case(name: str, question: str, parts: list[tuple[str, float]], want: str) -> Case:
    sounds, replies = answer(question, *parts)
    return Case(name, sounds, ["help me with something", want], replies=replies)


DEV = [
    # --- real-log repros (one each, for the bug they prove) -------------------------------------
    Case("log: narration after a bare 'Zoya' wake", after_wake("Here's where", wake="Zoya"), []),
    Case("log: naming the hotkey after a wake", after_wake("control option.", wake="Zoya"), []),
    Case("log: wake word plus a remark", one_breath("Zoya, I'm going to make a video."), []),
    Case(
        "log: garbled Hindi after a wake",
        after_wake("ज़िए ज़दर भी हां कि मुझे ये करना है ये करना है", wake="Zoya"),
        [],
    ),
    _answer_case(
        "log: answer begun over the end of her question",
        "What exact text would you like to tweet about Bangalore?",
        [("Bangalore weather is lovely this week, post that", OVERLAP_S)],
        "lovely this week",
    ),
    # --- fresh: short real commands -------------------------------------------------------------
    Case("push-to-talk 'pause'", [ptt("pause")], ["pause"]),
    Case("push-to-talk 'next'", [ptt("next")], ["next"]),
    Case("'dark mode' after a wake", after_wake("dark mode"), ["dark mode"]),
    _answer_case(
        "'yes' answers her question", "Shall I send it now?", [("yes", ANSWER_GAP_S)], "yes"
    ),
    _answer_case(
        "'5000' answers a budget", "What is your budget?", [("5000", ANSWER_GAP_S)], "5000"
    ),
    Case("push-to-talk 'stop' with nothing running", [ptt("stop")], [], stops=1),
    Case(
        "'Zoya, stop' while a task runs",
        [Sound("Zoya, stop", 2.0, spot="Zoya, stop")],
        [],
        stops=1,
        running=["grocery order"],
    ),
    Case("push-to-talk one word 'Namaste'", [ptt("Namaste")], ["Namaste"]),
    # --- fresh: wake forms ------------------------------------------------------------------------
    Case(
        "one breath: calendar question",
        one_breath("Hey Zoya, what's on my calendar tomorrow"),
        ["calendar tomorrow"],
    ),
    Case(
        "after wake: reminder",
        after_wake("remind me to water the plants at seven"),
        ["water the plants"],
    ),
    Case("after wake: Hinglish alarm", after_wake("kal subah 7 baje ka alarm laga do"), ["alarm"]),
    Case("after wake: Hindi call", after_wake("मम्मी को फ़ोन लगाओ"), ["मम्मी"]),
    Case(
        "after wake: demo narration",
        after_wake("so this is the part where it opens the browser for you"),
        [],
    ),
    Case(
        "name mid-sentence is no wake",
        [Sound("I told Zoya about it yesterday", WAKE_AT, spot="I told Zoya about it yesterday")],
        [],
    ),
    # --- fresh: follow-ups and side talk ------------------------------------------------------
    Case(
        "follow-up: side conversation in Hindi",
        follow_up("haan main bas abhi aata hoon"),
        [SETUP],
        replies={SETUP: SETUP_REPLY},
    ),
    Case(
        "follow-up: real question",
        follow_up("and what about tomorrow?"),
        [SETUP, "tomorrow"],
        replies={SETUP: SETUP_REPLY},
    ),
    Case(
        "overheard TV, no wake word",
        [Sound("and in other news the markets closed higher today", WAKE_AT, ROOM)],
        [],
    ),
    # --- fresh: push-to-talk over Zoya, answers --------------------------------------------
    Case(
        "push-to-talk while she speaks",
        [ptt(SETUP), Sound("skip this song", 0.5, ptt=True, cue=0)],
        [SETUP, "skip this song"],
        replies={SETUP: Reply("It is twenty eight degrees in Pune and sunny all day.", 0.5)},
    ),
    _answer_case(
        "answer split across a pause",
        "What should the tweet say?",
        [("launching our new app", ANSWER_GAP_S), ("on Monday at ten", SPLIT_PAUSE_S)],
        "app on Monday",
    ),
    _answer_case(
        "short answer over her last word",
        "Which city should I check?",
        [("Mumbai please", OVERLAP_S)],
        "Mumbai",
    ),
]

HELDOUT = [
    Case("after wake: volume", after_wake("turn the volume down a bit"), ["volume down"]),
    Case(
        "after wake: cricket score",
        after_wake("what's the score in the India match"),
        ["score"],
    ),
    Case(
        "after wake: podcast in the room",
        after_wake("the thing about compound interest is that it grows quietly", speaker=ROOM),
        [],
    ),
    Case("one breath: a remark", one_breath("Zoya, I just got back from the gym"), []),
    Case(
        "one breath: Hinglish reminder",
        one_breath("Hey Zoya, mujhe kal ki meeting yaad dila dena"),
        ["meeting"],
    ),
    Case(
        "follow-up: side talk in English",
        follow_up("yeah I'll be there in five minutes"),
        [SETUP],
        replies={SETUP: SETUP_REPLY},
    ),
    Case(
        "follow-up: louder",
        follow_up("make it a bit louder"),
        [SETUP, "louder"],
        replies={SETUP: SETUP_REPLY},
    ),
    Case("push-to-talk one word 'lights'", [ptt("lights")], ["lights"]),
    _answer_case(
        "answer in two pieces",
        "Who should I send it to?",
        [("to Priya", ANSWER_GAP_S), ("and also Karan", 1.0)],
        "Priya and also Karan",
    ),
    _answer_case(
        "answer over her question",
        "What time works for you?",
        [("around six thirty", -0.2)],
        "six thirty",
    ),
    Case("after wake: Hinglish weather", after_wake("aaj mausam kaisa hai"), ["mausam"]),
    Case(
        "after wake: Hindi news anchor on TV",
        after_wake("aur ab dekhte hain aaj ki badi khabrein", speaker=ROOM),
        [],
    ),
    Case(
        "'Zoya, stop' while a silent task works",
        [Sound("Zoya stop", 2.5, spot="Zoya stop")],
        [],
        stops=1,
        running=["presentation"],
    ),
    Case("after wake: brightness up", after_wake("brightness up"), ["brightness"]),
    Case(
        "push-to-talk cancel while she speaks",
        [ptt(SETUP), Sound("no wait, cancel that", 0.4, ptt=True, cue=0)],
        [SETUP],
        stops=1,
        replies={SETUP: Reply("It is twenty eight degrees in Pune and sunny all day long.", 0.5)},
    ),
    Case(
        "one breath: read my message",
        one_breath("Okay Zoya, read me my last message"),
        ["last message"],
    ),
]
