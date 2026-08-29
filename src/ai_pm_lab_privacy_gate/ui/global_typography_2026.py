from __future__ import annotations

"""Application-wide 0.5 typography/readability system.

Protect established the approved visual reference: inherited 10pt body copy already
reads well, while local 7-13px micro-styles are too small on a Windows desktop.
This module applies the same readability floor across the whole application,
including the redesigned sidebar, cards, controls, badges, dialogs and tables.

Presentation only: no geometry, spacing, navigation or business behavior is changed.
The runtime also watches widgets created/restyled later so workspace switches,
dialogs and lazy product surfaces keep the same typography without page-specific
patches.
"""

import re

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QTableView, QTableWidget, QWidget


_FONT_SIZE_RE = re.compile(
    r"(font-size\s*:\s*)(\d+(?:\.\d+)?)(px|pt)",
    re.IGNORECASE,
)

# The Protect pilot scale approved for the 0.5 visual baseline.
_MICRO_PX = 11.0
_SECONDARY_PX = 12.0
_BODY_PX = 13.0
_BODY_LARGE_PX = 14.0
_TABLE_PX = 14.0

# Application stylesheet roles that historically use 7.5-8pt. A direct local
# role floor is necessary because QWidget.styleSheet() does not include the
# QApplication-level stylesheet where those legacy rules live.
_ROLE_PIXEL_FLOORS = {
    "SidebarProduct": 11.0,
    "SidebarNote": 11.0,
    "ProductFooter": 11.0,
    "ConnectionBadge": 12.0,
    "CopyFeedback": 11.0,
    "TokenHint": 11.0,
    "ColorLegend": 11.0,
    "PdfBadge": 11.0,
    "Tiny": 12.0,
    # Current 2026 shell/sidebar roles.
    "RedesignNavButton": 13.0,
    "RedesignSubNavButton": 12.0,
    "RedesignWorkspaceButton": 13.0,
    "RedesignAccountButton": 12.0,
}


def _readable_px(value: float) -> float:
    """Map legacy micro typography onto the approved Protect readability scale."""
    if value <= 8.0:
        return _MICRO_PX
    if value <= 9.0:
        return _SECONDARY_PX
    if value <= 11.0:
        return _BODY_PX
    if value <= 13.0:
        return _BODY_LARGE_PX
    return value


def _scaled_style_sheet(style: str) -> str:
    """Scale only font-size declarations, preserving every other QSS property."""

    def replace(match: re.Match[str]) -> str:
        prefix, raw_value, unit = match.groups()
        value = float(raw_value)
        # 1pt = 4/3px at the CSS/Qt 96dpi reference. Converting both units through
        # px lets the same visual scale work for old point-based and new pixel QSS.
        px_value = value if unit.lower() == "px" else value * (4.0 / 3.0)
        upgraded_px = _readable_px(px_value)
        if upgraded_px == px_value:
            return match.group(0)
        upgraded = upgraded_px if unit.lower() == "px" else upgraded_px * 0.75
        rendered = (
            str(int(upgraded))
            if float(upgraded).is_integer()
            else f"{upgraded:.2f}".rstrip("0").rstrip(".")
        )
        return f"{prefix}{rendered}{unit}"

    return _FONT_SIZE_RE.sub(replace, style)


def _font_sizes_px(style: str) -> tuple[float, ...]:
    values: list[float] = []
    for match in _FONT_SIZE_RE.finditer(style):
        value = float(match.group(2))
        if match.group(3).lower() == "pt":
            value *= 4.0 / 3.0
        values.append(value)
    return tuple(values)


def _role_floor_rule(widget: QWidget, pixels: float) -> str:
    class_name = widget.metaObject().className()
    object_name = widget.objectName()
    rendered = str(int(pixels)) if pixels.is_integer() else f"{pixels:g}"
    return f"{class_name}#{object_name}{{font-size:{rendered}px;}}"


def _apply_role_floor(widget: QWidget) -> None:
    pixels = _ROLE_PIXEL_FLOORS.get(widget.objectName())
    if pixels is None:
        return
    style = widget.styleSheet()
    marker = f"_privacygate_global_role_{widget.objectName()}_{pixels:g}"
    if getattr(widget, marker, False):
        return
    rule = _role_floor_rule(widget, pixels)
    widget.setStyleSheet(style + ("\n" if style else "") + rule)
    setattr(widget, marker, True)


