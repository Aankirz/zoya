"""Stills of every pill state for a before/after look check (S2-Feel), drawn offscreen in this
process: no window server, so it runs with the screen locked or asleep.

    uv run python scripts/motion_stills.py --out design/s2/stills/after [--dark]
    PYTHONPATH=<old checkout> uv run python scripts/motion_stills.py --out .../before

Core Animation draws the layer tree as committed after each state settles. Liquid Glass is
drawn by the window server, so the glass itself is missing; the eyes, words, Stop, chips,
borders, sizes and positions are what this compares.

API: https://developer.apple.com/documentation/quartzcore/calayer/rendering(in:)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import AppKit
import Foundation
import Quartz

sys.path.insert(0, str(Path(__file__).resolve().parent))

import motion_harness  # noqa: E402

from zoya.overlay_pill import Pill  # noqa: E402

SETTLE_S = 0.6
SCALE = 2
STATES = (
    ("idle", "idle", "", None),
    ("listening", "listening", "Listening", None),
    ("you-said", "listening", "Listening", (motion_harness.LONG_ASK, True, ())),
    (
        "intent-hindi",
        "listening",
        "Listening",
        (motion_harness.HINDI_ASK, True, ("set reminder", "सुबह 6:30")),
    ),
    ("thinking", "thinking", "Checking your calendar", ("", False, ())),
    ("acting", "acting", "Typing · using Notes", ("", False, ())),
    ("speaking-hindi", "speaking", "Speaking", (motion_harness.SAID, False, ())),
    ("asking", "waiting", "", ("", False, ())),
    ("error", "error", "Couldn’t finish that", ("", False, ())),
    ("stopped", "stopped", "Stopped", ("", False, ())),
)


def _settle() -> None:
    until = Foundation.NSDate.dateWithTimeIntervalSinceNow_(SETTLE_S)
    Foundation.NSRunLoop.currentRunLoop().runUntilDate_(until)


def _png(layer: Any, path: Path) -> None:
    width, height = (int(v * SCALE) for v in layer.bounds().size)
    space = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    context = Quartz.CGBitmapContextCreate(
        None, width, height, 8, 0, space, Quartz.kCGImageAlphaPremultipliedLast
    )
    Quartz.CGContextScaleCTM(context, SCALE, SCALE)
    layer.renderInContext_(context)
    image = Quartz.CGBitmapContextCreateImage(context)
    rep = AppKit.NSBitmapImageRep.alloc().initWithCGImage_(image)
    data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
    path.parent.mkdir(parents=True, exist_ok=True)
    data.writeToFile_atomically_(str(path), True)


def _pose(pill: Pill, state: str, words: str, caption: tuple | None) -> None:
    if caption is not None:
        text, heard, chips = caption
        pill.set_caption(text, heard, chips)
    pill.show(state, words, "Pay ₹4,180 to Bescom", "Say “confirm”, or “stop”")
    _settle()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    app = AppKit.NSApplication.sharedApplication()
    name = AppKit.NSAppearanceNameDarkAqua if args.dark else AppKit.NSAppearanceNameAqua
    app.setAppearance_(AppKit.NSAppearance.appearanceNamed_(name))
    pill = Pill(AppKit.NSMenu.alloc().init(), on_stop=lambda: None, on_open=lambda: None)
    pill.place(AppKit.NSScreen.screens()[0])
    theme = "dark" if args.dark else "light"
    for label, state, words, caption in STATES:
        _pose(pill, state, words, caption)
        _png(pill.container.layer(), args.out / f"{label}-{theme}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
