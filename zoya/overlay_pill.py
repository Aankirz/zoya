"""The pill (D121, Glass Daylight): native Liquid Glass, Zoya's eyes, a Stop, and a caption that
grows out of the pill. Its look is in pill_style.py, its motion in pill_motion.py and the caption
in pill_caption.py."""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

import AppKit
import Foundation
import Quartz

from zoya import pill_motion
from zoya.pill_caption import CaptionMixin
from zoya.pill_style import (
    BLINK_S,
    CAPTION_GAP_PT,
    CAPTION_INK,
    CAPTION_RADIUS,
    CONFIRM_RING_PT,
    CONTAINER_SPACING_PT,
    CONTRAST_RING_PT,
    DRAG_SLOP_PT,
    EYE_BOX,
    EYE_GAP_PT,
    EYES,
    GLANCE_PT,
    GLANCE_S,
    GLOSS,
    GLOSS_EDGE,
    GLOSS_SHINE,
    GLOSS_STOPS,
    IDLE_TIP,
    INK,
    LARGE_SCALE,
    LEVEL_S,
    LOOKS,
    NOTCH_GAP_PT,
    OFFSET_KEY,
    OPEN_HELP,
    PAPER,
    READY,
    ROOM_PT,
    SCREEN_INSET_PT,
    STOP_LABEL,
    TALK_S,
    TINT_CAPTION_WARM,
    WAVE_ALPHA,
    WAVE_BAR_PT,
    WAVE_BARS,
    WAVE_GAP_PT,
    WAVE_MAX_PT,
    WAVE_REST,
    YES,
    Look,
    Metrics,
    accessibility,
    cg,
    color,
    fitted,
    font,
    glass,
    loop,
    metrics,
    panel,
    register_fonts,
    srgb,
    text_field,
)

WARM_STATES = ("listening", "waiting", "thinking", "speaking")
WARM_CAPTION = "Ready नमस्ते"


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


class Pill(CaptionMixin):
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
        self.posed: tuple[str, bool, bool] | None = None
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
        self._build_face(self.pill.contentView())
        self._build_bubble()

    def _build_face(self, body: Any) -> None:
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

    def _build_bubble(self) -> None:
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

    def warm_up(self) -> None:
        """Lay out every state once, unseen, so the first key-down is as quick as the rest."""
        self.panel.setAlphaValue_(0.0)
        self.caption_text = WARM_CAPTION
        for state in WARM_STATES:
            self.show(state, state.title(), state, state)
            self.panel.displayIfNeeded()
        self.caption_text = ""
        self.show("idle", "")
        self.panel.setAlphaValue_(1.0)

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
        if self.reduce_motion and state != self.state and self.state:
            pill_motion.cross_fade(self.face.layer(), pill_motion.seconds_for(state))
        self.state, self.words, self.stake, self.how = state, words, stake, how
        self.refresh()

    def beat(self) -> None:
        """A sound inside a state: one blink, on the frame the sound is queued."""
        layers = [self.eyes_box] if self.reduce_motion else self.eyes
        pill_motion.beat(layers, self.reduce_motion)

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
        pill_motion.still(lambda: self._paint(look))
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
        self._paint_face(look, warm, confirm)

    def _paint_face(self, look: Look, warm: bool, confirm: bool) -> None:
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
        """Move the eyes from wherever they are on screen; the same pose keeps its loop going."""
        if (pose, self.large, self.reduce_motion) == self.posed:
            return
        self.posed = (pose, self.large, self.reduce_motion)
        k = LARGE_SCALE if self.large else 1.0
        width, height, lift, tilt = EYES[pose]
        width, height, lift, gap = width * k, height * k, lift * k, EYE_GAP_PT * k
        box_w, box_h = self.eye_box()
        centers = (box_w / 2 - (width + gap) / 2, box_w / 2 + (width + gap) / 2)
        seconds = pill_motion.seconds_for(self.state)
        for eye, center, sign in zip(self.eyes, centers, (1, -1), strict=True):

            def change(eye: Any = eye, center: float = center, sign: int = sign) -> None:
                eye.removeAnimationForKey_("loop")
                eye.setBounds_(((0, 0), (width, height)))
                eye.setPosition_((center, box_h / 2 + lift))
                eye.setCornerRadius_(min(width, height) / 2)
                eye.setTransform_(Quartz.CATransform3DMakeRotation(sign * tilt, 0, 0, 1))

            if self.reduce_motion:
                pill_motion.still(change)
            else:
                pill_motion.settle(eye, change, seconds)
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

    def layout(self) -> None:
        """Lay out the stage, then move the window, shown together on one frame."""
        if not self.state:
            return
        m = metrics(self.large)
        self._fonts(m)
        width, height = (math.ceil(v) for v in self._content(m))
        wanted = bool(self.caption_text) and self.state not in ("idle", "waiting")
        room = self.caption_room(m)
        cap_w, cap_h = room or (0, 0)
        stage = (max(width, cap_w) + 2 * ROOM_PT, height + 2 * ROOM_PT)
        if room:
            stage = (stage[0], stage[1] + cap_h + CAPTION_GAP_PT)
        below = cap_h + CAPTION_GAP_PT if room and self.hanging else 0.0
        pill_y = ROOM_PT + below
        origin = self._origin(width, height, stage[0], pill_y)
        was = self.panel.frame().origin
        self.panel.disableScreenUpdatesUntilFlush()
        self._frame_stage(stage)
        pill_frame = (((stage[0] - width) / 2, pill_y), (width, height))
        self._frame_pill(m, pill_frame)
        cap_y = ROOM_PT if self.hanging else ROOM_PT + height + CAPTION_GAP_PT
        caption_frame = (((stage[0] - cap_w) / 2, cap_y), (cap_w, cap_h))
        self._caption(wanted, pill_frame, caption_frame, (was.x - origin[0], was.y - origin[1]))
        self.panel.setFrame_display_((origin, stage), False)
        Quartz.CATransaction.flush()

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
        self._frame_eyes(m, width, height)
        self.stop.setFrame_(((stop_x, (height - stop_pt) / 2), (stop_pt, stop_pt)))
        self.stop.layer().setCornerRadius_(stop_pt / 2)
        glyph = round(stop_pt * 0.3)
        box = (((stop_pt - glyph) / 2, (stop_pt - glyph) / 2), (glyph, glyph))
        pill_motion.still(lambda: self.glyph.setFrame_(box))

    def _frame_eyes(self, m: Metrics, width: float, height: float) -> None:
        box = self.eye_box()
        if self.state == "idle":
            eyes_x = (width - box[0]) / 2
        else:
            eyes_x = m.confirm_pad if self.state == "waiting" else m.pad_left
        frame = ((eyes_x, (height - box[1]) / 2), box)
        if self.reduce_motion:
            pill_motion.still(lambda: self.eyes_box.setFrame_(frame))
            return
        seconds = pill_motion.seconds_for(self.state)
        change = lambda: self.eyes_box.setFrame_(frame)  # noqa: E731
        pill_motion.settle(self.eyes_box, change, seconds, pill_motion.FRAME)

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

    def _frame_stage(self, stage: tuple[float, float]) -> None:
        self.container.setFrame_(((0, 0), stage))
        self.container.contentView().setFrame_(((0, 0), stage))

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
