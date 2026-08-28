from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon


BLUE = "#2563EB"
BLUE_SOFT = "#EEF4FF"
INK = "#111827"
MUTED = "#667085"
BORDER = "#E4E7EC"
SIDEBAR_BG = "#FBFCFE"
WHITE = "#FFFFFF"
SUCCESS = "#16A34A"

_NAV_STYLE = f"""
QPushButton#RedesignNavButton {{
    background: transparent;
    color: {INK};
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    font-size: 10px;
    font-weight: 650;
    min-height: 24px;
}}
QPushButton#RedesignNavButton:hover {{ background: #F2F4F7; }}
QPushButton#RedesignNavButton:checked {{
    background: {BLUE_SOFT};
    color: {BLUE};
    font-weight: 800;
}}
"""

_SUBNAV_STYLE = f"""
QPushButton#RedesignSubNavButton {{
    background: transparent;
    color: #475467;
    border: none;
    border-radius: 8px;
    padding: 7px 10px 7px 38px;
    text-align: left;
    font-size: 9px;
    font-weight: 650;
}}
QPushButton#RedesignSubNavButton:hover {{ background: #F5F7FA; color: {INK}; }}
QPushButton#RedesignSubNavButton:checked {{
    background: {BLUE_SOFT};
    color: {BLUE};
    font-weight: 800;
}}
"""


def _page_index(main_window, attribute: str) -> int:
    page = getattr(main_window, attribute, None)
    pages = getattr(main_window, "pages", None)
    if page is None or pages is None:
        return -1
    return int(pages.indexOf(page))


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


