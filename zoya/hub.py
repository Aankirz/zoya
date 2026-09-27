"""Zoya's Hub window: a WKWebView of bundled files behind a fixed command allowlist (D119)."""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import AppKit
import Foundation
import objc
import WebKit
from PyObjCTools import AppHelper

from zoya import hub_bridge, hub_data, login_item

HUB_DIR = Path(__file__).parent / "hub"
SCHEME = "zoya"
ORIGIN = f"{SCHEME}://hub"
HANDLER = "zoya"

MAX_MESSAGE_CHARS = 16_384
WINDOW_SIZE = (1080.0, 720.0)
DRAG_HEIGHT = 28.0
MIN_SIZE = (820.0, 560.0)
TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self'; "
    "connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
)
RULES_ID = "zoya-hub-local-only"
RULES = json.dumps(
    [
        {"trigger": {"url-filter": ".*"}, "action": {"type": "block"}},
        {
            "trigger": {"url-filter": f"^{SCHEME}://hub/"},
            "action": {"type": "ignore-previous-rules"},
        },
    ]
)
NOT_FOUND = 404
OK = 200


def bundled_file(url_path: str) -> Path | None:
    relative = url_path.lstrip("/") or "index.html"
    candidate = (HUB_DIR / relative).resolve()
    inside = candidate.is_relative_to(HUB_DIR.resolve())
    return candidate if inside and candidate.is_file() and candidate.suffix in TYPES else None


class SchemeHandler(AppKit.NSObject, protocols=[objc.protocolNamed("WKURLSchemeHandler")]):
    def webView_startURLSchemeTask_(self, _view: Any, task: Any) -> None:  # noqa: N802
        url = task.request().URL()
        path = bundled_file(str(url.path() or "")) if url.host() == "hub" else None
        body = path.read_bytes() if path else b""
        headers = {"Content-Type": TYPES[path.suffix] if path else "text/plain"}
        headers["Content-Security-Policy"] = CSP
        response = (
            Foundation.NSHTTPURLResponse.alloc().initWithURL_statusCode_HTTPVersion_headerFields_(
                url, OK if path else NOT_FOUND, "HTTP/1.1", headers
            )
        )
        task.didReceiveResponse_(response)
        task.didReceiveData_(Foundation.NSData.dataWithBytes_length_(body, len(body)))
        task.didFinish()

    def webView_stopURLSchemeTask_(self, _view: Any, _task: Any) -> None:  # noqa: N802
        return


class DragStrip(AppKit.NSView):
    def mouseDownCanMoveWindow(self) -> bool:  # noqa: N802
        return True

    def mouseDown_(self, event: Any) -> None:  # noqa: N802
        self.window().performWindowDragWithEvent_(event)


class Messages(AppKit.NSObject, protocols=[objc.protocolNamed("WKScriptMessageHandler")]):
    def userContentController_didReceiveScriptMessage_(  # noqa: N802
        self, _controller: Any, message: Any
    ) -> None:
        self.hub.receive(message.body())


class WindowEvents(AppKit.NSObject, protocols=[objc.protocolNamed("NSWindowDelegate")]):
    def windowWillClose_(self, _notification: Any) -> None:  # noqa: N802
        AppKit.NSApp().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)


def _decode(body: object) -> object:
    if not isinstance(body, str) or len(body) > MAX_MESSAGE_CHARS:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


