"""Zoya closes the tabs her task opened, and never a tab the user opened (Phase H)."""

from zoya.tools.browser import opened_by_zoya

WORKING = "work"


def tab(target: str, opener: str | None = None) -> dict[str, str]:
    return {"targetId": target, **({"openerId": opener} if opener else {})}


def test_tabs_a_page_opened_from_the_working_tab_are_closed_transitively() -> None:
    targets = [tab(WORKING), tab("popup", WORKING), tab("from-popup", "popup")]
    assert opened_by_zoya(targets, frozenset({WORKING}), WORKING) == {"popup", "from-popup"}


def test_a_tab_the_user_opened_is_never_closed() -> None:
    targets = [tab(WORKING), tab("user-cmd-t"), tab("user-link", "user-cmd-t")]
    assert opened_by_zoya(targets, frozenset({WORKING}), WORKING) == set()


def test_a_tab_open_before_the_task_is_never_closed() -> None:
    targets = [tab(WORKING), tab("earlier", WORKING)]
    assert opened_by_zoya(targets, frozenset({WORKING, "earlier"}), WORKING) == set()
