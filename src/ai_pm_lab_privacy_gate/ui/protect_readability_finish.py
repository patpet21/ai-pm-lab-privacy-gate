from __future__ import annotations

"""Final readability polish for the dense Protect review area.

The general Protect typography pilot is intentionally conservative. This layer
only gives the lower review controls and the Detected items table a small extra
increase so dense text remains readable without changing the approved layout.
"""

import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget


_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)


def _bump_review_micro_style(style: str) -> str:
    """Add one pixel only to remaining 11-12 px review microcopy."""

    def replace(match: re.Match[str]) -> str:
        current = float(match.group(1))
        upgraded = current + 1.0 if 11.0 <= current <= 12.0 else current
        rendered = str(int(upgraded)) if upgraded.is_integer() else f"{upgraded:g}"
        return f"font-size:{rendered}px"

    return _FONT_SIZE_RE.sub(replace, style)


def _set_min_point_size(widget: QWidget, minimum: float) -> None:
    font = widget.font()
    current = font.pointSizeF()
    if current <= 0 or current >= minimum:
        return
    font.setPointSizeF(minimum)
    widget.setFont(font)


def _style_findings_table(table) -> None:
    """Set an explicit local QSS floor so the app stylesheet cannot keep it tiny.

    A QFont-only increase is easy for Qt's application stylesheet to override.
    The review table therefore gets a small explicit pixel size while retaining
    the existing colors, selection behavior and column layout.
    """
    table.setStyleSheet(
        "QTableWidget{font-size:13px;}"
        "QTableWidget::item{font-size:13px;padding:5px 8px;}"
        "QHeaderView::section{font-size:12px;font-weight:800;padding:7px 8px;}"
    )
    header_font = table.horizontalHeader().font()
    header_font.setPointSizeF(max(header_font.pointSizeF(), 10.0))
    header_font.setBold(True)
    table.horizontalHeader().setFont(header_font)
    table.verticalHeader().setDefaultSectionSize(
        max(table.verticalHeader().defaultSectionSize(), 34)
    )


def _refresh_readability(page) -> None:
    table = getattr(page, "findings_table", None)
    if table is not None:
        _style_findings_table(table)

    card = getattr(page, "findings_card", None)
    if card is None:
        return

    # Status/count/category pills in the review card often carry explicit local
    # 11-12 px styles after the general Protect pilot. Give only those micro
    # labels one additional pixel; larger headings remain untouched.
    for widget_type in (QLabel, QPushButton, QLineEdit):
        for widget in card.findChildren(widget_type):
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
            elif isinstance(widget, (QPushButton, QLineEdit)):
                _set_min_point_size(widget, 10.0)


def apply_protect_readability_finish(main_window) -> None:
    """Apply the approved small readability increase only inside Protect review."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_readability_finish", False):
        return
    page._privacygate_readability_finish = True

    _refresh_readability(page)
    QTimer.singleShot(0, lambda: _refresh_readability(page))

    # Scan repopulates the table/status widgets. The local QSS persists for new
    # items; refresh once more after the click to cover any compatibility restyle.
    scan = getattr(page, "scan_button", None)
    if scan is not None:
        scan.clicked.connect(
            lambda _checked=False: QTimer.singleShot(
                0, lambda: _refresh_readability(page)
            )
        )
