"""The pill's motion under the frequency gate (D152): every transition under 150 ms, exits faster
than entrances, nothing staggered or bouncing, and each change starts from what is on screen so
an interrupted move never jumps. Reduce Motion turns every transition into a cross-fade."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import Quartz

from zoya.pill_style import ease

ENTER_S = 0.12
EXIT_S = 0.08
BEAT_S = 0.1
BEAT_SQUINT = 0.15
BEAT_DIM = 0.35
EXIT_STATES = frozenset({"idle", "stopped"})
GEOMETRY = ("bounds", "position", "cornerRadius", "transform")
FRAME = ("bounds", "position")


def seconds_for(state: str) -> float:
    return EXIT_S if state in EXIT_STATES else ENTER_S


def still(change: Callable[[], None]) -> None:
    """Apply layer changes on this frame with no implicit animation."""
    Quartz.CATransaction.begin()
    Quartz.CATransaction.setDisableActions_(True)
    change()
    Quartz.CATransaction.commit()


def settle(
    layer: Any, change: Callable[[], None], seconds: float, keys: tuple[str, ...] = GEOMETRY
) -> None:
    """Make the change, animating each key that moved from its value on screen now; a key
    whose target is unchanged keeps its move in flight."""
    shown = layer.presentationLayer() or layer
    starts = {key: shown.valueForKey_(key) for key in keys}
    models = {key: layer.valueForKey_(key) for key in keys}
    still(change)
    for key in keys:
        end = layer.valueForKey_(key)
        if models[key] == end or starts[key] is None or starts[key] == end:
            continue
        move = Quartz.CABasicAnimation.animationWithKeyPath_(key)
        move.setFromValue_(starts[key])
        move.setToValue_(end)
        move.setDuration_(seconds)
        move.setTimingFunction_(ease())
        layer.addAnimation_forKey_(move, f"move.{key}")


def cross_fade(layer: Any, seconds: float) -> None:
    """Reduce Motion: the next committed change to this layer's tree dissolves in place."""
    fade = Quartz.CATransition.animation()
    fade.setType_(Quartz.kCATransitionFade)
    fade.setDuration_(seconds)
    layer.addAnimation_forKey_(fade, "fade")


def beat(layers: list[Any], reduce_motion: bool) -> None:
    """One blink: the visual for a sound that doesn't change the state."""
    key, low = ("opacity", BEAT_DIM) if reduce_motion else ("transform.scale.y", BEAT_SQUINT)
    blink = Quartz.CAKeyframeAnimation.animationWithKeyPath_(key)
    blink.setValues_([1.0, low, 1.0])
    blink.setKeyTimes_([0.0, 0.4, 1.0])
    blink.setDuration_(BEAT_S)
    blink.setTimingFunction_(ease())
    for layer in layers:
        layer.addAnimation_forKey_(blink, "beat")
