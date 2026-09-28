"""The pill (D121, Glass Daylight): native Liquid Glass, Zoya's eyes, a Stop, and a caption that
grows out of the pill."""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
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
MERGE_S = 0.45
FADE_S = 0.2
POSE_S = 0.22
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


class StopButton(AppKit.NSButton):
    def acceptsFirstMouse_(self, _event: Any) -> bool:  # noqa: N802
        return True


class Face(AppKit.NSView):
    def acceptsFirstMouse_(self, _event: Any) -> bool:  # noqa: N802
        return True

    def mouseDown_(self, _event: Any) -> None:  # noqa: N802
        self.pill.press_began()

    def mouseDragged_(self, _event: Any) -> None:  # noqa: N802
        self.pill.dragged()

    def mouseUp_(self, _event: Any) -> None:  # noqa: N802
        self.pill.press_ended()

    def rightMouseDown_(self, event: Any) -> None:  # noqa: N802
        AppKit.NSMenu.popUpContextMenu_withEvent_forView_(self.pill.menu, event, self)

    def isAccessibilityElement(self) -> bool:  # noqa: N802
        return True

    def accessibilityRole(self) -> str:  # noqa: N802
        return AppKit.NSAccessibilityButtonRole

    def accessibilityLabel(self) -> str:  # noqa: N802
        return self.pill.spoken_label

    def accessibilityHelp(self) -> str:  # noqa: N802
        return OPEN_HELP

    def accessibilityPerformPress(self) -> bool:  # noqa: N802
        self.pill.on_open()
        return True

    def stopPressed_(self, _sender: Any) -> None:  # noqa: N802
        self.pill.on_stop()


