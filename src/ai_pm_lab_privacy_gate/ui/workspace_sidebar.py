from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout


class _WorkspaceCombo(QComboBox):
    """Compact sidebar switcher with clean display labels and rich tooltips."""


def apply_workspace_sidebar(main_window) -> None:
    if getattr(main_window, "_privacygate_workspace_sidebar", False):
        return
    page = getattr(main_window, "team_page", None)
    if page is None or not hasattr(page, "_privacygate_workspace_store"):
        return
    main_window._privacygate_workspace_sidebar = True

    card = QFrame(objectName="WorkspaceSwitcherCard")
    card.setMinimumHeight(68)
    card.setStyleSheet(
        "QFrame#WorkspaceSwitcherCard{background:#0A4D67;border:1px solid #16758A;"
        "border-radius:11px;}"
    )
    outer = QHBoxLayout(card)
    outer.setContentsMargins(10, 9, 8, 9)
    outer.setSpacing(9)

    building = QLabel("▥")
    building.setAlignment(Qt.AlignmentFlag.AlignCenter)
    building.setFixedSize(28, 28)
    building.setStyleSheet(
        "background:#EAF7F7;color:#0B7180;border:none;border-radius:8px;"
        "font-size:17px;font-weight:900;"
    )
    outer.addWidget(building, 0, Qt.AlignmentFlag.AlignVCenter)

    text_box = QVBoxLayout()
    text_box.setContentsMargins(0, 0, 0, 0)
    text_box.setSpacing(1)
    title = QLabel("ACTIVE WORKSPACE")
    title.setStyleSheet(
        "color:#A9D9DE;font-size:7px;font-weight:900;letter-spacing:1px;"
        "border:none;background:transparent;"
    )
    combo = _WorkspaceCombo()
    combo.setMinimumHeight(32)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(12)
    combo.setStyleSheet(
        "QComboBox{background:transparent;color:#FFFFFF;border:none;padding:2px 22px 2px 0;"
        "font-size:10px;font-weight:900;}"
        "QComboBox::drop-down{border:none;width:20px;}"
        "QComboBox::down-arrow{width:9px;height:9px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;"
        "selection-background-color:#EAF7F7;selection-color:#062B4F;padding:5px;outline:0;}"
    )
    text_box.addWidget(title)
    text_box.addWidget(combo)
    outer.addLayout(text_box, 1)

    main_window.side_layout.insertWidget(3, card)
    main_window.workspace_sidebar_combo = combo
    main_window.workspace_sidebar_card = card

    def rebuild(*_args) -> None:
        context = page._privacygate_workspace_store.load()
        combo.blockSignals(True)
        combo.clear()
        for key, descriptor in context.workspaces.items():
            if descriptor.personal:
                display = "Personal"
                detail = f"Personal • {descriptor.plan.label} • You"
            else:
                display = descriptor.name
                detail = f"{descriptor.name} • {descriptor.plan.label} • {descriptor.role.title()}"
            combo.addItem(display, key)
            combo.setItemData(combo.count() - 1, detail, Qt.ItemDataRole.ToolTipRole)
        index = combo.findData(context.active_key)
        combo.setCurrentIndex(max(0, index))
        current = context.workspaces.get(context.active_key)
        if current is not None:
            title.setText(
                "PERSONAL WORKSPACE" if current.personal else current.plan.label.upper()
            )
            combo.setToolTip(
                f"{current.name} • {current.plan.label}"
                + (f" • {current.role.title()}" if current.role else "")
            )
        combo.blockSignals(False)

    def changed(_index: int) -> None:
        key = str(combo.currentData() or "")
        if not key:
            return
        selector = getattr(page, "workspace_selector", None)
        if selector is not None:
            index = selector.findData(key)
            if index >= 0:
                selector.setCurrentIndex(index)
                return
        try:
            page._privacygate_workspace_store.set_active(key)
        except KeyError:
            return
        page.refresh_silent()

    combo.currentIndexChanged.connect(changed)
    page.state_changed.connect(rebuild)
    rebuild()
