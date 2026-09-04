from __future__ import annotations

"""Compact the Protect guidance strip into the Document workspace header.

The four-step flow is guidance only.  This layer removes its dedicated full-width
card and reuses the same How it works action beside a compact step summary in the
Document workspace header.  No Protect behavior, callbacks or document widgets are
replaced.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QSizePolicy

from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    MUTED,
    TEXT,
)


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _document_title(page) -> QLabel | None:
    for label in page.preview_card.findChildren(QLabel):
        if " ".join(label.text().split()).lower() == "document workspace":
            return label
    return None


def _step(number: str, title: str) -> QFrame:
    host = QFrame()
    host.setStyleSheet("QFrame{background:transparent;border:none;}")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)

    badge = QLabel(number)
    badge.setFixedSize(16, 16)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #C7D7FE;"
        "border-radius:8px;font-size:6.3px;font-weight:950;"
    )
    row.addWidget(badge)

    label = QLabel(title)
    label.setStyleSheet(
        f"color:{TEXT};font-size:6.6px;font-weight:850;background:transparent;border:none;"
    )
    row.addWidget(label)
    return host


def _compact_flow(page) -> None:
    flow = getattr(page, "_protect_2026_flow", None)
    if flow is None:
        return

    title = _document_title(page)
    if title is None:
        return

    header_layout = None
    parent = title.parentWidget()
    while parent is not None and header_layout is None:
        header_layout = _find_layout(parent.layout(), title)
        parent = parent.parentWidget()
    if not isinstance(header_layout, QHBoxLayout):
        return

    existing = getattr(page, "_protect_2026_compact_steps", None)
    if existing is not None:
        flow.hide()
        flow.setMaximumHeight(0)
        return

    steps = QFrame(objectName="Protect2026CompactSteps")
    steps.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    steps.setMinimumWidth(330)
    steps.setMaximumWidth(380)
    steps.setStyleSheet(
        f"QFrame#Protect2026CompactSteps{{background:#F8FAFC;border:1px solid {BORDER};"
        "border-radius:9px;}"
    )
    row = QHBoxLayout(steps)
    row.setContentsMargins(5, 4, 5, 4)
    row.setSpacing(3)

    for index, (number, name) in enumerate(
        (("1", "Source"), ("2", "Scan"), ("3", "Review"), ("4", "Safe copy"))
    ):
        row.addWidget(_step(number, name))
        if index < 3:
            arrow = QLabel("›")
            arrow.setStyleSheet(
                f"color:{MUTED};font-size:11px;font-weight:800;background:transparent;border:none;"
            )
            row.addWidget(arrow)

    info = getattr(page, "_protect_info_document_workspace", None)
    title_index = header_layout.indexOf(title)
    insert_index = title_index + 1
    if info is not None and header_layout.indexOf(info) >= 0:
        insert_index = header_layout.indexOf(info) + 1
    header_layout.insertWidget(insert_index, steps, 0, Qt.AlignmentFlag.AlignVCenter)

    how = getattr(page, "_protect_2026_how_it_works", None)
    if how is not None:
        old_layout = flow.layout()
        if old_layout is not None:
            old_layout.removeWidget(how)
        how.setParent(page.preview_card)
        how.setMinimumHeight(30)
        how.setMaximumHeight(30)
        how.setMinimumWidth(112)
        how.setMaximumWidth(132)
        how.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:8px;padding:5px 6px;font-size:6.7px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        )
        header_layout.insertWidget(insert_index + 1, how, 0, Qt.AlignmentFlag.AlignVCenter)

    # Keep the existing real comparison action and color explanation on this same
    # header row, but make their vertical footprint match the compact guidance.
    focus = getattr(page, "focus_preview_button", None)
    if focus is not None:
        focus.setMinimumHeight(30)
        focus.setMaximumHeight(30)
        focus.setMinimumWidth(170)
        focus.setMaximumWidth(195)
        focus.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D0D5DD;"
            "border-radius:8px;padding:5px 6px;font-size:6.8px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;border-color:#9DB7F8;color:#1D4ED8;}"
        )

    for label in page.preview_card.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text in {"Protected values are color coded", "Color-coded by protected category"}:
            label.setMinimumHeight(30)
            label.setMaximumHeight(30)
            label.setMinimumWidth(220)
            label.setMaximumWidth(255)
            label.setStyleSheet(
                f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #C7D7FE;"
                "border-radius:8px;padding:5px 6px;font-size:6.3px;font-weight:800;"
            )

    flow.hide()
    flow.setMaximumHeight(0)
    page._protect_2026_compact_steps = steps


def apply_mockup_protect_compact_steps_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_compact_steps_applied", False)):
        return
    page._protect_2026_compact_steps_applied = True
    _compact_flow(page)