class _RedesignSidebarController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.team_page = getattr(main_window, "team_page", None)
        self._buttons: list[QPushButton] = []
        self._page_buttons: dict[int, QPushButton] = {}

        self.widget = QFrame(objectName="RedesignSidebar")
        self.widget.setFixedWidth(286)
        self.widget.setStyleSheet(
            f"QFrame#RedesignSidebar{{background:{SIDEBAR_BG};"
            f"border:none;border-right:1px solid {BORDER};}}"
        )

        root = QVBoxLayout(self.widget)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.workspace_menu = QMenu(self.widget)
        self.workspace_menu.aboutToShow.connect(self._rebuild_workspace_menu)

        self.workspace_button = QPushButton(objectName="RedesignWorkspaceButton")
        self.workspace_button.setMenu(self.workspace_menu)
        self.workspace_button.setIcon(icon("protect", color=BLUE, size=20))
        self.workspace_button.setIconSize(QSize(20, 20))
        self.workspace_button.setMinimumHeight(58)
        self.workspace_button.setStyleSheet(
            f"QPushButton#RedesignWorkspaceButton{{background:{WHITE};color:{INK};"
            f"border:1px solid {BORDER};border-radius:11px;padding:8px 11px;"
            "text-align:left;font-size:10px;font-weight:800;}"
            "QPushButton#RedesignWorkspaceButton:hover{background:#F8FAFC;border-color:#CBD5E1;}"
            "QPushButton#RedesignWorkspaceButton::menu-indicator{subcontrol-position:right center;"
            "subcontrol-origin:padding;right:10px;}"
        )
        root.addWidget(self.workspace_button)

        self.context_note = QLabel()
        self.context_note.setWordWrap(True)
        self.context_note.setStyleSheet(
            f"color:{MUTED};font-size:8px;padding:0 4px;background:transparent;border:none;"
        )
        root.addWidget(self.context_note)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:6px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#D0D5DD;border-radius:3px;min-height:26px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        self.nav_host = QWidget()
        self.nav_host.setStyleSheet("background:transparent;")
        self.nav_layout = QVBoxLayout(self.nav_host)
        self.nav_layout.setContentsMargins(0, 4, 0, 4)
        self.nav_layout.setSpacing(3)
        self.scroll.setWidget(self.nav_host)
        root.addWidget(self.scroll, 1)

        self.account_button = QPushButton(objectName="RedesignAccountButton")
        self.account_button.setMinimumHeight(54)
        self.account_button.setStyleSheet(
            f"QPushButton#RedesignAccountButton{{background:{WHITE};color:{INK};"
            f"border:1px solid {BORDER};border-radius:11px;padding:8px 11px;"
            "text-align:left;font-size:9px;font-weight:750;}"
            "QPushButton#RedesignAccountButton:hover{background:#F8FAFC;border-color:#CBD5E1;}"
        )
        self.account_button.clicked.connect(self._open_account_menu)
        root.addWidget(self.account_button)

        status = QFrame(objectName="RedesignStatusCard")
        status.setStyleSheet(
            f"QFrame#RedesignStatusCard{{background:{WHITE};border:1px solid {BORDER};"
            "border-radius:11px;}"
        )
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(10, 8, 10, 8)
        status_row.setSpacing(8)
        shield = QLabel()
        shield.setPixmap(icon("check", color=SUCCESS, size=17).pixmap(17, 17))
        status_row.addWidget(shield, 0, Qt.AlignmentFlag.AlignTop)
        status_text = QLabel(
            "Local-first protection\nDocuments and restore mappings stay on this device"
        )
        status_text.setWordWrap(True)
        status_text.setStyleSheet(
            f"color:{MUTED};font-size:7.5px;background:transparent;border:none;"
        )
        status_row.addWidget(status_text, 1)
        root.addWidget(status)

        self._connect_runtime()
        self.rebuild()

    def _connect_runtime(self) -> None:
        pages = getattr(self.main_window, "pages", None)
        if pages is not None:
            pages.currentChanged.connect(lambda _index: self._sync_checked_state())

        old_combo = getattr(self.main_window, "workspace_sidebar_combo", None)
        if old_combo is not None:
            old_combo.currentIndexChanged.connect(
                lambda _index: QTimer.singleShot(0, self.rebuild)
            )

        if self.team_page is not None:
            state_changed = getattr(self.team_page, "state_changed", None)
            if state_changed is not None:
                state_changed.connect(lambda _state: QTimer.singleShot(0, self.rebuild))

    def _workspace_context(self):
        store = getattr(self.team_page, "_privacygate_workspace_store", None)
        if store is None:
            return None
        try:
            return store.load()
        except Exception:
            return None

    def _active_descriptor(self):
        context = self._workspace_context()
        if context is None:
            return None
        return context.workspaces.get(context.active_key)

    def _is_organization(self) -> bool:
        descriptor = self._active_descriptor()
        return bool(descriptor is not None and not descriptor.personal)

    def _rebuild_workspace_menu(self) -> None:
        self.workspace_menu.clear()
        context = self._workspace_context()
        if context is None:
            action = self.workspace_menu.addAction("Personal")
            action.setEnabled(False)
            return

        for key, descriptor in context.workspaces.items():
            label = "Personal" if descriptor.personal else descriptor.name
            detail = descriptor.plan.label
            if descriptor.role:
                detail += f" · {descriptor.role.title()}"
            action = self.workspace_menu.addAction(f"{label}    {detail}")
            action.setCheckable(True)
            action.setChecked(key == context.active_key)
            action.triggered.connect(
                lambda _checked=False, workspace_key=key: self._select_workspace(workspace_key)
            )

    def _select_workspace(self, key: str) -> None:
        old_combo = getattr(self.main_window, "workspace_sidebar_combo", None)
        if old_combo is not None:
            index = old_combo.findData(key)
            if index >= 0:
                old_combo.setCurrentIndex(index)
                QTimer.singleShot(0, self.rebuild)
                return

        store = getattr(self.team_page, "_privacygate_workspace_store", None)
        if store is None:
            return
        try:
            store.set_active(key)
        except Exception:
            return
        refresher = getattr(self.team_page, "refresh_silent", None)
        if callable(refresher):
            refresher()
        QTimer.singleShot(0, self.rebuild)

    def _open_page(self, attribute: str) -> None:
        index = _page_index(self.main_window, attribute)
        if index >= 0:
            self.main_window._show_page(index)
            QTimer.singleShot(0, self._sync_checked_state)

    def _open_activity(self) -> None:
        controller = getattr(self.main_window, "privacygate_feature_suite", None)
        if controller is None:
            self._open_page("settings_page")
            return
        try:
            from ai_pm_lab_privacy_gate.domain.plans import Capability
            from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import ActivityDialog

            controller.open_feature(
                Capability.ACTIVITY_CENTER,
                "Activity Center",
                ActivityDialog,
            )
        except Exception:
            self._open_page("settings_page")

    def _open_org_tab(self, visual_index: int) -> None:
        if self.team_page is None:
            return
        self._open_page("team_page")
        dashboard = getattr(self.team_page, "_privacygate_premium_dashboard", None)
        selector = getattr(dashboard, "_select_tab", None) if dashboard is not None else None
        if callable(selector):
            selector(visual_index)
        QTimer.singleShot(0, self._sync_checked_state)

    def _open_account_menu(self) -> None:
        controller = getattr(self.main_window, "_privacygate_account_menu_controller", None)
        button = getattr(controller, "button", None) if controller is not None else None
        if button is not None:
            button.click()
            return
        self._open_page("settings_page")

    def _section_label(self, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet(
            "color:#98A2B3;font-size:7px;font-weight:900;letter-spacing:1px;"
            "padding:10px 10px 4px;background:transparent;border:none;"
        )
        self.nav_layout.addWidget(label)

    def _divider(self) -> None:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{BORDER};border:none;margin:7px 8px;")
        self.nav_layout.addWidget(line)

    def _nav_button(
        self,
        label: str,
        icon_name: str,
        callback,
        *,
        page_attribute: str | None = None,
        subnav: bool = False,
    ) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("RedesignSubNavButton" if subnav else "RedesignNavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(icon(icon_name, color="#475467", size=18 if not subnav else 15))
        button.setIconSize(QSize(18 if not subnav else 15, 18 if not subnav else 15))
        button.setStyleSheet(_SUBNAV_STYLE if subnav else _NAV_STYLE)
        button.clicked.connect(lambda _checked=False: callback())
        self.nav_layout.addWidget(button)
        self._buttons.append(button)
        if page_attribute:
            index = _page_index(self.main_window, page_attribute)
            if index >= 0:
                self._page_buttons[index] = button
        return button

    def _collapsible_group(
        self,
        title: str,
        icon_name: str,
        children: list[tuple[str, str, object]],
    ) -> None:
        group_button = QPushButton(f"{title}   ▾")
        group_button.setObjectName("RedesignNavButton")
        group_button.setCheckable(True)
        group_button.setCursor(Qt.CursorShape.PointingHandCursor)
        group_button.setIcon(icon(icon_name, color="#475467", size=18))
        group_button.setIconSize(QSize(18, 18))
        group_button.setStyleSheet(_NAV_STYLE)

        frame = QFrame()
        frame.setStyleSheet("background:transparent;border:none;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        frame.setVisible(False)

        for label, child_icon, callback in children:
            button = QPushButton(label)
            button.setObjectName("RedesignSubNavButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(icon(child_icon, color="#667085", size=15))
            button.setIconSize(QSize(15, 15))
            button.setStyleSheet(_SUBNAV_STYLE)
            button.clicked.connect(lambda _checked=False, cb=callback: cb())
            layout.addWidget(button)
            self._buttons.append(button)

        def toggle(checked: bool) -> None:
            frame.setVisible(checked)
            group_button.setText(f"{title}   {'⌃' if checked else '▾'}")

        group_button.toggled.connect(toggle)
        self.nav_layout.addWidget(group_button)
        self.nav_layout.addWidget(frame)
        self._buttons.append(group_button)

    def _update_workspace_copy(self) -> None:
        descriptor = self._active_descriptor()
        if descriptor is None or descriptor.personal:
            self.workspace_button.setText("PrivacyGate Personal\nPersonal workspace")
            self.context_note.setText("Your private local-first workspace.")
        else:
            self.workspace_button.setText(
                f"{descriptor.name}\n{descriptor.plan.label} organization"
            )
            role = descriptor.role.title() if descriptor.role else "Member"
            self.context_note.setText(
                f"Organization workspace · {role} · company policy active"
            )

    def _update_account_copy(self) -> None:
        controller = getattr(self.main_window, "_privacygate_account_menu_controller", None)
        if controller is None:
            self.account_button.setText("Account\nOpen account & settings")
            return
        try:
            name = controller._display_name()
            plan = controller._plan_line()
            self.account_button.setText(f"Account\n{name} · {plan}")
        except Exception:
            self.account_button.setText("Account\nOpen account & settings")

    def rebuild(self) -> None:
        _clear_layout(self.nav_layout)
        self._buttons.clear()
        self._page_buttons.clear()
        self._update_workspace_copy()
        self._update_account_copy()

        if self._is_organization():
            self._nav_button(
                "Overview",
                "document",
                lambda: self._open_org_tab(0),
                page_attribute="team_page",
            )
            self._section_label("WORKSPACE")

        self._nav_button(
            "Protect",
            "protect",
            lambda: self._open_page("protection_page"),
            page_attribute="protection_page",
        )
        self._nav_button(
            "Restore",
            "restore",
            lambda: self._open_page("restore_page"),
            page_attribute="restore_page",
        )
        self._nav_button(
            "Library",
            "library",
            lambda: self._open_page("library_page"),
            page_attribute="library_page",
        )
        self._nav_button(
            "Connections",
            "workflow",
            lambda: self._open_page("local_automation_page"),
            page_attribute="local_automation_page",
        )
        self._nav_button(
            "AI",
            "workflow",
            lambda: self._open_page("cloud_automation_page"),
            page_attribute="cloud_automation_page",
        )
        if getattr(self.main_window, "apps_hub_page", None) is not None:
            self._nav_button(
                "Apps",
                "cloud",
                lambda: self._open_page("apps_hub_page"),
                page_attribute="apps_hub_page",
            )
        self._nav_button("Activity", "history", self._open_activity)

        if self._is_organization():
            self._divider()
            self._section_label("ORGANIZATION")
            self._nav_button("AI & Apps", "workflow", lambda: self._open_org_tab(3))
            self._collapsible_group(
                "Governance",
                "protect",
                [
                    ("Policy Center", "protect", lambda: self._open_org_tab(2)),
                    ("Devices", "document", lambda: self._open_org_tab(4)),
                ],
            )
            self._collapsible_group(
                "Team",
                "contact",
                [("Members & roles", "contact", lambda: self._open_org_tab(1))],
            )
            self._nav_button(
                "Settings",
                "settings",
                lambda: self._open_page("settings_page"),
                page_attribute="settings_page",
            )
        else:
            self._divider()
            self._nav_button(
                "Settings",
                "settings",
                lambda: self._open_page("settings_page"),
                page_attribute="settings_page",
            )
            if getattr(self.main_window, "contact_page", None) is not None:
                self._nav_button(
                    "Workflows",
                    "contact",
                    lambda: self._open_page("contact_page"),
                    page_attribute="contact_page",
                )

        self.nav_layout.addStretch(1)
        self._sync_checked_state()

    def _sync_checked_state(self) -> None:
        pages = getattr(self.main_window, "pages", None)
        current = int(pages.currentIndex()) if pages is not None else -1
        for button in self._buttons:
            if button.isCheckable():
                button.setChecked(False)
        button = self._page_buttons.get(current)
        if button is not None:
            button.setChecked(True)


def apply_mockup_redesign_shell_2026(main_window) -> None:
    """Install the new visual shell without moving PrivacyGate business logic."""

    if bool(getattr(main_window, "_privacygate_mockup_redesign_shell_2026", False)):
        return
    main_window._privacygate_mockup_redesign_shell_2026 = True

    old_sidebar = getattr(main_window, "sidebar", None)
    if old_sidebar is not None:
        old_sidebar.hide()

    footer = main_window.findChild(QLabel, "ProductFooter")
    if footer is not None:
        footer.hide()

    try:
        main_window.statusBar().hide()
    except Exception:
        pass

    shell = main_window.centralWidget().layout()
    if shell is None or not hasattr(shell, "insertWidget"):
        return

    controller = _RedesignSidebarController(main_window)
    shell.insertWidget(0, controller.widget)
    main_window._privacygate_redesign_sidebar_controller = controller
