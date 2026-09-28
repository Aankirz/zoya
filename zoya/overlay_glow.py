"""While Zoya acts: a breathing glow around the window she is working in, and her own cursor
gliding to each target with a ripple on the click (D145). Both are click-through panels in the
overlay's process, so `screen.own_pids` keeps them out of her screenshots, OCR and evidence.
They only draw; nothing here waits on them, and the user's real pointer is never touched."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from typing import Any

import AppKit
import Quartz
from PyObjCTools import AppHelper

from zoya.overlay_pill import oklch

GLOW_PT = 12.0
GLOW_RADIUS = 12.0
GLOW_LINE_PT = 3.0
BREATHE_S = 2.4
BREATHE_LOW = 0.55
HANDED_BACK = 0.3
QUIET_S = 1.5
FOLLOW_S = 0.5
FADE_S = 0.2
GLIDE_S = 0.25
RIPPLE_S = 0.45
RIPPLE_PT = 34.0
CURSOR_PT = (26.0, 30.0)
CURSOR_TIP = (3.0, 29.0)
EASE = (0.22, 1.0, 0.36, 1.0)
GLOW_BLUE = oklch(0.75, 0.12, 253)
GLOW_WAIT = oklch(0.62, 0.15, 70)
CURSOR_TOP, CURSOR_BOTTOM = oklch(0.81, 0.095, 250), oklch(0.56, 0.13, 255)
CURSOR_EDGE = oklch(0.99, 0.01, 240, 0.95)
CURSOR_INK = oklch(0.15, 0.005, 260)
WEB_TOOLS = ("browser", "amazon", "youtube", "spotify", "web", "x ", "hotels")
GLOWING = frozenset({"acting", "thinking", "waiting"})
ARROW = (
    (0.0, 0.0),
    (0.0, 22.0),
    (6.0, 17.0),
    (10.0, 26.0),
    (13.5, 24.5),
    (9.5, 15.8),
    (17.0, 15.8),
)


def window_at(point: tuple[float, float], windows: Iterable[dict], own: set[int]) -> dict | None:
    """The frontmost ordinary window under a top-left-origin point, never one of Zoya's own.
    CGWindowList lists windows front to back."""
    x, y = point
    for window in windows:
        if window.get("kCGWindowLayer") != 0 or window.get("kCGWindowOwnerPID") in own:
            continue
        b = window.get("kCGWindowBounds") or {}
        if b.get("X", 0) <= x <= b.get("X", 0) + b.get("Width", 0) and b.get("Y", 0) <= y <= b.get(
            "Y", 0
        ) + b.get("Height", 0):
            return window
    return None


def target_for(
    tool: str, point: tuple[float, float], windows: list[dict], own: set[int], chrome: int | None
) -> dict | None:
    """A web tool works in Zoya's Chrome even when another window covers the point."""
    if is_web(tool) and chrome and (window := largest_of(chrome, windows)):
        return window
    return window_at(point, windows, own)


def largest_of(pid: int, windows: Iterable[dict]) -> dict | None:
    """The app's main window: its biggest ordinary one."""
    mine = [
        w for w in windows if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer") == 0
    ]

    def area(window: dict) -> float:
        b = window["kCGWindowBounds"]
        return b["Width"] * b["Height"]

    return max(mine, key=area, default=None)


def is_web(tool: str) -> bool:
    return tool.replace("_", " ").startswith(WEB_TOOLS)


def _on_screen() -> list[dict]:
    return list(
        Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, 0
        )
        or []
    )


def _chrome_pid() -> int | None:
    from zoya.config import CHROME_PID_FILE

    try:
        return int(CHROME_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def _flip(rect: tuple[float, float, float, float]) -> tuple[tuple, tuple]:
    """Top-left-origin global rect to AppKit's bottom-left origin."""
    x, y, width, height = rect
    main_height = AppKit.NSScreen.screens()[0].frame().size.height
    return ((x, main_height - y - height), (width, height))


def _cg(rgba: tuple[float, ...], alpha: float | None = None) -> Any:
    red, green, blue, base = rgba
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
        red, green, blue, base if alpha is None else alpha
    ).CGColor()


def _ease() -> Any:
    return Quartz.CAMediaTimingFunction.functionWithControlPoints____(*EASE)


def _arrow_path() -> Any:
    path = Quartz.CGPathCreateMutable()
    height = CURSOR_PT[1]
    first, *rest = ARROW
    Quartz.CGPathMoveToPoint(path, None, first[0] + 3, height - 1 - first[1])
    for x, y in rest:
        Quartz.CGPathAddLineToPoint(path, None, x + 3, height - 1 - y)
    Quartz.CGPathCloseSubpath(path)
    return path


