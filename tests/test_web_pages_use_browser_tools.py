"""Phase H round 1: a web page is never pixel-driven by computer_task, on any site."""

import pytest

from zoya.agents import computer_agent, web_loop


@pytest.fixture
def web_page_in_front(monkeypatch):
    driven: list[str] = []
    monkeypatch.setattr(computer_agent, "front_is_web_page", lambda: True)
    monkeypatch.setattr(computer_agent.computer, "begin_session", lambda: None)
    monkeypatch.setattr(computer_agent, "replay_flow", lambda *_: driven.append("replay"))
    monkeypatch.setattr(computer_agent, "_run_step_loop", lambda *_: driven.append("steps"))
    monkeypatch.setattr(computer_agent, "_run_agent", lambda *_: driven.append("pixels"))
    monkeypatch.setattr(computer_agent.computer, "log_stage", lambda *_a, **_k: None)
    front = type("Front", (), {"processIdentifier": lambda _self: 1})()
    monkeypatch.setattr(computer_agent.ax, "frontmost_regular_app", lambda: front)
    return driven


def test_a_page_in_another_browser_goes_to_the_browser_tools(web_page_in_front, monkeypatch):
    from zoya.tools import browser

    monkeypatch.setattr(browser, "is_ours", lambda _pid: False)
    said = computer_agent.run_computer_task("subscribe to this channel")
    assert said == computer_agent.OTHER_BROWSER_SAY and web_page_in_front == []


def test_zoyas_page_gets_the_web_loop_and_never_pixels(web_page_in_front, monkeypatch):
    from zoya.tools import browser

    monkeypatch.setattr(browser, "is_ours", lambda _pid: True)
    monkeypatch.setattr(
        web_loop, "run", lambda goal, cancel: web_loop.Outcome(reason="Jev unavailable (403)")
    )
    said = computer_agent.run_computer_task("open the channel")
    assert said.startswith("That's a web page") and "browser_task" in said
    assert web_page_in_front == []
