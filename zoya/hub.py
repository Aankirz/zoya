"""Zoya's Hub window: a WKWebView of bundled files behind a fixed command allowlist (D119)."""

from __future__ import annotations

import json
import sys
import threading
import urllib.parse
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import AppKit
import Foundation
import objc
import WebKit
from PyObjCTools import AppHelper

from zoya import hub_bridge, hub_chrome, hub_data, login_item

HUB_DIR = Path(__file__).parent / "hub"
SCHEME = "zoya"
ORIGIN = f"{SCHEME}://hub"
HANDLER = "zoya"

MAX_MESSAGE_CHARS = 16_384
WINDOW_SIZE = (1080.0, 720.0)
WINDOW_TITLE = "Zoya"
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
APP_ICON_PREFIX = "/appicon/"
APP_ICON_PX = 128


def bundled_file(url_path: str) -> Path | None:
    relative = url_path.lstrip("/") or "index.html"
    candidate = (HUB_DIR / relative).resolve()
    inside = candidate.is_relative_to(HUB_DIR.resolve())
    return candidate if inside and candidate.is_file() and candidate.suffix in TYPES else None


@lru_cache(maxsize=64)
def app_icon(name: str) -> bytes | None:
    if not hub_data.APP_NAME.fullmatch(name):
        return None
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    path = workspace.fullPathForApplication_(name)
    if not path:
        return None
    bitmap = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        None, APP_ICON_PX, APP_ICON_PX, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0
    )
    AppKit.NSGraphicsContext.saveGraphicsState()
    AppKit.NSGraphicsContext.setCurrentContext_(
        AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(bitmap)
    )
    workspace.iconForFile_(path).drawInRect_(((0, 0), (APP_ICON_PX, APP_ICON_PX)))
    AppKit.NSGraphicsContext.restoreGraphicsState()
    return bytes(bitmap.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {}))


def _resource(url_path: str) -> tuple[bytes, str] | None:
    if url_path.startswith(APP_ICON_PREFIX):
        icon = app_icon(urllib.parse.unquote(url_path.removeprefix(APP_ICON_PREFIX)))
        return (icon, TYPES[".png"]) if icon else None
    path = bundled_file(url_path)
    return (path.read_bytes(), TYPES[path.suffix]) if path else None


class SchemeHandler(AppKit.NSObject, protocols=[objc.protocolNamed("WKURLSchemeHandler")]):
    def webView_startURLSchemeTask_(self, _view: Any, task: Any) -> None:  # noqa: N802
        url = task.request().URL()
        found = _resource(str(url.path() or "")) if url.host() == "hub" else None
        body, kind = found or (b"", "text/plain")
        headers = {"Content-Type": kind, "Content-Security-Policy": CSP}
        response = (
            Foundation.NSHTTPURLResponse.alloc().initWithURL_statusCode_HTTPVersion_headerFields_(
                url, OK if found else NOT_FOUND, "HTTP/1.1", headers
            )
        )
        task.didReceiveResponse_(response)
        task.didReceiveData_(Foundation.NSData.dataWithBytes_length_(body, len(body)))
        task.didFinish()

    def webView_stopURLSchemeTask_(self, _view: Any, _task: Any) -> None:  # noqa: N802
        return


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
        self.sidebar: Any = None
        self.keep: list[Any] = []
        self.clear_guard = hub_bridge.ClearGuard()

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
        window.setTitle_(WINDOW_TITLE)
        window.setTitleVisibility_(AppKit.NSWindowTitleHidden)
        window.setReleasedWhenClosed_(False)
        window.setContentMinSize_(MIN_SIZE)
        events = WindowEvents.alloc().init()
        window.setDelegate_(events)
        self.view = self._web_view()
        content = AppKit.NSViewController.alloc().init()
        content.setView_(self.view)
        self.sidebar = hub_chrome.sidebar(self.go)
        split = AppKit.NSSplitViewController.alloc().init()
        side_item = AppKit.NSSplitViewItem.sidebarWithViewController_(self.sidebar)
        side_item.setMinimumThickness_(hub_chrome.SIDEBAR_MIN)
        side_item.setMaximumThickness_(hub_chrome.SIDEBAR_MAX)
        split.addSplitViewItem_(side_item)
        split.addSplitViewItem_(AppKit.NSSplitViewItem.splitViewItemWithViewController_(content))
        window.setContentViewController_(split)
        bar, self.chrome = hub_chrome.toolbar(self.toolbar_action)
        window.setToolbar_(bar)
        window.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnified)
        window.setTitlebarAppearsTransparent_(True)
        window.setTitlebarSeparatorStyle_(AppKit.NSTitlebarSeparatorStyleNone)
        window.setContentSize_(WINDOW_SIZE)
        window.setFrameAutosaveName_("ZoyaHub")
        window.center()
        self.keep += [events, content, split, bar]
        self.sidebar.select("today")
        self.chrome.show("today", True)
        store = WebKit.WKContentRuleListStore.defaultStore()
        store.compileContentRuleListForIdentifier_encodedContentRuleList_completionHandler_(
            RULES_ID, RULES, self._load
        )
        return window

    def set_status(self, state: str) -> None:
        if self.sidebar is not None:
            self.sidebar.set_status(state)

    def go(self, page: str) -> None:
        self.run_js(f"location.hash = {json.dumps(page)}")

    def toolbar_action(self, action: str) -> None:
        self.run_js(f"window.zoyaToolbar({json.dumps(action)})")

    def page_state(self, page: str, header_visible: bool) -> None:
        self.sidebar.select(page)
        self.chrome.show(page, header_visible)

    def run_js(self, code: str) -> None:
        if self.view is not None:
            self.view.evaluateJavaScript_completionHandler_(code, None)

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
        self.run_js(f"window.zoyaReceive({payload})")

    def reply_later(self, request_id: int, work: Callable[[], object]) -> None:
        def run() -> None:
            AppHelper.callAfter(self.reply, request_id, work())

        threading.Thread(target=run, name="zoya-hub-work", daemon=True).start()


PAGES: dict[str, Callable[[], object]] = {
    "today": lambda: {
        "entries": hub_data.today(),
        "setup": hub_data.setup(),
        "name": AppKit.NSFullUserName().split(" ")[0],
    },
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


def _prepare_clear(hub: Hub, command: hub_bridge.Command) -> None:
    count = len(hub_data.history(limit=hub_data.READ_LINES))
    hub.reply(command.request_id, {"token": hub.clear_guard.issue(), "count": count})


def _clear_history(hub: Hub, command: hub_bridge.Command) -> None:
    if not hub.clear_guard.redeem(command.args["token"]):
        print("hub: refused to clear history without the confirm step", file=sys.stderr, flush=True)
        hub.reply(command.request_id, {"cleared": None})
        return
    hub.reply(command.request_id, {"cleared": hub_data.clear_history()})


def _page_state(hub: Hub, command: hub_bridge.Command) -> None:
    hub.page_state(command.args["page"], command.args["headerVisible"])
    hub.reply(command.request_id, True)


COMMANDS: dict[str, Callable[[Hub, hub_bridge.Command], None]] = {
    "getPage": _get_page,
    "deleteMemory": _delete_memory,
    "openPermissionPane": _open_pane,
    "checkForUpdates": _check_updates,
    "sendProblemReport": _problem_report,
    "setSetting": _set_setting,
    "prepareClearHistory": _prepare_clear,
    "clearHistory": _clear_history,
    "pageState": _page_state,
}
