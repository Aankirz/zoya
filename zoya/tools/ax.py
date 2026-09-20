"""T1 — the Accessibility tier (§9.4, D6): read an app's controls and press them by name.

Also the evidence for Guard 2 on every native-app input: `facts_at` / `click_facts` describe the
element that will REALLY receive a pixel click or AX press, whatever the model said it was.
AX text is page/app text: untrusted (§12.2), only ever returned inside <untrusted_content>.

These tools belong to computer_agent (which holds the GUI lock), so this module has no TOOLS list.

APIs (pyobjc-framework-ApplicationServices 12.2.2, checked live on this Mac 2026-09-14):
- https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition
- https://developer.apple.com/documentation/applicationservices/1459345-axuielementsetmessagingtimeout
- https://developer.apple.com/documentation/applicationservices/1462091-axuielementperformaction
- https://developer.apple.com/documentation/applicationservices/1462092-axvaluegetvalue
- AXManualAccessibility (Chromium/Electron build their web AX tree on request):
  https://www.electronjs.org/docs/latest/tutorial/accessibility#macos
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from strands import tool

from zoya import safety
from zoya.config import (
    AX_CHARS_PER_TOKEN,
    AX_INNER_LABEL_MAX,
    AX_INNER_LABEL_NODES,
    AX_MAX_ANCESTORS,
    AX_MESSAGING_TIMEOUT_S,
    AX_NEARBY_MAX_CHARS,
    AX_READ_MAX_ITEMS,
    AX_READ_TOKEN_BUDGET,
    AX_TREE_SETTLE_S,
    AX_WALK_DEADLINE_S,
    AX_WINDOWS_POLL_S,
    AX_WINDOWS_WAIT_S,
)
from zoya.screen import AX_CLICKABLE_ROLES, AX_LABEL_ATTRIBUTES, _ax
from zoya.tools import ToolError

TEXT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"}
PRESSABLE_ROLES = AX_CLICKABLE_ROLES | {"AXPopUpButton", "AXMenuButton", "AXTab", "AXCell"}
LISTED_ROLES = PRESSABLE_ROLES | TEXT_ROLES | {"AXStaticText", "AXHeading", "AXSlider"}
NAME_ATTRIBUTES = ("AXTitle", "AXDescription", "AXValue", "AXPlaceholderValue", "AXHelp")
TEXT_LABEL_ROLES = {"AXStaticText", "AXHeading"}
DIALOG_SUBROLES = {"AXDialog", "AXSystemDialog", "AXFloatingWindow"}
MAX_ANCESTORS_FOR_URL = 40
ROOT_ROLES = {"AXWindow", "AXSheet", "AXApplication", "AXSystemWide"}
HIDDEN = "[hidden]"  # what a secure field's typed value becomes, everywhere Zoya reads AX text
AX_SUCCESS = 0
WEB_PAGE_SCHEMES = {"http", "https"}
WEB_SUBSTRATE_ANSWER = (
    "is showing a web page. Read that page with the browser tools: a page's accessibility tree is "
    "tens of thousands of tokens and does not belong here."
)


def frontmost_regular_app() -> Any:
    """The frontmost NSRunningApplication with a regular activation policy.

    Widget and intents extensions share their app's localizedName and answer no AX messages
    (com.apple.Notes.WidgetExtension shadows com.apple.Notes), so identity is never a name.
    """
    import AppKit

    workspace = AppKit.NSWorkspace.sharedWorkspace()
    regular = AppKit.NSApplicationActivationPolicyRegular
    app = workspace.frontmostApplication()
    if app is None:
        raise ToolError("I can't tell which app is in front.")
    if app.activationPolicy() == regular:
        return app
    return next(
        (
            candidate
            for candidate in workspace.runningApplications()
            if candidate.isActive() and candidate.activationPolicy() == regular
        ),
        app,
    )


def front_app() -> tuple[str, Any]:
    """(name, AX application element) of the frontmost app, with a bounded messaging timeout."""
    import ApplicationServices as AS

    app = frontmost_regular_app()
    element = AS.AXUIElementCreateApplication(app.processIdentifier())
    AS.AXUIElementSetMessagingTimeout(element, AX_MESSAGING_TIMEOUT_S)
    AS.AXUIElementSetAttributeValue(element, "AXManualAccessibility", True)  # no-op elsewhere
    return str(app.localizedName()), element


def element_at(x: float, y: float) -> Any:
    """The accessible element under global point (x, y), or None (canvas, no AX, no permission)."""
    import ApplicationServices as AS

    system = AS.AXUIElementCreateSystemWide()
    AS.AXUIElementSetMessagingTimeout(system, AX_MESSAGING_TIMEOUT_S)
    error, element = AS.AXUIElementCopyElementAtPosition(system, x, y, None)
    return element if error == AX_SUCCESS else None


def focused_element() -> Any:
    _name, app = front_app()
    return _ax(app, "AXFocusedUIElement")


def texts_of(element: Any, attributes: tuple[str, ...]) -> list[str]:
    """String attributes of `element`; a secure field's AXValue (what was typed) is never read
    (§12.1, AGENTS.md §6): it would reach the model, logs and spoken summaries."""
    secure = is_secure(element)
    return [
        str(v)
        for a in attributes
        if not (secure and a == "AXValue") and isinstance(v := _ax(element, a), str) and v
    ]


def name_of(element: Any) -> str:
    names = texts_of(element, NAME_ATTRIBUTES)
    if is_secure(element):
        return f"{names[0]} (password field, {HIDDEN})" if names else f"password field, {HIDDEN}"
    return names[0] if names else ""


def inner_label(element: Any) -> str:
    """The text a row, cell or tab draws inside itself, when it publishes no name of its own.

    A System Settings sidebar row is an unnamed AXCell whose label is a descendant AXStaticText;
    39 of them read as "" and never reach the step loop's candidate list, which is why the loop
    could press a control but never enter a section to find one.
    """
    texts: list[str] = []
    queue = list(_ax(element, "AXChildren") or [])
    for _ in range(AX_INNER_LABEL_NODES):
        if not queue or len(texts) >= AX_INNER_LABEL_MAX:
            break
        node = queue.pop(0)
        if str(_ax(node, "AXRole") or "") in TEXT_LABEL_ROLES and (text := name_of(node)):
            texts.append(text)
        queue += list(_ax(node, "AXChildren") or [])
    return ", ".join(texts)


def frame_of(element: Any) -> tuple[float, float, float, float] | None:
    import ApplicationServices as AS

    position, size = _ax(element, "AXPosition"), _ax(element, "AXSize")
    if position is None or size is None:
        return None
    ok_p, point = AS.AXValueGetValue(position, AS.kAXValueCGPointType, None)
    ok_s, extent = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok_p and ok_s):
        return None
    return point.x, point.y, extent.width, extent.height


def _clickable(element: Any) -> tuple[Any, list[str], bool]:
    """(element a click on `element` presses, labels on the way up, whether the walk is complete).

    Complete = a pressable ancestor-or-self was found, or the window/app root was reached with
    none. A walk cut short by the depth or time cap is incomplete: a "Delete" button may sit
    above it, so callers must fail closed (coordinator attack 1).
    """
    labels: list[str] = []
    current = element
    deadline = time.monotonic() + AX_WALK_DEADLINE_S
    for _ in range(AX_MAX_ANCESTORS):
        labels += texts_of(current, AX_LABEL_ATTRIBUTES)
        role = _ax(current, "AXRole")
        if role in PRESSABLE_ROLES:
            if not labels and (inner := inner_label(current)):
                labels.append(inner)
            return current, labels, True
        parent = _ax(current, "AXParent")
        if parent is None or role in ROOT_ROLES:
            return element, labels, True
        if time.monotonic() > deadline:
            break
        current = parent
    return element, labels, False


def _web_path(element: Any) -> str:
    """URL path of the web page holding `element` (Chrome/Safari AXWebArea), "" in native apps."""
    current = element
    for _ in range(MAX_ANCESTORS_FOR_URL):
        if current is None:
            return ""
        if _ax(current, "AXRole") == "AXWebArea" and (url := _ax(current, "AXURL")) is not None:
            return urlparse(str(url)).path
        current = _ax(current, "AXParent")
    return ""


def _nearby_text(element: Any) -> str:
    """Text of the target's siblings and its parent's siblings: where a price would sit."""
    texts: list[str] = []
    parent = _ax(element, "AXParent")
    for container in (parent, _ax(parent, "AXParent") if parent is not None else None):
        for child in (_ax(container, "AXChildren") or []) if container is not None else []:
            texts += texts_of(child, AX_LABEL_ATTRIBUTES)
            if sum(map(len, texts)) > AX_NEARBY_MAX_CHARS:
                return " ".join(texts)[:AX_NEARBY_MAX_CHARS]
    return " ".join(texts)


def click_facts(element: Any) -> safety.ClickFacts:
    """What the app says about the element that will really be pressed. No element, or a walk cut
    short before a pressable ancestor or the window → no labels, which click_risk treats as an
    unnamed target (asks: fail closed)."""
    if element is None:
        return safety.ClickFacts(labels=[])
    target, labels, complete = _clickable(element)
    if not complete:
        return safety.ClickFacts(labels=[])
    window = _ax(target, "AXWindow")
    default = _ax(window, "AXDefaultButton") if window is not None else None
    return safety.ClickFacts(
        labels=labels,
        is_submit=default is not None and default == target,  # Return presses it: a form's submit
        path=_web_path(target),
        nearby_text=_nearby_text(target),
    )


def is_secure(element: Any) -> bool:
    """Password/OTP/card field (§12.1): secure subrole, or a label/identifier that says so."""
    if element is None:
        return False
    names = " ".join(
        str(v)
        for a in (*NAME_ATTRIBUTES, "AXIdentifier", "AXRoleDescription")
        if isinstance(v := _ax(element, a), str) and a != "AXValue"  # the value is what's typed
    )
    return safety.is_secret_field(name=names, ax_subrole=str(_ax(element, "AXSubrole") or ""))


# --- Reading and pressing -----------------------------------------------------------------------


def _windows(app: Any) -> list[Any]:
    """Dialogs and sheets first (§6 Flow 5), then the focused window, then the rest."""
    windows = list(_ax(app, "AXWindows") or [])
    focused = _ax(app, "AXFocusedWindow")
    return sorted(
        windows,
        key=lambda w: (_ax(w, "AXSubrole") not in DIALOG_SUBROLES, w != focused),
    )


def _drawn_windows(app: Any) -> list[Any]:
    """`_windows`, waiting out the gap between an app becoming frontmost and drawing a window."""
    deadline = time.monotonic() + AX_WINDOWS_WAIT_S
    while True:
        windows = _windows(app)
        if windows or time.monotonic() >= deadline:
            return windows
        time.sleep(AX_WINDOWS_POLL_S)


def is_web_page(url: str) -> bool:
    """Whether an AXWebArea's URL is a site. An Electron window is a web area too, but its page
    is a vscode-file:// bundle URL, so those apps stay on the accessibility substrate."""
    return urlparse(url).scheme in WEB_PAGE_SCHEMES


