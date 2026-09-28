"""D145: Zoya's glow and cursor never land on her own windows, and never take a click or focus."""

from zoya import overlay, screen
from zoya.overlay_glow import is_web, largest_of, target_for, window_at


def _window(pid: int, x: float, y: float, w: float, h: float, layer: int = 0) -> dict:
    bounds = {"X": x, "Y": y, "Width": w, "Height": h}
    return {"kCGWindowOwnerPID": pid, "kCGWindowLayer": layer, "kCGWindowBounds": bounds}


def test_the_glow_takes_the_frontmost_window_under_the_target_but_never_zoyas_own():
    zoya_panel = _window(1, 0, 0, 500, 500)
    menu_bar = _window(9, 0, 0, 2000, 30, layer=25)
    chrome = _window(7, 0, 0, 1200, 800)
    notes = _window(8, 0, 0, 900, 700)
    listed = [menu_bar, zoya_panel, chrome, notes]
    assert window_at((100, 10), listed, own={1}) is chrome
    assert window_at((1500, 900), listed, own={1}) is None


def test_a_web_click_glows_zoyas_chrome_even_behind_the_users_terminal():
    terminal, chrome = _window(5, 0, 0, 1500, 900), _window(7, 0, 0, 1200, 800)
    listed = [terminal, chrome]
    assert target_for("browser click", (100, 100), listed, own={1}, chrome=7) is chrome
    assert target_for("ax press", (100, 100), listed, own={1}, chrome=7) is terminal


def test_the_main_window_is_the_apps_biggest_ordinary_one():
    small, big = _window(7, 0, 0, 300, 200), _window(7, 0, 0, 1200, 800)
    assert largest_of(7, [small, _window(7, 0, 0, 3000, 30, layer=3), big]) is big
    assert is_web("browser_click") and not is_web("ax_press")


def test_the_glow_and_cursor_panels_are_click_through_and_never_key():
    from zoya.overlay_app import _panel

    panel = _panel(((0, 0), (40, 40)))
    assert panel.ignoresMouseEvents()
    assert not panel.canBecomeKeyWindow() and not panel.canBecomeMainWindow()


def test_the_overlay_process_is_left_out_of_every_capture(monkeypatch):
    monkeypatch.setattr(overlay, "pids", lambda: {4242})
    assert 4242 in screen.own_pids()


def test_under_reduce_motion_the_glow_holds_still_and_the_cursor_jumps(monkeypatch):
    from zoya.overlay_app import _panel
    from zoya.overlay_glow import Glow

    off_screen = _window(7, -6000, -6000, 400, 300)
    monkeypatch.setattr(Glow, "_first_target", lambda _self: off_screen)
    glow = Glow(_panel, reduce_motion=lambda: True)
    glow.update("acting", "ax_press")
    assert glow.edge is not None and glow.edge.animationForKey_("breathe") is None
    glow._glide((-5000.0, -5000.0))
    assert tuple(glow.cursor.frame().origin) == glow._origin((-5000.0, -5000.0))
    glow.update("stopped", "")
    assert not glow.panel.isVisible() and not glow.cursor.isVisible()
