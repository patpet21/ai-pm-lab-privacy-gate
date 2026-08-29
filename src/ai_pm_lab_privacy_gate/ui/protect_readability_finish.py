from __future__ import annotations

"""Final readability polish for the dense Protect review area.

The general Protect typography pilot is intentionally conservative. This layer
only gives the lower review controls and the Detected items table a small extra
increase so dense text remains readable without changing the approved layout.
"""

import re
from types import MethodType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget


_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)


def _bump_review_micro_style(style: str) -> str:
    """Lift only genuinely small review microcopy; leave normal copy alone."""

    def replace(match: re.Match[str]) -> str:
        current = float(match.group(1))
        if current <= 11.0:
            upgraded = 13.0
        elif current <= 12.0:
            upgraded = 14.0
        else:
            upgraded = current
        rendered = str(int(upgraded)) if upgraded.is_integer() else f"{upgraded:g}"
        return f"font-size:{rendered}px"

    return _FONT_SIZE_RE.sub(replace, style)


def _set_min_point_size(widget: QWidget, minimum: float) -> None:
    font = widget.font()
    current = font.pointSizeF()
    if current > 0 and current >= minimum:
        return
    font.setPointSizeF(minimum)
    widget.setFont(font)


def _style_findings_table(table) -> None:
    """Give the real item renderer a visible but still compact typography floor.

    The application base font is 10pt, which is already roughly 13px on Windows.
    The previous 13px table rule therefore looked almost identical. Use a modest
    15px body / 14px header here and also stamp the QTableWidgetItems themselves
    so later Protect compatibility layers cannot silently fall back to the base
    font after a scan repopulates the table.
    """
    table.setStyleSheet(
        "QTableWidget{font-size:15px;}"
        "QTableWidget::item{font-size:15px;padding:6px 8px;}"
        "QHeaderView::section{font-size:14px;font-weight:800;padding:8px 8px;}"
    )

    table_font = table.font()
    table_font.setPointSizeF(max(table_font.pointSizeF(), 11.25))
    table.setFont(table_font)

    header = table.horizontalHeader()
    header_font = header.font()
    header_font.setPointSizeF(max(header_font.pointSizeF(), 10.5))
    header_font.setBold(True)
    header.setFont(header_font)

    # Header items and body items can carry their own fonts. Set them explicitly
    # because those are the objects Qt actually paints in the review grid.
    for column in range(table.columnCount()):
        header_item = table.horizontalHeaderItem(column)
        if header_item is not None:
            font = header_item.font()
            font.setPointSizeF(max(font.pointSizeF(), 10.5))
            font.setBold(True)
            header_item.setFont(font)

    for row in range(table.rowCount()):
        table.setRowHeight(row, max(table.rowHeight(row), 36))
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None:
                font = item.font()
                font.setPointSizeF(max(font.pointSizeF(), 11.25))
                item.setFont(font)
            cell = table.cellWidget(row, column)
            if cell is not None:
                _set_min_point_size(cell, 11.0)
                for label in cell.findChildren(QLabel):
                    _set_min_point_size(label, 11.0)

    table.verticalHeader().setDefaultSectionSize(
        max(table.verticalHeader().defaultSectionSize(), 36)
    )
    table.viewport().update()
    header.viewport().update()


def _refresh_readability(page) -> None:
    table = getattr(page, "findings_table", None)
    if table is not None:
        _style_findings_table(table)

    # This is the context/details box directly below Detected items. It was still
    # using the 10pt application default, so make it visibly easier to read too.
    context = getattr(page, "finding_context", None)
    if context is not None:
        context.setStyleSheet(
            "QLabel#ReviewContext{color:#294C60;background:#F7FAFC;"
            "border:1px solid #D7E2EA;border-radius:7px;padding:8px 10px;"
            "font-size:14px;}"
        )

    card = getattr(page, "findings_card", None)
    if card is None:
        return

    # Status/count/category pills in the review card can carry explicit local
    # micro-font styles. Raise only those small styles; normal headings are left
    # untouched.
    for widget_type in (QLabel, QPushButton, QLineEdit):
        for widget in card.findChildren(widget_type):
            if widget is context:
                continue
            style = widget.styleSheet()
            if style:
                last_applied = getattr(
                    widget, "_privacygate_findings_readability_style", None
                )
                if style == last_applied:
                    continue
                upgraded = _bump_review_micro_style(style)
                if upgraded != style:
                    widget.setStyleSheet(upgraded)
                widget._privacygate_findings_readability_style = upgraded


def _wrap_findings_population(page) -> None:
    """Reapply typography after the asynchronous scan actually fills the table."""
    original = getattr(page, "_populate_findings", None)
    if not callable(original) or getattr(page, "_privacygate_readability_population_wrapped", False):
        return

    page._privacygate_readability_population_wrapped = True

    def populate_findings(self) -> None:
        original()
        _refresh_readability(self)
        # Managed-policy annotations may adjust row labels immediately after
        # population; one next-turn pass keeps the same font on those final items.
        QTimer.singleShot(0, lambda: _refresh_readability(self))

    page._populate_findings = MethodType(populate_findings, page)


def apply_protect_readability_finish(main_window) -> None:
    """Apply the approved small readability increase only inside Protect review."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_readability_finish", False):
        return
    page._privacygate_readability_finish = True

    _wrap_findings_population(page)
    _refresh_readability(page)
    QTimer.singleShot(0, lambda: _refresh_readability(page))

    # The scan is asynchronous. These delayed passes are only a safety net; the
    # authoritative hook above runs after _populate_findings has actually created
    # every row.
    scan = getattr(page, "scan_button", None)
    if scan is not None:
        scan.clicked.connect(
            lambda _checked=False: (
                QTimer.singleShot(250, lambda: _refresh_readability(page)),
                QTimer.singleShot(800, lambda: _refresh_readability(page)),
            )
        )
