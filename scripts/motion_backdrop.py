"""A stand-in wallpaper for the motion harness: one borderless window behind the pill, so the
glass is recorded over a known light, dark or busy picture without touching the desktop picture.
It floats above ordinary windows and the recording never reaches past it, so nothing else on
the screen is captured.

    uv run python scripts/motion_backdrop.py daylight|night|vivid
"""

from __future__ import annotations

import sys
from typing import Any

import AppKit
from PyObjCTools import AppHelper

WIDTH_PT, HEIGHT_PT = 1120.0, 620.0
WALLPAPERS = {
    "daylight": ((0.80, 0.89, 0.98), (0.99, 0.97, 0.93), (0.93, 0.84, 0.74)),
    "night": ((0.02, 0.03, 0.08), (0.08, 0.10, 0.22), (0.20, 0.12, 0.28)),
    "vivid": ((0.95, 0.30, 0.20), (0.98, 0.80, 0.15), (0.10, 0.55, 0.85)),
}
STRIPES = 9


def _rgb(rgb: tuple[float, float, float]) -> Any:
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*rgb, 1.0)


class Picture(AppKit.NSView):
    def drawRect_(self, _rect: Any) -> None:  # noqa: N802 — AppKit override
        colors = [_rgb(c) for c in WALLPAPERS[self.name]]
        AppKit.NSGradient.alloc().initWithColors_(colors).drawInRect_angle_(self.bounds(), 70.0)
        if self.name != "vivid":
            return
        width = self.bounds().size.width / STRIPES
        for index in range(0, STRIPES, 2):
            _rgb((0.08, 0.08, 0.10) if index % 4 else (0.98, 0.98, 0.98)).setFill()
            AppKit.NSBezierPath.fillRect_(
                ((index * width, 0), (width / 2, self.bounds().size.height))
            )


def show(name: str) -> Any:
    screen = AppKit.NSScreen.mainScreen().frame()
    x = screen.origin.x + (screen.size.width - WIDTH_PT) / 2
    frame = ((x, screen.origin.y), (WIDTH_PT, HEIGHT_PT))
    window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False
    )
    picture = Picture.alloc().initWithFrame_(((0, 0), frame[1]))
    picture.name = name
    window.setContentView_(picture)
    window.setTitle_(f"motion backdrop {name}")
    window.setLevel_(AppKit.NSFloatingWindowLevel)
    window.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    window.setIgnoresMouseEvents_(True)
    window.orderFrontRegardless()
    return window


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "daylight"
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    window = show(name)
    print(f"backdrop {name} window {window.windowNumber()}", flush=True)
    AppHelper.runEventLoop(installInterrupt=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
