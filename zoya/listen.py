"""Is this utterance meant for Zoya, and is it something to act on? One decision (D159, L1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from zoya.router import clean_command, match_rules


class Channel(StrEnum):
    PUSH_TO_TALK = "push_to_talk"
    ANSWER = "answer"
    WAKE = "wake"
    AFTER_WAKE = "after_wake"
    FOLLOW_UP = "follow_up"


TRUSTED = {Channel.PUSH_TO_TALK, Channel.ANSWER}
MIN_VOICED_FRACTION = 0.2
MIN_COMMAND_WORDS = 2
MAX_TRANSCRIPT_WORDS = 60
RUNAWAY_REPEATS = 4

WORD = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+|[ऀ-ॿ]+")
SUPPORTED_SCRIPT = re.compile(r"[A-Za-z0-9ऀ-ॿ]")
HALLUCINATIONS = {
    *("you", "thank you", "thanks for watching", "bye", "so", "okay"),
    *("um", "uh", "hmm", "mm", "ah", "er"),
}
LEADING_LINKS = {"and", "also", "then", "now", "so", "ok", "okay", "please", "just", "oh", "but"}
QUESTION_WORDS = {
    *("what", "what's", "whats", "who", "who's", "where", "where's", "when", "why", "how"),
    *("how's", "which", "whose", "is", "are", "am", "was", "were", "can", "could", "do", "does"),
    *("did", "will", "would", "should", "shall", "may", "have", "has", "isn't", "aren't"),
    *("don't", "doesn't", "didn't", "won't", "can't"),
}
VERBS = {
    *("open", "close", "quit", "launch", "start", "stop", "pause", "play", "resume", "skip"),
    *("next", "previous", "mute", "unmute", "turn", "switch", "set", "change", "make", "put"),
    *("increase", "decrease", "raise", "lower", "search", "find", "look", "show", "tell", "give"),
    *("read", "write", "type", "note", "save", "add", "remove", "delete", "send", "message"),
    *("text", "call", "email", "mail", "reply", "remind", "schedule", "book", "order", "buy"),
    *("cancel", "confirm", "check", "go", "navigate", "scroll", "click", "copy", "paste"),
    *("share", "download", "upload", "print", "enable", "disable", "update", "translate"),
    *("summarize", "summarise", "explain", "describe", "compare", "list", "get", "bring", "take"),
    *("tweet", "post", "create", "draft", "plan", "help", "repeat", "continue", "try", "run"),
    *("lock", "sleep", "restart", "brighten", "dim", "find", "track", "pay", "transfer", "log"),
    *("sign", "join", "leave", "answer", "record", "capture", "screenshot", "zoom", "fill"),
}
REQUEST_FRAMES = (
    re.compile(r"^(?:can|could|would|will) you\b"),
    re.compile(r"^i(?: would|'d)? (?:want|need|like|wanna)\b"),
    re.compile(r"^(?:let's|lets)\b"),
    re.compile(r"^(?:remind|tell|show|give|send|help) me\b"),
)
SETTING = re.compile(r"\b(?:mode|on|off|up|down)$")
HINDI_REQUEST = {
    *("karo", "kardo", "kariye", "kijiye", "dijiye", "do", "dena", "bhejo", "kholo", "chalao"),
    *("bajao", "batao", "bataiye", "dikhao", "lagao", "sunao", "suno", "padho", "likho"),
    *("dhundo", "dhoondo", "mangao", "rakho", "hatao", "badhao", "ghatao", "roko", "ruko", "bolo"),
    *("chahiye", "करो", "कर", "दो", "दीजिए", "दीजिये", "कीजिए", "कीजिये", "देना", "भेजो"),
    *("खोलो", "चलाओ", "बजाओ", "बताओ", "बताइए", "बताइये", "दिखाओ", "लगाओ", "सुनाओ", "सुनो"),
    *("पढ़ो", "लिखो", "ढूंढो", "ढूँढो", "मंगाओ", "रखो", "हटाओ", "बढ़ाओ", "घटाओ", "रोको", "बोलो"),
    "चाहिए",
}
HINDI_QUESTION = {
    *("kya", "kab", "kahan", "kaha", "kaise", "kaisa", "kaisi", "kaun", "kitna", "kitne"),
    *("kitni", "kyun", "kyon", "क्या", "कब", "कहाँ", "कहां", "कैसे", "कैसा", "कैसी", "कौन"),
    *("कितना", "कितने", "कितनी", "क्यों"),
}
HINDI_MUST = re.compile(r"(?:^|\s)(\S+)\s+(?:karna|करना|karni|करनी)\s+(?:hai|है)\b")
DEICTIC = {"ye", "yeh", "wo", "woh", "vo", "kuch", "ये", "यह", "वो", "वह", "कुछ", "this", "that"}


@dataclass(frozen=True)
class Verdict:
    act: bool
    reason: str


def words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("’", "'"))


def is_runaway(spoken: list[str]) -> bool:
    if len(spoken) > MAX_TRANSCRIPT_WORDS:
        return True
    return any(
        len(set(spoken[i : i + RUNAWAY_REPEATS])) == 1
        for i in range(len(spoken) - RUNAWAY_REPEATS + 1)
    )


def junk_reason(text: str, channel: Channel, voiced_fraction: float) -> str:
    """Why this is not speech at all ("" when it is): noise, Whisper's filler, a runaway."""
    command = clean_command(text)
    spoken = words(command)
    if not spoken or not SUPPORTED_SCRIPT.search(command):
        return "empty"
    if is_runaway(spoken):
        return "runaway"
    if " ".join(spoken) in HALLUCINATIONS:
        return "hallucination"
    if channel is not Channel.PUSH_TO_TALK and voiced_fraction < MIN_VOICED_FRACTION:
        return "background"
    return ""


def is_request(text: str) -> bool:
    """Shaped like something to do or answer: a rule, a question, an imperative, a request."""
    command = clean_command(text)
    if match_rules(command) is not None or command.rstrip().endswith("?"):
        return True
    spoken = words(command)
    while spoken and spoken[0] in LEADING_LINKS:
        spoken = spoken[1:]
    if not spoken:
        return False
    plain = " ".join(spoken)
    if spoken[0] in QUESTION_WORDS or spoken[0] in VERBS:
        return True
    if any(frame.match(plain) for frame in REQUEST_FRAMES) or SETTING.search(plain):
        return True
    return _hindi_request(spoken, plain)


def _hindi_request(spoken: list[str], plain: str) -> bool:
    if any(word in HINDI_REQUEST or word in HINDI_QUESTION for word in spoken):
        return True
    return any(match not in DEICTIC for match in HINDI_MUST.findall(plain))


def judge(text: str, channel: Channel, voiced_fraction: float = 1.0) -> Verdict:
    """Push-to-talk and answers to Zoya's own question are trusted: when in doubt, the user
    meant it. Hands-free speech must also be shaped like a request, or Zoya stays quiet."""
    if reason := junk_reason(text, channel, voiced_fraction):
        return Verdict(False, reason)
    if channel in TRUSTED:
        return Verdict(True, "trusted")
    command = clean_command(text)
    spoken = words(command)
    has_number = any(word.isdigit() for word in spoken)
    if len(words(text)) < MIN_COMMAND_WORDS and not has_number and match_rules(command) is None:
        return Verdict(False, "fragment")
    if not is_request(text):
        return Verdict(False, "not_a_request")
    return Verdict(True, "request")
