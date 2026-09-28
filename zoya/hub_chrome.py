"""The Hub sidebar in heyyzoya.com's look (D131): light glass, the ‿‿ mark, lowercase rows, a
gloss capsule on the selected row, counts and the plan meter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import AppKit
import objc
import Quartz

from zoya.overlay_pill import accessibility, loop, oklch, register_fonts

ROWS: tuple[tuple[str, str, str], ...] = (
    ("today", "today", "sun.max"),
    ("history", "history", "clock.arrow.circlepath"),
    ("memory", "memory", "brain"),
    ("", "", ""),
    ("setup", "setup", "checkmark.circle"),
    ("voice", "voice & keys", "slider.horizontal.3"),
)
PAGE_ROWS = {page: index for index, (page, _title, _symbol) in enumerate(ROWS) if page}
ROW_HEIGHT = 36.0
GAP_HEIGHT = 14.0
ROW_SPACING = 2.0
SIDEBAR_MIN, SIDEBAR_MAX = 228.0, 260.0
SYMBOL_W = 16.0
ROW_PAD = 12.0
ICON_GAP = 10.0
EDGE = 10.0
TOP = 46.0
ROW_PT, COUNT_PT, BRAND_PT, PLAN_PT = 14.5, 12.5, 17.0, 12.5
BRAND_KERN = -0.34
MARK_W, MARK_H = 30.0, 20.0
MARK_EYES = ((7.0, 11.0), (19.0, 11.0))
MARK_EYE = (4.0, 7.0)
MARK_SMILE = ((5.0, 7.0), (8.0, 2.0), (22.0, 2.0), (25.0, 7.0))
MARK_STROKE = 3.2
BLINK_S, SQUISH_S = 4.2, 6.0
BLINK_TIMES = [0.0, 0.92, 0.95, 1.0]
SQUISH_TIMES = [0.0, 0.8, 0.86, 0.92, 1.0]
SQUISH_X = [1.0, 1.0, 1.14, 0.94, 1.0]
SQUISH_Y = [1.0, 1.0, 0.84, 1.06, 1.0]
METER_PT = 5.0
METER_RADIUS = 3.0
DASH = [3.0, 3.0]
INTER = {
    "regular": "InterVariable",
    "medium": "InterVariable-Medium",
    "semibold": "InterVariable-SemiBold",
}
WEIGHTS = {
    "regular": AppKit.NSFontWeightRegular,
    "medium": AppKit.NSFontWeightMedium,
    "semibold": AppKit.NSFontWeightSemibold,
}

TEXT = (oklch(0.15, 0.005, 260), oklch(0.965, 0.003, 260))
MUTED = (oklch(0.40, 0.006, 260), oklch(0.76, 0.006, 260))
QUIET = (oklch(0.52, 0.006, 260), oklch(0.64, 0.006, 260))
LINK = (oklch(0.43, 0.16, 258), oklch(0.78, 0.11, 252))
RULE = (oklch(0.86, 0.004, 260), oklch(0.34, 0.005, 260))
PANE = (oklch(0.975, 0.003, 260, 0.82), oklch(0.21, 0.004, 260, 0.82))
CAPSULE_TOP = (oklch(0.91, 0.05, 245), oklch(0.36, 0.06, 252))
CAPSULE_BOTTOM = (oklch(0.86, 0.07, 248), oklch(0.31, 0.07, 254))
CAPSULE_EDGE = (oklch(0.70, 0.1, 252, 0.55), oklch(0.58, 0.1, 252, 0.55))
CAPSULE_SHINE = (oklch(1.0, 0, 0, 0.8), oklch(1.0, 0, 0, 0.12))
METER_TOP = (oklch(0.81, 0.095, 250), oklch(0.62, 0.13, 250))
METER_BOTTOM = (oklch(0.75, 0.12, 253), oklch(0.52, 0.15, 254))


def _dark(appearance: Any) -> bool:
    return "Dark" in str(appearance.name())


def _ns(rgba: tuple[float, ...]) -> Any:
    return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(*rgba)


def _dynamic(pair: tuple[tuple[float, ...], tuple[float, ...]]) -> Any:
    light, dark = pair
    return AppKit.NSColor.colorWithName_dynamicProvider_(
        None, lambda appearance: _ns(dark if _dark(appearance) else light)
    )


def _cg(pair: tuple[tuple[float, ...], tuple[float, ...]], view: Any) -> Any:
    return _ns(pair[1] if _dark(view.effectiveAppearance()) else pair[0]).CGColor()


def inter(size: float, weight: str) -> Any:
    register_fonts()
    chosen = AppKit.NSFont.fontWithName_size_(INTER[weight], size)
    return chosen or AppKit.NSFont.systemFontOfSize_weight_(size, WEIGHTS[weight])


def tabular(font: Any) -> Any:
    feature = {
        AppKit.NSFontFeatureTypeIdentifierKey: AppKit.kNumberSpacingType,
        AppKit.NSFontFeatureSelectorIdentifierKey: AppKit.kMonospacedNumbersSelector,
    }
    descriptor = font.fontDescriptor().fontDescriptorByAddingAttributes_(
        {AppKit.NSFontFeatureSettingsAttribute: [feature]}
    )
    return AppKit.NSFont.fontWithDescriptor_size_(descriptor, font.pointSize())


def _fixed(view: Any, width: float, height: float) -> Any:
    view.setTranslatesAutoresizingMaskIntoConstraints_(False)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            view.widthAnchor().constraintEqualToConstant_(width),
            view.heightAnchor().constraintEqualToConstant_(height),
        ]
    )
    return view


def _label(text: str, font: Any, color: Any) -> Any:
    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(font)
    field.setTextColor_(color)
    field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    return field


class Themed(AppKit.NSView):
    def viewDidChangeEffectiveAppearance(self) -> None:  # noqa: N802
        objc.super(Themed, self).viewDidChangeEffectiveAppearance()
        self.on_theme()


class Mark(Themed):
    def isFlipped(self) -> bool:  # noqa: N802
        return False


def _smile() -> Any:
    path = Quartz.CGPathCreateMutable()
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = MARK_SMILE
    Quartz.CGPathMoveToPoint(path, None, x0, y0)
    Quartz.CGPathAddCurveToPoint(path, None, x1, y1, x2, y2, x3, y3)
    layer = Quartz.CAShapeLayer.layer()
    layer.setPath_(path)
    layer.setFillColor_(None)
    layer.setLineWidth_(MARK_STROKE)
    layer.setLineCap_(Quartz.kCALineCapRound)
    return layer


def mark() -> Any:
    view = _fixed(Mark.alloc().initWithFrame_(((0, 0), (MARK_W, MARK_H))), MARK_W, MARK_H)
    view.setWantsLayer_(True)
    view.setAccessibilityElement_(False)
    body = Quartz.CALayer.layer()
    body.setBounds_(((0, 0), (MARK_W, MARK_H)))
    body.setPosition_((MARK_W / 2, MARK_H / 2))
    view.layer().addSublayer_(body)
    eyes = []
    for x, y in MARK_EYES:
        eye = Quartz.CALayer.layer()
        eye.setFrame_(((x, y), MARK_EYE))
        eye.setCornerRadius_(MARK_EYE[0] / 2)
        body.addSublayer_(eye)
        eyes.append(eye)
    smile = _smile()
    body.addSublayer_(smile)

    def paint() -> None:
        ink = _cg(TEXT, view)
        for eye in eyes:
            eye.setBackgroundColor_(ink)
        smile.setStrokeColor_(ink)

    view.on_theme = paint
    paint()
    if not accessibility()[0]:
        blink = loop("transform.scale.y", [1.0, 1.0, 0.12, 1.0], BLINK_S, key_times=BLINK_TIMES)
        for eye in eyes:
            eye.addAnimation_forKey_(blink, "blink")
        body.addAnimation_forKey_(
            loop("transform.scale.x", SQUISH_X, SQUISH_S, key_times=SQUISH_TIMES), "squishX"
        )
        body.addAnimation_forKey_(
            loop("transform.scale.y", SQUISH_Y, SQUISH_S, key_times=SQUISH_TIMES), "squishY"
        )
    return view


def _brand() -> Any:
    name = AppKit.NSTextField.labelWithAttributedString_(
        AppKit.NSAttributedString.alloc().initWithString_attributes_(
            "zoya",
            {
                AppKit.NSFontAttributeName: inter(BRAND_PT, "semibold"),
                AppKit.NSForegroundColorAttributeName: _dynamic(TEXT),
                AppKit.NSKernAttributeName: BRAND_KERN,
            },
        )
    )
    row = AppKit.NSStackView.stackViewWithViews_([mark(), name])
    row.setSpacing_(10.0)
    row.setAccessibilityElement_(True)
    row.setAccessibilityLabel_("Zoya")
    return row


class DashedRule(AppKit.NSView):
    def drawRect_(self, _rect: Any) -> None:  # noqa: N802
        path = AppKit.NSBezierPath.bezierPath()
        width = self.bounds().size.width
        path.moveToPoint_((0, self.bounds().size.height - 0.5))
        path.lineToPoint_((width, self.bounds().size.height - 0.5))
        path.setLineWidth_(1.0)
        path.setLineDash_count_phase_(DASH, len(DASH), 0.0)
        _dynamic(RULE).setStroke()
        path.stroke()


class PageCell(AppKit.NSTableCellView):
    @objc.python_method
    def paint(self) -> None:
        on = self.selected
        self.textField().setTextColor_(_dynamic(TEXT if on else MUTED))
        self.textField().setFont_(inter(ROW_PT, "medium" if on else "regular"))
        self.imageView().setContentTintColor_(_dynamic(TEXT if on else MUTED))
        self.number.setTextColor_(_dynamic(LINK if on else QUIET))


def _symbol(name: str) -> Any:
    image = AppKit.NSImageView.imageViewWithImage_(
        AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    )
    image.setSymbolConfiguration_(
        AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
            13.0, AppKit.NSFontWeightRegular
        )
    )
    return _fixed(image, SYMBOL_W, SYMBOL_W)


def _page_cell(title: str, symbol: str, count: str, selected: bool) -> Any:
    cell = PageCell.alloc().initWithFrame_(((0, 0), (200, ROW_HEIGHT)))
    image = _symbol(symbol)
    label = _label(title, inter(ROW_PT, "regular"), _dynamic(MUTED))
    number = _label(count, tabular(inter(COUNT_PT, "regular")), _dynamic(QUIET))
    number.setAccessibilityElement_(False)
    for view in (image, label, number):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        cell.addSubview_(view)
    cell.setImageView_(image)
    cell.setTextField_(label)
    cell.number, cell.selected = number, selected
    cell.setAccessibilityLabel_(f"{title}, {count}" if count else title)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            image.leadingAnchor().constraintEqualToAnchor_constant_(cell.leadingAnchor(), ROW_PAD),
            image.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            label.leadingAnchor().constraintEqualToAnchor_constant_(
                image.trailingAnchor(), ICON_GAP
            ),
            label.centerYAnchor().constraintEqualToAnchor_(cell.centerYAnchor()),
            number.trailingAnchor().constraintEqualToAnchor_constant_(
                cell.trailingAnchor(), -ROW_PAD
            ),
            number.firstBaselineAnchor().constraintEqualToAnchor_(label.firstBaselineAnchor()),
            number.leadingAnchor().constraintGreaterThanOrEqualToAnchor_constant_(
                label.trailingAnchor(), 6.0
            ),
        ]
    )
    cell.paint()
    return cell


class CapsuleRow(AppKit.NSTableRowView):
    def setSelected_(self, selected: bool) -> None:  # noqa: N802
        objc.super(CapsuleRow, self).setSelected_(selected)
        self.setNeedsDisplay_(True)

    def drawBackgroundInRect_(self, _rect: Any) -> None:  # noqa: N802
        if not self.isSelected():
            return
        box = self.bounds()
        radius = box.size.height / 2
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box, radius, radius)
        gradient = AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(
            _dynamic(CAPSULE_TOP), _dynamic(CAPSULE_BOTTOM)
        )
        gradient.drawInBezierPath_angle_(path, -90.0 if self.isFlipped() else 90.0)
        edge = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            AppKit.NSInsetRect(box, 0.5, 0.5), radius - 0.5, radius - 0.5
        )
        edge.setLineWidth_(1.0)
        _dynamic(CAPSULE_EDGE).setStroke()
        edge.stroke()
        self._shine(box, radius)

    @objc.python_method
    def _shine(self, box: Any, radius: float) -> None:
        AppKit.NSGraphicsContext.saveGraphicsState()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            AppKit.NSInsetRect(box, 1.0, 1.0), radius - 1, radius - 1
        ).addClip()
        top = box.origin.y + 1.0 if self.isFlipped() else box.origin.y + box.size.height - 2.0
        _dynamic(CAPSULE_SHINE).setFill()
        AppKit.NSRectFillUsingOperation(
            ((box.origin.x, top), (box.size.width, 1.0)), AppKit.NSCompositingOperationSourceOver
        )
        AppKit.NSGraphicsContext.restoreGraphicsState()

    def isEmphasized(self) -> bool:  # noqa: N802
        return False


class GradientView(Themed):
    def makeBackingLayer(self) -> Any:  # noqa: N802
        return Quartz.CAGradientLayer.layer()


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


def _meter() -> tuple[Any, Any]:
    track = Themed.alloc().initWithFrame_(((0, 0), (200, METER_PT)))
    fill = GradientView.alloc().initWithFrame_(((0, 0), (0, METER_PT)))
    for part in (track, fill):
        part.setWantsLayer_(True)
        part.layer().setCornerRadius_(METER_RADIUS)

    def paint() -> None:
        track.layer().setBackgroundColor_(_cg(RULE, track))
        fill.layer().setColors_([_cg(METER_TOP, fill), _cg(METER_BOTTOM, fill)])
        fill.layer().setStartPoint_((0.5, 1.0))
        fill.layer().setEndPoint_((0.5, 0.0))

    track.on_theme = fill.on_theme = paint
    paint()
    fill.setTranslatesAutoresizingMaskIntoConstraints_(False)
    track.addSubview_(fill)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            fill.leadingAnchor().constraintEqualToAnchor_(track.leadingAnchor()),
            fill.topAnchor().constraintEqualToAnchor_(track.topAnchor()),
            fill.bottomAnchor().constraintEqualToAnchor_(track.bottomAnchor()),
        ]
    )
    return track, fill


def _plan_bar(on_open: Callable[[], None]) -> tuple[Any, Any, Any, Any]:
    bar = PlanBar.alloc().initWithFrame_(((0, 0), (200, 44)))
    bar.on_open, bar.spoken = on_open, "Plan"
    rule = DashedRule.alloc().initWithFrame_(((0, 0), (200, 1)))
    left = _label("this month", inter(PLAN_PT, "regular"), _dynamic(MUTED))
    right = _label("", tabular(inter(PLAN_PT, "medium")), _dynamic(TEXT))
    track, fill = _meter()
    for view in (rule, left, right, track):
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        bar.addSubview_(view)
    AppKit.NSLayoutConstraint.activateConstraints_(
        [
            rule.topAnchor().constraintEqualToAnchor_(bar.topAnchor()),
            rule.leadingAnchor().constraintEqualToAnchor_(bar.leadingAnchor()),
            rule.trailingAnchor().constraintEqualToAnchor_(bar.trailingAnchor()),
            rule.heightAnchor().constraintEqualToConstant_(1.0),
            left.topAnchor().constraintEqualToAnchor_constant_(rule.bottomAnchor(), 14.0),
            left.leadingAnchor().constraintEqualToAnchor_constant_(bar.leadingAnchor(), ROW_PAD),
            right.firstBaselineAnchor().constraintEqualToAnchor_(left.firstBaselineAnchor()),
            right.trailingAnchor().constraintEqualToAnchor_constant_(
                bar.trailingAnchor(), -ROW_PAD
            ),
            track.topAnchor().constraintEqualToAnchor_constant_(left.bottomAnchor(), 8.0),
            track.leadingAnchor().constraintEqualToAnchor_(left.leadingAnchor()),
            track.trailingAnchor().constraintEqualToAnchor_(right.trailingAnchor()),
            track.heightAnchor().constraintEqualToConstant_(METER_PT),
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
            top.leadingAnchor().constraintEqualToAnchor_constant_(
                container.leadingAnchor(), EDGE + 10.0
            ),
            middle.topAnchor().constraintEqualToAnchor_constant_(top.bottomAnchor(), 18.0),
            middle.leadingAnchor().constraintEqualToAnchor_constant_(
                container.leadingAnchor(), EDGE
            ),
            middle.trailingAnchor().constraintEqualToAnchor_constant_(
                container.trailingAnchor(), -EDGE
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
        inner.setWantsLayer_(True)
        inner.on_theme = lambda: inner.layer().setBackgroundColor_(_cg(PANE, inner))
        inner.on_theme()
        return inner
    pane = AppKit.NSGlassEffectView.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
    pane.setTintColor_(_dynamic(PANE))
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
        table.setIntercellSpacing_((0.0, ROW_SPACING))
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
        inner = Themed.alloc().initWithFrame_(((0, 0), (SIDEBAR_MIN, 400)))
        inner.on_theme = lambda: None
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
        return ROW_HEIGHT if ROWS[row][0] else GAP_HEIGHT

    def tableView_shouldSelectRow_(self, _table: Any, row: int) -> bool:  # noqa: N802
        return bool(ROWS[row][0])

    def tableView_viewForTableColumn_row_(  # noqa: N802
        self, table: Any, _column: Any, row: int
    ) -> Any:
        page, title, symbol = ROWS[row]
        if not page:
            return AppKit.NSView.alloc().initWithFrame_(((0, 0), (1, GAP_HEIGHT)))
        selected = table.selectedRow() == row
        return _page_cell(title, symbol, self.counts.get(page, ""), selected)

    def tableView_rowViewForRow_(self, _table: Any, _row: int) -> Any:  # noqa: N802
        return CapsuleRow.alloc().init()

    def tableViewSelectionDidChange_(self, _notification: Any) -> None:  # noqa: N802
        self._repaint_rows()
        row = self.table.selectedRow()
        if 0 <= row < len(ROWS) and ROWS[row][0] and not self.syncing:
            self.on_select(ROWS[row][0])

    @objc.python_method
    def _repaint_rows(self) -> None:
        chosen = self.table.selectedRow()
        for row in range(len(ROWS)):
            cell = self.table.viewAtColumn_row_makeIfNecessary_(0, row, False)
            if isinstance(cell, PageCell):
                cell.selected = row == chosen
                cell.paint()

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
        self._repaint_rows()
        self.syncing = False

    @objc.python_method
    def set_counts(self, counts: dict[str, str]) -> None:
        self.view()
        self.counts = counts
        selected = self.table.selectedRowIndexes()
        self.table.reloadData()
        self.syncing = True
        self.table.selectRowIndexes_byExtendingSelection_(selected, False)
        self._repaint_rows()
        self.syncing = False

    @objc.python_method
    def set_plan(self, plan: dict[str, Any] | None) -> None:
        self.view()
        shown = plan is not None and plan["capCents"] > 0
        share = min(plan["usedCents"] / plan["capCents"], 1.0) if shown else 0.0
        self.plan_right.setStringValue_(f"{round(share * 100)}% used" if shown else "")
        self.plan.spoken = f"Plan, {round(share * 100)} percent used" if shown else "Plan"
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
