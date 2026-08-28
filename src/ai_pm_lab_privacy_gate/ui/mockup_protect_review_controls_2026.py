from __future__ import annotations

"""Guaranteed placement for manual-rule controls in the compact Review summary."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton

from .mockup_protect_review_experience_2026 import (
    _edit_selected_rule,
    _remove_selected_rule,
)


def _button(text: str, *, danger: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(30)
    button.setEnabled(False)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if danger:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#B42318;border:1px solid #FECDCA;"
            "border-radius:8px;padding:5px 8px;font-size:7px;font-weight:850;}"
            "QPushButton:hover{background:#FEF3F2;}"
            "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:8px;padding:5px 8px;font-size:7px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;}"
            "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
        )
    return button


def apply_mockup_protect_review_controls_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_review_controls", False)):
        return
    page._protect_2026_review_controls = True

    # The main review layer first tries to place these beside Add missed value. If
    # the legacy nested layout prevents that, place them in the new summary bar.
    if getattr(page, "_protect_edit_manual", None) is not None:
        return
    summary = getattr(page, "_protect_review_summary", None)
    layout = summary.layout() if summary is not None else None
    if not isinstance(layout, QHBoxLayout):
        return

    edit = _button("Edit rule")
    remove = _button("Remove rule", danger=True)
    edit.setToolTip("Edit the selected manual local rule and regenerate the safe copy.")
    remove.setToolTip("Remove the selected manual local rule and regenerate the safe copy.")

    # Insert before the stretch/risk badge so rule management stays with Review.
    insert_at = max(0, layout.count() - 2)
    layout.insertWidget(insert_at, edit)
    layout.insertWidget(insert_at + 1, remove)
    edit.clicked.connect(lambda _checked=False: _edit_selected_rule(page))
    remove.clicked.connect(lambda _checked=False: _remove_selected_rule(page))
    page._protect_edit_manual = edit
    page._protect_remove_manual = remove
