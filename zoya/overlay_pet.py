"""Zoya's presence (Phase 7 redesign): a small character drawn with Core Animation only.

A flat, matte rounded square in Zoya blue, three darker translucent planes turning slowly
inside it, and two small eyes set low whose shape and motion carry the state. Visual language
from Plane's Agent Avatar Lab (https://agents.plane.so: flat silhouette, turning planes, low
eyes; reference only, no assets or paths copied).

Everything is GPU-composited layer animation: no timers, no per-frame Python. Transitions start
from the presentation value, so bursts of events retarget instead of jumping. Reduce Motion: no
loops, poses change with a short crossfade.
"""

from __future__ import annotations

import math
from typing import Any

import AppKit
import Quartz

PET_PT = 76.0
BODY_PT = 66.0  # the rounded square, inside the 76 pt layer (room for the turning planes' edge)
BODY_RADIUS_PT = 17.0
EYE_W, EYE_H, EYE_R = 8.0, 12.0, 2.0
EYE_GAP = 20.0  # centre to centre
EYE_Y = 30.0  # low in the body, like a face looking out
PLANE_W, PLANE_H, PLANE_R = 50.0, 30.0, 8.0
PLANE_OFFSETS = ((-16.0, 10.0), (12.0, -6.0), (18.0, 20.0))  # from the centre, before turning
PLANE_PERIODS_S = (22.0, -30.0, 38.0)
PLANE_TINT = ((0, 40, 130), 0.2)  # darker blue at 20 %: the matte "multiply" planes
ERROR_TILT_RAD = math.radians(24)  # error eyes droop: distinct from "stopped" without colour
POSE_S = 0.32
EASE_OUT_QUINT = (0.22, 1.0, 0.36, 1.0)
CROSSFADE_S = 0.2

# One signature colour, so the room remembers Zoya: states are told by the eyes, motion and the
# label, never by hue. Only "stopped" dims. sRGB 0..255, top-left → bottom-right: nearly flat.
ZOYA_BLUE = ((40, 140, 255), (10, 116, 240))  # the blue orb; no violet
ZOYA_BLUE_DIM = ((140, 158, 186), (126, 144, 172))
PALETTE: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    state: ZOYA_BLUE_DIM if state == "stopped" else ZOYA_BLUE
    for state in (
        "idle",
        "listening",
        "thinking",
        "acting",
        "speaking",
        "waiting",
        "stopped",
        "error",
    )
}
EYE_COLOUR = (250, 250, 255)

# state → (left eye, right eye) as (cx, cy, w, h, radius); orbit/bob/talk loops are added on top
_L, _R = PET_PT / 2 - EYE_GAP / 2, PET_PT / 2 + EYE_GAP / 2
POSES: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    "idle": ((_L, EYE_Y, EYE_W, EYE_H, EYE_R), (_R, EYE_Y, EYE_W, EYE_H, EYE_R)),
    "listening": ((_L - 1, EYE_Y + 1, 9.0, 15.0, 3.5), (_R + 1, EYE_Y + 1, 9.0, 15.0, 3.5)),
    "thinking": ((38.0, 36.0, 9.0, 9.0, 4.5), (38.0, 36.0, 9.0, 9.0, 4.5)),  # one dot
    "acting": ((27.0, 38.0, 8.0, 8.0, 4.0), (49.0, 38.0, 8.0, 8.0, 4.0)),  # two orbiting dots
    "speaking": ((_L, EYE_Y, EYE_W, EYE_H, EYE_R), (_R, EYE_Y, EYE_W, EYE_H, EYE_R)),
    "waiting": ((_L, EYE_Y + 6, EYE_W, EYE_H, EYE_R), (_R, EYE_Y + 6, EYE_W, EYE_H, EYE_R)),
    "stopped": ((_L, EYE_Y, 11.0, 3.0, 1.5), (_R, EYE_Y, 11.0, 3.0, 1.5)),
    "error": ((_L, EYE_Y - 2, 10.0, 3.0, 1.5), (_R, EYE_Y - 2, 10.0, 3.0, 1.5)),
}


def _cg(rgb: tuple[int, int, int], alpha: float = 1.0) -> Any:
    red, green, blue = (c / 255 for c in rgb)
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(red, green, blue, alpha).CGColor()


def _body_path() -> Any:
    """A rounded square: the most familiar, most remembered silhouette (an app icon with a face)."""
    inset = (PET_PT - BODY_PT) / 2
    return Quartz.CGPathCreateWithRoundedRect(
        ((inset, inset), (BODY_PT, BODY_PT)), BODY_RADIUS_PT, BODY_RADIUS_PT, None
    )


def _ease() -> Any:
    return Quartz.CAMediaTimingFunction.functionWithControlPoints____(*EASE_OUT_QUINT)


