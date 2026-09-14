"""The overlay child process (Phase 7): AppKit panel + ring. Started by zoya.overlay.start; reads
JSON lines on stdin and exits when Zoya closes the pipe. Display only: it never becomes key or
main, ignores the mouse, never activates, and draws nothing Zoya's model can see (screen.py
excludes this pid from every capture). API references: zoya/overlay.py docstring, plus
- https://developer.apple.com/documentation/quartzcore/calayer/presentation()
- https://developer.apple.com/documentation/quartzcore/camediatimingfunction/init(controlpoints::::)
- https://developer.apple.com/documentation/appkit/nsview/layerusescoreimagefilters
- https://developer.apple.com/documentation/appkit/nsfont/monospaceddigitsystemfont(ofsize:weight:)

Motion (make-interfaces-feel-better, translated to Core Animation): every animation starts from the
layer's presentation value so event bursts retarget instead of jumping; loops change only when the
state does; icon swaps cross-fade (scale 0.25→1, opacity 0→1, blur 4→0, 300 ms, no bounce; exits
150 ms with a 4 pt rise); nothing animates on first show or on caption text. Reduce Motion: fades
only. Every state also differs by colour, symbol and title.
"""

from __future__ import annotations

import json
import os
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
PANEL_MARGIN_PT = 24.0  # from the screen edge
PADDING_PT = 16.0
ORB_PT = 64.0
CORNER_RADIUS_PT = ORB_PT / 2 + PADDING_PT  # concentric with the orb in the top-left corner
TEXT_GAP_PT = 16.0
SYMBOL_PT = 26.0
ICON_BOX_PT = 40.0
TITLE_PT = 15.0
CAPTION_PT = 20.0  # readable on a projector from the back of a room
USER_PT = CAPTION_PT - 3
CAPTION_LINES = 2
RING_LINE_PT = 4.0
RING_SHOW_S = 1.4
RING_ENTER_SCALE = 1.08
RING_ENTER_S = 0.2
EXIT_S = 0.15  # exits are shorter and softer than enters
STATE_FADE_S = 0.15  # colour change: frequent, so a short fade only
ICON_ENTER_S = 0.3
ICON_START_SCALE = 0.25
ICON_BLUR_PT = 4.0
EXIT_RISE_PT = 4.0
SETTLE_S = 0.3  # a loop eases back to rest before the next state's loop starts
EASE = (0.2, 0.0, 0.0, 1.0)
USER_PREFIX = "You: "
SPEED_ENV = "ZOYA_OVERLAY_SPEED"

# state → (title, SF Symbol, colour name, loop)
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
# loop → (keyPath, peak, seconds per half cycle); every loop starts and ends at rest (1.0)
LOOPS = {
    "breathe": ("transform.scale", 1.05, 2.2),
    "pulse": ("transform.scale", 1.1, 0.45),
    "shimmer": ("opacity", 0.6, 0.9),
    "speak": ("transform.scale", 1.07, 0.3),
}
LOOP_KEY = "presence.loop"
# Optical centring inside the orb (pt, AppKit y-up): glyphs whose visual mass is off-centre.
OPTICAL_OFFSET = {
    "speaker.wave.2.fill": (1.5, 0.0),
    "cursorarrow.click": (1.0, -1.0),
    "exclamationmark.triangle.fill": (0.0, 1.0),
    "hand.raised.fill": (0.0, -0.5),
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


def _symbol_contents(name: str, scale: float) -> Any:
    image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    config = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        SYMBOL_PT, AppKit.NSFontWeightSemibold
    ).configurationByApplyingConfiguration_(
        AppKit.NSImageSymbolConfiguration.configurationWithPaletteColors_(
            [AppKit.NSColor.whiteColor()]
        )
    )
    return image.imageWithSymbolConfiguration_(config).layerContentsForContentsScale_(scale)


