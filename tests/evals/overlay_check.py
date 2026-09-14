"""Phase 7 stage overlay checks on the demo Mac. No synthetic clicks or keys: safe beside the user.

  states   — every presence state in turn (Done-when #5/#6/#7: toggle Reduce Motion / Reduce
             Transparency / Increase Contrast between runs, light and dark, on the projector),
             with sample captions, a named task waiting for yes, and a ring on screen centre.
  capture  — proof the overlay and ring never reach a model: pixel diffs of the panel/ring region
             through screen.display_filter (what capture_display / capture_region_jpeg use) vs an
             unfiltered filter, and a desktop-independent window capture (the Phase 3 OCR check)
             of the window under the ring. Prints numbers only; never saves the user's screen.

Usage: .venv/bin/python -u tests/evals/overlay_check.py states|capture
An eval, not a pytest. The overlay's own latency line lands in logs/overlay.log on exit.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

import numpy as np

from zoya import events, overlay, screen

STATE_HOLD_S = 3.0
RING = (120, 60)


def states() -> None:
    steps: list[tuple[str, events.Event]] = [
        ("idle", events.TaskEvent("t1", "done", "", "orchestrator")),
        ("listening", events.EarconEvent("listening")),
        (
            "user caption",
            events.OverlayEvent("Order my usual groceries", "listening", {"role": "user"}),
        ),
        ("thinking", events.EarconEvent("working")),
        (
            "thinking + step",
            events.OverlayEvent("checking the cart total", "working", {"task": ""}),
        ),
        ("acting", events.OverlayEvent("", "working", {"tool": "browser click", "task": ""})),
        ("speaking", events.NarrateEvent("Your cart has 3 items for 243 rupees.")),
        ("secret caption", events.NarrateEvent("Please type the OTP 482913 yourself.")),
        ("waiting for yes", events.ConfirmationEvent("t1", "Place the order for 243 rupees?")),
        ("stopped", events.EarconEvent("stop")),
        ("error", events.EarconEvent("error")),
    ]
    for label, event in steps:
        print(label)
        events.emit(event)
        if isinstance(event, events.NarrateEvent):
            time.sleep(STATE_HOLD_S)
            events.emit(events.OverlayEvent("", "idle", {"speech": "done"}))
        time.sleep(STATE_HOLD_S)
    print("ring at screen centre")
    width, height = _main_size()
    overlay.show_ring(width / 2 - RING[0] / 2, height / 2 - RING[1] / 2, *RING)
    time.sleep(STATE_HOLD_S)


def _main_size() -> tuple[float, float]:
    import AppKit

    frame = AppKit.NSScreen.screens()[0].frame()
    return frame.size.width, frame.size.height


def _content() -> Any:
    import ScreenCaptureKit as SCK

    return screen._await(
        lambda h: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(  # noqa: E501
            True, True, h
        )
    )[0]


def _pixels(image: Any, width: float) -> np.ndarray:
    import Quartz

    raw = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image)))
    per_row, rows = Quartz.CGImageGetBytesPerRow(image), Quartz.CGImageGetHeight(image)
    pixels = np.frombuffer(raw, np.uint8)[: per_row * rows].reshape(rows, per_row // 4, 4)
    return pixels[:, : int(width), :3].astype(int)


def _grab(excluded: bool, rect: tuple[float, float, float, float]) -> np.ndarray:
    import Quartz
    import ScreenCaptureKit as SCK

    content = _content()
    display = next(d for d in content.displays() if d.displayID() == Quartz.CGMainDisplayID())
    if excluded:
        content_filter = screen.display_filter(content, display)
    else:
        content_filter = SCK.SCContentFilter.alloc()
        content_filter = content_filter.initWithDisplay_excludingApplications_exceptingWindows_(
            display, [], []
        )
    return _pixels(screen._capture_image(content_filter, rect[2], rect[3], rect), rect[2])


def _ring_blue(pixels: np.ndarray) -> int:
    """Pixels of the ring's systemBlue (BGRA rows): content under it (a video) rarely matches."""
    blue, green, red = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    return int(((blue > 200) & (red < 70) & (green > 90) & (green < 170)).sum())


