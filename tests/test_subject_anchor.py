"""D138 (c): browser_click's confirmation subject anchors on the clicked element."""

from zoya import page_items, safety
from zoya.tools import browser

FILLER = "".join(f'- heading "Recommended video {n}" [level=3, ref=e{n}]\n' for n in range(10, 40))
CHANNEL = """\
- heading "MrBeast" [level=1, ref=e2]
- button "Subscribe" [ref=e3]
"""
PAGE = f'- heading "Home" [level=1, ref=e1]\n{CHANNEL}{FILLER}{FILLER.replace("ref=e", "ref=f")}'


def test_the_subject_is_read_around_the_control_that_was_clicked():
    ref = browser.anchor_ref(PAGE, "subscribe")
    names = [s.name for s in page_items.subject_candidates(PAGE, ref, "YouTube")]
    assert ref == "e3" and "MrBeast" in names


def test_without_the_anchor_the_middle_of_the_page_misses_it():
    names = [s.name for s in page_items.subject_candidates(PAGE, "", "YouTube")]
    assert "MrBeast" not in names


def test_a_control_the_snapshot_does_not_name_keeps_the_old_anchor():
    assert browser.anchor_ref(PAGE, "join") == ""
    assert browser.anchor_ref(PAGE, "") == ""


def target(kind_label: str) -> browser.Target:
    facts = safety.ClickFacts(labels=[kind_label], host="www.video.example")
    return browser.Target(None, facts, "MrBeast - Video", "www.video.example")


def subject_with(monkeypatch, kind: str, item: str) -> str:
    monkeypatch.setattr(browser, "page_subject", lambda *a, **k: "MrBeast")
    return browser._subject_for(safety.RiskyLabel(kind, kind), target(kind), item, "")


def test_a_subscribe_names_the_page_subject_even_when_the_brain_passes_an_item(monkeypatch):
    assert subject_with(monkeypatch, "post", "MrBeast (@MrBeast)") == "MrBeast"


def test_send_delete_and_purchase_keep_the_item_the_screen_verifies(monkeypatch):
    for kind in ("send", "delete"):
        assert subject_with(monkeypatch, kind, "Riya") == ""
    assert subject_with(monkeypatch, "purchase", "") == ""