def _loop(key_path: str, values: list[float], seconds: float, **options: Any) -> Any:
    anim = Quartz.CAKeyframeAnimation.animationWithKeyPath_(key_path)
    anim.setValues_(values)
    anim.setDuration_(seconds)
    anim.setRepeatCount_(float("inf"))
    anim.setAdditive_(options.get("additive", False))
    if "key_times" in options:
        anim.setKeyTimes_(options["key_times"])
    anim.setCalculationMode_(options.get("mode", Quartz.kCAAnimationCubic))
    return anim


def _retarget(layer: Any, key_paths: tuple[str, ...]) -> None:
    """Freeze what is on screen into the model and drop the pose/loop animations, so the next pose
    animates from there (no snap back). The body's colour fade keeps running."""
    shown = layer.presentationLayer()
    if shown is None:
        return
    values = {path: shown.valueForKeyPath_(path) for path in key_paths}
    Quartz.CATransaction.begin()
    Quartz.CATransaction.setDisableActions_(True)
    for key in list(layer.animationKeys() or []):
        if key != "colors":
            layer.removeAnimationForKey_(key)
    for path, value in values.items():
        layer.setValue_forKeyPath_(value, path)
    Quartz.CATransaction.commit()


class Pet:
    """The character's layers. `set_state` is the only entry point; call on the main thread."""

    def __init__(self, reduce_motion: bool, contrast: bool) -> None:
        self.reduce_motion = reduce_motion
        self.state = ""
        path = _body_path()
        self.layer = Quartz.CALayer.layer()  # host: soft ambient shadow in the body's shape
        self.layer.setBounds_(((0, 0), (PET_PT, PET_PT)))
        self.layer.setShadowPath_(path)
        self.layer.setShadowColor_(_cg((20, 16, 44)))
        self.layer.setShadowOpacity_(0.26)
        self.layer.setShadowRadius_(12.0)
        self.layer.setShadowOffset_((0, -5))
        self.plate = self._sublayer(self.layer)  # tight contact shadow, then the body
        self.plate.setShadowPath_(path)
        self.plate.setShadowColor_(_cg((20, 16, 44)))
        self.plate.setShadowOpacity_(0.2)
        self.plate.setShadowRadius_(1.5)
        self.plate.setShadowOffset_((0, -1))
        self.body = Quartz.CAGradientLayer.layer()
        self._place(self.body, self.plate)
        self.body.setStartPoint_((0.0, 1.0))
        self.body.setEndPoint_((1.0, 0.0))
        mask = Quartz.CAShapeLayer.layer()
        mask.setPath_(path)
        self.body.setMask_(mask)
        if contrast:
            edge = Quartz.CAShapeLayer.layer()
            edge.setPath_(path)
            edge.setFillColor_(None)
            edge.setStrokeColor_(AppKit.NSColor.labelColor().CGColor())
            edge.setLineWidth_(3.0)  # half is clipped by the mask: a 1.5 pt inside edge
            self.contrast_edge = edge
        self.planes = [self._plane(i) for i in range(len(PLANE_PERIODS_S))]
        self.face = self._sublayer(self.body)  # eyes move and orbit together
        self.eyes = [self._eye(), self._eye()]
        if contrast:
            self.body.addSublayer_(self.contrast_edge)

    def _sublayer(self, parent: Any) -> Any:
        layer = Quartz.CALayer.layer()
        self._place(layer, parent)
        return layer

    @staticmethod
    def _place(layer: Any, parent: Any) -> None:
        layer.setBounds_(((0, 0), (PET_PT, PET_PT)))
        layer.setPosition_((PET_PT / 2, PET_PT / 2))
        parent.addSublayer_(layer)

    def _plane(self, index: int) -> Any:
        """A darker translucent rounded plane on its own slowly turning arm: the matte texture."""
        arm = self._sublayer(self.body)
        plane = Quartz.CAShapeLayer.layer()
        dx, dy = PLANE_OFFSETS[index]
        rect = ((PET_PT / 2 + dx - PLANE_W / 2, PET_PT / 2 + dy - PLANE_H / 2), (PLANE_W, PLANE_H))
        plane.setPath_(Quartz.CGPathCreateWithRoundedRect(rect, PLANE_R, PLANE_R, None))
        rgb, alpha = PLANE_TINT
        plane.setFillColor_(_cg(rgb, alpha))
        plane.setBounds_(((0, 0), (PET_PT, PET_PT)))
        plane.setPosition_((PET_PT / 2, PET_PT / 2))
        start = index * 2 * math.pi / len(PLANE_PERIODS_S)
        arm.setTransform_(Quartz.CATransform3DMakeRotation(start, 0, 0, 1))
        arm.addSublayer_(plane)
        if not self.reduce_motion:
            period = PLANE_PERIODS_S[index]
            turn = math.copysign(2 * math.pi, period)
            spin = Quartz.CABasicAnimation.animationWithKeyPath_("transform.rotation.z")
            spin.setByValue_(turn)
            spin.setDuration_(abs(period))
            spin.setRepeatCount_(float("inf"))
            spin.setAdditive_(True)
            arm.addAnimation_forKey_(spin, "drift")
        return arm

    def _eye(self) -> Any:
        eye = Quartz.CALayer.layer()
        eye.setBackgroundColor_(_cg(EYE_COLOUR))
        eye.setCornerCurve_(Quartz.kCACornerCurveContinuous)
        self.face.addSublayer_(eye)
        return eye

    # --- state ---------------------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        state = state if state in POSES else "idle"
        if state == self.state:
            return
        first = not self.state
        self.state = state
        self._colour(state, first)
        self._pose(state, first)
        if not self.reduce_motion:
            self._loops(state)

    def _colour(self, state: str, first: bool) -> None:
        colours = [_cg(c) for c in PALETTE[state]]
        if first:
            self.body.setColors_(colours)
            return
        shown = self.body.presentationLayer()
        anim = Quartz.CABasicAnimation.animationWithKeyPath_("colors")
        anim.setFromValue_(shown.colors() if shown is not None else self.body.colors())
        anim.setToValue_(colours)
        anim.setDuration_(POSE_S)
        anim.setTimingFunction_(_ease())
        self.body.setColors_(colours)
        self.body.addAnimation_forKey_(anim, "colors")

    def _pose(self, state: str, first: bool) -> None:
        for layer in (*self.eyes, self.face, self.body):
            _retarget(layer, ("position", "bounds", "cornerRadius", "transform"))
        Quartz.CATransaction.begin()
        if first:
            Quartz.CATransaction.setDisableActions_(True)
        elif self.reduce_motion:  # no movement: the new pose fades in
            Quartz.CATransaction.setDisableActions_(True)
            fade = Quartz.CATransition.animation()
            fade.setType_(Quartz.kCATransitionFade)
            fade.setDuration_(CROSSFADE_S)
            self.face.addAnimation_forKey_(fade, "pose")
        else:
            Quartz.CATransaction.setAnimationDuration_(POSE_S)
            Quartz.CATransaction.setAnimationTimingFunction_(_ease())
        for eye, (cx, cy, width, height, radius) in zip(self.eyes, POSES[state], strict=True):
            eye.setBounds_(((0, 0), (width, height)))
            eye.setPosition_((cx, cy))
            eye.setCornerRadius_(radius)
        for layer in (self.face, self.body):
            layer.setTransform_(Quartz.CATransform3DIdentity)
        tilt = ERROR_TILT_RAD if state == "error" else 0.0
        for eye, sign in zip(self.eyes, (1, -1), strict=True):  # eyes droop outward: sorry
            eye.setTransform_(Quartz.CATransform3DMakeRotation(sign * tilt, 0, 0, 1))
        Quartz.CATransaction.commit()

    def _loops(self, state: str) -> None:
        """One calm motion per state, starting after the pose transition settles."""
        begin = Quartz.CACurrentMediaTime() + POSE_S
        loops: list[tuple[Any, Any]] = []
        if state == "idle":
            blink = _loop(
                "transform.scale.y", [1.0, 1.0, 0.1, 1.0], 4.6, key_times=[0, 0.92, 0.96, 1]
            )
            loops += [(eye, blink) for eye in self.eyes]
            loops.append((self.face, _loop("position.x", [0, 1.5, -1.5, 0], 9.0, additive=True)))
        elif state == "listening":
            loops.append((self.body, _loop("transform.scale", [1.0, 1.035, 1.0], 1.1)))
        elif state == "thinking":
            loops.append((self.face, _loop("position.y", [0, 5, 0, -5, 0], 1.6, additive=True)))
        elif state == "acting":
            spin = _loop(
                "transform.rotation.z", [0, -2 * math.pi], 1.5, mode=Quartz.kCAAnimationLinear
            )
            loops.append((self.face, spin))
        elif state == "speaking":
            talk = _loop("transform.scale.y", [1.0, 0.7, 1.0], 0.34)
            loops += [(eye, talk) for eye in self.eyes]
            loops.append((self.body, _loop("transform.scale", [1.0, 1.025, 1.0], 0.34)))
        elif state == "waiting":
            blink = _loop(
                "transform.scale.y", [1.0, 1.0, 0.1, 1.0], 2.8, key_times=[0, 0.86, 0.93, 1]
            )
            loops += [(eye, blink) for eye in self.eyes]
            loops.append((self.body, _loop("transform.scale", [1.0, 1.02, 1.0], 2.8)))
        elif state == "error":  # one short "no" shake, then still
            shake = _loop("position.x", [0, -4, 4, -3, 3, 0], 0.5, additive=True)
            shake.setRepeatCount_(1.0)
            loops.append((self.face, shake))
        for layer, anim in loops:
            anim.setBeginTime_(begin)
            layer.addAnimation_forKey_(anim, "loop")
