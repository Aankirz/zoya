"""The Hub sidebar: the mini eyes-pill, mono section labels, counts and the plan bar (D129)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import AppKit
import objc
import Quartz

from zoya.overlay_pill import accessibility, loop

ROWS: tuple[tuple[str, str, str], ...] = (
    ("", "Navigation", ""),
    ("today", "Today", "sun.max"),
    ("history", "History", "clock.arrow.circlepath"),
    ("memory", "Memory", "brain"),
    ("", "Settings", ""),
    ("setup", "Setup", "checkmark.circle"),
    ("voice", "Voice & keys", "slider.horizontal.3"),
)
PAGE_ROWS = {page: index for index, (page, _title, _symbol) in enumerate(ROWS) if page}
ROW_HEIGHT = 30.0
LABEL_HEIGHT = 34.0
SIDEBAR_MIN, SIDEBAR_MAX = 220.0, 260.0
SYMBOL_W = 18.0
EDGE = 18.0
TOP = 44.0
UI_PT, MONO_PT, LABEL_PT = 13.0, 11.0, 10.5
EYE_W, EYE_H, EYE_GAP = 5.0, 9.0, 5.0
MINI_W, MINI_H = 44.0, 24.0
BLINK_S = 5.0
BLINK_TIMES = [0.0, 0.94, 0.96, 1.0]
SELECTED_RADIUS = 7.0
SELECTED_INSET = (8.0, 1.0)
SELECTED_FILL = 0.045
HAIRLINE = 0.08
DASH = [3.0, 3.0]
PLAN_BAR_PT = 3.0
ZOYA_BLUE_DARK = (0.36, 0.61, 1.0)
ZOYA_BLUE_LIGHT = (0.0, 0.33, 0.77)
PANE_DARK = (0.1, 0.105, 0.12, 0.82)
PANE_LIGHT = (0.945, 0.95, 0.96, 0.85)
MINI_FILL = (0.13, 0.135, 0.16, 0.9)
SUBTITLE = "hold fn ⇧ to talk"
CELL_ID = "zoya.page"


def _dark(appearance: Any) -> bool:
    return "Dark" in str(appearance.name())


def _dynamic(name: str, dark: tuple[float, ...], light: tuple[float, ...]) -> Any:
    def provide(appearance: Any) -> Any:
        rgba = dark if _dark(appearance) else light
        return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*rgba[:3], *(rgba[3:] or (1.0,)))

    return AppKit.NSColor.colorWithName_dynamicProvider_(name, provide)


def zoya_blue() -> Any:
    return _dynamic("zoyaBlue", ZOYA_BLUE_DARK, ZOYA_BLUE_LIGHT)


def month_name(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%b")
    except ValueError:
        return month


def mono(size: float) -> Any:
    return AppKit.NSFont.monospacedSystemFontOfSize_weight_(size, AppKit.NSFontWeightRegular)


def _fixed(view: Any, width: float, height: float) -> Any:
    view.setTranslatesAutoresizingMaskIntoConstraints_(False)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            view.widthAnchor().constraintEqualToConstant_(width),
            view.heightAnchor().constraintEqualToConstant_(height),
        ]
    )
    return view


def mini_pill() -> Any:
    pill = _fixed(AppKit.NSView.alloc().initWithFrame_(((0, 0), (MINI_W, MINI_H))), MINI_W, MINI_H)
    pill.setWantsLayer_(True)
    pill.setAccessibilityElement_(False)
    body = pill.layer()
    body.setCornerRadius_(MINI_H / 2)
    body.setBackgroundColor_(
        AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*MINI_FILL).CGColor()
    )
    body.setBorderWidth_(0.5)
    body.setBorderColor_(AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.1).CGColor())
    left = (MINI_W - 2 * EYE_W - EYE_GAP) / 2
    for index in range(2):
        eye = Quartz.CALayer.layer()
        eye.setFrame_(((left + index * (EYE_W + EYE_GAP), (MINI_H - EYE_H) / 2), (EYE_W, EYE_H)))
        eye.setCornerRadius_(EYE_W / 2 + 0.5)
        eye.setBackgroundColor_(
            AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*ZOYA_BLUE_DARK, 1.0).CGColor()
        )
        eye.setShadowColor_(eye.backgroundColor())
        eye.setShadowOpacity_(0.8)
        eye.setShadowRadius_(4.0)
        eye.setShadowOffset_((0, 0))
        if not accessibility()[0]:
            eye.addAnimation_forKey_(
                loop("transform.scale.y", [1.0, 1.0, 0.15, 1.0], BLINK_S, key_times=BLINK_TIMES),
                "blink",
            )
        body.addSublayer_(eye)
    return pill


def _label(text: str, font: Any, color: Any) -> Any:
    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(font)
    field.setTextColor_(color)
    field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    return field


def _brand() -> Any:
    name = _label(
        "Zoya",
        AppKit.NSFont.systemFontOfSize_weight_(14.0, AppKit.NSFontWeightSemibold),
        AppKit.NSColor.labelColor(),
    )
    hint = _label(SUBTITLE, mono(MONO_PT), AppKit.NSColor.tertiaryLabelColor())
    words = AppKit.NSStackView.stackViewWithViews_([name, hint])
    words.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationVertical)
    words.setAlignment_(AppKit.NSLayoutAttributeLeading)
    words.setSpacing_(0.0)
    row = AppKit.NSStackView.stackViewWithViews_([mini_pill(), words])
    row.setSpacing_(11.0)
    row.setAccessibilityElement_(True)
    row.setAccessibilityLabel_(f"Zoya, {SUBTITLE.replace('⇧', 'Shift')}")
    return row


class DashedRule(AppKit.NSView):
    def drawRect_(self, _rect: Any) -> None:  # noqa: N802
        path = AppKit.NSBezierPath.bezierPath()
        width = self.bounds().size.width
        path.moveToPoint_((0, self.bounds().size.height - 0.5))
        path.lineToPoint_((width, self.bounds().size.height - 0.5))
        path.setLineWidth_(0.5)
        path.setLineDash_count_phase_(DASH, len(DASH), 0.0)
        AppKit.NSColor.labelColor().colorWithAlphaComponent_(HAIRLINE).setStroke()
        path.stroke()


def _page_cell(title: str, symbol: str, count: str) -> Any:
    cell = AppKit.NSTableCellView.alloc().initWithFrame_(((0, 0), (200, ROW_HEIGHT)))
    image = AppKit.NSImageView.imageViewWithImage_(
        AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
    )
    image.setSymbolConfiguration_(
        AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
            13.0, AppKit.NSFontWeightRegular
        )
    )
    image.setContentTintColor_(AppKit.NSColor.secondaryLabelColor())
    _fixed(image, SYMBOL_W, SYMBOL_W)
    label = _label(
        title,
        AppKit.NSFont.systemFontOfSize_weight_(UI_PT, AppKit.NSFontWeightMedium),
        AppKit.NSColor.labelColor(),
    )
    number = _label(count, mono(MONO_PT), AppKit.NSColor.tertiaryLabelColor())
    number.setAccessibilityElement_(False)
    for view in (image, label, number):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        cell.addSubview_(view)
    cell.setImageView_(image)
    cell.setTextField_(label)
    cell.setAccessibilityLabel_(f"{title}, {count}" if count else title)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            image.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 10.0),
            image.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            label.leadingAnchor().constraintEqualToAnchor_constant_(image.trailingAnchor(), 9.0),
            label.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            number.trailingAnchor().constraintEqualToAnchor_constant_(cell.trailingAnchor(), -10.0),
            number.firstBaselineAnchor().constraintEqualToAnchor_(label.firstBaselineAnchor()),
        ]
    )
    return cell


def _section_cell(title: str) -> Any:
    cell = AppKit.NSTableCellView.alloc().initWithFrame_(((0, 0), (200, LABEL_HEIGHT)))
    rule = DashedRule.alloc().initWithFrame_(((0, 0), (200, 1)))
    label = _label(title.upper(), mono(LABEL_PT), AppKit.NSColor.tertiaryLabelColor())
    label.setAccessibilityRole_(AppKit.NSAccessibilityStaticTextRole)
    label.setAccessibilityLabel_(title)
    for view in (rule, label):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        cell.addSubview_(view)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            rule.topAnchor().constraintEqualToAnchor_constant_(cell.topAnchor(), 4.0),
            rule.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 2.0),
            rule.trailingAnchor().constraintEqualToAnchor_(cell.trailingAnchor()),
            rule.heightAnchor().constraintEqualToConstant_(1.0),
            label.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), 10.0),
            label.bottomAnchor().constraintEqualToAnchor_constant_(cell.bottomAnchor(), -5.0),
        ]
    )
    return cell


class SelectedRow(AppKit.NSTableRowView):
    def setSelected_(self, selected: bool) -> None:  # noqa: N802
        objc.super(SelectedRow, self).setSelected_(selected)
        self.setNeedsDisplay_(True)

    def drawBackgroundInRect_(self, _rect: Any) -> None:  # noqa: N802
        if not self.isSelected():
            return
        dx, dy = SELECTED_INSET
        box = AppKit.NSInsetRect(self.bounds(), dx, dy)
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            box, SELECTED_RADIUS, SELECTED_RADIUS
        )
        ink = AppKit.NSColor.labelColor()
        ink.colorWithAlphaComponent_(SELECTED_FILL).setFill()
        path.fill()
        ink.colorWithAlphaComponent_(HAIRLINE).setStroke()
        path.setLineWidth_(0.5)
        path.stroke()

    def isEmphasized(self) -> bool:  # noqa: N802
        return False


class PlanBar(AppKit.NSControl):
    def acceptsFirstMouse_(self, _event: Any) -> bool:  # noqa: N802
        return True

    def mouseUp_(self, _event: Any) -> None:  # noqa: N802
        self.on_open()

    def resetCursorRects(self) -> None:  # noqa: N802
        self.addCursorRect_cursor_(self.bounds(), AppKit.NSCursor.pointingHandCursor())

    def isAccessibilityElement(self) -> bool:  # noqa: N802
        return True

    def accessibilityRole(self) -> str:  # noqa: N802
        return AppKit.NSAccessibilityButtonRole

    def accessibilityLabel(self) -> str:  # noqa: N802
        return self.spoken

    def accessibilityPerformPress(self) -> bool:  # noqa: N802
        self.on_open()
        return True


def _plan_bar(on_open: Callable[[], None]) -> tuple[Any, Any, Any, Any]:
    bar = PlanBar.alloc().initWithFrame_(((0, 0), (200, 40)))
    bar.on_open, bar.spoken = on_open, "Plan"
    rule = DashedRule.alloc().initWithFrame_(((0, 0), (200, 1)))
    left = _label("Plan", mono(MONO_PT), AppKit.NSColor.tertiaryLabelColor())
    right = _label("", mono(MONO_PT), AppKit.NSColor.tertiaryLabelColor())
    track = AppKit.NSView.alloc().initWithFrame_(((0, 0), (200, PLAN_BAR_PT)))
    fill = AppKit.NSView.alloc().initWithFrame_(((0, 0), (0, PLAN_BAR_PT)))
    for part in (track, fill):
        part.setWantsLayer_(True)
        part.layer().setCornerRadius_(PLAN_BAR_PT / 2)
    fill.setTranslatesAutoresizingMaskIntoConstraints_(False)
    track.addSubview_(fill)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            fill.leadingAnchor().constraintEqualToAnchor_(track.leadingAnchor()),
            fill.topAnchor().constraintEqualToAnchor_(track.topAnchor()),
            fill.bottomAnchor().constraintEqualToAnchor_(track.bottomAnchor()),
        ]
    )
    for view in (rule, left, right, track):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        bar.addSubview_(view)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            rule.topAnchor().constraintEqualToAnchor_(bar.topAnchor()),
            rule.leadingAnchor().constraintEqualToAnchor_(bar.leadingAnchor()),
            rule.trailingAnchor().constraintEqualToAnchor_(bar.trailingAnchor()),
            rule.heightAnchor().constraintEqualToConstant_(1.0),
            left.topAnchor().constraintEqualToAnchor_constant_(rule.bottomAnchor(), 11.0),
            left.leadingAnchor().constraintEqualToAnchor_constant_(bar.leadingAnchor(), 10.0),
            right.firstBaselineAnchor().constraintEqualToAnchor_(left.firstBaselineAnchor()),
            right.trailingAnchor().constraintEqualToAnchor_constant_(bar.trailingAnchor(), -10.0),
            track.topAnchor().constraintEqualToAnchor_constant_(left.bottomAnchor(), 8.0),
            track.leadingAnchor().constraintEqualToAnchor_(left.leadingAnchor()),
            track.trailingAnchor().constraintEqualToAnchor_(right.trailingAnchor()),
            track.heightAnchor().constraintEqualToConstant_(PLAN_BAR_PT),
            track.bottomAnchor().constraintEqualToAnchor_constant_(bar.bottomAnchor(), -4.0),
        ]
    )
    return bar, left, right, (track, fill)


def _pin(container: Any, top: Any, middle: Any, bottom: Any) -> None:
    for view in (top, middle, bottom):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        container.addSubview_(view)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            top.topAnchor().constraintEqualToAnchor_constant_(container.topAnchor(), TOP),
            top.leadingAnchor().constraintEqualToAnchor_constant_(container.leadingAnchor(), EDGE),
            middle.topAnchor().constraintEqualToAnchor_constant_(top.bottomAnchor(), 14.0),
            middle.leadingAnchor().constraintEqualToAnchor_constant_(
                container.leadingAnchor(), 8.0
            ),
            middle.trailingAnchor().constraintEqualToAnchor_constant_(
                container.trailingAnchor(), -8.0
            ),
            middle.bottomAnchor().constraintEqualToAnchor_constant_(bottom.topAnchor(), -8.0),
            bottom.leadingAnchor().constraintEqualToAnchor_(middle.leadingAnchor()),
            bottom.trailingAnchor().constraintEqualToAnchor_(middle.trailingAnchor()),
            bottom.bottomAnchor().constraintEqualToAnchor_constant_(
                container.bottomAnchor(), -14.0
            ),
        ]
    )


def _pane(inner: Any) -> Any:
    if not hasattr(AppKit, "NSGlassEffectView") or accessibility()[1]:
        return inner
    pane = AppKit.NSGlassEffectView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
    pane.setTintColor_(_dynamic("zoyaSidebarPane", PANE_DARK, PANE_LIGHT))
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
        table.setStyle_(AppKit.NSTableViewStylePlain)
        table.setHeaderView_(None)
        table.setIntercellSpacing_((0.0, 2.0))
        table.setBackgroundColor_(AppKit.NSColor.clearColor())
        table.setSelectionHighlightStyle_(AppKit.NSTableViewSelectionHighlightStyleNone)
        column = AppKit.NSTableColumn.alloc().initWithIdentifier_("page")
        column.setResizingMask_(AppKit.NSTableColumnAutoresizingMask)
        table.addTableColumn_(column)
        table.setColumnAutoresizingStyle_(AppKit.NSTableViewUniformColumnAutoresizingStyle)
        table.setDataSource_(self)
        table.setDelegate_(self)
        table.setAccessibilityLabel_("Zoya")
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        scroll.setDocumentView_(table)
        scroll.setDrawsBackground_(False)
        plan, self.plan_left, self.plan_right, (self.plan_track, self.plan_fill) = _plan_bar(
            lambda: self.on_select("plan")
        )
        self.plan = plan
        self.plan_width = None
        inner = AppKit.NSView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        _pin(inner, _brand(), scroll, plan)
        self.table = table
        self.setView_(_pane(inner))
        self.set_plan(None)

    def viewDidLayout(self) -> None:  # noqa: N802
        objc.super(Sidebar, self).viewDidLayout()
        column = self.table.tableColumns()[0]
        column.setWidth_(self.table.enclosingScrollView().contentSize().width)

    def numberOfRowsInTableView_(self, _table: Any) -> int:  # noqa: N802
        return len(ROWS)

    def tableView_heightOfRow_(self, _table: Any, row: int) -> float:  # noqa: N802
        return ROW_HEIGHT if ROWS[row][0] else LABEL_HEIGHT

    def tableView_shouldSelectRow_(self, _table: Any, row: int) -> bool:  # noqa: N802
        return bool(ROWS[row][0])

    def tableView_viewForTableColumn_row_(  # noqa: N802
        self, _table: Any, _column: Any, row: int
    ) -> Any:
        page, title, symbol = ROWS[row]
        if not page:
            return _section_cell(title)
        return _page_cell(title, symbol, self.counts.get(page, ""))

    def tableView_rowViewForRow_(self, _table: Any, _row: int) -> Any:  # noqa: N802
        return SelectedRow.alloc().init()

    def tableViewSelectionDidChange_(self, _notification: Any) -> None:  # noqa: N802
        row = self.table.selectedRow()
        if 0 <= row < len(ROWS) and ROWS[row][0] and not self.syncing:
            self.on_select(ROWS[row][0])

    @objc.python_method
    def select(self, page: str) -> None:
        self.view()
        self.syncing = True
        if page in PAGE_ROWS:
            self.table.selectRowIndexes_byExtendingSelection_(
                AppKit.NSIndexSet.indexSetWithIndex_(PAGE_ROWS[page]), False
            )
        else:
            self.table.deselectAll_(None)
        self.syncing = False

    @objc.python_method
    def set_counts(self, counts: dict[str, str]) -> None:
        self.view()
        self.counts = counts
        selected = self.table.selectedRowIndexes()
        self.table.reloadData()
        self.syncing = True
        self.table.selectRowIndexes_byExtendingSelection_(selected, False)
        self.syncing = False

    @objc.python_method
    def set_plan(self, plan: dict[str, Any] | None) -> None:
        self.view()
        shown = plan is not None and plan["capCents"] > 0
        share = min(plan["usedCents"] / plan["capCents"], 1.0) if shown else 0.0
        self.plan_left.setStringValue_(f"Plan · {month_name(plan['month'])}" if shown else "Plan")
        self.plan_right.setStringValue_(f"{round(share * 100)}%" if shown else "")
        self.plan.spoken = f"Plan, {round(share * 100)} percent used" if shown else "Plan"
        ink = AppKit.NSColor.labelColor()
        self.plan_track.layer().setBackgroundColor_(
            ink.colorWithAlphaComponent_(HAIRLINE).CGColor()
        )
        self.plan_fill.layer().setBackgroundColor_(AppKit.NSColor.secondaryLabelColor().CGColor())
        if self.plan_width is not None:
            self.plan_width.setActive_(False)
        self.plan_width = self.plan_fill.widthAnchor().constraintEqualToAnchor_multiplier_(
            self.plan_track.widthAnchor(), max(share, 0.0001)
        )
        self.plan_width.setActive_(True)


def sidebar(on_select: Callable[[str], None]) -> Any:
    controller = Sidebar.alloc().init()
    controller.on_select = on_select
    controller.syncing = False
    controller.counts = {}
    return controller
