"""Shopping money and cart decisions, parsers and recipe-cache refusal rules (D37)."""

from __future__ import annotations

import pytest

from zoya import cache, harness, recipes
from zoya.skills.shopping import actions as shopping
from zoya.tools import ToolError

CART = [
    "THE 48 LAWS OF POWER",
    "Oral-B Pro 3 Rechargeable Rotating Electric Toothbrush",
    "Hawkins Classic 1.5 Litre Aluminium Pressure Cooker",
    "Hawkins Contura 2 Litre Pressure Cooker",
]


def test_cart_removal_picks_the_one_line_the_user_named():
    assert shopping.match_cart_item(CART, "48 laws of power") == 0
    assert shopping.match_cart_item(CART, "the toothbrush") == 1


@pytest.mark.parametrize("item", ["pressure cooker", "Hawkins"])
def test_cart_removal_never_guesses_between_several_lines(item):
    with pytest.raises(shopping.FinalAnswer, match="Several"):
        shopping.match_cart_item(CART, item)


@pytest.mark.parametrize("item", ["headphones", "the", ""])
def test_cart_removal_refuses_an_item_that_isnt_there_or_has_no_name(item):
    with pytest.raises(ToolError):
        shopping.match_cart_item(CART, item)


@pytest.mark.parametrize(
    ("summary", "total"),
    [
        (
            "Items: ₹399.00 Delivery: ₹40.00 Promotion applied: -₹40.00 Order Total: ₹399.00",
            "₹399.00",
        ),
        ("Bill Summary Items total ₹291 Handling fee ₹10 To pay ₹253 Place Order", "₹253"),
        ("Order total ₹ 2,440.00", "₹2,440.00"),
        ("Items: ₹399.00 Delivery: ₹40.00", ""),
    ],
)
def test_order_total_reads_the_payable_amount_only(summary, total):
    assert shopping.order_total(summary) == total


def test_buying_skips_sponsored_ads():
    results = [{"sponsored": "yes"}, {"sponsored": ""}, {"sponsored": ""}]

    assert shopping.pick_result(results) == 2
    assert shopping.pick_result([{"sponsored": "yes"}]) == 1
    with pytest.raises(ToolError):
        shopping.pick_result([])


@pytest.mark.parametrize(
    ("command", "action", "args"),
    [
        (
            "buy this book 48 Loss of Power from Amazon",
            "amazon_buy",
            {"query": "book 48 Loss of Power"},
        ),
        (
            "I wanted to order eggs from Amazon. Can you please do that",
            "amazon_buy",
            {"query": "eggs"},
        ),
        ("remove the headphones from my amazon cart", "amazon_cart_remove", {"item": "headphones"}),
    ],
)
def test_owner_commands_reach_shopping_actions_without_a_model(command, action, args):
    assert harness.match_trigger(command) == harness.SkillMatch("shopping", action, args)


@pytest.mark.parametrize(
    "intent", ["place order", "pay now", "buy now", "proceed to checkout", "confirm", "sign in", ""]
)
def test_recipes_never_remember_paying_confirming_or_signing_in(intent, tmp_path, monkeypatch):
    monkeypatch.setattr(recipes, "RECIPES_FILE", tmp_path / "recipes.json")

    recipes.record("www.amazon.in", intent, "fast_path")

    assert recipes.ordered("www.amazon.in", intent, ["slow", "fast_path"]) == ["slow", "fast_path"]


def test_recipes_replay_the_last_winner_first_per_site(tmp_path, monkeypatch):
    monkeypatch.setattr(recipes, "RECIPES_FILE", tmp_path / "recipes.json")
    calls = []

    def strategy(name, found):
        return lambda: calls.append(name) or found

    recipes.first_found(
        "www.amazon.in",
        "add to cart",
        {"row": strategy("row", None), "panel": strategy("panel", "el")},
    )
    calls.clear()
    winner = recipes.first_found(
        "www.amazon.in",
        "Add to  Cart",
        {"row": strategy("row", None), "panel": strategy("panel", "el")},
    )

    assert winner == ("panel", "el") and calls == ["panel"]
    assert recipes.ordered("other.example", "add to cart", ["row", "panel"]) == ["row", "panel"]


@pytest.mark.parametrize(
    "name", ["amazon_buy", "amazon_buy_now", "amazon_cart_remove", "amazon_add_to_cart"]
)
def test_results_cache_refuses_shopping_actions(name):
    cache.put(name, {"query": "eggs"}, "cached", ttl_s=60)

    assert cache.get(name, {"query": "eggs"}) is None


@pytest.mark.parametrize(
    ("path", "control", "verdict"),
    [
        ("/checkout/p/p-404-6769146-9165111/pay", False, "payment_step"),
        ("/checkout/p/p-404-6769146-9165111/offers", False, "payment_step"),
        ("/checkout/p/p-404-6769146-9165111/pay/thankyou", False, "order_placed"),
        ("/checkout/p/p-404-6769146-9165111/spc", True, "ok"),
        ("/gp/cart/view.html", False, "unexpected"),
    ],
)
def test_newer_amazon_checkout_payment_step_is_recognised(path, control, verdict):
    state = shopping.CheckoutState(
        "www.amazon.in", path, "Payment method Use this payment method", control
    )

    assert shopping.checkout_verdict(state) == verdict