TOGGLE_ROLES = {"AXCheckBox", "AXRadioButton", "AXMenuItem", "AXTab", "AXCell"}
CHECKED_BY_VALUE = {0: "unchecked", 1: "checked", 2: "mixed"}
VALUE_ROLES = {"AXPopUpButton", "AXComboBox", "AXSlider", "AXMenuButton"}
STATE_MAX_CHARS = 40


def control_state(element: Any) -> str:
    """What the app says this control's state is: selected, checked, its value, or disabled.

    Without it a control list cannot answer "did that work" — System Settings' Appearance pane
    serialises byte-identically before and after dark mode is turned on, because only AXSelected
    moves (measured on this Mac, 2026-09-20).
    """
    if element is None:
        return ""
    marks = []
    if _ax(element, "AXSelected") is True:
        marks.append("selected")
    role = str(_ax(element, "AXRole") or "")
    value = _ax(element, "AXValue")
    if role in TOGGLE_ROLES and isinstance(value, int) and not isinstance(value, bool):
        marks.append(CHECKED_BY_VALUE.get(value, ""))
    elif role in TOGGLE_ROLES and value is True:
        marks.append("checked")
    elif role in VALUE_ROLES and value is not None and str(value):
        marks.append(f"= {str(value)[:STATE_MAX_CHARS]}")
    if _ax(element, "AXEnabled") is False:
        marks.append("disabled")
    return ", ".join(mark for mark in marks if mark)


