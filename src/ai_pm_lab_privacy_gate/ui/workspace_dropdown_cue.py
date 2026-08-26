from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget


class _WorkspaceDropCue(QLabel):
    def __init__(self, combo, parent=None) -> None:
        super().__init__("⌄", parent)
        self.combo = combo
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Switch workspace")
        self.setStyleSheet(
            "QLabel{background:#E9F7F7;color:#0B7180;border:1px solid #BEE3E4;"
            "border-radius:9px;font-size:18px;font-weight:900;padding-bottom:4px;}"
            "QLabel:hover{background:#DDF3F3;border-color:#90CBCD;}"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.combo.showPopup()
            event.accept()
            return
        super().mousePressEvent(event)


def _find_layout(layout: QLayout, target: QWidget) -> QLayout | None:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is target:
            return layout
        child = item.layout()
        if child is not None:
            found = _find_layout(child, target)
            if found is not None:
                return found
    return None


def apply_workspace_dropdown_cue(main_window) -> None:
    """Make the active-workspace selector visibly look interactive.

    The workspace logic stays untouched; this only adds a compact, clickable
    chevron directly beside the selected workspace name.
    """
    if bool(getattr(main_window, "_privacygate_workspace_dropdown_cue", False)):
        return
    combo = getattr(main_window, "workspace_sidebar_combo", None)
    card = getattr(main_window, "workspace_sidebar_card", None)
    if combo is None or card is None or card.layout() is None:
        return

    containing = _find_layout(card.layout(), combo)
    if containing is None:
        return

    try:
        containing.removeWidget(combo)
    except RuntimeError:
        return

    holder = QWidget(card)
    holder.setObjectName("WorkspaceSelectorWithCue")
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addWidget(combo, 1)
    cue = _WorkspaceDropCue(combo, holder)
    row.addWidget(cue, 0, Qt.AlignmentFlag.AlignVCenter)

    if isinstance(containing, QVBoxLayout):
        containing.addWidget(holder)
    else:
        containing.addWidget(holder)

    combo.setToolTip("Choose where PrivacyGate is working")
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    combo.setStyleSheet(
        combo.styleSheet()
        + "QComboBox{padding-right:6px;}QComboBox:hover{color:#FFFFFF;}"
    )
    main_window.workspace_dropdown_cue = cue
    main_window._privacygate_workspace_dropdown_cue = True
