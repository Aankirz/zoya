"""The overlay child process (Phase 7): AppKit panel + ring. Started by zoya.overlay.start; reads
JSON lines on stdin and exits when Zoya closes the pipe. Display only: it never becomes key or
main, ignores the mouse, never activates, and draws nothing Zoya's model can see (screen.py
excludes this pid from every capture). API references: zoya/overlay.py docstring.
"""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from typing import Any

import AppKit
import Quartz
from PyObjCTools import AppHelper

PANEL_WIDTH_PT = 480.0
PANEL_HEIGHT_PT = 148.0
PANEL_MARGIN_PT = 24.0
CORNER_RADIUS_PT = 28.0
ORB_PT = 64.0
SYMBOL_PT = 26.0
TITLE_PT = 15.0
CAPTION_PT = 20.0  # readable on a projector from the back of a room
RING_LINE_PT = 4.0
RING_SHOW_S = 1.4
STATE_FADE_S = 0.18  # HIG motion: brief; also well inside the ~100 ms-to-start target
USER_PREFIX = "You: "

# state → (title, SF Symbol, colour name, animation)
STATES: dict[str, tuple[str, str, str, str]] = {
    "idle": ("Zoya", "circle.fill", "systemGrayColor", "breathe"),
    "listening": ("Listening", "waveform", "systemBlueColor", "pulse"),
    "thinking": ("Thinking", "sparkles", "systemIndigoColor", "shimmer"),
    "acting": ("Acting", "cursorarrow.click", "systemTealColor", "pulse"),
    "speaking": ("Speaking", "speaker.wave.2.fill", "systemGreenColor", "speak"),
    "waiting": ("Waiting for your yes", "hand.raised.fill", "systemOrangeColor", "breathe"),
    "stopped": ("Stopped", "stop.fill", "systemGrayColor", ""),
    "error": ("Something went wrong", "exclamationmark.triangle.fill", "systemRedColor", ""),
}
# animation → (keyPath, from, to, seconds per half cycle)
ANIMATIONS = {
    "breathe": ("transform.scale", 1.0, 1.05, 2.2),
    "pulse": ("transform.scale", 0.94, 1.1, 0.45),
    "shimmer": ("opacity", 0.55, 1.0, 0.9),
    "speak": ("transform.scale", 0.97, 1.08, 0.3),
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


def _panel(frame: Any) -> Any:
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
    return panel


def _label(size: float, weight: float, color: Any) -> Any:
    label = AppKit.NSTextField.labelWithString_("")  # plain text: page text is never markup
    label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size, weight))
    label.setTextColor_(color)
    label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    return label


