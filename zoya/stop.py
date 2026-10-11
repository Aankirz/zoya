"""What counts as "stop" (§11.3, D177): one grammar for the spotter, a captured command, a
confirmation reply and the router, instead of a word list in each.

A stop is a whole short phrase: greetings and Zoya's name, one stop verb, then only filler words
or the name of what to stop. A stop word inside a sentence ("don't stop the music", "stop by the
store") is not one; Jev may still judge a named phrase the grammar rejects (voice.py).

A bare "stop" carries no name, so Zoya's own voice could say it: the caller checks
`speech.recently_said` before acting on one that was not named.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from zoya.spoken import is_name, words

VERBS = {"stop", "cancel", "ruko", "rukiye", "ruk", "bas", "chup", "quiet"}
VERB_LEADS = {"be"}  # "be quiet"
VERB_TAILS = {"jao", "ja", "karo", "kar", "do"}  # "ruk jao", "bas karo", "chup ho ja"
GREETINGS = {"hey", "hi", "ok", "okay", "oh", "please"}
# Turbo writes a real "Zoya" as "Soya" (D51 replay); in a phrase this short it can only be her.
STOP_NAMES = {"soya"}
FILLER = {
    *("the", "my", "it", "that", "this", "now", "right", "please", "current", "ho"),
    *("what", "you", "re", "doing", "task", "tasks", "abhi", "yeh", "ye"),
}
ALL_WORDS = {"all", "everything", "sab", "kuch", "every"}
NEGATIONS = {"mat", "nahi", "na", "not", "dont", "don"}  # "ruko mat": don't stop
DOING = {"kijiye", "karo", "kar", "karna", "do", "it", "that"}  # "rukiye, mat kijiye": don't do it
MAX_PHRASE_WORDS = 7


@dataclass(frozen=True)
class Stop:
    """A parsed stop. `target` is "" for whatever is going on now, "everything", or the words
    naming one task ("presentation")."""

    verb: str
    named: bool
    target: str = ""


def _is_name(word: str) -> bool:
    return is_name(word) or word in STOP_NAMES


def _strip_edges(spoken: list[str]) -> tuple[list[str], bool]:
    """Greetings and names off both ends; whether a name was among them."""
    named = False
    while spoken and (spoken[0] in GREETINGS or _is_name(spoken[0])):
        named = named or _is_name(spoken[0])
        spoken = spoken[1:]
    while spoken and (spoken[-1] in GREETINGS or _is_name(spoken[-1])):
        named = named or _is_name(spoken[-1])
        spoken = spoken[:-1]
    return spoken, named


def _negated(rest: list[str]) -> bool:
    """A negation of the stop itself, not of what Zoya was doing ("don't" reads as don, t)."""
    rest = [w for i, w in enumerate(rest) if not (w == "t" and i and rest[i - 1] == "don")]
    return any(
        word in NEGATIONS and not (rest[i + 1 :] and rest[i + 1] in DOING)
        for i, word in enumerate(rest)
    )


def _target(rest: list[str]) -> str:
    skipped = FILLER | VERB_TAILS | NEGATIONS | DOING | {"t"}
    named = [w for w in rest if w not in skipped and not _is_name(w)]
    if named and set(named) <= ALL_WORDS:
        return "everything"
    return " ".join(named)


def parse(text: str, known: Callable[[str], bool] | None = None) -> Stop | None:
    """The stop `text` says, or None. `known` decides whether target words name something that can
    be stopped (a running task); None accepts any, for when "the presentation" may already be gone
    and must never fall through to a bare stop of another task."""
    spoken = words(text)
    if not spoken or len(spoken) > MAX_PHRASE_WORDS:
        return None
    spoken, named = _strip_edges(spoken)
    if spoken[:1] and spoken[0] in VERB_LEADS:
        spoken = spoken[1:]
    if not spoken or spoken[0] not in VERBS:
        return None
    if _negated(spoken[1:]):
        return None
    target = _target(spoken[1:])
    if target and target != "everything" and known is not None and not known(target):
        return None
    return Stop(verb=spoken[0], named=named, target=target)


def is_named_stop(text: str) -> bool:
    found = parse(text)
    return found is not None and found.named
