"""Rule matcher is a parser (D37): a silent misroute opens the wrong thing or hits a 2 s model call.

No network: match_rules() never calls a model or AWS.
"""

import pytest

from zoya.router import RouteChoice, decision_from_choice, match_rules
from zoya.tools import ToolError, collect_tools
from zoya.tools.fast import media_control, normalise_url


@pytest.mark.parametrize(
    ("command", "tool", "args"),
    [
        ("open Spotify", "open_app", {"app_name": "Spotify"}),
        ("Now open Spotify.", "open_app", {"app_name": "Spotify"}),
        ("I want you to open Spotify.", "open_app", {"app_name": "Spotify"}),
        ("Can you now open open.spotify.com?", "open_url", {"url": "open.spotify.com"}),
        ("Can you stop playing the song?", "media_control", {"action": "pause", "app": "spotify"}),
        ("Play music from Spotify.", "media_control", {"action": "play", "app": "spotify"}),
        ("Hey Zoya, open Spotify!", "open_app", {"app_name": "Spotify"}),
        ("uh, launch the Notes app please", "open_app", {"app_name": "Notes"}),
        ("Spotify khol do", "open_app", {"app_name": "Spotify"}),
        ("Chrome open kardo", "open_app", {"app_name": "Chrome"}),
        ("open youtube.com", "open_url", {"url": "youtube.com"}),
        ("open https://amazon.in/cart", "open_url", {"url": "https://amazon.in/cart"}),
        ("write a note: buy milk", "notes_create", {"body": "buy milk"}),
        (
            "Take a note that the plumber comes Monday",
            "notes_create",
            {"body": "the plumber comes Monday"},
        ),
        ("note: open the window at 6", "notes_create", {"body": "open the window at 6"}),
        ("doodh lena hai note kar lo", "notes_create", {"body": "doodh lena hai"}),
        (
            "add fix the tap to my plumber note",
            "notes_append",
            {"note_name": "plumber", "text": "fix the tap"},
        ),
        ("search my notes for plumber", "notes_search", {"query": "plumber"}),
        ("what time is it", "get_time", {}),
        ("set volume to 40", "set_volume", {"level": 40}),
        ("turn the volume up", "volume_up", {}),
        ("mute", "mute", {}),
        ("pause spotify", "media_control", {"action": "pause", "app": "spotify"}),
        ("stop the music", "media_control", {"action": "pause", "app": "spotify"}),
        ("next song on music", "media_control", {"action": "next", "app": "music"}),
    ],
)
def test_fast_commands_match_without_a_model(command, tool, args):
    decision = match_rules(command)

    assert decision is not None and decision.route == "fast"
    assert (decision.tool, decision.args) == (tool, args)


@pytest.mark.parametrize(
    "command", ["Zoya stop", "stop", "cancel that", "Ruk jao Zoya", "Rukiye, mat kijiye"]
)
def test_stop_phrases_route_to_stop(command):
    decision = match_rules(command)

    assert decision is not None and decision.route == "stop"


@pytest.mark.parametrize(
    "command",
    [
        "Plan a trip and book a hotel",
        "Open Amazon and search for running shoes",
        "open Spotify then play my playlist",
        "Amazon kholo aur shoes dhundo",
        "Hey Zoya, what's the capital of Japan?",
        "Open Spotify in a browser.",
        "open youtube in chrome",
        "and its population?",
        "What's the weather in Delhi",
    ],
)
def test_multi_step_commands_go_straight_to_orchestrator(command):
    decision = match_rules(command)

    assert decision is not None and decision.route == "orchestrator"


@pytest.mark.parametrize(
    "command",
    [
        "open my latest email from Karthik",
        "notes",
        "cancel my Amazon order",
        "",
    ],
)
def test_multi_step_or_unknown_commands_fall_through_to_the_model(command):
    assert match_rules(command) is None


def test_model_fast_answer_missing_required_args_goes_to_orchestrator():
    choice = RouteChoice(route="fast", tool="open_app")

    assert decision_from_choice(choice).route == "orchestrator"


def test_model_fast_answer_keeps_only_that_tools_args():
    choice = RouteChoice(route="fast", tool="open_url", url="youtube.com", app_name="YouTube")

    decision = decision_from_choice(choice)

    assert (decision.route, decision.tool, decision.args) == (
        "fast",
        "open_url",
        {"url": "youtube.com"},
    )


SHELL_PAYLOADS = [
    'tell application "Notes"\n  do shell ¬\n script "echo PWNED"\nend tell',
    'tell application "Notes"\r\n  do shell ¬\r\n script "echo PWNED"\r\nend tell',
    'tell application "Music" to Do Shell Script "echo PWNED"',
]


def test_no_tool_accepts_free_form_applescript():
    """Regression for the ¬ bypass: the brain must have no tool that takes script text."""
    for zoya_tool in collect_tools("zoya.tools", "zoya.agents"):
        params = zoya_tool.tool_spec["inputSchema"]["json"].get("properties", {})
        assert "script" not in params, zoya_tool.tool_name
        assert zoya_tool.tool_name != "run_applescript"


@pytest.mark.parametrize("payload", SHELL_PAYLOADS)
@pytest.mark.parametrize("field", ["action", "app"])
def test_media_control_rejects_script_text(payload, field, monkeypatch):
    ran = []
    monkeypatch.setattr("zoya.tools.fast.osascript", lambda *args: ran.append(args))
    kwargs = {"action": "play", "app": "spotify", field: payload}

    with pytest.raises(ToolError):
        media_control(**kwargs)
    assert ran == []


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "localhost"])
def test_non_web_urls_are_refused(url):
    with pytest.raises(ToolError):
        normalise_url(url)
