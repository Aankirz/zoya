"""The overlay child: the pill, the Hub, the menu-bar item and the action ring."""

from __future__ import annotations

import json
import os
import statistics
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import AppKit
import ApplicationServices
import Foundation
import Quartz
from PyObjCTools import AppHelper

from zoya import config, hotkey, hub_data, sparkle
from zoya.hub import Hub
from zoya.hub_bridge import OPEN_HUB_NOTICE
from zoya.overlay_glow import Glow
from zoya.overlay_pill import BLUE, Pill

IDLE_HIDE_S = 5.0
RING_LINE_PT = 4.0
RING_RGB = BLUE
RING_SHOW_S = 1.4
RING_ENTER_SCALE = 1.08
RING_ENTER_S = 0.2
EXIT_S = 0.15
EASE = (0.22, 1.0, 0.36, 1.0)
THEME_CHANGED = "AppleInterfaceThemeChangedNotification"
CONFIRM_HOW = "Say “confirm”, or “stop”"
CONFIRM_FALLBACK = "Waiting for you to say confirm"

LABELS = {
    "idle": "",
    "listening": "Listening",
    "thinking": "Thinking",
    "acting": "Working",
    "speaking": "Speaking",
    "stopped": "Stopped",
    "error": "Couldn’t finish that",
}


QUIT_KEY_CODE = 53
QUIT_FLAGS = AppKit.NSEventModifierFlagControl | AppKit.NSEventModifierFlagShift
CHORD_FLAGS = QUIT_FLAGS | AppKit.NSEventModifierFlagOption | AppKit.NSEventModifierFlagCommand
FOLLOW_POINTER_S = 1.0
USER_INPUT = (
    AppKit.NSEventMaskMouseMoved
    | AppKit.NSEventMaskLeftMouseDown
    | AppKit.NSEventMaskKeyDown
    | AppKit.NSEventMaskScrollWheel
)
STATUS_SYMBOL = "circle.fill"


_parent_gone = threading.Event()


def send_command(command: str) -> None:
    """Tell Zoya (the parent) to stop or quit: one JSON line on our stdout."""
    send_message({"cmd": command})


def send_message(message: dict[str, Any]) -> None:
    print(json.dumps(message), flush=True)


def _main_menu() -> Any:
    bar = AppKit.NSMenu.alloc().init()
    sections = (
        ("Zoya", (("Quit Zoya", "terminate:", "q"),)),
        ("Edit", (("Copy", "copy:", "c"), ("Select All", "selectAll:", "a"))),
        (
            "Window",
            (("Close Window", "performClose:", "w"), ("Minimize", "performMiniaturize:", "m")),
        ),
    )
    for name, items in sections:
        menu = AppKit.NSMenu.alloc().initWithTitle_(name)
        for title, action, key in items:
            menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
        holder = bar.addItemWithTitle_action_keyEquivalent_(name, None, "")
        bar.setSubmenu_forItem_(menu, holder)
    return bar


class Controls(AppKit.NSObject):
    """Menu-bar item (Stop, Quit Zoya) and the Control + Shift + Esc quit key. The status item's
    menu never activates this app, and the overlay panels stay click-through."""

    def install(self) -> Any:
        bar = AppKit.NSStatusBar.systemStatusBar()
        self.item = bar.statusItemWithLength_(AppKit.NSSquareStatusItemLength)
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            STATUS_SYMBOL, "Zoya"
        )
        image.setTemplate_(True)
        self.item.button().setImage_(image)
        self.item.button().setToolTip_("Zoya")
        menu = AppKit.NSMenu.alloc().init()
        entries = (
            ("Open Zoya", "openHub:"),
            ("Stop", "stop:"),
            (None, None),
            ("Quit Zoya", "quitZoya:"),
        )
        for title, action in entries:
            if title is None:
                menu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            entry = menu.addItemWithTitle_action_keyEquivalent_(title, action, "")
            entry.setTarget_(self)
        quit_entry = menu.itemWithTitle_("Quit Zoya")
        quit_entry.setKeyEquivalent_("\x1b")
        quit_entry.setKeyEquivalentModifierMask_(QUIT_FLAGS)  # shown in the menu, handled below
        self.item.setMenu_(menu)
        AppKit.NSApp().setMainMenu_(_main_menu())
        Foundation.NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "openHub:", OPEN_HUB_NOTICE, None
        )
        if not ApplicationServices.AXIsProcessTrusted():  # global key monitors need it
            print("overlay: no Accessibility access, Control + Shift + Esc is off", file=sys.stderr)
        self.monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            AppKit.NSEventMaskKeyDown, self.keyDown_
        )
        return self

    def keyDown_(self, event: Any) -> None:  # noqa: N802 — AppKit naming
        flags = event.modifierFlags() & CHORD_FLAGS
        if event.keyCode() == QUIT_KEY_CODE and flags == QUIT_FLAGS:
            send_command("quit")

    def stop_(self, _sender: Any) -> None:
        send_command("stop")

    def openHub_(self, _sender: Any) -> None:  # noqa: N802
        self.hub.show()

    def applicationShouldHandleReopen_hasVisibleWindows_(  # noqa: N802
        self, _app: Any, _visible: bool
    ) -> bool:
        self.hub.show()
        return False

    def quitZoya_(self, _sender: Any) -> None:  # noqa: N802
        send_command("quit")

    def applicationShouldTerminate_(self, _sender: Any) -> int:  # noqa: N802
        if _parent_gone.is_set():
            return AppKit.NSTerminateNow
        send_command("quit")
        return AppKit.NSTerminateCancel


