"""The snapshot ref parser and Guard 2's ref check (AGENTS.md §5: parsers and the gate).

Sample lines are taken verbatim from the Phase A spike captures in logs/spikes/snapshots/.
"""

from __future__ import annotations

import pytest

from zoya.tools import ToolError
from zoya.tools.browser import Ref, _same_control, click_ref, parse_ref_line, parse_refs

AMAZON = """- searchbox "Search Amazon.in" [ref=e430]: wireless mouse
- heading "Portronics Toad 23 Wireless Optical Mouse, USB Nano" [level=2, ref=e690]
- generic "Add to cart" [ref=e826] clickable [cursor:pointer]
  - button "Add to cart" [ref=e898]
- combobox [expanded=false, ref=e650]: All Categories
  - option "All Categories" [selected, ref=e853]
- StaticText "1,299"
- paragraph
"""

SPOTIFY = """- combobox "What do you want to play?" [expanded=false, ref=e1306]
- gridcell "1 Play Love Me Not by Ravyn Lenae" [ref=e1377]
  - button "Play Love Me Not by Ravyn Lenae" [ref=e1568]
- button [ref=e1214]
"""


def test_parses_role_name_and_ref():
    node = parse_ref_line('- button "Add to cart" [ref=e898]')

    assert (node.ref, node.role, node.name) == ("e898", "button", "Add to cart")


def test_parses_the_value_after_the_ref():
    node = parse_ref_line('- searchbox "Search Amazon.in" [ref=e430]: wireless mouse')

    assert node.value == "wireless mouse"


def test_reads_the_ref_past_other_attributes():
    node = parse_ref_line('- heading "Portronics Toad 23" [level=2, ref=e690]')

    assert node.ref == "e690"


def test_marks_a_clickable_wrapper():
    node = parse_ref_line('- generic "Add to cart" [ref=e826] clickable [cursor:pointer]')

    assert node.clickable is True
    assert node.name == "Add to cart"


def test_reads_an_unnamed_control():
    node = parse_ref_line("- button [ref=e1214]")

    assert (node.ref, node.name, node.identity()) == ("e1214", "", "button")


def test_ignores_lines_with_no_ref():
    assert parse_ref_line('- StaticText "1,299"') is None
    assert parse_ref_line("- paragraph") is None
    assert parse_ref_line("") is None


def test_parses_a_whole_snapshot():
    refs = parse_refs(AMAZON + SPOTIFY)

    assert set(refs) == {
        "e430",
        "e690",
        "e826",
        "e898",
        "e650",
        "e853",
        "e1306",
        "e1377",
        "e1568",
        "e1214",
    }
    assert refs["e1377"].role == "gridcell"
    assert refs["e1568"].name == "Play Love Me Not by Ravyn Lenae"


# --- Guard 2 on a ref ---------------------------------------------------------------------------


def button(name: str, ref: str = "e898") -> Ref:
    return Ref(ref=ref, role="button", name=name, value="", clickable=True, line="")


def test_the_approved_identity_matches_the_same_control():
    assert _same_control(button("Add to cart"), 'button "Add to cart"')


def test_a_bare_accessible_name_matches_too():
    assert _same_control(button("Add to cart"), "Add to cart")


def test_a_different_name_under_the_same_ref_is_refused():
    assert not _same_control(button("Place order"), 'button "Add to cart"')


def test_a_different_role_under_the_same_name_is_refused():
    link = Ref(ref="e898", role="link", name="Add to cart", value="", clickable=True, line="")

    assert not _same_control(link, 'button "Add to cart"')


def test_an_empty_approval_never_matches():
    assert not _same_control(button("Add to cart"), "")


def _snapshot_probe(monkeypatch, snapshot: str):
    """click_ref's one agent-browser call, answered with a snapshot and nothing focusable."""
    answers = [
        {"success": True, "result": {"url": "https://www.amazon.in/s"}},
        {"success": True, "result": {"title": "Amazon.in"}},
        {"success": True, "result": {"snapshot": snapshot}},
        {"success": False, "result": {}},
        {"success": True, "result": {"result": "{}"}},
    ]
    monkeypatch.setattr("zoya.tools.browser._agent_browser_batch", lambda commands: answers)
    monkeypatch.setattr(
        "zoya.tools.browser._agent_browser",
        lambda *a, **k: pytest.fail("Guard 2 let a rejected ref through to a click"),
    )


def test_guard_2_rejects_a_stale_ref(monkeypatch):
    _snapshot_probe(monkeypatch, SPOTIFY)

    with pytest.raises(ToolError) as refused:
        click_ref("e898", 'button "Add to cart"')

    assert "isn't on the page any more" in str(refused.value)


def test_guard_2_rejects_a_ref_whose_name_changed(monkeypatch):
    _snapshot_probe(monkeypatch, '- button "Place order" [ref=e898]')

    with pytest.raises(ToolError) as refused:
        click_ref("e898", 'button "Add to cart"')

    assert "Place order" in str(refused.value)