class Presence:
    """The panel's views and what they show. All methods run on the main thread."""

    def __init__(self) -> None:
        self.reduce_motion, self.reduce_transparency, self.contrast = _accessibility()
        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - PANEL_WIDTH_PT - PANEL_MARGIN_PT
        frame = ((x, screen.origin.y + PANEL_MARGIN_PT), (PANEL_WIDTH_PT, PANEL_HEIGHT_PT))
        self.panel = _panel(frame)
        content = self._material()
        self.panel.setContentView_(content)
        self.orb, self.symbol = self._orb()
        self.title = _label(TITLE_PT, AppKit.NSFontWeightSemibold, AppKit.NSColor.labelColor())
        secondary = (
            AppKit.NSColor.labelColor() if self.contrast else AppKit.NSColor.secondaryLabelColor()
        )
        self.user = _label(CAPTION_PT - 3, AppKit.NSFontWeightRegular, secondary)
        self.zoya = _label(CAPTION_PT, AppKit.NSFontWeightMedium, AppKit.NSColor.labelColor())
        self.zoya.setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
        self.zoya.setMaximumNumberOfLines_(2)
        self._layout(content)
        self.base = ("idle", "", "")  # state, step, task: what shows when Zoya isn't talking
        self.speaking = False
        self.rings: list[Any] = []
        self.latencies_ms: list[float] = []
        self.show()
        self.panel.orderFrontRegardless()  # visible without activating Zoya

    def _material(self) -> Any:
        size = ((0, 0), (PANEL_WIDTH_PT, PANEL_HEIGHT_PT))
        if self.reduce_transparency:
            view = AppKit.NSView.alloc().initWithFrame_(size)
            view.setWantsLayer_(True)
            view.layer().setBackgroundColor_(AppKit.NSColor.windowBackgroundColor().CGColor())
            view.layer().setCornerRadius_(CORNER_RADIUS_PT)
            inner = view
        elif hasattr(AppKit, "NSGlassEffectView"):  # Liquid Glass, macOS 26
            view = AppKit.NSGlassEffectView.alloc().initWithFrame_(size)
            view.setCornerRadius_(CORNER_RADIUS_PT)
            inner = AppKit.NSView.alloc().initWithFrame_(size)
            view.setContentView_(inner)
        else:
            view = AppKit.NSVisualEffectView.alloc().initWithFrame_(size)
            view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
            view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            view.setState_(AppKit.NSVisualEffectStateActive)
            view.setWantsLayer_(True)
            view.layer().setCornerRadius_(CORNER_RADIUS_PT)
            view.layer().setMasksToBounds_(True)
            inner = view
        if self.contrast:
            view.setWantsLayer_(True)
            view.layer().setBorderWidth_(2.0)
            view.layer().setBorderColor_(AppKit.NSColor.labelColor().CGColor())
            view.layer().setCornerRadius_(CORNER_RADIUS_PT)
        self.inner = inner
        return view

    def _orb(self) -> tuple[Any, Any]:
        orb = AppKit.NSView.alloc().initWithFrame_(
            ((20, (PANEL_HEIGHT_PT - ORB_PT) / 2), (ORB_PT, ORB_PT))
        )
        orb.setWantsLayer_(True)
        layer = orb.layer()
        layer.setCornerRadius_(ORB_PT / 2)
        layer.setShadowOpacity_(0.35)
        layer.setShadowRadius_(10.0)
        layer.setShadowOffset_((0, 0))
        symbol = AppKit.NSImageView.alloc().initWithFrame_(((16, 16), (ORB_PT - 32, ORB_PT - 32)))
        symbol.setContentTintColor_(AppKit.NSColor.whiteColor())
        symbol.setSymbolConfiguration_(
            AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
                SYMBOL_PT, AppKit.NSFontWeightSemibold
            )
        )
        orb.addSubview_(symbol)
        return orb, symbol

    def _layout(self, content: Any) -> None:
        text_x = 20 + ORB_PT + 18
        width = PANEL_WIDTH_PT - text_x - 20
        self.title.setFrame_(((text_x, PANEL_HEIGHT_PT - 40), (width, 22)))
        self.user.setFrame_(((text_x, PANEL_HEIGHT_PT - 70), (width, 24)))
        self.zoya.setFrame_(((text_x, 14), (width, 54)))
        for view in (self.orb, self.title, self.user, self.zoya):
            self.inner.addSubview_(view)

    # --- updates ------------------------------------------------------------------------------

    def apply(self, message: dict[str, Any]) -> None:
        kind = message.get("k")
        if kind == "state":
            self.speaking = False
            self.base = (message["state"], message.get("step", ""), message.get("task", ""))
            if message["state"] == "listening":
                self.zoya.setStringValue_("")
        elif kind == "zoya":
            self.speaking = True
            self.zoya.setStringValue_(message["text"])
        elif kind == "user":
            self.user.setStringValue_(USER_PREFIX + message["text"])
        elif kind == "speech_done":
            self.speaking = False
        elif kind == "ring":
            self.ring(message["rect"])
        self.show()
        if "t" in message:
            self.latencies_ms.append((time.time() - message["t"]) * 1000)

    def show(self) -> None:
        state, step, task = ("speaking", "", self.base[2]) if self.speaking else self.base
        title, symbol, colour, animation = STATES.get(state, STATES["idle"])
        if step and state in ("thinking", "acting"):
            title = f"{title} · {step}"
        self.title.setStringValue_(f"{task} — {title}" if task else title)
        color = getattr(AppKit.NSColor, colour)()
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setAnimationDuration_(0 if self.reduce_motion else STATE_FADE_S)
        self.orb.layer().setBackgroundColor_(color.CGColor())
        self.orb.layer().setShadowColor_(color.CGColor())
        Quartz.CATransaction.commit()
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title)
        self.symbol.setImage_(image)
        self._animate(animation)

    def _animate(self, animation: str) -> None:
        layer = self.orb.layer()
        layer.removeAllAnimations()
        if self.reduce_motion or not animation:
            return  # Reduce Motion: static states, colour + symbol + title still differ
        key_path, low, high, seconds = ANIMATIONS[animation]
        anim = Quartz.CABasicAnimation.animationWithKeyPath_(key_path)
        anim.setFromValue_(low)
        anim.setToValue_(high)
        anim.setDuration_(seconds)
        anim.setAutoreverses_(True)
        anim.setRepeatCount_(float("inf"))
        anim.setTimingFunction_(
            Quartz.CAMediaTimingFunction.functionWithName_(
                Quartz.kCAMediaTimingFunctionEaseInEaseOut
            )
        )
        layer.addAnimation_forKey_(anim, "presence")

    def ring(self, rect: list[float]) -> None:
        """Ring a global top-left-origin rect (AppKit's origin: the main screen's bottom-left)."""
        x, y, width, height = rect
        main_height = AppKit.NSScreen.screens()[0].frame().size.height
        frame = ((x, main_height - y - height), (width, height))
        panel = _panel(frame)
        view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (width, height)))
        view.setWantsLayer_(True)
        layer = view.layer()
        layer.setBorderWidth_(RING_LINE_PT)
        layer.setBorderColor_(AppKit.NSColor.systemBlueColor().CGColor())
        layer.setCornerRadius_(min(12.0, height / 2))
        layer.setShadowColor_(AppKit.NSColor.systemBlueColor().CGColor())
        layer.setShadowOpacity_(0.6)
        layer.setShadowRadius_(8.0)
        panel.setContentView_(view)
        panel.orderFrontRegardless()
        self.rings.append(panel)
        AppHelper.callLater(RING_SHOW_S, self._drop_ring, panel)

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
