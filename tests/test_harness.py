"""Phase 4 harness (D37: parsers and safety paths only): trigger index, URL templates, track and
channel pickers, skill risk inheritance, the result cache, learned picks, Flow 10 "done"."""

import re
from pathlib import Path

import pytest

from zoya import cache, harness, router, safety
from zoya.skills.shopping import actions as shopping
from zoya.skills.spotify_web import actions as spotify
from zoya.skills.youtube import actions as youtube
from zoya.tools import ToolError, handoff

# --- Trigger index (parser) --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "action", "args"),
    [
        ("Open the MrBeast channel on YouTube", "youtube_open_channel", {"name": "MrBeast"}),
        ("open MrBeast's channel", "youtube_open_channel", {"name": "MrBeast"}),
        ("open youtube MrBeast", "youtube_open_channel", {"name": "MrBeast"}),
        ("open MrBeast on YouTube", "youtube_open_channel", {"name": "MrBeast"}),
        ("play Love Me Not on Spotify", "spotify_play_song", {"song": "Love Me Not"}),
        (
            "play the song Love Me Not by Ravyn Lenae on spotify",
            "spotify_play_song",
            {"song": "Love Me Not", "artist": "Ravyn Lenae"},
        ),
        ("play Escape 100 Cops on YouTube", "youtube_play_video", {"title": "Escape 100 Cops"}),
        ("search lofi beats on youtube", "youtube_search", {"query": "lofi beats"}),
        ("what's the weather in New Delhi", "get_weather", {"city": "New Delhi"}),
        ("search for basmati rice on amazon", "amazon_search", {"query": "basmati rice"}),
    ],
)
def test_triggers_capture_the_action_and_slots(command, action, args):
    match = harness.match_trigger(command)

    assert (match.action, match.args) == (action, args)


@pytest.mark.parametrize(
    "command", ["open youtube", "open youtube music", "play music on spotify", "open spotify"]
)
def test_triggers_leave_plain_app_commands_alone(command):
    decision = router.route(command)

    assert decision.route == "fast"


def test_skill_route_uses_no_model_call():
    decision = router.route("Open the MrBeast channel on YouTube")

    assert (decision.route, decision.source, decision.skill) == ("skill", "trigger", "youtube")
    assert "model_ms" not in decision.timings_ms


def test_a_trigger_naming_an_unknown_argument_is_rejected(monkeypatch):
    bad = harness.Skill(
        "bad",
        "bad",
        metadata={"triggers": [{"action": "get_weather", "pattern": "^w (?P<town>.+)$"}]},
    )
    monkeypatch.setattr(harness, "catalog", lambda: {"bad": bad})
    harness.trigger_index.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            harness.trigger_index()
    finally:
        harness.trigger_index.cache_clear()


# --- URL templates and pickers (parsers) ----------------------------------------------------------


def test_url_templates_encode_the_query():
    assert youtube.search_url("Mr Beast & co") == (
        "https://www.youtube.com/results?search_query=Mr+Beast+%26+co"
    )
    assert spotify.search_url("Love Me Not/2") == (
        "https://open.spotify.com/search/Love%20Me%20Not%2F2/tracks"
    )
    assert shopping.search_url("amul milk 1l") == "https://www.amazon.in/s?k=amul+milk+1l"


def test_product_url_only_takes_a_real_asin():
    assert shopping.product_url("B07XJ8C8F5") == "https://www.amazon.in/dp/B07XJ8C8F5"
    with pytest.raises(ToolError):
        shopping.product_url("../gp/buy")


def test_checkout_summary_keeps_items_and_bill_not_address_or_ads():
    page = (
        "16 mins Asha, Flat 1, Main Rd, 560001 Review your items 3 items Brown Bread 1 ₹ 69 "
        "Eggs 12 Pcs 1 ₹ 97 Add more items You might have missed Paneer ₹128 Bill Summary Items "
        "total ₹291 Handling fee ₹10 To pay ₹253 Place Order"
    )

    summary = shopping.checkout_summary(page)

    assert "Brown Bread" in summary and "To pay ₹253" in summary
    assert "560001" not in summary and "Paneer" not in summary


LABELS = [
    "Play Love Me Not (feat. Rex Orange County) by Ravyn Lenae, Rex Orange County",
    "Play her by JVKE",
    "Play Love Me Not by Ravyn Lenae",
    "Play Love Me Not - Slowed + Reverb by NovaX, Sevven",
]


def test_track_picker_prefers_the_exact_title():
    assert spotify.pick_track("Love Me Not", "", LABELS) == 0  # "(feat. …)" is ignored
    assert spotify.pick_track("love me not", "Ravyn Lenae", LABELS[1:]) == 1


def test_track_picker_respects_the_artist_and_refuses_no_match():
    assert spotify.pick_track("Love Me Not", "NovaX", LABELS) == 3
    assert spotify.pick_track("Blinding Lights", "", LABELS) is None


def test_channel_picker_matches_the_name_else_the_top_result():
    rows = [("MrBeast @MrBeast•517M", "/@MrBeast"), ("MrBeast Gaming", "/@MrBeastGaming")]

    assert youtube.best_match("mrbeast gaming", rows)[1] == "/@MrBeastGaming"
    assert youtube.best_match("Mr Beast", rows)[1] == "/@MrBeast"


# --- Skill risk inheritance (safety) --------------------------------------------------------------