def listed_line(role: str, name: str, state: str = "") -> str:
    line = f"{role.removeprefix('AX')}: {name}".strip()
    return f"{line} [{state}]" if state else line


def described(role: str, name: str, element: Any) -> str:
    """The line a model or Jev reads: the control, plus whatever state the app publishes."""
    return listed_line(role, name, control_state(element))


def estimated_tokens(text: str) -> int:
    return -(-len(text) // AX_CHARS_PER_TOKEN)


def spend(spent: int, role: str, name: str, state: str = "") -> int | None:
    """The token total after listing this control, or None when the budget cannot pay for it."""
    total = spent + estimated_tokens(listed_line(role, name, state))
    return None if total > AX_READ_TOKEN_BUDGET else total


def _walk_once(app: Any) -> tuple[list[tuple[str, str, Any]], bool]:
    """Named controls within the token budget, and whether the window is a web page.

    A page's own tree belongs to the browser substrate — Safari's is 2,684 controls for one
    Wikipedia article — so the walk stops at the web area and keeps only the browser's own chrome.
    """
    deadline = time.monotonic() + AX_WALK_DEADLINE_S
    queue, found, spent = _drawn_windows(app), [], 0
    while queue and len(found) < AX_READ_MAX_ITEMS and time.monotonic() < deadline:
        element = queue.pop(0)
        role = str(_ax(element, "AXRole") or "")
        if role == "AXWebArea" and is_web_page(str(_ax(element, "AXURL") or "")):
            return found, True
        name = name_of(element) or (inner_label(element) if role in PRESSABLE_ROLES else "")
        if role in LISTED_ROLES and (name or role in TEXT_ROLES):
            affordable = spend(spent, role, name, control_state(element))
            if affordable is None:
                break
            found.append((role, name, element))
            spent = affordable
        queue += list(_ax(element, "AXChildren") or [])
    return found, False


def read_controls(app: Any) -> tuple[list[tuple[str, str, Any]], bool]:
    """`_walk_once`, retrying an empty first pass once.

    A Chromium app builds its tree only after AXManualAccessibility is set and publishes almost
    nothing for seconds after launch: Cursor listed 2 controls until t+5 s, then 333.
    """
    found, web = _walk_once(app)
    if found or web:
        return found, web
    time.sleep(AX_TREE_SETTLE_S)
    return _walk_once(app)


def listed_elements(app: Any) -> list[tuple[str, str, Any]]:
    """(role, name, element) of named controls and text, breadth first, within the token budget."""
    return read_controls(app)[0]


@tool
def ax_read() -> str:
    """List the frontmost app's windows, dialogs first, with their buttons, fields and text.

    Fast and exact: use before taking a screenshot. Press a listed control with ax_press.
    """
    name, app = front_app()
    items, web = read_controls(app)
    if web:
        return f"{name} {WEB_SUBSTRATE_ANSWER}"
    if not items:
        return f"{name} doesn't expose its controls. Take a screenshot instead."
    lines = [described(role, label, element) for role, label, element in items]
    return f"Frontmost app: {name}\n" + safety.wrap_untrusted("\n".join(lines))


def find(label: str, occurrence: int = 1) -> Any:
    """The `occurrence`-th pressable element named `label` (exact name first, then contains)."""
    _name, app = front_app()
    wanted = safety.normalise(label)
    pressable = [
        (safety.normalise(n), e) for r, n, e in listed_elements(app) if r in PRESSABLE_ROLES
    ]
    for matches in (
        [e for n, e in pressable if n == wanted],
        [e for n, e in pressable if wanted and wanted in n],
    ):
        if len(matches) >= occurrence >= 1:
            return matches[occurrence - 1]
    raise ToolError(f"I can't find {label} in this app. Read it again or take a screenshot.")


@tool
def ax_press(label: str, occurrence: int = 1) -> str:
    """Press a button, checkbox, tab or menu item in the frontmost app by its name from ax_read.

    Quitting, deleting, sending, paying and unnamed controls make Zoya ask the user out loud
    first. macOS permission prompts (Allow / Don't Allow) are never pressed: the user answers them.

    Args:
        label: The control's name exactly as ax_read listed it, e.g. "Dark".
        occurrence: 1 for the first control with that name, 2 for the second, ...
    """
    from zoya.tools import computer

    computer.check_user_idle()
    app_name, _app = front_app()
    element = find(label, occurrence)
    facts = click_facts(element)
    computer.refuse_if_blocked(facts.labels, app_name)
    risky = computer.native_risk(computer.centre_of(frame_of(element)), facts)
    safety.log_safety_timing(event="ax_press", risk=risky.kind if risky else "free")
    if risky is not None:
        computer.session.asked = True
        action = safety.Action(risky.kind, risky.say, target=app_name)
        verified: list[Any] = []

        def live() -> safety.Action:
            again = find(label, occurrence)
            same = click_facts(again) == facts and front_app()[0] == app_name
            verified.append(again)
            return action if same else safety.Action("changed", "changed")

        safety.require_confirmation(action, current=live)
        element = verified[-1]
    target, _labels, _complete = _clickable(element)
    computer.press_element(target, frame_of(target))
    return f"Pressed {label}." + (" The user confirmed it out loud." if risky else "")


AX_TOOLS = [ax_read, ax_press]
