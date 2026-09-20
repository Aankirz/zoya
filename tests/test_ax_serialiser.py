"""The AX serialiser's two hard bounds (Phase A, Spike 4): a token budget and the web substrate.

Both are parsers in front of a 32k context. Safari's tree for one Wikipedia article measured
2,684 controls / 24,486 cl100k tokens — 76% of Jev's window — so a silent bug here is a decider
that sees a truncated page instead of an app, or no decision at all.
"""

from zoya.config import AX_CHARS_PER_TOKEN, AX_READ_TOKEN_BUDGET
from zoya.tools.ax import estimated_tokens, is_web_page, listed_line, spend

WIKIPEDIA = "https://en.wikipedia.org/wiki/Accessibility"
ELECTRON = "vscode-file://vscode-app/Applications/Cursor.app/Contents/Resources/app/out/index.html"


def test_token_estimate_never_undercounts_a_real_control_line():
    line = listed_line("AXButton", "Toggle Primary Side Bar (⌘B)")

    assert estimated_tokens(line) * AX_CHARS_PER_TOKEN >= len(line)


def test_budget_pays_for_short_controls_and_stops_before_it_is_exceeded():
    spent = 0
    for _ in range(10_000):
        affordable = spend(spent, "AXButton", "Play")
        if affordable is None:
            break
        spent = affordable

    assert spent <= AX_READ_TOKEN_BUDGET
    assert spend(spent, "AXButton", "Play") is None


def test_one_long_web_link_cannot_blow_the_whole_budget():
    link = "x" * (AX_READ_TOKEN_BUDGET * AX_CHARS_PER_TOKEN + 1)

    assert spend(0, "AXLink", link) is None


def test_a_web_page_is_the_browser_substrate_and_an_electron_bundle_is_not():
    assert is_web_page(WIKIPEDIA)
    assert is_web_page("http://localhost:3000/")
    assert not is_web_page(ELECTRON)
    assert not is_web_page("file:///Users/owner/report.pdf")
    assert not is_web_page("")