def _pointer_screen() -> Any:
    point = AppKit.NSEvent.mouseLocation()
    for screen in AppKit.NSScreen.screens():
        if AppKit.NSPointInRect(point, screen.frame()):
            return screen
    return AppKit.NSScreen.mainScreen()


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


class Observer(AppKit.NSObject):
    def changed_(self, _notification: Any) -> None:
        self.callback()


def _observe(callback: Callable[[], None]) -> Any:
    observer = Observer.alloc().init()
    observer.callback = callback
    AppKit.NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
        observer,
        "changed:",
        AppKit.NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification,
        None,
    )
    Foundation.NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        observer, "changed:", THEME_CHANGED, None
    )
    return observer


class Presence:
    def __init__(self, menu: Any, open_hub: Callable[[], None]) -> None:
        self.pill = Pill(menu, on_stop=lambda: send_command("stop"), on_open=open_hub)
        self.observer = _observe(self.pill.environment_changed)
        self.base = ("idle", "", "")
        self.stake = ""
        self.on_status: Callable[[str], None] = lambda _state: None
        self.speaking = False
        self.rings: list[Any] = []
        self.glow = Glow(_panel, lambda: self.pill.reduce_motion)
        self.glow.own = {os.getpid(), os.getppid()}
        self.tool = ""
        self.input_monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            USER_INPUT, lambda _event: self.glow.user_input()
        )
        self.latencies_ms: list[float] = []
        self.screen_name = ""
        self.settings(hub_data.settings())
        self.follow_pointer()
        self.show()

    def settings(self, chosen: dict[str, Any]) -> None:
        self.pill.configure(
            chosen.get("largerText") is True,
            chosen.get("easierLetters") is True,
            str(chosen.get("pillPosition", "bottom")),
            hotkey.spoken(config.HOTKEYS.get(str(chosen.get("hotkey")), config.PUSH_TO_TALK_KEYS)),
        )

    def _update_hit(self) -> None:
        self.pill.click_through(bool(self.rings))

    def follow_pointer(self) -> None:
        screen = _pointer_screen()
        self.pill.place(screen)
        if screen.localizedName() != self.screen_name:
            self.screen_name = screen.localizedName()
            print(f"overlay: on {self.screen_name}", file=sys.stderr, flush=True)
        AppHelper.callLater(FOLLOW_POINTER_S, self.follow_pointer)

    def apply(self, message: dict[str, Any]) -> None:
        kind = message.get("k")
        if kind == "level":
            self.pill.set_level(float(message.get("v", 0.0)))
            return
        if kind == "state":
            self.speaking = False
            self.base = (message["state"], message.get("step", ""), message.get("task", ""))
            self.stake = message.get("stake", "")
            self.tool = message.get("tool", "")
            if message["state"] == "listening":
                self.pill.set_caption("", heard=False)
        elif kind == "zoya":
            self.speaking = True
            self.pill.set_caption(message["text"], heard=False)
        elif kind == "user":
            self.pill.set_caption(message["text"], heard=True)
        elif kind == "intent":
            if self.base[0] != "listening":
                return
            self.pill.set_caption(message["text"], heard=True, chips=message.get("chips", ()))
        elif kind == "speech_done":
            self.speaking = False
        elif kind == "ring":
            self.ring(message["rect"])
            self.glow.point_at(message["rect"])
        self.show()
        if "t" in message:
            self.latencies_ms.append((time.time() - message["t"]) * 1000)

    def show(self) -> None:
        state, step, task = self.base
        if self.speaking and state not in ("waiting", "error", "stopped"):
            state = "speaking"
        words = LABELS.get(state, "")
        if step and state in ("thinking", "acting"):
            words = step
        if task and words:
            words = f"{task} · {words}"
        self.glow.update(state, self.tool)
        if self.glow.app and state in ("acting", "thinking"):
            words = f"{words} · using {self.glow.app}"
        self.pill.show(state, words, self.stake or CONFIRM_FALLBACK, CONFIRM_HOW)
        self.on_status(state)
        self._update_hit()
        if state == "idle":
            AppHelper.callLater(IDLE_HIDE_S, self._hide_if_idle)

    def _hide_if_idle(self) -> None:
        if not self.speaking and self.base[0] == "idle":
            self.pill.set_caption("", heard=False)

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
        if not self.pill.reduce_motion:
            _animate(layer, "transform.scale", 1.0, RING_ENTER_S, start=RING_ENTER_SCALE)
        self.rings.append(panel)
        self._update_hit()
        AppHelper.callLater(RING_SHOW_S, self._fade_ring, panel, layer)

    def _fade_ring(self, panel: Any, layer: Any) -> None:
        _animate(layer, "opacity", 0.0, EXIT_S)
        AppHelper.callLater(EXIT_S, self._drop_ring, panel)

    def _drop_ring(self, panel: Any) -> None:
        panel.orderOut_(None)
        if panel in self.rings:
            self.rings.remove(panel)
        self._update_hit()