class Pill:
    def __init__(self, menu: Any, on_stop: Callable[[], None], on_open: Callable[[], None]) -> None:
        register_fonts()
        self.menu, self.on_stop, self.on_open = menu, on_stop, on_open
        self.reduce_motion, self.reduce_transparency, self.contrast = accessibility()
        self.large = self.legible = False
        self.position = "bottom"
        self.anchor = (0.0, 0.0)
        self.hanging = False
        self.tip = IDLE_TIP.format(keys="fn + Shift")
        self.state, self.words, self.stake, self.how = "", "", "", ""
        self.caption_text, self.caption_heard = "", False
        self.chip_words: tuple[str, ...] = ()
        self.caption_shown = False
        self.spoken_label = READY
        self.press: tuple[Any, Any] | None = None
        self.moved = False
        self._build()
        self.report()

    def _build(self) -> None:
        self.panel = panel()
        self.container = AppKit.NSGlassEffectContainerView.alloc().initWithFrame_(
            ((0, 0), (10, 10))
        )
        self.container.setSpacing_(CONTAINER_SPACING_PT)
        stage = AppKit.NSView.alloc().initWithFrame_(((0, 0), (10, 10)))
        self.container.setContentView_(stage)
        self.panel.setContentView_(self.container)
        self.pill, self.bubble = glass(23.0), glass(20.0)
        stage.addSubview_(self.bubble)
        stage.addSubview_(self.pill)
        body = self.pill.contentView()
        self.face = Face.alloc().initWithFrame_(((0, 0), (10, 10)))
        self.face.pill = self
        self.face.setWantsLayer_(True)
        body.addSubview_(self.face)
        self.eyes_box = Quartz.CALayer.layer()
        self.face.layer().addSublayer_(self.eyes_box)
        self.eyes = [Quartz.CALayer.layer(), Quartz.CALayer.layer()]
        for eye in self.eyes:
            self.eyes_box.addSublayer_(eye)
        self.wave = [Quartz.CALayer.layer() for _ in WAVE_BARS]
        for bar in self.wave:
            bar.setCornerRadius_(WAVE_BAR_PT / 2)
            self.face.layer().addSublayer_(bar)
        self.label, self.stake_field, self.how_field = text_field(), text_field(3), text_field()
        for field in (self.label, self.stake_field, self.how_field):
            self.face.addSubview_(field)
        self.stop = self._stop_button()
        body.addSubview_(self.stop)
        self.gloss, self.shine = Quartz.CAGradientLayer.layer(), Quartz.CALayer.layer()
        self.gloss.setColors_([srgb(c).CGColor() for c in GLOSS])
        self.gloss.setLocations_(GLOSS_STOPS)
        self.gloss.setStartPoint_((0.5, 1.0))
        self.gloss.setEndPoint_((0.5, 0.0))
        self.gloss.setCornerRadius_(CAPTION_RADIUS)
        self.gloss.setBorderWidth_(1.0)
        self.gloss.setBorderColor_(srgb(GLOSS_EDGE).CGColor())
        self.shine.setBackgroundColor_(srgb(GLOSS_SHINE).CGColor())
        self.gloss.addSublayer_(self.shine)
        self.bubble.contentView().layer().addSublayer_(self.gloss)
        self.caption_field = text_field(3)
        self.caption_field.setAlignment_(AppKit.NSTextAlignmentCenter)
        self.bubble.contentView().addSubview_(self.caption_field)
        self.chips: list[Any] = []
        self.bubble.setHidden_(True)

    def _stop_button(self) -> Any:
        button = StopButton.alloc().initWithFrame_(((0, 0), (32, 32)))
        button.setBordered_(False)
        button.setTitle_("")
        button.setWantsLayer_(True)
        button.setTarget_(self.face)
        button.setAction_("stopPressed:")
        button.setAccessibilityLabel_(STOP_LABEL)
        button.setToolTip_(STOP_LABEL)
        self.glyph = Quartz.CALayer.layer()
        self.glyph.setCornerRadius_(2.5)
        button.layer().addSublayer_(self.glyph)
        return button

    # --- settings and environment ---------------------------------------------------------

    def configure(self, large: bool, legible: bool, position: str, keys: str) -> None:
        self.tip = IDLE_TIP.format(keys=keys)
        if position != self.position:
            Foundation.NSUserDefaults.standardUserDefaults().removeObjectForKey_(OFFSET_KEY)
        self.large, self.legible, self.position = large, legible, position
        self.refresh()

    def environment_changed(self) -> None:
        self.reduce_motion, self.reduce_transparency, self.contrast = accessibility()
        self.report()
        self.refresh()

    def report(self) -> None:
        print(
            f"overlay: reduce motion {self.reduce_motion}, reduce transparency "
            f"{self.reduce_transparency}, increase contrast {self.contrast}",
            file=sys.stderr,
            flush=True,
        )

    def place(self, screen: Any) -> None:
        visible = screen.visibleFrame()
        x, y = visible.origin.x, visible.origin.y
        width, height = visible.size.width, visible.size.height
        anchors = {
            "bottom": (x + width / 2, y + SCREEN_INSET_PT),
            "left": (x + SCREEN_INSET_PT, y + height / 2),
            "right": (x + width - SCREEN_INSET_PT, y + height / 2),
        }
        hanging = self.position == "notch" and screen.safeAreaInsets().top > 0
        if hanging:
            frame = screen.frame()
            anchors["notch"] = (frame.origin.x + frame.size.width / 2, y + height - NOTCH_GAP_PT)
        anchor = anchors.get(self.position, anchors["bottom"])
        if (anchor, hanging) != (self.anchor, self.hanging):
            self.anchor, self.hanging = anchor, hanging
            self.layout()

    # --- state ------------------------------------------------------------------------------

    def show(self, state: str, words: str, stake: str = "", how: str = "") -> None:
        self.state, self.words, self.stake, self.how = state, words, stake, how
        self.refresh()

    def set_caption(self, text: str, heard: bool, chips: Any = ()) -> None:
        self.caption_text, self.caption_heard = text, heard
        if tuple(chips) != self.chip_words:
            self.chip_words = tuple(chips)
            self._make_chips()
        self.layout()

    def _make_chips(self) -> None:
        for chip in self.chips:
            chip.removeFromSuperview()
        self.chips = []
        for word in self.chip_words:
            chip = text_field()
            chip.setStringValue_(word)
            chip.setAlignment_(AppKit.NSTextAlignmentCenter)
            chip.setTextColor_(srgb(CHIP_INK))
            chip.setWantsLayer_(True)
            chip.setDrawsBackground_(False)
            layer = chip.layer()
            layer.setBackgroundColor_(srgb(CHIP_FILL).CGColor())
            layer.setBorderWidth_(1.0)
            layer.setBorderColor_(srgb(CHIP_EDGE).CGColor())
            self.bubble.contentView().addSubview_(chip)
            self.chips.append(chip)
        self.bubble.contentView().setAccessibilityLabel_(", ".join(self.chip_words) or None)

    def set_level(self, level: float) -> None:
        if self.state != "listening" or self.reduce_motion:
            return
        loud = max(WAVE_REST, min(level, 1.0))
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setAnimationDuration_(LEVEL_S)
        for bar, share in zip(self.wave, WAVE_BARS, strict=True):
            bar.setTransform_(Quartz.CATransform3DMakeScale(1.0, max(WAVE_REST, loud * share), 1.0))
        Quartz.CATransaction.commit()

    def refresh(self) -> None:
        if not self.state:
            return
        look = LOOKS.get(self.state, LOOKS["idle"])
        self._paint(look)
        self._pose(look.eyes)
        self.layout()
        self.spoken_label = f"Zoya: {self.words}" if self.words else f"{READY}. {self.tip}"
        self.face.setToolTip_(self.tip if self.state == "idle" else None)
        self.panel.orderFrontRegardless()

    def _tint(self, tint: tuple[tuple[int, int, int], float]) -> Any:
        rgb, alpha = tint
        return color(rgb, 1.0 if self.reduce_transparency else alpha)

    def _paint(self, look: Look) -> None:
        self.pill.setTintColor_(self._tint(look.tint))
        warm = look.caption == TINT_CAPTION_WARM
        self.bubble.setTintColor_(self._tint(look.caption) if warm else srgb(GLOSS[1]))
        self.gloss.setHidden_(warm)
        confirm = self.state == "waiting"
        edge = self.pill.contentView().layer()
        edge.setBorderWidth_(
            CONFIRM_RING_PT if confirm else (CONTRAST_RING_PT if self.contrast else 0.0)
        )
        edge.setBorderColor_(cg(YES) if confirm else cg(INK))
        bubble_edge = self.bubble.contentView().layer()
        bubble_edge.setBorderWidth_(CONTRAST_RING_PT if self.contrast else 0.0)
        bubble_edge.setBorderColor_(cg(INK))
        for eye in self.eyes:
            eye.setBackgroundColor_(cg(YES if confirm else look.ink))
        self.stop.layer().setBackgroundColor_(cg(PAPER))
        self.glyph.setBackgroundColor_(cg(INK))
        self.label.setTextColor_(color(look.ink))
        self.stake_field.setTextColor_(color(PAPER))
        self.how_field.setTextColor_(color(YES))
        self.caption_field.setTextColor_(color(PAPER) if warm else srgb(CAPTION_INK))
        for bar in self.wave:
            bar.setBackgroundColor_(cg(look.ink, WAVE_ALPHA))
            bar.setHidden_(self.state != "listening")

    def eye_box(self) -> tuple[float, float]:
        k = LARGE_SCALE if self.large else 1.0
        return (EYE_BOX[0] * k, EYE_BOX[1] * k)

    def _pose(self, pose: str) -> None:
        k = LARGE_SCALE if self.large else 1.0
        width, height, lift, tilt = EYES[pose]
        width, height, lift, gap = width * k, height * k, lift * k, EYE_GAP_PT * k
        box_w, box_h = self.eye_box()
        centers = (box_w / 2 - (width + gap) / 2, box_w / 2 + (width + gap) / 2)
        for eye in self.eyes:
            eye.removeAllAnimations()
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(self.reduce_motion)
        Quartz.CATransaction.setAnimationDuration_(POSE_S)
        Quartz.CATransaction.setAnimationTimingFunction_(ease())
        for eye, center, sign in zip(self.eyes, centers, (1, -1), strict=True):
            eye.setBounds_(((0, 0), (width, height)))
            eye.setPosition_((center, box_h / 2 + lift))
            eye.setCornerRadius_(min(width, height) / 2)
            eye.setTransform_(Quartz.CATransform3DMakeRotation(sign * tilt, 0, 0, 1))
        Quartz.CATransaction.commit()
        if not self.reduce_motion:
            self._loop(pose)

    def _loop(self, pose: str) -> None:
        if pose == "rest":
            anim = loop(
                "transform.scale.y", [1.0, 1.0, 0.1, 1.0], BLINK_S, key_times=[0, 0.92, 0.96, 1]
            )
        elif pose == "dot":
            anim = loop(
                "position.x", [-GLANCE_PT, GLANCE_PT], GLANCE_S, additive=True, autoreverses=True
            )
        elif pose == "squint":
            anim = loop("transform.scale.y", [1.0, 0.6], TALK_S, autoreverses=True)
        else:
            return
        for eye in self.eyes:
            eye.addAnimation_forKey_(anim, "loop")

    # --- layout -----------------------------------------------------------------------------

    def _fonts(self, m: Metrics) -> None:
        self.label.setFont_(font(m.label_pt, "semibold", self.legible))
        self.stake_field.setFont_(font(m.stake_pt, "bold", self.legible))
        self.how_field.setFont_(font(m.how_pt, "semibold", self.legible))
        self.caption_field.setFont_(font(m.caption_pt, "semibold", self.legible))

    def _content(self, m: Metrics) -> tuple[float, float]:
        confirm = self.state == "waiting"
        idle = self.state == "idle"
        self.label.setHidden_(idle or confirm)
        self.stake_field.setHidden_(not confirm)
        self.how_field.setHidden_(not confirm)
        self.stop.setHidden_(idle)
        if idle:
            return m.idle_width, m.idle_height
        if confirm:
            return self._confirm_content(m)
        self.label.setStringValue_(self.words)
        size = fitted(self.label, m.label_width)
        label_w = math.ceil(min(size.width, m.label_width))
        x = m.pad_left + self.eye_box()[0] + m.gap
        if self.state == "listening":
            x = self._place_wave(x, m) + m.gap
        self.label.setFrame_(
            ((x, math.floor((m.height - size.height) / 2)), (label_w, size.height))
        )
        return x + label_w + m.gap + m.stop_pt + m.pad_right, m.height

    def _place_wave(self, x: float, m: Metrics) -> float:
        k = LARGE_SCALE if self.large else 1.0
        tallest = WAVE_MAX_PT * k
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        for bar in self.wave:
            bar.setBounds_(((0, 0), (WAVE_BAR_PT * k, tallest)))
            bar.setPosition_((x + WAVE_BAR_PT * k / 2, m.height / 2))
            x += (WAVE_BAR_PT + WAVE_GAP_PT) * k
        Quartz.CATransaction.commit()
        return x - WAVE_GAP_PT * k

    def _confirm_content(self, m: Metrics) -> tuple[float, float]:
        self.stake_field.setStringValue_(self.stake)
        self.how_field.setStringValue_(self.how)
        stake = fitted(self.stake_field, m.stake_width)
        how = fitted(self.how_field, m.stake_width)
        text_w = math.ceil(min(max(stake.width, how.width), m.stake_width))
        text_h = stake.height + 4 * m.scale + how.height
        height = math.ceil(max(text_h, m.confirm_stop_pt) + 2 * m.confirm_pad)
        x = m.confirm_pad + self.eye_box()[0] + m.gap
        bottom = (height - text_h) / 2
        self.how_field.setFrame_(((x, bottom), (text_w, how.height)))
        self.stake_field.setFrame_(((x, bottom + how.height + 4 * m.scale), (text_w, stake.height)))
        return x + text_w + m.gap + m.confirm_stop_pt + m.confirm_pad, height

    def _chip_sizes(self, m: Metrics) -> list[tuple[float, float]]:
        sizes = []
        for chip in self.chips:
            chip.setFont_(font(CHIP_PT * m.scale, "semibold", self.legible))
            width = fitted(chip, m.caption_width).width + 2 * CHIP_PAD * m.scale
            sizes.append((math.ceil(width), CHIP_H * m.scale))
        return sizes

    def _caption_size(self, m: Metrics) -> tuple[float, float]:
        shown = f"“{self.caption_text}”" if self.caption_heard else self.caption_text
        self.caption_field.setStringValue_(shown)
        pad_x, pad_y = CAPTION_PAD
        room = m.caption_width - 2 * pad_x
        text = fitted(self.caption_field, room)
        text_w, text_h = math.ceil(min(text.width, room)), math.ceil(text.height)
        chips, gap = self._chip_sizes(m), CHIP_GAP * m.scale
        row_w = sum(w for w, _ in chips) + gap * max(len(chips) - 1, 0)
        chip_h = chips[0][1] if chips else 0.0
        one_line = text_h < self.caption_field.font().pointSize() * 1.8
        inline = one_line and text_w + gap + row_w <= room
        self.caption_parts = (text_w, text_h, chips, inline)
        if not chips:
            return text_w + 2 * pad_x, text_h + 2 * pad_y
        if inline:
            return text_w + gap + row_w + 2 * pad_x, max(text_h, chip_h) + 2 * pad_y
        return max(text_w, row_w) + 2 * pad_x, text_h + gap + chip_h + 2 * pad_y

    def layout(self) -> None:
        if not self.state:
            return
        m = metrics(self.large)
        self._fonts(m)
        width, height = (math.ceil(v) for v in self._content(m))
        wants_caption = bool(self.caption_text) and self.state not in ("idle", "waiting")
        cap_w, cap_h = self._caption_size(m) if wants_caption else (0, 0)
        stage_w = max(width, cap_w) + 2 * ROOM_PT
        stage_h = height + (cap_h + CAPTION_GAP_PT if wants_caption else 0) + 2 * ROOM_PT
        below = cap_h + CAPTION_GAP_PT if wants_caption and self.hanging else 0.0
        pill_y = ROOM_PT + below
        self._frame_panel(width, height, stage_w, stage_h, pill_y)
        pill_frame = (((stage_w - width) / 2, pill_y), (width, height))
        self._frame_pill(m, pill_frame)
        cap_y = ROOM_PT if self.hanging else ROOM_PT + height + CAPTION_GAP_PT
        caption_frame = (((stage_w - cap_w) / 2, cap_y), (cap_w, cap_h))
        self._caption(wants_caption, pill_frame, caption_frame)

    def _frame_pill(self, m: Metrics, frame: Any) -> None:
        (_x, _y), (width, height) = frame
        confirm = self.state == "waiting"
        radius = height / 2 if not confirm else min(height / 2, 28.0 * m.scale)
        self.pill.setFrame_(frame)
        self.pill.setCornerRadius_(radius)
        body = self.pill.contentView()
        body.setFrame_(((0, 0), (width, height)))
        body.layer().setCornerRadius_(radius)
        stop_pt = m.confirm_stop_pt if confirm else m.stop_pt
        right = m.confirm_pad if confirm else m.pad_right
        stop_x = width - right - stop_pt
        self.face.setFrame_(((0, 0), (width if self.state == "idle" else stop_x, height)))
        box = self.eye_box()
        eyes_x = (
            (width - box[0]) / 2
            if self.state == "idle"
            else (m.confirm_pad if confirm else m.pad_left)
        )
        self.eyes_box.setFrame_(((eyes_x, (height - box[1]) / 2), box))
        self.stop.setFrame_(((stop_x, (height - stop_pt) / 2), (stop_pt, stop_pt)))
        self.stop.layer().setCornerRadius_(stop_pt / 2)
        glyph = round(stop_pt * 0.3)
        self.glyph.setFrame_((((stop_pt - glyph) / 2, (stop_pt - glyph) / 2), (glyph, glyph)))

    def _bud(self, pill_frame: Any, caption_frame: Any) -> Any:
        (px, py), (pw, ph) = pill_frame
        (_cx, _cy), (cw, ch) = caption_frame
        width, height = max(pw * 0.4, 24.0), max(ch * 0.5, 16.0)
        y = py if self.hanging else py + ph - height
        return ((px + (pw - width) / 2, y), (width, height))

    def _place_caption(self, cw: float, ch: float) -> None:
        pad_x, pad_y = CAPTION_PAD
        text_w, text_h, chips, inline = self.caption_parts
        gap = CHIP_GAP * (LARGE_SCALE if self.large else 1.0)
        if inline or not chips:
            self.caption_field.setFrame_(((pad_x, (ch - text_h) / 2), (text_w, text_h)))
            x = pad_x + text_w + gap
        else:
            row_w = sum(w for w, _ in chips) + gap * (len(chips) - 1)
            self.caption_field.setFrame_(((pad_x, ch - pad_y - text_h), (cw - 2 * pad_x, text_h)))
            x = (cw - row_w) / 2
        for chip, (width, height) in zip(self.chips, chips, strict=True):
            y = (ch - height) / 2 if inline else pad_y
            chip.setFrame_(((x, y), (width, height)))
            chip.layer().setCornerRadius_(height / 2)
            x += width + gap
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        self.gloss.setFrame_(((0, 0), (cw, ch)))
        self.shine.setFrame_(((CAPTION_RADIUS, ch - 2.0), (max(cw - 2 * CAPTION_RADIUS, 0), 1.0)))
        Quartz.CATransaction.commit()

    def _caption(self, wanted: bool, pill_frame: Any, caption_frame: Any) -> None:
        (_x, _y), (cw, ch) = caption_frame
        if wanted:
            self._place_caption(cw, ch)
        self.bubble.contentView().setFrame_(((0, 0), (cw, ch)))
        self.bubble.contentView().layer().setCornerRadius_(CAPTION_RADIUS)
        if wanted and not self.caption_shown:
            self._grow(pill_frame, caption_frame)
        elif wanted:
            self.bubble.setFrame_(caption_frame)
        elif self.caption_shown:
            self._sink(pill_frame, caption_frame)
        self.caption_shown = wanted

    def _grow(self, pill_frame: Any, caption_frame: Any) -> None:
        self.bubble.setHidden_(False)
        if self.reduce_motion:
            self.bubble.setFrame_(caption_frame)
            self.bubble.setAlphaValue_(0.0)
            self._animate(FADE_S, lambda: self.bubble.animator().setAlphaValue_(1.0))
            return
        self.bubble.setAlphaValue_(1.0)
        self.bubble.setFrame_(self._bud(pill_frame, caption_frame))
        self._animate(MERGE_S, lambda: self.bubble.animator().setFrame_(caption_frame))

    def _sink(self, pill_frame: Any, caption_frame: Any) -> None:
        if self.reduce_motion:
            self._animate(
                FADE_S, lambda: self.bubble.animator().setAlphaValue_(0.0), self._hide_bubble
            )
            return
        bud = self._bud(pill_frame, self.bubble.frame())
        self._animate(MERGE_S, lambda: self.bubble.animator().setFrame_(bud), self._hide_bubble)

    def _hide_bubble(self) -> None:
        if not self.caption_shown:
            self.bubble.setHidden_(True)

    def _animate(
        self, seconds: float, change: Callable[[], None], done: Callable[[], None] | None = None
    ) -> None:
        def group(context: Any) -> None:
            context.setDuration_(seconds)
            context.setTimingFunction_(ease())
            change()

        AppKit.NSAnimationContext.runAnimationGroup_completionHandler_(group, done)

    def _origin(
        self, width: float, height: float, stage_w: float, pill_y: float
    ) -> tuple[float, float]:
        x, y = self.anchor
        if self.hanging:
            pill = (x - width / 2, y - height)
        elif self.position == "left":
            pill = (x, y - height / 2)
        elif self.position == "right":
            pill = (x - width, y - height / 2)
        else:
            pill = (x - width / 2, y)
        offset = Foundation.NSUserDefaults.standardUserDefaults().arrayForKey_(OFFSET_KEY) or (0, 0)
        left = pill[0] - (stage_w - width) / 2 + offset[0]
        return (round(left), round(pill[1] - pill_y + offset[1]))

    def _frame_panel(
        self, width: float, height: float, stage_w: float, stage_h: float, pill_y: float
    ) -> None:
        origin = self._origin(width, height, stage_w, pill_y)
        self.panel.setFrame_display_((origin, (stage_w, stage_h)), True)
        self.container.setFrame_(((0, 0), (stage_w, stage_h)))
        self.container.contentView().setFrame_(((0, 0), (stage_w, stage_h)))

    # --- pointer ----------------------------------------------------------------------------

    def press_began(self) -> None:
        self.press = (AppKit.NSEvent.mouseLocation(), self.panel.frame().origin)
        self.moved = False

    def dragged(self) -> None:
        if self.press is None:
            return
        start, origin = self.press
        now = AppKit.NSEvent.mouseLocation()
        dx, dy = now.x - start.x, now.y - start.y
        self.moved = self.moved or abs(dx) > DRAG_SLOP_PT or abs(dy) > DRAG_SLOP_PT
        if self.moved:
            self.panel.setFrameOrigin_((origin.x + dx, origin.y + dy))

    def press_ended(self) -> None:
        if self.press is None:
            return
        _, origin = self.press
        self.press = None
        if not self.moved:
            self.on_open()
            return
        now = self.panel.frame().origin
        defaults = Foundation.NSUserDefaults.standardUserDefaults()
        previous = defaults.arrayForKey_(OFFSET_KEY) or (0, 0)
        moved = [previous[0] + now.x - origin.x, previous[1] + now.y - origin.y]
        defaults.setObject_forKey_(moved, OFFSET_KEY)

    def click_through(self, through: bool) -> None:
        self.panel.setIgnoresMouseEvents_(through)

    def windows(self) -> list[Any]:
        return [self.panel]
