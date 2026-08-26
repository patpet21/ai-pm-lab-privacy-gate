from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QVBoxLayout


def apply_workspace_sidebar(main_window) -> None:
    if getattr(main_window, "_privacygate_workspace_sidebar", False):
        return
    page = getattr(main_window, "team_page", None)
    if page is None or not hasattr(page, "_privacygate_workspace_store"):
        return
    main_window._privacygate_workspace_sidebar = True

    card = QFrame()
    card.setObjectName("WorkspaceSwitcherCard")
    card.setStyleSheet(
        "QFrame#WorkspaceSwitcherCard{background:#0B5870;border:1px solid #16829A;"
        "border-radius:10px;}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(4)
    title = QLabel("WORKSPACE")
    title.setStyleSheet("color:#BFE7EA;font-size:8px;font-weight:900;")
    combo = QComboBox()
    combo.setStyleSheet(
        "QComboBox{background:#0B5870;color:#FFFFFF;border:none;padding:6px;"
        "font-weight:900;} QComboBox::drop-down{border:none;}"
    )
    layout.addWidget(title)
    layout.addWidget(combo)

    main_window.side_layout.insertWidget(3, card)
    main_window.workspace_sidebar_combo = combo

    def rebuild(*_args) -> None:
        context = page._privacygate_workspace_store.load()
        combo.blockSignals(True)
        combo.clear()
        for key, descriptor in context.workspaces.items():
            prefix = "Personal" if descriptor.personal else "Org"
            combo.addItem(
                f"{prefix}  •  {descriptor.name}  •  {descriptor.plan.label}",
                key,
            )
        index = combo.findData(context.active_key)
        combo.setCurrentIndex(max(0, index))
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
