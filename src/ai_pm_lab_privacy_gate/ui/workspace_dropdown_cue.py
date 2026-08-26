from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
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


def _force_readable_combo(combo) -> None:
    """Keep the selected workspace readable on Windows native Qt styles."""
    combo.setMinimumHeight(32)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    combo.setToolTip("Choose where PrivacyGate is working")
    combo.setStyleSheet(
        "QComboBox{background:#0A5066;color:#FFFFFF;border:1px solid #2A8392;"
        "border-radius:8px;padding:5px 8px;font-size:11px;font-weight:900;}"
        "QComboBox:hover{background:#0C5B70;border-color:#55A8B2;color:#FFFFFF;}"
        "QComboBox:focus{border-color:#77C7CC;}"
        "QComboBox::drop-down{border:none;width:0px;}"
        "QComboBox::down-arrow{image:none;width:0px;height:0px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;"
        "border-radius:8px;selection-background-color:#EAF7F7;selection-color:#062B4F;"
        "padding:6px;outline:0;font-size:10px;}"
    )
    palette = combo.palette()
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#0A5066"))
    combo.setPalette(palette)


def apply_workspace_dropdown_cue(main_window) -> None:
    """Make the active-workspace selector visibly look interactive and readable."""
    if bool(getattr(main_window, "_privacygate_workspace_dropdown_cue", False)):
        combo = getattr(main_window, "workspace_sidebar_combo", None)
        if combo is not None:
            _force_readable_combo(combo)
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

    _force_readable_combo(combo)
    main_window.workspace_dropdown_cue = cue
    main_window._privacygate_workspace_dropdown_cue = True
