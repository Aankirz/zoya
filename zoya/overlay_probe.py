"""Frame probe for the motion harness (scripts/motion_harness.py, S2-Feel). Off unless
ZOYA_MOTION_PROBE names a file: then every overlay message and every display frame is logged
there, so a transition's first frame and its length are measured, not guessed.

Times are CACurrentMediaTime seconds, the clock the display link ticks on; the harness stamps
each message with the same clock in "m".

APIs: https://developer.apple.com/documentation/appkit/nsscreen/displaylink(target:selector:)
https://developer.apple.com/documentation/quartzcore/cadisplaylink
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import AppKit
import Quartz
from PyObjCTools import AppHelper

PROBE_ENV = "ZOYA_MOTION_PROBE"
REDUCE_ENV = "ZOYA_MOTION_PROBE_REDUCE"
FLUSH_S = 0.5
AMBIENT_KEYS = frozenset({"loop", "breathe"})


def _rect(frame: Any) -> list[float]:
    return [
        round(v, 2) for v in (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)
    ]


def _busy(layers: list[Any]) -> list[str]:
    keys: list[str] = []
    for layer in layers:
        for key in layer.animationKeys() or []:
            if key not in AMBIENT_KEYS:
                keys.append(str(key))
    return sorted(keys)


def _shown(layer: Any) -> Any:
    shown = layer.presentationLayer()
    return shown if shown is not None else layer


def _eye(layer: Any) -> list[float]:
    shown = _shown(layer)
    bounds = shown.bounds()
    return [round(bounds.size.width, 2), round(bounds.size.height, 2), round(shown.opacity(), 3)]


def _window(panel: Any) -> list[float] | None:
    if panel is None or not panel.isVisible():
        return None
    return [*_rect(panel.frame()), round(panel.alphaValue(), 3)]


def _view(view: Any) -> list[float]:
    layer = view.layer()
    frame = _shown(layer).frame() if layer is not None else view.frame()
    alpha = _shown(layer).opacity() if layer is not None else view.alphaValue()
    return [*_rect(frame), round(alpha * (0.0 if view.isHidden() else 1.0), 3)]


def _tint(view: Any) -> list[float]:
    tint = view.tintColor()
    if tint is None:
        return []
    srgb = tint.colorUsingColorSpace_(AppKit.NSColorSpace.sRGBColorSpace())
    return [
        round(srgb.redComponent(), 3),
        round(srgb.greenComponent(), 3),
        round(srgb.alphaComponent(), 3),
    ]


def _dark(window: Any) -> bool:
    names = [AppKit.NSAppearanceNameAqua, AppKit.NSAppearanceNameDarkAqua]
    best = window.effectiveAppearance().bestMatchFromAppearancesWithNames_(names)
    return best == AppKit.NSAppearanceNameDarkAqua


class Probe(AppKit.NSObject):
    def setUp_(self, presence: Any) -> Any:  # noqa: N802 — NSObject init style
        self.presence = presence
        self.rows: list[str] = []
        self.path = Path(os.environ[PROBE_ENV])
        self.contexts: list[float] = []
        return self

    def snapshot(self) -> dict[str, Any]:
        pill, glow = self.presence.pill, self.presence.glow
        layers = [
            *pill.eyes,
            pill.eyes_box,
            pill.face.layer(),
            pill.bubble.layer(),
            pill.pill.layer(),
        ]
        layers += [layer for layer in (glow.edge,) if layer is not None]
        return {
            "state": pill.state,
            "panel": _window(pill.panel),
            "pill": _view(pill.pill),
            "tint": _tint(pill.pill),
            "bubble": _view(pill.bubble),
            "eyes": _eye(pill.eyes[0]),
            "eyes_box": round(_shown(pill.eyes_box).opacity(), 3),
            "label": str(pill.label.stringValue()),
            "glow": _window(glow.panel),
            "cursor": _window(glow.cursor),
            "rings": len(self.presence.rings),
            "windows": sum(1 for w in AppKit.NSApp().windows() if w.isVisible()),
            "dark": _dark(pill.panel),
            "busy": _busy(layers),
            "contexts": len(self.contexts),
        }

    def tick_(self, link: Any) -> None:
        row = {"k": "frame", "t": link.timestamp(), "next": link.targetTimestamp()}
        row.update(self.snapshot())
        self.rows.append(json.dumps(row))

    def flush(self) -> None:
        if self.rows:
            with self.path.open("a", encoding="utf-8") as out:
                out.write("\n".join(self.rows) + "\n")
            self.rows = []
        AppHelper.callLater(FLUSH_S, self.flush)


def _wrap_apply(probe: Probe, presence: Any) -> None:
    apply = presence.apply

    def measured(message: dict[str, Any]) -> None:
        start = Quartz.CACurrentMediaTime()
        apply(message)
        end = Quartz.CACurrentMediaTime()
        row = {"k": "msg", "id": message.get("probe"), "m": message.get("m"), "start": start}
        row.update({"end": end, "msg": message.get("k"), "state": presence.pill.state})
        probe.rows.append(json.dumps(row))

    presence.apply = measured


def _wrap_contexts(probe: Probe, pill: Any) -> None:
    animate = pill._animate

    def measured(seconds: float, change: Any, done: Any = None) -> None:
        token = Quartz.CACurrentMediaTime()
        probe.contexts.append(token)

        def finished() -> None:
            if token in probe.contexts:
                probe.contexts.remove(token)
            if done is not None:
                done()

        animate(seconds, change, finished)

    pill._animate = measured


def install(presence: Any) -> Any:
    """Start logging; returns the probe so it stays alive."""
    probe = Probe.alloc().init().setUp_(presence)
    if os.environ.get(REDUCE_ENV):
        presence.pill.reduce_motion = True
    _wrap_apply(probe, presence)
    _wrap_contexts(probe, presence.pill)
    link = AppKit.NSScreen.mainScreen().displayLinkWithTarget_selector_(probe, "tick:")
    link.addToRunLoop_forMode_(AppKit.NSRunLoop.mainRunLoop(), AppKit.NSRunLoopCommonModes)
    probe.link = link
    probe.flush()
    return probe
