"""Zoya's presence (Phase 7 redesign): a small rounded character drawn with Core Animation only.

A squircle body filled with a two-tone gradient of the state's colour, three soft clouds drifting
inside it, and two eyes whose shape and motion carry the state. Inspired by Plane's Agent Avatar
Lab (https://agents.plane.so, reference only, no assets copied) and ChatGPT Voice's flowing orb.

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
PET_RADIUS_PT = 24.0
EYE_W, EYE_H, EYE_R = 8.0, 12.0, 3.0
EYE_GAP = 18.0  # centre to centre
EYE_Y = 33.0  # a little below the middle, like a face
CLOUD_PT = 64.0
CLOUD_ORBIT_PT = 14.0
CLOUD_PERIODS_S = (13.0, 19.0, -27.0)
POSE_S = 0.32
EASE_OUT_QUINT = (0.22, 1.0, 0.36, 1.0)
CROSSFADE_S = 0.2

# state → (top-left colour, bottom-right colour) as sRGB 0..255; tinted, never pure black/white
PALETTE: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "idle": ((150, 146, 184), (96, 92, 132)),
    "listening": ((104, 176, 255), (46, 104, 240)),
    "thinking": ((164, 132, 255), (92, 70, 226)),
    "acting": ((72, 212, 190), (18, 138, 128)),
    "speaking": ((108, 220, 158), (28, 156, 100)),
    "waiting": ((255, 196, 102), (236, 132, 40)),
    "stopped": ((170, 171, 180), (118, 119, 128)),
    "error": ((255, 128, 112), (214, 58, 60)),
}
EYE_COLOUR = (250, 250, 255)

# state → (left eye, right eye) as (cx, cy, w, h, radius); orbit/bob/talk loops are added on top
_L, _R = PET_PT / 2 - EYE_GAP / 2, PET_PT / 2 + EYE_GAP / 2
POSES: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {
    "idle": ((_L, EYE_Y, EYE_W, EYE_H, EYE_R), (_R, EYE_Y, EYE_W, EYE_H, EYE_R)),
    "listening": ((_L - 1, EYE_Y + 1, 9.0, 15.0, 3.5), (_R + 1, EYE_Y + 1, 9.0, 15.0, 3.5)),
    "thinking": ((38.0, 38.0, 10.0, 10.0, 5.0), (38.0, 38.0, 10.0, 10.0, 5.0)),  # one dot
    "acting": ((28.0, 38.0, 8.0, 8.0, 4.0), (48.0, 38.0, 8.0, 8.0, 4.0)),  # two orbiting dots
    "speaking": ((_L, EYE_Y, EYE_W, EYE_H, EYE_R), (_R, EYE_Y, EYE_W, EYE_H, EYE_R)),
    "waiting": ((_L, EYE_Y + 6, EYE_W, EYE_H, EYE_R), (_R, EYE_Y + 6, EYE_W, EYE_H, EYE_R)),
    "stopped": ((_L, EYE_Y, 11.0, 3.0, 1.5), (_R, EYE_Y, 11.0, 3.0, 1.5)),
    "error": ((_L, EYE_Y - 2, 10.0, 3.0, 1.5), (_R, EYE_Y - 2, 10.0, 3.0, 1.5)),
}


def _cg(rgb: tuple[int, int, int], alpha: float = 1.0) -> Any:
    red, green, blue = (c / 255 for c in rgb)
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(red, green, blue, alpha).CGColor()


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
        self.layer = Quartz.CALayer.layer()  # host: soft ambient shadow
        self.layer.setBounds_(((0, 0), (PET_PT, PET_PT)))
        path = Quartz.CGPathCreateWithRoundedRect(
            ((0, 0), (PET_PT, PET_PT)), PET_RADIUS_PT, PET_RADIUS_PT, None
        )
        self.layer.setShadowPath_(path)
        self.layer.setShadowColor_(_cg((20, 18, 40)))
        self.layer.setShadowOpacity_(0.28)
        self.layer.setShadowRadius_(14.0)
        self.layer.setShadowOffset_((0, -6))
        self.plate = self._sublayer(self.layer)  # tight contact shadow, then the body
        self.plate.setShadowPath_(path)
        self.plate.setShadowColor_(_cg((20, 18, 40)))
        self.plate.setShadowOpacity_(0.22)
        self.plate.setShadowRadius_(1.5)
        self.plate.setShadowOffset_((0, -1))
        self.body = Quartz.CAGradientLayer.layer()
        self._place(self.body, self.plate)
        self.body.setCornerRadius_(PET_RADIUS_PT)
        self.body.setCornerCurve_(Quartz.kCACornerCurveContinuous)
        self.body.setMasksToBounds_(True)
        self.body.setStartPoint_((0.0, 1.0))
        self.body.setEndPoint_((1.0, 0.0))
        if contrast:
            self.body.setBorderWidth_(1.5)
            self.body.setBorderColor_(AppKit.NSColor.labelColor().CGColor())
        self.clouds = [self._cloud(period, index) for index, period in enumerate(CLOUD_PERIODS_S)]
        self.face = self._sublayer(self.body)  # eyes move and orbit together
        self.eyes = [self._eye(), self._eye()]

    def _sublayer(self, parent: Any) -> Any:
        layer = Quartz.CALayer.layer()
        self._place(layer, parent)
        return layer

    @staticmethod
    def _place(layer: Any, parent: Any) -> None:
        layer.setBounds_(((0, 0), (PET_PT, PET_PT)))
        layer.setPosition_((PET_PT / 2, PET_PT / 2))
        parent.addSublayer_(layer)

    def _cloud(self, period: float, index: int) -> Any:
        """A soft radial highlight (or shade) on a slowly turning arm: the flowing interior."""
        arm = self._sublayer(self.body)
        cloud = Quartz.CAGradientLayer.layer()
        cloud.setType_(Quartz.kCAGradientLayerRadial)
        shade = index == 2
        tint = (30, 24, 70) if shade else EYE_COLOUR
        cloud.setColors_([_cg(tint, 0.22 if shade else 0.38), _cg(tint, 0.0)])
        cloud.setStartPoint_((0.5, 0.5))
        cloud.setEndPoint_((1.0, 1.0))
        cloud.setBounds_(((0, 0), (CLOUD_PT, CLOUD_PT)))
        angle = index * 2 * math.pi / len(CLOUD_PERIODS_S)
        cloud.setPosition_(
            (
                PET_PT / 2 + CLOUD_ORBIT_PT * math.cos(angle),
                PET_PT / 2 + CLOUD_ORBIT_PT * math.sin(angle),
            )
        )
        arm.addSublayer_(cloud)
        if not self.reduce_motion:
            direction = 1 if period > 0 else -1
            spin = _loop(
                "transform.rotation.z",
                [0.0, direction * 2 * math.pi],
                abs(period),
                mode=Quartz.kCAAnimationLinear,
            )
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
        for layer in (*self.eyes, self.face, self.body):
            layer.setTransform_(Quartz.CATransform3DIdentity)
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
