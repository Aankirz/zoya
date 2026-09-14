"""Rule matcher is a parser (D37): a silent misroute opens the wrong thing or hits a 2 s model call.

No network: match_rules() never calls a model or AWS.
"""

import pytest

from zoya.router import RouteChoice, decision_from_choice, match_rules
from zoya.tools import ToolError
from zoya.tools.fast import check_applescript_allowed, normalise_url


@pytest.mark.parametrize(
    ("command", "tool", "args"),
    [
        ("open Spotify", "open_app", {"app_name": "Spotify"}),
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
        "open my latest email from Karthik",
        "What's the weather in Delhi",
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


@pytest.mark.parametrize(
    "script",
    [
        'tell application "Terminal" to activate',
        'tell app "Notes" to activate\ntell application id "com.apple.Terminal" to activate',
        'tell application "Notes" to do shell script "rm -rf ~"',
        'set x to "Terminal"\ntell application x to activate',
        'tell application "Music" to open location "file:///etc/passwd"',
        "beep",
    ],
)
def test_applescript_outside_the_allow_list_is_refused(script):
    with pytest.raises(ToolError):
        check_applescript_allowed(script)


def test_applescript_for_allowed_app_passes():
    check_applescript_allowed('tell application "Music" to playpause')


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "localhost"])
def test_non_web_urls_are_refused(url):
    with pytest.raises(ToolError):
        normalise_url(url)