class Hub:
    def __init__(self, send_command: Callable[[dict[str, Any]], None]) -> None:
        self.send_command = send_command
        self.on_settings: Callable[[dict[str, Any]], None] = lambda _settings: None
        self.window: Any = None
        self.view: Any = None
        self.keep: list[Any] = []

    def _web_view(self) -> Any:
        config = WebKit.WKWebViewConfiguration.alloc().init()
        schemes, messages = SchemeHandler.alloc().init(), Messages.alloc().init()
        messages.hub = self
        config.setURLSchemeHandler_forURLScheme_(schemes, SCHEME)
        config.userContentController().addScriptMessageHandler_name_(messages, HANDLER)
        view = WebKit.WKWebView.alloc().initWithFrame_configuration_(((0, 0), WINDOW_SIZE), config)
        self.keep += [schemes, messages]
        return view

    def _make_window(self) -> Any:
        style = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskMiniaturizable
            | AppKit.NSWindowStyleMaskResizable
            | AppKit.NSWindowStyleMaskFullSizeContentView
        )
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), WINDOW_SIZE), style, AppKit.NSBackingStoreBuffered, False
        )
        window.setTitle_("Zoya")
        window.setTitleVisibility_(AppKit.NSWindowTitleHidden)
        window.setTitlebarAppearsTransparent_(True)
        window.setReleasedWhenClosed_(False)
        window.setContentMinSize_(MIN_SIZE)
        window.setFrameAutosaveName_("ZoyaHub")
        events = WindowEvents.alloc().init()
        window.setDelegate_(events)
        self.keep.append(events)
        self.view = self._web_view()
        root = AppKit.NSView.alloc().initWithFrame_(((0, 0), WINDOW_SIZE))
        self.view.setFrame_(((0, 0), WINDOW_SIZE))
        self.view.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        strip = DragStrip.alloc().initWithFrame_(
            ((0, WINDOW_SIZE[1] - DRAG_HEIGHT), (WINDOW_SIZE[0], DRAG_HEIGHT))
        )
        strip.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMinYMargin)
        root.addSubview_(self.view)
        root.addSubview_(strip)
        window.setContentView_(root)
        window.center()
        store = WebKit.WKContentRuleListStore.defaultStore()
        store.compileContentRuleListForIdentifier_encodedContentRuleList_completionHandler_(
            RULES_ID, RULES, self._load
        )
        return window

    def _load(self, rules: Any, error: Any) -> None:
        if rules is None:
            print(f"hub: no rule list, page not loaded ({error})", file=sys.stderr, flush=True)
            return
        self.view.configuration().userContentController().addContentRuleList_(rules)
        home = Foundation.NSURL.URLWithString_(f"{ORIGIN}/index.html")
        AppHelper.callAfter(self.view.loadRequest_, Foundation.NSURLRequest.requestWithURL_(home))

    def show(self) -> None:
        if self.window is None:
            self.window = self._make_window()
        app = AppKit.NSApp()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(self.view)
        app.activateIgnoringOtherApps_(True)

    def receive(self, body: object) -> None:
        command = hub_bridge.parse(_decode(body))
        if command is None:
            print("hub: refused a message that isn't on the allowlist", file=sys.stderr, flush=True)
            return
        handler = COMMANDS[command.name]
        handler(self, command)

    def reply(self, request_id: int, result: object) -> None:
        payload = json.dumps({"id": request_id, "result": result}, ensure_ascii=True)
        if self.view is not None:
            self.view.evaluateJavaScript_completionHandler_(f"window.zoyaReceive({payload})", None)

    def reply_later(self, request_id: int, work: Callable[[], object]) -> None:
        def run() -> None:
            AppHelper.callAfter(self.reply, request_id, work())

        threading.Thread(target=run, name="zoya-hub-work", daemon=True).start()


PAGES: dict[str, Callable[[], object]] = {
    "today": lambda: {"entries": hub_data.today(), "setup": hub_data.setup()},
    "history": lambda: {"entries": hub_data.history()},
    "memory": lambda: {"items": hub_data.memories()},
    "plan": lambda: {"plan": hub_data.plan()},
    "setup": hub_data.setup,
    "voice": hub_data.settings,
}


def _get_page(hub: Hub, command: hub_bridge.Command) -> None:
    hub.reply_later(command.request_id, PAGES[command.args["page"]])


def _delete_memory(hub: Hub, command: hub_bridge.Command) -> None:
    hub.send_command(
        {"cmd": "forget", "memory": command.args["memory"], "request": command.request_id}
    )


def _open_pane(hub: Hub, command: hub_bridge.Command) -> None:
    from zoya import permissions

    permissions.open_pane(command.args["pane"])
    hub.reply(command.request_id, True)


def _check_updates(hub: Hub, command: hub_bridge.Command) -> None:
    from zoya import sparkle

    hub.reply(command.request_id, sparkle.check_now())


def _problem_report(hub: Hub, command: hub_bridge.Command) -> None:
    hub.send_command({"cmd": "report"})
    hub.reply(command.request_id, True)


def _set_setting(hub: Hub, command: hub_bridge.Command) -> None:
    key, value = command.args["key"], command.args["value"]
    if key == "launchAtLogin":
        value = login_item.set_enabled(value)
    saved = hub_data.save_setting(key, value)
    hub.on_settings(saved)
    hub.reply(command.request_id, saved)


COMMANDS: dict[str, Callable[[Hub, hub_bridge.Command], None]] = {
    "getPage": _get_page,
    "deleteMemory": _delete_memory,
    "openPermissionPane": _open_pane,
    "checkForUpdates": _check_updates,
    "sendProblemReport": _problem_report,
    "setSetting": _set_setting,
}
