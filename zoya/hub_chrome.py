"""The Hub's native chrome: a source-list sidebar with SF Symbols and a unified toolbar (D121)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import AppKit
import objc
import Quartz

from zoya.overlay_pill import accessibility, loop

PAGES = (
    ("today", "Today", "sun.max"),
    ("history", "History", "clock.arrow.circlepath"),
    ("memory", "Memory", "brain"),
    ("plan", "Plan", "gauge.with.dots.needle.33percent"),
    ("setup", "Setup", "checklist"),
    ("voice", "Voice and settings", "slider.horizontal.3"),
)
TITLES = {page: title for page, title, _symbol in PAGES}
ACTIONS = {
    "history": ("clearHistory", "Clear history"),
    "setup": ("checkForUpdates", "Check for updates"),
}
ROW_HEIGHT = 34.0
SYMBOL_W = 20.0
WORDMARK_PT = 14.0
EYE_W, EYE_H, EYE_GAP = 5.0, 11.0, 4.5
BLINK_S = 5.5
BLINK_TIMES = [0.0, 0.93, 0.96, 1.0]
CAPSULE_INSET = (6.0, 2.0)
CAPSULE_SHADOW = (0.0, -1.0, 4.0, 0.14)
EDGE = 16.0
WARM_TINT = (0.99, 0.965, 0.9, 0.62)
WARM_TINT_DARK = (0.2, 0.18, 0.16, 0.7)
STATUS = {
    "idle": "Hold fn + Shift, or say “Hey Zoya”",
    "listening": "Listening",
    "thinking": "Thinking",
    "acting": "Working on it",
    "speaking": "Speaking",
    "waiting": "Waiting for your confirm",
    "stopped": "Stopped",
    "error": "Couldn’t finish that",
}
SIDEBAR_MIN, SIDEBAR_MAX = 200.0, 260.0
TITLE_ITEM = "zoya.title"
ACTION_ITEM = "zoya.action"
CELL_ID = "zoya.page"
TOOLBAR_ID = "ZoyaHubToolbar"


def _cell(title: str, symbol: str) -> Any:
    cell = AppKit.NSTableCellView.alloc().initWithFrame_(((0, 0), (200, ROW_HEIGHT)))
    image = AppKit.NSImageView.imageViewWithImage_(
        AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
    )
    image.setContentTintColor_(AppKit.NSColor.labelColor())
    AppKit.NSLayoutConstraint.activateConstraints_(
        [image.widthAnchor().constraintEqualToConstant_(SYMBOL_W)]
    )
    label = AppKit.NSTextField.labelWithString_(title)
    label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(13.0, AppKit.NSFontWeightMedium))
    stack = AppKit.NSStackView.stackViewWithViews_([image, label])
    stack.setSpacing_(8.0)
    stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    cell.addSubview_(stack)
    cell.setImageView_(image)
    cell.setTextField_(label)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            stack.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 10.0),
            stack.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
        ]
    )
    return cell


def eyes(color: Any, scale: float = 1.0) -> Any:
    view = AppKit.NSView.alloc().initWithFrame_(
        ((0, 0), ((2 * EYE_W + EYE_GAP) * scale, EYE_H * scale))
    )
    view.setWantsLayer_(True)
    view.setAccessibilityElement_(False)
    for index in range(2):
        eye = Quartz.CALayer.layer()
        eye.setFrame_(((index * (EYE_W + EYE_GAP) * scale, 0), (EYE_W * scale, EYE_H * scale)))
        eye.setCornerRadius_(EYE_W * scale / 2)
        eye.setBackgroundColor_(color.CGColor())
        if not accessibility()[0]:
            eye.addAnimation_forKey_(
                loop("transform.scale.y", [1.0, 1.0, 0.12, 1.0], BLINK_S, key_times=BLINK_TIMES),
                "blink",
            )
        view.layer().addSublayer_(eye)
    size = view.frame().size
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            view.widthAnchor().constraintEqualToConstant_(size.width),
            view.heightAnchor().constraintEqualToConstant_(size.height),
        ]
    )
    return view


class CapsuleRow(AppKit.NSTableRowView):
    def setSelected_(self, selected: bool) -> None:  # noqa: N802
        objc.super(CapsuleRow, self).setSelected_(selected)
        self.setNeedsDisplay_(True)

    def drawBackgroundInRect_(self, _rect: Any) -> None:  # noqa: N802
        if not self.isSelected():
            return
        dx, dy = CAPSULE_INSET
        box = AppKit.NSInsetRect(self.bounds(), dx, dy)
        radius = box.size.height / 2
        AppKit.NSGraphicsContext.saveGraphicsState()
        shadow = AppKit.NSShadow.alloc().init()
        x, y, blur, alpha = CAPSULE_SHADOW
        shadow.setShadowOffset_((x, y))
        shadow.setShadowBlurRadius_(blur)
        shadow.setShadowColor_(AppKit.NSColor.blackColor().colorWithAlphaComponent_(alpha))
        shadow.set()
        dark = "Dark" in str(self.effectiveAppearance().name())
        fill = AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.16 if dark else 0.96)
        fill.setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box, radius, radius).fill()
        AppKit.NSGraphicsContext.restoreGraphicsState()

    def isEmphasized(self) -> bool:  # noqa: N802
        return False


def _brand() -> Any:
    name = AppKit.NSTextField.labelWithString_("Zoya")
    name.setFont_(AppKit.NSFont.systemFontOfSize_weight_(WORDMARK_PT, AppKit.NSFontWeightSemibold))
    row = AppKit.NSStackView.stackViewWithViews_([eyes(AppKit.NSColor.labelColor()), name])
    row.setSpacing_(10.0)
    return row


def _status() -> tuple[Any, Any]:
    label = AppKit.NSTextField.labelWithString_(STATUS["idle"])
    label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(12.0, AppKit.NSFontWeightMedium))
    label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
    label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    blue = AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.0, 0.33, 0.77, 1.0)
    row = AppKit.NSStackView.stackViewWithViews_([eyes(blue, 0.7), label])
    row.setSpacing_(8.0)
    return row, label


def _pin(container: Any, top: Any, middle: Any, bottom: Any) -> None:
    for view in (top, middle, bottom):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        container.addSubview_(view)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            top.topAnchor().constraintEqualToAnchor_constant_(container.topAnchor(), 52.0),
            top.leadingAnchor().constraintEqualToAnchor_constant_(container.leadingAnchor(), EDGE),
            middle.topAnchor().constraintEqualToAnchor_constant_(top.bottomAnchor(), EDGE),
            middle.leadingAnchor().constraintEqualToAnchor_(container.leadingAnchor()),
            middle.trailingAnchor().constraintEqualToAnchor_(container.trailingAnchor()),
            middle.bottomAnchor().constraintEqualToAnchor_constant_(bottom.topAnchor(), -8.0),
            bottom.leadingAnchor().constraintEqualToAnchor_constant_(
                container.leadingAnchor(), EDGE
            ),
            bottom.trailingAnchor().constraintLessThanOrEqualToAnchor_constant_(
                container.trailingAnchor(), -EDGE
            ),
            bottom.bottomAnchor().constraintEqualToAnchor_constant_(
                container.bottomAnchor(), -EDGE
            ),
        ]
    )


def _warm_tint(appearance: Any) -> Any:
    dark = "Dark" in str(appearance.name())
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
        *(WARM_TINT_DARK if dark else WARM_TINT)
    )


def _warm(inner: Any) -> Any:
    if not hasattr(AppKit, "NSGlassEffectView") or accessibility()[1]:
        return inner
    pane = AppKit.NSGlassEffectView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
    pane.setTintColor_(AppKit.NSColor.colorWithName_dynamicProvider_("zoyaWarmPane", _warm_tint))
    pane.setContentView_(inner)
    return pane


class Sidebar(
    AppKit.NSViewController,
    protocols=[
        objc.protocolNamed("NSTableViewDataSource"),
        objc.protocolNamed("NSTableViewDelegate"),
    ],
):
    def loadView(self) -> None:  # noqa: N802
        table = AppKit.NSTableView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        table.setStyle_(AppKit.NSTableViewStyleSourceList)
        table.setHeaderView_(None)
        table.setRowHeight_(ROW_HEIGHT)
        table.setBackgroundColor_(AppKit.NSColor.clearColor())
        table.setSelectionHighlightStyle_(AppKit.NSTableViewSelectionHighlightStyleNone)
        table.addTableColumn_(AppKit.NSTableColumn.alloc().initWithIdentifier_("page"))
        table.setDataSource_(self)
        table.setDelegate_(self)
        table.setAccessibilityLabel_("Zoya")
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        scroll.setDocumentView_(table)
        scroll.setDrawsBackground_(False)
        status, self.status = _status()
        inner = AppKit.NSView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        _pin(inner, _brand(), scroll, status)
        self.table = table
        self.setView_(_warm(inner))

    def numberOfRowsInTableView_(self, _table: Any) -> int:  # noqa: N802
        return len(PAGES)

    def tableView_viewForTableColumn_row_(
        self, _table: Any, _column: Any, row: int
    ) -> Any:  # noqa: N802
        _page, title, symbol = PAGES[row]
        return _cell(title, symbol)

    def tableView_rowViewForRow_(self, _table: Any, _row: int) -> Any:  # noqa: N802
        return CapsuleRow.alloc().init()

    def tableViewSelectionDidChange_(self, _notification: Any) -> None:  # noqa: N802
        row = self.table.selectedRow()
        if 0 <= row < len(PAGES) and not self.syncing:
            self.on_select(PAGES[row][0])

    @objc.python_method
    def select(self, page: str) -> None:
        index = next((i for i, (p, _t, _s) in enumerate(PAGES) if p == page), 0)
        self.syncing = True
        self.table.selectRowIndexes_byExtendingSelection_(
            AppKit.NSIndexSet.indexSetWithIndex_(index), False
        )
        self.syncing = False

    @objc.python_method
    def set_status(self, state: str) -> None:
        self.view()
        self.status.setStringValue_(STATUS.get(state, STATUS["idle"]))


def sidebar(on_select: Callable[[str], None]) -> Any:
    controller = Sidebar.alloc().init()
    controller.on_select = on_select
    controller.syncing = False
    return controller


class Toolbar(AppKit.NSObject, protocols=[objc.protocolNamed("NSToolbarDelegate")]):
    def toolbarDefaultItemIdentifiers_(self, _toolbar: Any) -> list[str]:  # noqa: N802
        return [
            AppKit.NSToolbarSidebarTrackingSeparatorItemIdentifier,
            TITLE_ITEM,
            AppKit.NSToolbarFlexibleSpaceItemIdentifier,
            ACTION_ITEM,
        ]

    def toolbarAllowedItemIdentifiers_(self, toolbar: Any) -> list[str]:  # noqa: N802
        return self.toolbarDefaultItemIdentifiers_(toolbar)

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(  # noqa: N802
        self, _toolbar: Any, identifier: str, _flag: bool
    ) -> Any:
        item = AppKit.NSToolbarItem.alloc().initWithItemIdentifier_(identifier)
        if identifier == TITLE_ITEM:
            self.title = AppKit.NSTextField.labelWithString_("")
            self.title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13.0))
            self.title.setAccessibilityElement_(False)
            item.setView_(self.title)
            return item
        self.button = AppKit.NSButton.buttonWithTitle_target_action_("", self, "pressed:")
        self.button.setBezelStyle_(AppKit.NSBezelStylePush)
        item.setView_(self.button)
        self.action_item = item
        return item

    def pressed_(self, _sender: Any) -> None:
        if self.action:
            self.on_action(self.action)

    @objc.python_method
    def show(self, page: str, header_visible: bool) -> None:
        self.title.setStringValue_("" if header_visible else TITLES.get(page, ""))
        self.action, label = ACTIONS.get(page, ("", ""))
        self.button.setTitle_(label)
        self.button.setAccessibilityLabel_(label)
        self.action_item.setHidden_(not self.action)


def toolbar(on_action: Callable[[str], None]) -> tuple[Any, Any]:
    delegate = Toolbar.alloc().init()
    delegate.on_action = on_action
    delegate.action = ""
    bar = AppKit.NSToolbar.alloc().initWithIdentifier_(TOOLBAR_ID)
    bar.setDelegate_(delegate)
    bar.setDisplayMode_(AppKit.NSToolbarDisplayModeIconOnly)
    bar.setAllowsUserCustomization_(False)
    return bar, delegate