@pytest.fixture
def actions_agent(monkeypatch):
    """The Layer 1 agent never calls its model; it only needs one to exist."""
    monkeypatch.setenv("ROUTER_MODEL", "unused")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    harness._actions_agent.cache_clear()
    yield
    harness._actions_agent.cache_clear()


def test_every_skill_action_has_an_explicit_risk_class():
    assert [n for n in harness.action_tools() if n not in safety.TOOL_RISK] == []


def test_every_skill_tool_listed_in_skill_md_exists():
    for name in harness.catalog():
        assert [t for t in harness.skill_tool_names(name) if t not in harness.all_tools()] in (
            [],
            ["narrate"],
        )


CLICKING = re.compile(r"click_checked|confirm_then_click|\.click\(")


def test_recipes_that_click_are_never_free():
    """A recipe's source that clicks → its tools must be guarded (the guard lives in the action)."""
    for actions in Path("zoya/skills").glob("*/actions.py"):
        source = actions.read_text()
        for block in re.split(r"\n@tool\n", source)[1:]:
            name = re.match(r"def (\w+)", block)[1]
            if CLICKING.search(block):
                assert safety.risk_of(name) != "free", name


def test_skill_metadata_cannot_lower_risk():
    """SKILL.md has no say: allowed_tools/metadata are text, TOOL_RISK is code."""
    for skill in harness.catalog().values():
        assert "risk" not in skill.metadata
        assert skill.allowed_tools is None


@pytest.mark.parametrize(
    "label", ["Place your order", "Subscribe to MrBeast.", "Comment", "like this video", "Reply"]
)
def test_known_final_buttons_are_risky(label):
    assert safety.risky_label([label]) is not None


def test_add_to_cart_is_safe_only_on_amazon_with_that_exact_name():
    cart = safety.ClickFacts(["Add to Cart"], is_submit=True, path="/dp/B0", host="www.amazon.in")

    assert safety.click_risk(cart) is None
    assert safety.click_risk(safety.ClickFacts(**{**cart.__dict__, "host": "amazon.in.evil.test"}))
    assert safety.click_risk(
        safety.ClickFacts(**{**cart.__dict__, "labels": ["Add to Cart", "Buy Now"]})
    )
    assert safety.click_risk(
        safety.ClickFacts(**{**cart.__dict__, "labels": ["Add to Cart", "Place your order"]})
    )


def test_direct_skill_call_without_the_voice_loop_publishes_nothing(monkeypatch, actions_agent):
    """Layer 1 path to a publishing recipe: the in-action token check refuses (no voice channel)."""
    clicked = []
    target = type("T", (), {"facts": safety.ClickFacts(["Subscribe to MrBeast."])})()
    monkeypatch.setattr(youtube.browser, "on_page", lambda work: target)
    monkeypatch.setattr(youtube.browser, "_on_browser", lambda call: target)
    monkeypatch.setattr(youtube.browser, "_click", clicked.append)
    safety._reset_for_tests()

    with pytest.raises(ToolError):
        harness.run_action("youtube_subscribe", {})

    assert clicked == []


def test_direct_call_after_a_decline_ends_the_task(monkeypatch, actions_agent):
    safety._reset_for_tests()
    monkeypatch.setattr(safety, "task_declined", lambda: True)

    with pytest.raises(safety.ConfirmationDeclined):
        harness.run_action("get_time", {})


# --- Result cache and learned picks (never money, send, post, delete) -----------------------------


@pytest.mark.parametrize(
    "name",
    ["amazon_place_order", "amazon_add_to_cart", "youtube_comment", "youtube_subscribe", "unknown"],
)
def test_risky_or_unknown_results_are_never_cached(name):
    cache.clear()
    cache.put(name, {"x": 1}, "done", ttl_s=60)

    assert cache.get(name, {"x": 1}) is None


def test_free_results_are_cached_until_the_ttl(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cache, "_now", lambda: now[0])
    cache.clear()
    cache.put("get_weather", {"city": "Delhi"}, "sunny", ttl_s=60)

    assert cache.get("get_weather", {"city": " delhi "}) == "sunny"
    now[0] += 61
    assert cache.get("get_weather", {"city": "Delhi"}) is None


def test_publishing_picks_are_never_learned(monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "LEARNED_PICKS_FILE", tmp_path / "picks.json")
    harness.learn_pick("subscribe please", harness.SkillMatch("youtube", "youtube_subscribe"))
    harness.learn_pick(
        "mrbeast pls", harness.SkillMatch("youtube", "youtube_open_channel", {"name": "MrBeast"})
    )

    assert harness.learned_pick("subscribe please") is None
    assert harness.learned_pick("MrBeast pls").args == {"name": "MrBeast"}


# --- Flow 10: "done" ------------------------------------------------------------------------


def test_done_resumes_only_a_pending_handoff(monkeypatch):
    handoff._pending.clear()
    assert router.match_rules("done") is None

    handoff._pending.update(command="order my usual groceries", at=__import__("time").monotonic())
    decision = router.route("I'm done")

    assert decision.route == "orchestrator"
    assert decision.text.endswith("order my usual groceries")
    assert handoff.pending_handoff() is None  # consumed once


@pytest.mark.parametrize("reply", ["done", "I'm done", "signed in", "ho gaya"])
def test_done_is_never_a_confirmation(reply):
    assert safety.classify_reply(reply) != "confirm"