class Presence:
    """The panel's views and what they show. All methods run on the main thread."""

    def __init__(self) -> None:
        self.reduce_motion, self.reduce_transparency, self.contrast = _accessibility()
        screen = AppKit.NSScreen.mainScreen()
        self.scale = screen.backingScaleFactor()
        visible = screen.visibleFrame()
        x = visible.origin.x + visible.size.width - PANEL_WIDTH_PT - PANEL_MARGIN_PT
        frame = ((x, visible.origin.y + PANEL_MARGIN_PT), (PANEL_WIDTH_PT, PANEL_HEIGHT_PT))
        self.panel = _panel(frame, shadow=True)
        self.panel.setContentView_(self._material())
        self._build_orb()
        self._build_labels()
        self.base = ("idle", "", "")  # state, step, task: what shows when Zoya isn't talking
        self.speaking = False
        self.loop = ""
        self.symbol = ""
        self.colour = ""
        self.rings: list[Any] = []
        self.latencies_ms: list[float] = []
        self.show()  # first show: no animation
        self.panel.orderFrontRegardless()  # visible without activating Zoya

    def _material(self) -> Any:
        size = ((0, 0), (PANEL_WIDTH_PT, PANEL_HEIGHT_PT))
        if self.reduce_transparency:  # opaque surface
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
        if self.contrast:  # a structural edge, only for Increase Contrast
            view.setWantsLayer_(True)
            view.layer().setBorderWidth_(2.0)
            view.layer().setBorderColor_(AppKit.NSColor.labelColor().CGColor())
            view.layer().setCornerRadius_(CORNER_RADIUS_PT)
        inner.setWantsLayer_(True)
        inner.setLayerUsesCoreImageFilters_(True)  # icon blur
        # Review aid: ZOYA_OVERLAY_SPEED=0.1 replays every animation at 10 % speed.
        inner.layer().setSpeed_(float(os.environ.get(SPEED_ENV, "1")))
        self.inner = inner
        return view

    def _build_orb(self) -> None:
        """Orb = a group (loops scale it about its centre) holding a coloured halo for the glow, the
        orb with a tight contact shadow, and two icon layers that cross-fade."""
        centre = (PADDING_PT + ORB_PT / 2, PANEL_HEIGHT_PT - PADDING_PT - ORB_PT / 2)
        bounds = ((0, 0), (ORB_PT, ORB_PT))
        self.group = Quartz.CALayer.layer()
        self.group.setBounds_(bounds)
        self.group.setPosition_(centre)
        self.halo = Quartz.CALayer.layer()
        self.orb = Quartz.CALayer.layer()
        for layer, radius, opacity, offset in (
            (self.halo, 14.0, 0.3, 0.0),
            (self.orb, 2.0, 0.18, -1.0),
        ):
            layer.setBounds_(bounds)
            layer.setPosition_((ORB_PT / 2, ORB_PT / 2))
            layer.setCornerRadius_(ORB_PT / 2)
            layer.setShadowRadius_(radius)
            layer.setShadowOpacity_(opacity)
            layer.setShadowOffset_((0, offset))
            self.group.addSublayer_(layer)
        self.orb.setShadowColor_(AppKit.NSColor.blackColor().CGColor())
        self.icons = [self._icon_layer(), self._icon_layer()]
        for icon in self.icons:
            self.orb.addSublayer_(icon)
        self.inner.layer().addSublayer_(self.group)

    def _icon_layer(self) -> Any:
        icon = Quartz.CALayer.layer()
        icon.setBounds_(((0, 0), (ICON_BOX_PT, ICON_BOX_PT)))
        icon.setPosition_((ORB_PT / 2, ORB_PT / 2))
        icon.setContentsGravity_(Quartz.kCAGravityCenter)
        icon.setContentsScale_(self.scale)
        icon.setOpacity_(0.0)
        if not self.reduce_motion:  # rest in the "exited" pose, so the first enter scales in too
            blur = Quartz.CIFilter.filterWithName_("CIGaussianBlur")
            blur.setValue_forKey_(ICON_BLUR_PT, "inputRadius")
            blur.setName_("blur")
            icon.setFilters_([blur])
            icon.setValue_forKeyPath_(ICON_START_SCALE, "transform.scale")
        return icon

    def _build_labels(self) -> None:
        text_x = PADDING_PT + ORB_PT + TEXT_GAP_PT
        width = PANEL_WIDTH_PT - text_x - PADDING_PT
        secondary = (
            AppKit.NSColor.labelColor() if self.contrast else AppKit.NSColor.secondaryLabelColor()
        )
        self.title = _label(TITLE_PT, AppKit.NSFontWeightSemibold, AppKit.NSColor.labelColor())
        self.user = _label(USER_PT, AppKit.NSFontWeightRegular, secondary)
        self.zoya = _label(
            CAPTION_PT, AppKit.NSFontWeightMedium, AppKit.NSColor.labelColor(), CAPTION_LINES
        )
        top = PANEL_HEIGHT_PT - PADDING_PT
        self.title.setFrame_(((text_x, top - 24), (width, 22)))  # cap height level with the orb
        self.user.setFrame_(((text_x, top - 52), (width, 24)))
        self.zoya.setFrame_(((text_x, PADDING_PT), (width, 56)))
        for view in (self.title, self.user, self.zoya):
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
            self.zoya.setStringValue_(message["text"])  # captions change often: never animated
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
        first = not self.symbol
        state, step, task = ("speaking", "", self.base[2]) if self.speaking else self.base
        title, symbol, colour, loop = STATES.get(state, STATES["idle"])
        if step and state in ("thinking", "acting"):
            title = f"{title} · {step}"
        self.title.setStringValue_(f"{task} — {title}" if task else title)
        self._colour(colour, first)
        self._swap_symbol(symbol, first)
        self._loop(loop)

    def _colour(self, colour: str, first: bool) -> None:
        if colour == self.colour:
            return
        self.colour = colour
        cg = getattr(AppKit.NSColor, colour)().CGColor()
        Quartz.CATransaction.begin()  # implicit actions retarget from the presentation value
        Quartz.CATransaction.setDisableActions_(first)
        Quartz.CATransaction.setAnimationDuration_(STATE_FADE_S)
        Quartz.CATransaction.setAnimationTimingFunction_(_ease())
        for layer in (self.halo, self.orb):
            layer.setBackgroundColor_(cg)
        self.halo.setShadowColor_(cg)
        Quartz.CATransaction.commit()

    def _swap_symbol(self, name: str, first: bool) -> None:
        if name == self.symbol:
            return
        self.symbol = name
        leaving, entering = self.icons
        self.icons = [entering, leaving]
        dx, dy = OPTICAL_OFFSET.get(name, (0.0, 0.0))
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setDisableActions_(True)
        entering.setContents_(_symbol_contents(name, self.scale))
        entering.setPosition_((ORB_PT / 2 + dx, ORB_PT / 2 + dy))
        Quartz.CATransaction.commit()
        enter = ICON_ENTER_S
        if first:  # no entrance on launch: straight to the resting pose
            enter = 0.0
        # From the presentation value: a swap back mid-exit reverses instead of jumping.
        _animate(entering, "opacity", 1.0, enter)
        _animate(leaving, "opacity", 0.0, EXIT_S)
        if self.reduce_motion:
            return  # fades only
        _animate(entering, "transform.scale", 1.0, enter)
        _animate(entering, "transform.translation.y", 0.0, enter)
        _animate(entering, "filters.blur.inputRadius", 0.0, enter)
        _animate(leaving, "transform.scale", ICON_START_SCALE, EXIT_S)
        _animate(leaving, "transform.translation.y", EXIT_RISE_PT, EXIT_S)
        _animate(leaving, "filters.blur.inputRadius", ICON_BLUR_PT, EXIT_S)

    def _loop(self, loop: str) -> None:
        """Change the ambient loop only when the state's loop does: step updates never restart it.
        The old loop eases back to rest from wherever it is, then the new one starts at rest."""
        if loop == self.loop:
            return
        self.loop = loop
        group = self.group
        now = {path: _presented(group, path, 1.0) for path in ("transform.scale", "opacity")}
        group.removeAnimationForKey_(LOOP_KEY)
        for path, value in now.items():
            if abs(value - 1.0) > 1e-3:
                _animate(group, path, 1.0, SETTLE_S, start=value)
        if self.reduce_motion or not loop:
            return  # Reduce Motion: static states; colour, symbol and title still differ
        key_path, peak, seconds = LOOPS[loop]
        anim = Quartz.CABasicAnimation.animationWithKeyPath_(key_path)
        anim.setFromValue_(1.0)
        anim.setToValue_(peak)
        anim.setDuration_(seconds)
        anim.setAutoreverses_(True)
        anim.setRepeatCount_(float("inf"))
        anim.setBeginTime_(Quartz.CACurrentMediaTime() + SETTLE_S)
        anim.setTimingFunction_(
            Quartz.CAMediaTimingFunction.functionWithName_(
                Quartz.kCAMediaTimingFunctionEaseInEaseOut
            )
        )
        group.addAnimation_forKey_(anim, LOOP_KEY)

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
        blue = AppKit.NSColor.systemBlueColor().CGColor()
        layer.setBorderWidth_(RING_LINE_PT)  # the ring is the state itself, not faked depth
        layer.setBorderColor_(blue)
        layer.setCornerRadius_(min(12.0, height / 2))
        layer.setShadowColor_(blue)
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
