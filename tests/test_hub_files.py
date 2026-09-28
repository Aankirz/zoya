import re

import pytest

from zoya.overlay_pill import oklch

hub = pytest.importorskip("zoya.hub")


@pytest.mark.parametrize(
    "path",
    ["/../../etc/passwd", "/appicon/..%2F..%2Fetc", "/appicon/%2FSystem%2FLibrary", "/hub.py"],
)
def test_the_hub_serves_nothing_outside_its_files(path) -> None:  # noqa: ANN001
    assert hub._resource(path) is None


def test_an_app_icon_is_a_small_png() -> None:
    body, kind = hub._resource("/appicon/Finder")
    assert kind == "image/png" and body.startswith(b"\x89PNG") and len(body) < 64_000


def _css_bg(css: str, dark: bool) -> tuple[float, ...]:
    block = css.split("prefers-color-scheme: dark")[int(dark)]
    found = re.search(r"--bg: oklch\(([\d.]+)% ([\d.]+) ([\d.]+)\)", block)
    lightness, chroma, hue = found.groups()
    return oklch(float(lightness) / 100, float(chroma), float(hue))


@pytest.mark.parametrize("dark", [False, True])
def test_the_window_paints_the_page_colour_before_the_page(dark) -> None:  # noqa: ANN001
    css = (hub.HUB_DIR / "tokens.css").read_text()
    assert hub.hub_chrome.PAGE[int(dark)] == pytest.approx(_css_bg(css, dark), abs=1e-3)


def test_the_web_view_never_paints_its_own_white() -> None:
    view = hub.Hub(lambda _command: None)._web_view()
    assert not view.valueForKey_("drawsBackground")