def _read_stdin(presence: Presence | None) -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "update" in message:
            AppHelper.callAfter(sparkle.answer, message["update"])
        elif isinstance(message.get("hub"), dict):
            AppHelper.callAfter(_hub_reply, message["hub"])
        elif presence is not None:
            AppHelper.callAfter(presence.apply, message)
    latencies = presence.latencies_ms if presence is not None else []
    if latencies:  # printed here: stopping the AppKit loop exits without flushing Python
        print(
            f"overlay: {len(latencies)} updates, event→applied median "
            f"{statistics.median(latencies):.1f} ms, max {max(latencies):.1f} ms",
            file=sys.stderr,
            flush=True,
        )
    _parent_gone.set()
    AppHelper.callAfter(AppHelper.stopEventLoop)  # Zoya quit or crashed: the pipe closed


PARENT_POLL_S = 0.5
_hub: list[Hub] = []


def _hub_reply(reply: dict[str, Any]) -> None:
    request = reply.get("id")
    if _hub and isinstance(request, int) and not isinstance(request, bool):
        _hub[0].reply(request, reply.get("ok") is True)


def _exit_when_orphaned(parent_pid: int) -> None:
    # The stdin pipe can stay open after Zoya dies (e.g. the terminal is closed), so also watch
    # the parent: once it's gone the overlay must not linger on screen.
    while os.getppid() == parent_pid:
        time.sleep(PARENT_POLL_S)
    os._exit(0)


def run(controls_only: bool = False) -> int:
    threading.Thread(
        target=_exit_when_orphaned, args=(os.getppid(),), name="overlay-parent", daemon=True
    ).start()
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    controls = Controls.alloc().init()
    controls.hub = Hub(send_message)
    _hub.append(controls.hub)
    controls.install()
    app.setDelegate_(controls)
    print(f"updates: {sparkle.start(lambda _version: send_command('update'))}", file=sys.stderr)
    presence = None if controls_only else Presence(controls.item.menu(), controls.hub.show)
    if presence is not None:
        controls.hub.on_settings = presence.settings
        presence.on_status = controls.hub.set_status
    threading.Thread(
        target=_read_stdin, args=(presence,), name="overlay-stdin", daemon=True
    ).start()
    AppHelper.runEventLoop(installInterrupt=True)
    return 0