def _set_point_floor(widget: QWidget, minimum: float) -> None:
    font = widget.font()
    current = font.pointSizeF()
    if current > 0 and current >= minimum:
        return
    font.setPointSizeF(minimum)
    widget.setFont(font)


def _apply_table_floor(table: QTableView) -> None:
    """Use a readable table floor without changing row height or column geometry."""
    style = table.styleSheet()
    sizes = _font_sizes_px(style)
    max_local = max(sizes) if sizes else 0.0

    # Protect's approved Detected items table is deliberately 15px. Never reduce
    # a table that already has an equal or larger local treatment.
    if max_local < _TABLE_PX:
        selector = "QTableWidget" if isinstance(table, QTableWidget) else "QTableView"
        table_rule = (
            f"{selector}{{font-size:{int(_TABLE_PX)}px;}}"
            f"{selector}::item{{font-size:{int(_TABLE_PX)}px;}}"
        )
        marker = "_privacygate_global_table_rule"
        if not getattr(table, marker, False):
            table.setStyleSheet(style + ("\n" if style else "") + table_rule)
            setattr(table, marker, True)

    _set_point_floor(table, 10.5)  # ~14px
    header = table.horizontalHeader()
    if header is not None:
        _set_point_floor(header, 10.5)

    if not isinstance(table, QTableWidget):
        return
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is None:
                continue
            font = item.font()
            current = font.pointSizeF()
            if current <= 0 or current < 10.5:
                font.setPointSizeF(10.5)
                item.setFont(font)


def _apply_widget(widget: QWidget) -> None:
    # InfoButton is intentionally an 18x18 icon-like control. Enlarging its glyph
    # would clip inside the fixed geometry, so it stays the one typography exception.
    if widget.objectName() == "InfoButton":
        return

    style = widget.styleSheet()
    if style:
        last_applied = getattr(widget, "_privacygate_global_typography_style", None)
        if style != last_applied:
            upgraded = _scaled_style_sheet(style)
            if upgraded != style:
                widget.setStyleSheet(upgraded)
            widget._privacygate_global_typography_style = upgraded

    _apply_role_floor(widget)

    if isinstance(widget, QTableView):
        _apply_table_floor(widget)


def _apply_tree(root: QWidget) -> None:
    try:
        _apply_widget(root)
        for widget in root.findChildren(QWidget):
            _apply_widget(widget)
    except RuntimeError:
        # A queued typography pass may race a dialog/window being destroyed.
        return


class _GlobalTypographyFilter(QObject):
    """Keep late-created/restyled Qt surfaces on the same visual scale."""

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if not isinstance(watched, QWidget):
            return False
        event_type = event.type()
        if event_type in {QEvent.Type.Show, QEvent.Type.Polish}:
            QTimer.singleShot(0, lambda widget=watched: _apply_tree(widget))
        elif event_type == QEvent.Type.StyleChange:
            # Local compatibility/product layers often restyle an already-visible
            # widget. Re-run only that widget; the idempotent cache prevents loops.
            QTimer.singleShot(0, lambda widget=watched: _apply_widget(widget))
        return False


def apply_global_typography_2026(main_window) -> None:
    """Install and apply the unified 0.5 typography baseline for the whole app."""
    if getattr(main_window, "_privacygate_global_typography_2026", False):
        return
    main_window._privacygate_global_typography_2026 = True

    app = QApplication.instance()
    if app is not None and getattr(app, "_privacygate_global_typography_filter", None) is None:
        filter_object = _GlobalTypographyFilter(app)
        app.installEventFilter(filter_object)
        app._privacygate_global_typography_filter = filter_object
        main_window._privacygate_global_typography_filter = filter_object

    _apply_tree(main_window)

    # Startup has several intentionally layered 2026 surfaces. These passes catch
    # same-turn/queued rebuilds while the event filter owns all later changes.
    QTimer.singleShot(0, lambda: _apply_tree(main_window))
    QTimer.singleShot(180, lambda: _apply_tree(main_window))
    QTimer.singleShot(650, lambda: _apply_tree(main_window))

    pages = getattr(main_window, "pages", None)
    if pages is not None:
        pages.currentChanged.connect(
            lambda _index: QTimer.singleShot(0, lambda: _apply_tree(main_window))
        )