class Glow:
    def __init__(self, make_panel: Callable[[Any], Any], reduce_motion: Callable[[], bool]) -> None:
        self.make_panel, self.reduce_motion = make_panel, reduce_motion
        self.own: set[int] = set()
        self.state, self.tool = "idle", ""
        self.target: dict | None = None
        self.app = ""
        self.last_input = 0.0
        self.panel = self.edge = self.cursor = None
        self.following = False
        self.active = False

    # --- what Zoya is doing -------------------------------------------------------------------

    def update(self, state: str, tool: str) -> None:
        self.state = state
        if tool:
            self.tool = tool
        if state not in GLOWING:
            self.stop()
            return
        if state == "acting":
            self.active = True
        if state == "acting" and self.target is None:
            self._aim(self._first_target())
        self._draw()

    def point_at(self, rect: list[float]) -> None:
        """A click or type is 0.25 s away at this top-left-origin rect: glow its window, glide."""
        x, y, width, height = rect
        centre = (x + width / 2, y + height / 2)
        window = target_for(self.tool, centre, _on_screen(), self.own, _chrome_pid())
        self._aim(window or self.target)
        self._draw()
        self._glide(centre)

    def user_input(self) -> None:
        self.last_input = time.monotonic()
        self._draw()

    def stop(self) -> None:
        self.target, self.app, self.tool, self.active = None, "", "", False
        for panel in (self.panel, self.cursor):
            if panel is not None:
                panel.orderOut_(None)

    # --- choosing the window ------------------------------------------------------------------

    def _first_target(self) -> dict | None:
        windows = _on_screen()
        if is_web(self.tool) and (pid := _chrome_pid()):
            return largest_of(pid, windows)
        front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        pid = front.processIdentifier() if front else None
        return None if pid is None or pid in self.own else largest_of(pid, windows)

    def _aim(self, window: dict | None) -> None:
        self.target = window
        self.app = str(window.get("kCGWindowOwnerName", "")) if window else ""
        if window is not None and not self.following:
            self.following = True
            AppHelper.callLater(FOLLOW_S, self._follow)

    def _follow(self) -> None:
        if self.target is None:
            self.following = False
            return
        number = self.target.get("kCGWindowNumber")
        fresh = next((w for w in _on_screen() if w.get("kCGWindowNumber") == number), None)
        self.target = fresh or self.target
        self._draw()
        AppHelper.callLater(FOLLOW_S, self._follow)

    # --- drawing ------------------------------------------------------------------------------

    def _frame(self) -> tuple[tuple, tuple]:
        if self.target is not None:
            b = self.target["kCGWindowBounds"]
            (x, y), (width, height) = _flip((b["X"], b["Y"], b["Width"], b["Height"]))
            return ((x - GLOW_PT, y - GLOW_PT), (width + 2 * GLOW_PT, height + 2 * GLOW_PT))
        screen = AppKit.NSScreen.mainScreen().frame()
        return ((screen.origin.x, screen.origin.y), (screen.size.width, screen.size.height))

    def handed_back(self) -> bool:
        return time.monotonic() - self.last_input < QUIET_S

    def _draw(self) -> None:
        if self.state not in GLOWING or not self.active:
            return
        frame = self._frame()
        if self.panel is None:
            self.panel = self.make_panel(frame)
            view = AppKit.NSView.alloc().initWithFrame_(((0, 0), frame[1]))
            view.setWantsLayer_(True)
            self.edge = Quartz.CALayer.layer()
            view.layer().addSublayer_(self.edge)
            self.panel.setContentView_(view)
        self.panel.setFrame_display_(frame, False)
        self._paint(frame[1])
        self.panel.orderFrontRegardless()
        if self.cursor is not None:
            self.cursor.setAlphaValue_(0.0 if self.handed_back() else 1.0)

    def _paint(self, size: tuple) -> None:
        tone = GLOW_WAIT if self.state == "waiting" else GLOW_BLUE
        inset = GLOW_PT - GLOW_LINE_PT if self.target is not None else GLOW_LINE_PT
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        self.edge.setFrame_(((inset, inset), (size[0] - 2 * inset, size[1] - 2 * inset)))
        self.edge.setCornerRadius_(GLOW_RADIUS)
        self.edge.setBorderWidth_(GLOW_LINE_PT)
        self.edge.setBorderColor_(_cg(tone))
        self.edge.setShadowColor_(_cg(tone))
        self.edge.setShadowOpacity_(1.0)
        self.edge.setShadowRadius_(GLOW_PT * 0.75)
        self.edge.setShadowOffset_((0, 0))
        self.edge.setOpacity_(HANDED_BACK if self.handed_back() else 1.0)
        Quartz.CATransaction.commit()
        breathing = self.edge.animationForKey_("breathe") is not None
        if self.reduce_motion() or self.handed_back():
            self.edge.removeAnimationForKey_("breathe")
        elif not breathing:
            pulse = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
            pulse.setFromValue_(1.0)
            pulse.setToValue_(BREATHE_LOW)
            pulse.setDuration_(BREATHE_S / 2)
            pulse.setAutoreverses_(True)
            pulse.setRepeatCount_(math.inf)
            pulse.setTimingFunction_(_ease())
            self.edge.addAnimation_forKey_(pulse, "breathe")

    # --- the cursor ---------------------------------------------------------------------------

    def _make_cursor(self, at: tuple) -> None:
        self.cursor = self.make_panel((at, CURSOR_PT))
        view = AppKit.NSView.alloc().initWithFrame_(((0, 0), CURSOR_PT))
        view.setWantsLayer_(True)
        body = Quartz.CAGradientLayer.layer()
        body.setFrame_(((0, 0), CURSOR_PT))
        body.setColors_([_cg(CURSOR_TOP), _cg(CURSOR_BOTTOM)])
        shape = Quartz.CAShapeLayer.layer()
        shape.setPath_(_arrow_path())
        body.setMask_(shape)
        edge = Quartz.CAShapeLayer.layer()
        edge.setPath_(_arrow_path())
        edge.setFillColor_(None)
        edge.setStrokeColor_(_cg(CURSOR_EDGE))
        edge.setLineWidth_(1.5)
        edge.setShadowColor_(_cg(CURSOR_INK))
        edge.setShadowOpacity_(0.35)
        edge.setShadowRadius_(2.0)
        edge.setShadowOffset_((0, -1))
        view.layer().addSublayer_(body)
        view.layer().addSublayer_(edge)
        for x in (5.2, 8.4):
            eye = Quartz.CALayer.layer()
            eye.setFrame_(((x, CURSOR_PT[1] - 15.0), (1.6, 3.2)))
            eye.setCornerRadius_(0.8)
            eye.setBackgroundColor_(_cg(CURSOR_INK))
            view.layer().addSublayer_(eye)
        self.cursor.setContentView_(view)

    def _origin(self, centre: tuple[float, float]) -> tuple[float, float]:
        (x, y), _ = _flip((centre[0], centre[1], 0.0, 0.0))
        return (x - CURSOR_TIP[0], y - CURSOR_TIP[1])

    def _glide(self, centre: tuple[float, float]) -> None:
        end = self._origin(centre)
        if self.cursor is None:
            (fx, fy), (fw, fh) = self._frame()
            self._make_cursor((fx + fw / 2, fy + fh / 2))
        self.cursor.orderFrontRegardless()
        self.cursor.setAlphaValue_(0.0 if self.handed_back() else 1.0)
        if self.reduce_motion():
            self.cursor.setFrameOrigin_(end)
            return

        def move(context: Any) -> None:
            context.setDuration_(GLIDE_S)
            context.setTimingFunction_(_ease())
            self.cursor.animator().setFrame_display_((end, CURSOR_PT), True)

        AppKit.NSAnimationContext.runAnimationGroup_completionHandler_(
            move, lambda: self._ripple(centre)
        )

    def _ripple(self, centre: tuple[float, float]) -> None:
        if self.state not in GLOWING or self.handed_back():
            return
        (x, y), _ = _flip((centre[0], centre[1], 0.0, 0.0))
        half = RIPPLE_PT / 2
        panel = self.make_panel(((x - half, y - half), (RIPPLE_PT, RIPPLE_PT)))
        view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (RIPPLE_PT, RIPPLE_PT)))
        view.setWantsLayer_(True)
        ring = Quartz.CALayer.layer()
        ring.setFrame_(((0, 0), (RIPPLE_PT, RIPPLE_PT)))
        ring.setCornerRadius_(half)
        ring.setBorderWidth_(2.0)
        ring.setBorderColor_(_cg(GLOW_BLUE))
        ring.setOpacity_(0.0)
        view.layer().addSublayer_(ring)
        panel.setContentView_(view)
        panel.orderFrontRegardless()
        grow = Quartz.CABasicAnimation.animationWithKeyPath_("transform.scale")
        grow.setFromValue_(0.3)
        grow.setToValue_(1.0)
        fade = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
        fade.setFromValue_(0.9)
        fade.setToValue_(0.0)
        both = Quartz.CAAnimationGroup.animation()
        both.setAnimations_([grow, fade])
        both.setDuration_(RIPPLE_S)
        both.setTimingFunction_(_ease())
        ring.addAnimation_forKey_(both, "ripple")
        AppHelper.callLater(RIPPLE_S, panel.orderOut_, None)
