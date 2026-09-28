"""D138 (b): a browser task's final claim is checked against the page; it only makes Zoya more
honest, never blocks, and a check that can't run changes nothing."""

from typing import Any

import pytest

from zoya import decisions, orchestrator, tasks
from zoya.agents import web_loop

CLAIM = "Opened the official MrBeast YouTube channel."
RESULTS_PAGE = {
    "url": "https://video.example/results?search_query=mrbeast",
    "title": "mrbeast - Search results",
    "text": "Filters MrBeast 1 video MrBeast 2",
    "actions": [],
}


def jev(claims: float, supported: float, seen: list[str] | None = None) -> Any:
    def ask(state: str, questions: Any, *_a: Any, **_k: Any) -> decisions.Answers:
        if seen is not None:
            seen.append(state)
        found = {"claims": {"noul": claims}, "supported": {"noul": supported}}
        return decisions.Answers({k: v for k, v in found.items() if k in questions}, 1)

    return ask


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setattr(web_loop, "observe", lambda: RESULTS_PAGE)


def test_a_claim_the_page_does_not_support_is_replaced_with_what_is_true(page, monkeypatch):
    monkeypatch.setattr(decisions, "ask", jev(claims=0.95, supported=0.1))
    said = web_loop.honest_reply(CLAIM)
    assert "MrBeast YouTube channel" not in said and "couldn't confirm" in said
    assert "mrbeast - Search results" in said


def test_a_claim_the_page_supports_is_kept(page, monkeypatch):
    monkeypatch.setattr(decisions, "ask", jev(claims=0.95, supported=0.9))
    assert web_loop.honest_reply(CLAIM) == CLAIM


def test_a_reply_that_claims_nothing_is_kept(page, monkeypatch):
    reply = "I couldn't reach the search box. Please search for MrBeast yourself."
    monkeypatch.setattr(decisions, "ask", jev(claims=0.05, supported=0.0))
    assert web_loop.honest_reply(reply) == reply


def test_jev_unavailable_changes_nothing(page, monkeypatch):
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: decisions.unavailable("403"))
    assert web_loop.honest_reply(CLAIM) == CLAIM


def test_a_check_with_an_answer_missing_changes_nothing(page, monkeypatch):
    only_claims = decisions.Answers({"claims": {"noul": 0.95}}, 1)
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: only_claims)
    assert web_loop.honest_reply(CLAIM) == CLAIM


def test_a_page_that_cannot_be_read_changes_nothing(monkeypatch):
    def unreadable() -> dict[str, Any]:
        raise web_loop.ToolError("no browser")

    monkeypatch.setattr(web_loop, "observe", unreadable)
    monkeypatch.setattr(decisions, "ask", jev(claims=0.95, supported=0.0))
    assert web_loop.honest_reply(CLAIM) == CLAIM


def test_page_text_reaches_jev_only_wrapped(page, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(decisions, "ask", jev(0.95, 0.9, seen))
    web_loop.honest_reply(CLAIM)
    inside = seen[0].split("<untrusted_content>")[1]
    assert RESULTS_PAGE["text"] in inside and seen[0].count("</untrusted_content>") == 1


def stream(monkeypatch, events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    said: list[str] = []
    monkeypatch.setattr(tasks, "say", lambda text: said.append(text) if text else None)
    reply = orchestrator.HeldReply()
    handler = orchestrator._speak_stream(orchestrator.SentenceStream(), held=reply)
    for event in events:
        handler(**event)
    return said, reply.sentences


def test_after_a_browser_tool_the_final_answer_is_held_for_the_check(monkeypatch):
    said, held = stream(
        monkeypatch,
        [
            {"data": "Opening YouTube. "},
            {"current_tool_use": {"name": "browser_open"}},
            {"data": "Searching now. "},
            {"current_tool_use": {"name": "browser_task"}},
            {"data": "Opened the channel. "},
        ],
    )
    assert said == ["Opening YouTube.", "Searching now."]
    assert held == ["Opened the channel."]


def test_without_a_browser_tool_every_sentence_is_spoken_at_once(monkeypatch):
    said, held = stream(
        monkeypatch,
        [
            {"data": "Checking. "},
            {"current_tool_use": {"name": "get_weather"}},
            {"data": "It's 24 degrees in Pune. "},
        ],
    )
    assert said == ["Checking.", "It's 24 degrees in Pune."] and held == []
