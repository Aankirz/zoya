"""How the pill looks (D121, Glass Daylight): its colours, sizes, eyes and glass parts. Split
out of overlay_pill.py unchanged: the look lives here, motion in pill_motion.py."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import AppKit
import CoreText
import Foundation
import Quartz

FONT_DIR = Path(__file__).parent / "hub" / "fonts"
FONT_FILES = ("InterVariable.woff2", "AtkinsonHyperlegibleNext.woff2")
FONTS = {
    False: {"semibold": "InterVariable-SemiBold", "bold": "InterVariable-Bold"},
    True: {
        "semibold": "AtkinsonHyperlegibleNext-Regular_SemiBold",
        "bold": "AtkinsonHyperlegibleNext-Regular_Bold",
    },
}

PAPER = (250, 253, 255)
INK = (10, 11, 13)
YES = (251, 221, 103)
BLUE = (4, 98, 211)
TINT_BLUE = ((0, 83, 197), 0.9)
TINT_CAPTION = ((0, 63, 161), 0.95)
TINT_NEUTRAL = ((36, 38, 43), 0.88)
TINT_WARM = ((164, 30, 20), 0.9)
TINT_CAPTION_WARM = ((133, 25, 17), 0.95)
TINT_NIGHT = ((15, 20, 29), 0.97)
TINT_IDLE = ((248, 250, 252), 0.72)
WAVE_BARS = (0.35, 0.7, 1.0, 0.55, 0.85, 0.45, 0.65)
WAVE_BAR_PT = 2.0
WAVE_GAP_PT = 2.0
WAVE_MAX_PT = 14.0
WAVE_REST = 0.25
WAVE_ALPHA = 0.6

SCREEN_INSET_PT = 16.0
NOTCH_GAP_PT = 6.0
ROOM_PT = 24.0
CAPTION_GAP_PT = 10.0
CONTAINER_SPACING_PT = 28.0
CONFIRM_RING_PT = 3.0
CONTRAST_RING_PT = 1.0
LEVEL_S = 0.08
BLINK_S = 4.6
GLANCE_S = 0.8
TALK_S = 0.34
GLANCE_PT = 4.0
EASE_OUT_QUINT = (0.22, 1.0, 0.36, 1.0)
LARGE_SCALE = 1.25
DRAG_SLOP_PT = 3.0
OFFSET_KEY = "ZoyaPillOffset"
OPEN_HELP = "Opens Zoya"
STOP_LABEL = "Stop"
READY = "Zoya is ready"
IDLE_TIP = "Hold {keys} and talk"
CAPTION_PAD = (18.0, 10.0)
CAPTION_RADIUS = 20.0
CHIP_PT = 13.0
CHIP_PAD = 9.0
CHIP_H = 21.0
CHIP_GAP = 6.0


@dataclass(frozen=True)
class Look:
    tint: tuple[tuple[int, int, int], float]
    caption: tuple[tuple[int, int, int], float]
    ink: tuple[int, int, int]
    eyes: str


LOOKS = {
    "idle": Look(TINT_IDLE, TINT_CAPTION, INK, "rest"),
    "listening": Look(TINT_BLUE, TINT_CAPTION, PAPER, "tall"),
    "thinking": Look(TINT_NEUTRAL, TINT_CAPTION, PAPER, "dot"),
    "acting": Look(TINT_NEUTRAL, TINT_CAPTION, PAPER, "dot"),
    "speaking": Look(TINT_BLUE, TINT_CAPTION, PAPER, "squint"),
    "waiting": Look(TINT_NIGHT, TINT_CAPTION, PAPER, "up"),
    "stopped": Look(TINT_NEUTRAL, TINT_CAPTION, PAPER, "flat"),
    "error": Look(TINT_WARM, TINT_CAPTION_WARM, PAPER, "sad"),
}

EYES = {
    "rest": (8.0, 11.0, 0.0, 0.0),
    "tall": (9.0, 15.0, 0.0, 0.0),
    "dot": (8.0, 8.0, 0.0, 0.0),
    "squint": (11.0, 6.0, 0.0, 0.0),
    "up": (8.0, 13.0, 3.0, 0.0),
    "flat": (11.0, 3.0, 0.0, 0.0),
    "sad": (10.0, 3.0, -2.0, math.radians(18)),
}
EYE_GAP_PT = 6.0
EYE_BOX = (30.0, 24.0)


@dataclass(frozen=True)
class Metrics:
    height: float
    idle_height: float
    idle_width: float
    pad_left: float
    pad_right: float
    gap: float
    label_pt: float
    stop_pt: float
    confirm_pad: float
    stake_pt: float
    how_pt: float
    confirm_stop_pt: float
    caption_pt: float
    caption_width: float
    label_width: float
    stake_width: float
    scale: float


def metrics(large: bool) -> Metrics:
    k = LARGE_SCALE if large else 1.0
    return Metrics(
        height=46 * k,
        idle_height=30 * k,
        idle_width=60 * k,
        pad_left=12 * k,
        pad_right=8 * k,
        gap=12 * k,
        label_pt=15 * k,
        stop_pt=32 * k,
        confirm_pad=16 * k,
        stake_pt=24 * k,
        how_pt=16 * k,
        confirm_stop_pt=48 * k,
        caption_pt=24 if large else 18,
        caption_width=620 * k,
        label_width=360 * k,
        stake_width=480 * k,
        scale=k,
    )


def register_fonts() -> None:
    for name in FONT_FILES:
        url = Foundation.NSURL.fileURLWithPath_(str(FONT_DIR / name))
        CoreText.CTFontManagerRegisterFontsForURL(url, CoreText.kCTFontManagerScopeProcess, None)


def font(size: float, weight: str, legible: bool) -> Any:
    chosen = AppKit.NSFont.fontWithName_size_(FONTS[legible][weight], size)
    return chosen or AppKit.NSFont.systemFontOfSize_weight_(size, AppKit.NSFontWeightSemibold)


def color(rgb: tuple[int, int, int], alpha: float = 1.0) -> Any:
    red, green, blue = (c / 255 for c in rgb)
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(red, green, blue, alpha)


def cg(rgb: tuple[int, int, int], alpha: float = 1.0) -> Any:
    return color(rgb, alpha).CGColor()


def _encode(linear: float) -> float:
    linear = min(max(linear, 0.0), 1.0)
    return 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1 / 2.4) - 0.055


def oklch(lightness: float, chroma: float, hue: float, alpha: float = 1.0) -> tuple[float, ...]:
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    red = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    green = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    blue = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return (_encode(red), _encode(green), _encode(blue), alpha)


GLOSS = (oklch(0.91, 0.05, 245), oklch(0.81, 0.095, 250), oklch(0.75, 0.12, 253))
GLOSS_STOPS = [0.0, 0.6, 1.0]
GLOSS_EDGE = oklch(0.56, 0.13, 255)
GLOSS_SHINE = oklch(0.99, 0.01, 240, 0.9)
CAPTION_INK = oklch(0.15, 0.005, 260)
CHIP_FILL = oklch(1.0, 0, 0, 0.7)
CHIP_EDGE = oklch(0.70, 0.1, 252, 0.5)
CHIP_INK = oklch(0.43, 0.16, 258)


def srgb(rgba: tuple[float, ...]) -> Any:
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*rgba)


def accessibility() -> tuple[bool, bool, bool]:
    ws = AppKit.NSWorkspace.sharedWorkspace()
    return (
        bool(ws.accessibilityDisplayShouldReduceMotion()),
        bool(ws.accessibilityDisplayShouldReduceTransparency()),
        bool(ws.accessibilityDisplayShouldIncreaseContrast()),
    )


def text_field(lines: int = 1) -> Any:
    field = AppKit.NSTextField.labelWithString_("")
    field.setMaximumNumberOfLines_(lines)
    field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    field.setAccessibilityElement_(False)
    if lines > 1:
        field.cell().setWraps_(True)
        field.cell().setTruncatesLastVisibleLine_(True)
        field.setLineBreakStrategy_(AppKit.NSLineBreakStrategyStandard)
    return field


def fitted(field: Any, width: float) -> Any:
    return field.cell().cellSizeForBounds_(((0, 0), (width, 10_000)))


def ease() -> Any:
    return Quartz.CAMediaTimingFunction.functionWithControlPoints____(*EASE_OUT_QUINT)


def loop(key_path: str, values: list[float], seconds: float, **options: Any) -> Any:
    anim = Quartz.CAKeyframeAnimation.animationWithKeyPath_(key_path)
    anim.setValues_(values)
    anim.setDuration_(seconds)
    anim.setRepeatCount_(float("inf"))
    anim.setAdditive_(options.get("additive", False))
    anim.setAutoreverses_(options.get("autoreverses", False))
    if "key_times" in options:
        anim.setKeyTimes_(options["key_times"])
    return anim


def glass(radius: float) -> Any:
    view = AppKit.NSGlassEffectView.alloc().initWithFrame_(((0, 0), (10, 10)))
    view.setStyle_(AppKit.NSGlassEffectViewStyleRegular)
    view.setCornerRadius_(radius)
    content = AppKit.NSView.alloc().initWithFrame_(((0, 0), (10, 10)))
    content.setWantsLayer_(True)
    view.setContentView_(content)
    return view


class PillPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self) -> bool:  # noqa: N802
        return False

    def canBecomeMainWindow(self) -> bool:  # noqa: N802
        return False


def panel() -> Any:
    style = AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel
    made = PillPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        ((0, 0), (10, 10)), style, AppKit.NSBackingStoreBuffered, False
    )
    made.setBecomesKeyOnlyIfNeeded_(True)
    made.setHidesOnDeactivate_(False)
    made.setLevel_(AppKit.NSStatusWindowLevel)
    made.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorStationary
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorIgnoresCycle
    )
    made.setOpaque_(False)
    made.setBackgroundColor_(AppKit.NSColor.clearColor())
    made.setHasShadow_(False)
    return made