def _diff(a: np.ndarray, b: np.ndarray) -> float:
    return round(float(np.abs(a - b).mean()), 2)


def _panel_rect() -> tuple[float, float, float, float]:
    import AppKit

    from zoya.overlay_app import SCREEN_INSET_PT, WINDOW_H_PT, WINDOW_W_PT

    visible = AppKit.NSScreen.mainScreen().visibleFrame()
    height = _main_size()[1]
    x = visible.origin.x + visible.size.width - WINDOW_W_PT - SCREEN_INSET_PT
    y = height - (visible.origin.y + SCREEN_INSET_PT) - WINDOW_H_PT
    return (x, y, WINDOW_W_PT, WINDOW_H_PT)


def _window_under(point: tuple[float, float]) -> Any:
    import Quartz

    mine = screen.own_pids()
    return next(
        (
            w
            for w in _content().windows()
            if w.owningApplication()
            and w.windowLayer() == 0
            and w.owningApplication().processID() not in mine
            and Quartz.CGRectContainsPoint(w.frame(), point)
        ),
        None,
    )


def capture() -> None:
    import ScreenCaptureKit as SCK

    panel = _panel_rect()
    base = _grab(True, panel)
    print(f"overlay: {overlay.start()}")
    time.sleep(2.0)
    events.emit(events.NarrateEvent("Adding eggs to the cart."))
    time.sleep(0.5)
    print("panel region: display_filter diff", _diff(_grab(True, panel), base))
    print("panel region: unfiltered diff   ", _diff(_grab(False, panel), base), "(panel visible)")
    width, height = _main_size()
    ring = (width / 2 - RING[0] / 2, height / 2 - RING[1] / 2, *RING)
    pad = 2 * overlay.RING_PAD_PT  # show_ring pads the target: capture around the drawn border
    area = (ring[0] - pad, ring[1] - pad, ring[2] + 2 * pad, ring[3] + 2 * pad)
    ring_base = _grab(True, area)
    window = _window_under((width / 2, height / 2))
    window_base = None
    if window is not None:
        window_filter = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
        size = window.frame().size
        window_base = _pixels(
            screen._capture_image(window_filter, size.width, size.height), size.width
        )
    overlay.show_ring(*ring)  # returns after RING_LEAD_S: the ring should be on screen now
    print("ring-blue pixels: before", _ring_blue(ring_base), end=" ")
    print("unfiltered", _ring_blue(_grab(False, area)), end=" ")
    print("display_filter", _ring_blue(_grab(True, area)))
    if window_base is not None:
        after = _pixels(screen._capture_image(window_filter, size.width, size.height), size.width)
        name = window.owningApplication().applicationName()
        print(f"window capture ({name}) under the ring: ring-blue pixels", end=" ")
        print(_ring_blue(window_base), "→", _ring_blue(after))
    print(
        "capture_region_jpeg over the panel:",
        len(screen.capture_region_jpeg(panel[0] + panel[2] - 48, panel[1] + panel[3] - 48, 40, 40)),
        "bytes",
    )
    cpu = subprocess.run(
        ["ps", "-o", "%cpu=,rss=", "-p", str(overlay._child.pid)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    print("overlay %cpu / rss KB:", cpu.stdout.strip())


def main() -> int:
    import Quartz

    Quartz.CGMainDisplayID()  # window-server connection before any ScreenCaptureKit filter
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("states", "capture"):
        print(__doc__)
        return 2
    if mode == "states":
        print(f"overlay: {overlay.start()}")
        time.sleep(2.0)
        states()
    else:
        capture()
    overlay._child.stdin.close()
    overlay._child.wait(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
