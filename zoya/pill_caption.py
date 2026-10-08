"""The caption that grows out of the pill: what Zoya says or heard, with intent chips (D127)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import AppKit
import Quartz

from zoya import pill_motion
from zoya.pill_style import (
    CAPTION_PAD,
    CAPTION_RADIUS,
    CHIP_EDGE,
    CHIP_FILL,
    CHIP_GAP,
    CHIP_H,
    CHIP_INK,
    CHIP_PAD,
    CHIP_PT,
    LARGE_SCALE,
    Metrics,
    ease,
    fitted,
    font,
    srgb,
    text_field,
)


class CaptionMixin:
    """The bubble half of Pill; Pill provides the glass views, metrics and state."""

    sinking = False
    sink_room: tuple[float, float] = (0.0, 0.0)

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

    def caption_room(self, m: Metrics) -> tuple[float, float] | None:
        """The caption's size, or the size it is sinking from: the stage keeps room for a
        sinking caption until it is gone, so it is never clipped mid-move."""
        if bool(self.caption_text) and self.state not in ("idle", "waiting"):
            return self._caption_size(m)
        if self.sinking:
            return self.sink_room
        if self.caption_shown:
            size = self.bubble.frame().size
            return size.width, size.height
        return None

    def _caption(
        self, wanted: bool, pill_frame: Any, caption_frame: Any, shift: tuple[float, float]
    ) -> None:
        """`shift` keeps a sinking caption where it is on screen while the window moves."""
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
            (x, y), size = self.bubble.frame()
            self.bubble.setFrame_(((x + shift[0], y + shift[1]), size))
            self._sink(pill_frame, caption_frame)
        self.caption_shown = wanted

    def _grow(self, pill_frame: Any, caption_frame: Any) -> None:
        self.sinking = False
        self.bubble.setHidden_(False)
        seconds = pill_motion.ENTER_S
        if self.reduce_motion:
            self.bubble.setFrame_(caption_frame)
            self.bubble.setAlphaValue_(0.0)
            self._animate(seconds, lambda: self.bubble.animator().setAlphaValue_(1.0))
            return
        self.bubble.setAlphaValue_(1.0)
        self.bubble.setFrame_(self._bud(pill_frame, caption_frame))
        self._animate(seconds, lambda: self.bubble.animator().setFrame_(caption_frame))

    def _sink(self, pill_frame: Any, caption_frame: Any) -> None:
        self.sinking, self.sink_room = True, caption_frame[1]
        seconds = pill_motion.EXIT_S
        if self.reduce_motion:
            fade = lambda: self.bubble.animator().setAlphaValue_(0.0)  # noqa: E731
            self._animate(seconds, fade, self._hide_bubble)
            return
        bud = self._bud(pill_frame, caption_frame)
        self._animate(seconds, lambda: self.bubble.animator().setFrame_(bud), self._hide_bubble)

    def _hide_bubble(self) -> None:
        if self.caption_shown or not self.sinking:
            return
        self.sinking = False
        self.bubble.setHidden_(True)
        self.bubble.setAlphaValue_(1.0)
        self.layout()

    def _animate(
        self, seconds: float, change: Callable[[], None], done: Callable[[], None] | None = None
    ) -> None:
        def group(context: Any) -> None:
            context.setDuration_(seconds)
            context.setTimingFunction_(ease())
            change()

        AppKit.NSAnimationContext.runAnimationGroup_completionHandler_(group, done)
