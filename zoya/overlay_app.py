"""The overlay child process (Phase 7): AppKit panel + ring. Started by zoya.overlay.start; reads
JSON lines on stdin and exits when Zoya closes the pipe. Display only: it never becomes key or
main, ignores the mouse, never activates, and draws nothing Zoya's model can see (screen.py
excludes this pid from every capture). API references: zoya/overlay.py docstring, plus
- https://developer.apple.com/documentation/quartzcore/calayer/presentation()
- https://developer.apple.com/documentation/quartzcore/camediatimingfunction/init(controlpoints::::)
- https://developer.apple.com/documentation/appkit/nstextfieldcell (cellSizeForBounds, fitting)
- https://developer.apple.com/documentation/appkit/nsfont/monospaceddigitsystemfont(ofsize:weight:)

Layout: Zoya's character (zoya/overlay_pet.py) sits in the bottom-right corner; a caption bubble
fitted to its text sits beside it, bottom-aligned, showing a short state label and the latest words.
When nothing is happening only the character remains. Every state reads without motion: colour,
eye shape and the label. Reduce Motion: no loops, fades only. Reduce Transparency: opaque bubble.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import threading
import time
from typing import Any

import AppKit
import Quartz
from PyObjCTools import AppHelper

from zoya.overlay_pet import PET_PT, ZOYA_VIOLET, Pet

WINDOW_W_PT = 520.0
WINDOW_H_PT = 190.0
SCREEN_INSET_PT = 16.0  # window edge to the visible screen edge
SHADOW_ROOM_PT = 10.0  # window edge to the pet, so its shadow isn't clipped
BUBBLE_GAP_PT = 12.0
BUBBLE_MAX_W_PT = 360.0
BUBBLE_PAD_X_PT = 16.0
BUBBLE_PAD_Y_PT = 12.0
BUBBLE_RADIUS_PT = 22.0  # matches the pet's corner
LABEL_GAP_PT = 3.0
LABEL_PT = 13.0
CAPTION_PT = 18.0  # readable on a projector from the back of a room
CAPTION_LINES = 3
IDLE_HIDE_S = 5.0  # the bubble lingers this long after a task ends, then only the pet remains
FADE_S = 0.15
RING_LINE_PT = 4.0
RING_RGB = ZOYA_VIOLET[1]
RING_SHOW_S = 1.4
RING_ENTER_SCALE = 1.08
RING_ENTER_S = 0.2
EXIT_S = 0.15  # exits are shorter and softer than enters
EASE = (0.22, 1.0, 0.36, 1.0)  # ease-out quint
GLASS_TINT_ALPHA = 0.5  # tinted glass keeps captions legible over video and bright pages
SPEED_ENV = "ZOYA_OVERLAY_SPEED"

LABELS = {
    "idle": "Zoya",
    "listening": "Listening",
    "thinking": "Thinking",
    "acting": "Working",
    "speaking": "Speaking",
    "waiting": "Waiting for your yes",
    "stopped": "Stopped",
    "error": "Something went wrong",
}


class OverlayPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self) -> bool:  # noqa: N802 — AppKit override
        return False

    def canBecomeMainWindow(self) -> bool:  # noqa: N802
        return False


def _accessibility() -> tuple[bool, bool, bool]:
    ws = AppKit.NSWorkspace.sharedWorkspace()
    return (
        bool(ws.accessibilityDisplayShouldReduceMotion()),
        bool(ws.accessibilityDisplayShouldReduceTransparency()),
        bool(ws.accessibilityDisplayShouldIncreaseContrast()),
    )


def _panel(frame: Any, shadow: bool = False) -> Any:
    style = AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel
    panel = OverlayPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, style, AppKit.NSBackingStoreBuffered, False
    )
    panel.setIgnoresMouseEvents_(True)
    panel.setBecomesKeyOnlyIfNeeded_(True)
    panel.setHidesOnDeactivate_(False)
    panel.setLevel_(AppKit.NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorStationary
        | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        | AppKit.NSWindowCollectionBehaviorIgnoresCycle
    )
    panel.setOpaque_(False)
    panel.setBackgroundColor_(AppKit.NSColor.clearColor())
    panel.setHasShadow_(shadow)  # the system's layered window shadow follows the rounded content
    return panel


def _label(size: float, weight: float, color: Any, lines: int = 1) -> Any:
    label = AppKit.NSTextField.labelWithString_("")  # plain text: page text is never markup
    # Equal-width digits: amounts and step text change while on screen.
    label.setFont_(AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(size, weight))
    label.setTextColor_(color)
    label.setMaximumNumberOfLines_(lines)
    label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    if lines > 1:
        label.cell().setWraps_(True)
        label.cell().setTruncatesLastVisibleLine_(True)
        label.setLineBreakStrategy_(AppKit.NSLineBreakStrategyStandard)  # avoids orphan words
    return label


def _ease() -> Any:
    return Quartz.CAMediaTimingFunction.functionWithControlPoints____(*EASE)


def _presented(layer: Any, key_path: str, rest: float) -> float:
    shown = layer.presentationLayer()
    value = shown.valueForKeyPath_(key_path) if shown is not None else None
    return float(value) if value is not None else rest


def _animate(
    layer: Any, key_path: str, to: float, seconds: float, start: float | None = None
) -> None:
    """Set the model value and animate there from what is on screen now (interruptible)."""
    begin = _presented(layer, key_path, to) if start is None else start
    anim = Quartz.CABasicAnimation.animationWithKeyPath_(key_path)
    anim.setFromValue_(begin)
    anim.setToValue_(to)
    anim.setDuration_(seconds)
    anim.setTimingFunction_(_ease())
    Quartz.CATransaction.begin()
    Quartz.CATransaction.setDisableActions_(True)
    layer.setValue_forKeyPath_(to, key_path)
    Quartz.CATransaction.commit()
    layer.addAnimation_forKey_(anim, key_path)


class Presence:
    """The pet, its caption bubble and the action ring. All methods run on the main thread."""

    def __init__(self) -> None:
        self.reduce_motion, self.reduce_transparency, self.contrast = _accessibility()
        visible = AppKit.NSScreen.mainScreen().visibleFrame()
        origin = (
            visible.origin.x + visible.size.width - WINDOW_W_PT - SCREEN_INSET_PT,
            visible.origin.y + SCREEN_INSET_PT,
        )
        self.panel = _panel((origin, (WINDOW_W_PT, WINDOW_H_PT)))
        root = AppKit.NSView.alloc().initWithFrame_(((0, 0), (WINDOW_W_PT, WINDOW_H_PT)))
        root.setWantsLayer_(True)
        # Review aid: ZOYA_OVERLAY_SPEED=0.1 replays every animation at 10 % speed.
        root.layer().setSpeed_(float(os.environ.get(SPEED_ENV, "1")))
        self.panel.setContentView_(root)
        self.pet = Pet(self.reduce_motion, self.contrast)
        self.pet.layer.setPosition_(
            (WINDOW_W_PT - SHADOW_ROOM_PT - PET_PT / 2, SHADOW_ROOM_PT + PET_PT / 2)
        )
        root.layer().addSublayer_(self.pet.layer)
        self.bubble, self.bubble_content = self._bubble()
        root.addSubview_(self.bubble)
        self.label = _label(LABEL_PT, AppKit.NSFontWeightSemibold, self._secondary())
        self.caption = _label(
            CAPTION_PT, AppKit.NSFontWeightMedium, AppKit.NSColor.labelColor(), CAPTION_LINES
        )
        for view in (self.label, self.caption):
            self.bubble_content.addSubview_(view)
        self.base = ("idle", "", "")  # state, step, task: what shows when Zoya isn't talking
        self.speaking = False
        self.rings: list[Any] = []
        self.latencies_ms: list[float] = []
        self.bubble.setAlphaValue_(0.0)
        self.show()  # first show: no animation
        self.panel.orderFrontRegardless()  # visible without activating Zoya

    def _secondary(self) -> Any:
        return (
            AppKit.NSColor.labelColor() if self.contrast else AppKit.NSColor.secondaryLabelColor()
        )

    def _bubble(self) -> tuple[Any, Any]:
        frame = ((0, 0), (BUBBLE_MAX_W_PT, 60))
        if self.reduce_transparency:  # opaque surface
            view = AppKit.NSView.alloc().initWithFrame_(frame)
            view.setWantsLayer_(True)
            view.layer().setBackgroundColor_(AppKit.NSColor.windowBackgroundColor().CGColor())
            content = view
        elif hasattr(AppKit, "NSGlassEffectView"):  # Liquid Glass, macOS 26: the one glass surface
            view = AppKit.NSGlassEffectView.alloc().initWithFrame_(frame)
            view.setStyle_(AppKit.NSGlassEffectViewStyleRegular)
            view.setTintColor_(
                AppKit.NSColor.windowBackgroundColor().colorWithAlphaComponent_(GLASS_TINT_ALPHA)
            )
            content = AppKit.NSView.alloc().initWithFrame_(frame)
            view.setContentView_(content)
        else:
            view = AppKit.NSVisualEffectView.alloc().initWithFrame_(frame)
            view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
            view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            view.setState_(AppKit.NSVisualEffectStateActive)
            content = view
        view.setWantsLayer_(True)
        if hasattr(view, "setCornerRadius_"):
            view.setCornerRadius_(BUBBLE_RADIUS_PT)
        view.layer().setCornerRadius_(BUBBLE_RADIUS_PT)
        view.layer().setCornerCurve_(Quartz.kCACornerCurveContinuous)
        if not hasattr(view, "setContentView_"):
            view.layer().setMasksToBounds_(True)
        if self.contrast:  # a structural edge, only for Increase Contrast
            view.layer().setBorderWidth_(1.5)
            view.layer().setBorderColor_(AppKit.NSColor.labelColor().CGColor())
        return view, content

    # --- updates ------------------------------------------------------------------------------

    def apply(self, message: dict[str, Any]) -> None:
        kind = message.get("k")
        if kind == "state":
            self.speaking = False
            self.base = (message["state"], message.get("step", ""), message.get("task", ""))
            if message["state"] == "listening":
                self._set_caption("", user=False)  # a new turn starts clean
        elif kind == "zoya":
            self.speaking = True
            self._set_caption(message["text"], user=False)
        elif kind == "user":
            self._set_caption(message["text"], user=True)
        elif kind == "speech_done":
            self.speaking = False
        elif kind == "ring":
            self.ring(message["rect"])
        self.show()
        if "t" in message:
            self.latencies_ms.append((time.time() - message["t"]) * 1000)

    def _set_caption(self, text: str, user: bool) -> None:
        self.caption.setStringValue_(f"“{text}”" if user and text else text)  # never animated
        weight = AppKit.NSFontWeightRegular if user else AppKit.NSFontWeightMedium
        self.caption.setFont_(
            AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(CAPTION_PT, weight)
        )

    def show(self) -> None:
        state, step, task = ("speaking", "", self.base[2]) if self.speaking else self.base
        label = LABELS.get(state, LABELS["idle"])
        if step and state in ("thinking", "acting"):
            label = step  # already a plain verb ("Clicking", "Recalling")
        self.label.setStringValue_(f"{task} · {label}" if task else label)
        self.pet.set_state(state)
        self._layout_bubble()
        visible = state != "idle"
        if visible:
            self._fade_bubble(1.0)
        else:
            AppHelper.callLater(IDLE_HIDE_S, self._hide_if_idle)

    def _hide_if_idle(self) -> None:
        if not self.speaking and self.base[0] == "idle":
            self._fade_bubble(0.0)

    def _fade_bubble(self, alpha: float) -> None:
        if self.bubble.alphaValue() == alpha:
            return
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(FADE_S)
        self.bubble.animator().setAlphaValue_(alpha)
        AppKit.NSAnimationContext.endGrouping()

    def _layout_bubble(self) -> None:
        """Fit the bubble to its text, bottom-aligned with the pet and right next to it."""
        text_max = BUBBLE_MAX_W_PT - 2 * BUBBLE_PAD_X_PT
        label_size = self.label.cell().cellSizeForBounds_(((0, 0), (text_max, 1000)))
        has_caption = bool(self.caption.stringValue())
        caption_size = (
            self.caption.cell().cellSizeForBounds_(((0, 0), (text_max, 1000)))
            if has_caption
            else AppKit.NSMakeSize(0, 0)
        )
        # Whole points: fractional frames blur text.
        text_w = math.ceil(min(text_max, max(label_size.width, caption_size.width)))
        width = text_w + 2 * BUBBLE_PAD_X_PT
        gap = LABEL_GAP_PT if has_caption else 0.0
        height = math.ceil(label_size.height + gap + caption_size.height + 2 * BUBBLE_PAD_Y_PT)
        right = WINDOW_W_PT - SHADOW_ROOM_PT - PET_PT - BUBBLE_GAP_PT
        # Shorter than the pet: centred on it. Taller: bottom-aligned with it.
        bottom = SHADOW_ROOM_PT + max(0.0, math.floor((PET_PT - height) / 2))
        self.bubble.setFrame_(((right - width, bottom), (width, height)))
        self.bubble_content.setFrame_(((0, 0), (width, height)))
        self.caption.setFrame_(((BUBBLE_PAD_X_PT, BUBBLE_PAD_Y_PT), (text_w, caption_size.height)))
        self.label.setFrame_(
            (
                (BUBBLE_PAD_X_PT, height - BUBBLE_PAD_Y_PT - label_size.height),
                (text_w, label_size.height),
            )
        )

    def ring(self, rect: list[float]) -> None:
        """Ring a global top-left-origin rect (AppKit's origin: the main screen's bottom-left)."""
        x, y, width, height = rect
        main_height = AppKit.NSScreen.screens()[0].frame().size.height
        pad = RING_LINE_PT * 3  # room for the glow and the entering scale
        frame = ((x - pad, main_height - y - height - pad), (width + 2 * pad, height + 2 * pad))
        panel = _panel(frame)
        view = AppKit.NSView.alloc().initWithFrame_(((0, 0), frame[1]))
        view.setWantsLayer_(True)
        layer = Quartz.CALayer.layer()  # own layer: scales about its centre
        layer.setBounds_(((0, 0), (width, height)))
        layer.setPosition_((pad + width / 2, pad + height / 2))
        tone = AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
            *(c / 255 for c in RING_RGB), 1.0
        ).CGColor()  # the ring wears Zoya's colour too
        layer.setBorderWidth_(RING_LINE_PT)  # the ring is the state itself, not faked depth
        layer.setBorderColor_(tone)
        layer.setCornerRadius_(min(12.0, height / 2))
        layer.setShadowColor_(tone)
        layer.setShadowOpacity_(0.5)
        layer.setShadowRadius_(6.0)
        layer.setShadowOffset_((0, 0))
        view.layer().addSublayer_(layer)
        panel.setContentView_(view)
        panel.orderFrontRegardless()
        _animate(layer, "opacity", 1.0, RING_ENTER_S, start=0.0)
        if not self.reduce_motion:
            _animate(layer, "transform.scale", 1.0, RING_ENTER_S, start=RING_ENTER_SCALE)
        self.rings.append(panel)
        AppHelper.callLater(RING_SHOW_S, self._fade_ring, panel, layer)

    def _fade_ring(self, panel: Any, layer: Any) -> None:
        _animate(layer, "opacity", 0.0, EXIT_S)
        AppHelper.callLater(EXIT_S, self._drop_ring, panel)

    def _drop_ring(self, panel: Any) -> None:
        panel.orderOut_(None)
        if panel in self.rings:
            self.rings.remove(panel)


def _read_stdin(presence: Presence) -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        AppHelper.callAfter(presence.apply, message)
    latencies = presence.latencies_ms
    if latencies:  # printed here: stopping the AppKit loop exits without flushing Python
        print(
            f"overlay: {len(latencies)} updates, event→applied median "
            f"{statistics.median(latencies):.1f} ms, max {max(latencies):.1f} ms",
            file=sys.stderr,
            flush=True,
        )
    AppHelper.callAfter(AppHelper.stopEventLoop)  # Zoya quit or crashed: the pipe closed


def run() -> int:
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # no Dock, no focus
    presence = Presence()
    threading.Thread(
        target=_read_stdin, args=(presence,), name="overlay-stdin", daemon=True
    ).start()
    AppHelper.runEventLoop(installInterrupt=True)
    return 0
