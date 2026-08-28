from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_redesign_shell_2026 import _clear_layout, _page_index


BLUE = "#2563EB"
BLUE_DARK = "#1D4ED8"
BLUE_SOFT = "#EEF4FF"
INK = "#101828"
MUTED = "#667085"
BORDER = "#E4E7EC"
SURFACE = "#FFFFFF"
CANVAS = "#F8FAFC"
GREEN = "#16A34A"
RED = "#DC2626"


_PAGE_STYLE = f"""
QWidget {{
    color: {INK};
}}
QLabel#PageTitle {{
    color: {INK};
    font-size: 24pt;
    font-weight: 900;
}}
QLabel#SectionTitle {{
    color: {INK};
    font-size: 12pt;
    font-weight: 800;
}}
QLabel#Muted {{ color: {MUTED}; }}
QFrame#Card,
QFrame#ConnectionCard,
QFrame#SettingsPremiumCard,
QFrame#PremiumCard,
QFrame#CleanMembersCard,
QFrame#CleanDevicesCard,
QFrame#CleanPolicyRules,
QFrame#CleanPolicyDestinations {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QListWidget, QTableWidget {{
    background: {SURFACE};
    color: #344054;
    border: 1px solid #D0D5DD;
    border-radius: 9px;
    selection-background-color: #DDE8FF;
    selection-color: {INK};
}}
QLineEdit, QComboBox {{
    min-height: 28px;
    padding: 6px 9px;
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid #84ADFF;
}}
QPushButton {{
    border-radius: 9px;
    padding: 8px 13px;
    font-weight: 750;
}}
QPushButton#Primary {{
    background: {BLUE};
    color: white;
    border: 1px solid {BLUE};
}}
QPushButton#Primary:hover {{ background: {BLUE_DARK}; border-color: {BLUE_DARK}; }}
QPushButton#Secondary {{
    background: white;
    color: #344054;
    border: 1px solid #D0D5DD;
}}
QPushButton#Secondary:hover {{ background: #F9FAFB; border-color: #98A2B3; }}
QHeaderView::section {{
    background: #F9FAFB;
    color: #475467;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-size: 8.5pt;
    font-weight: 800;
}}
QTableWidget {{
    gridline-color: #EAECF0;
    alternate-background-color: #FCFCFD;
}}
QTableWidget::item {{ padding: 7px; }}
QTableWidget::item:selected {{ background: #EAF1FF; color: {INK}; }}
QTabBar::tab {{
    background: transparent;
    color: #475467;
    border: none;
    padding: 9px 13px;
    margin-right: 3px;
    font-weight: 700;
}}
QTabBar::tab:hover {{ color: {BLUE}; background: #F8FAFC; }}
QTabBar::tab:selected {{
    color: {BLUE};
    background: transparent;
    border-bottom: 2px solid {BLUE};
    font-weight: 850;
}}
QMenu {{ background: white; border: 1px solid {BORDER}; border-radius: 9px; padding: 5px; }}
QMenu::item {{ padding: 8px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {BLUE_SOFT}; color: {INK}; }}
"""


_DIALOG_STYLE = f"""
QDialog {{ background: {CANVAS}; color: {INK}; }}
QLabel {{ color: {INK}; background: transparent; border: none; }}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QListWidget, QTableWidget {{
    background: white;
    color: #344054;
    border: 1px solid #D0D5DD;
    border-radius: 9px;
}}
QHeaderView::section {{
    background: #F9FAFB;
    color: #475467;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-weight: 800;
}}
QPushButton {{ border-radius: 9px; padding: 8px 13px; font-weight: 750; }}
"""


def _open_governance(controller) -> None:
    if getattr(controller.main_window, "governance_page", None) is not None:
        controller._open_page("governance_page")
    else:
        controller._open_page("settings_page")


def _install_navigation_layout(controller) -> None:
    """Make Governance a universal workspace page and remove duplicate org governance."""

    def rebuild(self) -> None:
        _clear_layout(self.nav_layout)
        self._buttons.clear()
        self._page_buttons.clear()
        self._org_tab_buttons = {}
        self._update_workspace_copy()
        self._update_account_copy()

        if self._is_organization():
            overview = self._nav_button(
                "Overview", "document", lambda: self._open_org_tab(0)
            )
            self._org_tab_buttons[0] = overview
            self._section_label("WORKSPACE")

        self._nav_button(
            "Protect", "protect", lambda: self._open_page("protection_page"),
            page_attribute="protection_page",
        )
        self._nav_button(
            "Restore", "restore", lambda: self._open_page("restore_page"),
            page_attribute="restore_page",
        )
        self._nav_button(
            "Library", "library", lambda: self._open_page("library_page"),
            page_attribute="library_page",
        )
        self._nav_button(
            "Connections", "workflow", lambda: self._open_page("local_automation_page"),
            page_attribute="local_automation_page",
        )
        self._nav_button(
            "AI", "workflow", lambda: self._open_page("cloud_automation_page"),
            page_attribute="cloud_automation_page",
        )
        if getattr(self.main_window, "apps_hub_page", None) is not None:
            self._nav_button(
                "Apps", "cloud", lambda: self._open_page("apps_hub_page"),
                page_attribute="apps_hub_page",
            )
        self._nav_button("Activity", "history", self._open_activity)
        self._nav_button(
            "Governance",
            "protect",
            lambda: _open_governance(self),
            page_attribute="governance_page",
        )

        self._divider()

        if self._is_organization():
            self._section_label("ORGANIZATION")
            ai_apps = self._nav_button("AI & Apps", "workflow", lambda: self._open_org_tab(3))
            self._org_tab_buttons[3] = ai_apps
            policy = self._nav_button("Policy Center", "protect", lambda: self._open_org_tab(2))
            self._org_tab_buttons[2] = policy
            self._collapsible_group(
                "Team",
                "contact",
                [("Members & roles", "contact", lambda: self._open_org_tab(1))],
            )
            devices = self._nav_button("Devices", "document", lambda: self._open_org_tab(4))
            self._org_tab_buttons[4] = devices

        self._nav_button(
            "Settings", "settings", lambda: self._open_page("settings_page"),
            page_attribute="settings_page",
        )
        if not self._is_organization() and getattr(self.main_window, "contact_page", None) is not None:
            self._nav_button(
                "Workflows", "contact", lambda: self._open_page("contact_page"),
                page_attribute="contact_page",
            )

        self.nav_layout.addStretch(1)
        self._sync_checked_state()

    def sync_checked(self) -> None:
        pages = getattr(self.main_window, "pages", None)
        current = int(pages.currentIndex()) if pages is not None else -1
        for button in self._buttons:
            if button.isCheckable():
                button.setChecked(False)

        team_index = _page_index(self.main_window, "team_page")
        if current == team_index:
            dashboard = getattr(self.team_page, "_privacygate_premium_dashboard", None)
            stack = getattr(dashboard, "stack", None) if dashboard is not None else None
            stack_index = int(stack.currentIndex()) if stack is not None else 0
            visual = {0: 0, 1: 1, 2: 2, 4: 3, 3: 4}.get(stack_index, 0)
            button = getattr(self, "_org_tab_buttons", {}).get(visual)
            if button is not None:
                button.setChecked(True)
            return

        button = self._page_buttons.get(current)
        if button is not None:
            button.setChecked(True)

    controller.rebuild = MethodType(rebuild, controller)
    controller._sync_checked_state = MethodType(sync_checked, controller)

    dashboard = getattr(controller.team_page, "_privacygate_premium_dashboard", None)
    stack = getattr(dashboard, "stack", None) if dashboard is not None else None
    if stack is not None:
        stack.currentChanged.connect(lambda _index: QTimer.singleShot(0, controller._sync_checked_state))

    controller.rebuild()


def _hide_duplicate_organization_navigation(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    if dashboard is None:
        return

    # The redesigned sidebar is now the organization navigation. Hide the old
    # horizontal tab strip and the redundant Organization heading above the new
    # page-specific header, while leaving all underlying stack/controller logic alive.
    tabs = getattr(dashboard, "tabs_widget", None)
    if tabs is not None:
        tabs.hide()
        tabs.setMaximumHeight(0)
    line = getattr(dashboard, "tabs_line", None)
    if line is not None:
        line.hide()
        line.setMaximumHeight(0)

    root = dashboard.layout()
    if root is not None and root.count() > 0:
        header = root.itemAt(0).widget()
        if header is not None and header is not tabs:
            header.hide()
            header.setMaximumHeight(0)
        root.setContentsMargins(18, 12, 18, 14)
        root.setSpacing(10)


def _polish_page(page: QWidget | None) -> None:
    if page is None:
        return
    page.setStyleSheet(_PAGE_STYLE)

    for label in page.findChildren(QLabel):
        name = label.objectName()
        if name == "PageTitle":
            label.setStyleSheet(
                f"color:{INK};font-size:26px;font-weight:950;background:transparent;border:none;"
            )
        elif name == "SectionTitle":
            label.setStyleSheet(
                f"color:{INK};font-size:14px;font-weight:850;background:transparent;border:none;"
            )
        elif name == "Muted":
            label.setStyleSheet(
                f"color:{MUTED};font-size:9px;background:transparent;border:none;"
            )

    for table in page.findChildren(QTableWidget):
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        if header is not None:
            header.setHighlightSections(False)

    for combo in page.findChildren(QComboBox):
        combo.setMinimumHeight(max(34, combo.minimumHeight()))
    for field in page.findChildren(QLineEdit):
        field.setMinimumHeight(max(34, field.minimumHeight()))


def _install_activity_dialog_polish() -> None:
    try:
        from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import ActivityDialog
    except Exception:
        return

    if bool(getattr(ActivityDialog, "_mockup_global_visual_2026", False)):
        return
    original = ActivityDialog.__init__

    def init(self, *args, **kwargs) -> None:
        original(self, *args, **kwargs)
        self.setStyleSheet(_DIALOG_STYLE)
        hero = self.findChild(QFrame, "AdvancedFeatureHero")
        if hero is not None:
            hero.setStyleSheet(
                f"QFrame#AdvancedFeatureHero{{background:#FFFFFF;border:1px solid {BORDER};border-radius:14px;}}"
            )
            labels = hero.findChildren(QLabel)
            if labels:
                labels[0].setStyleSheet(
                    f"color:{INK};font-size:20px;font-weight:950;background:transparent;border:none;"
                )
            if len(labels) > 1:
                labels[1].setStyleSheet(
                    f"color:{MUTED};font-size:9px;background:transparent;border:none;"
                )
        for table in self.findChildren(QTableWidget):
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)

    ActivityDialog.__init__ = init
    ActivityDialog._mockup_global_visual_2026 = True


def apply_mockup_global_visual_system_2026(main_window) -> None:
    """Apply the mockup language broadly without changing page behavior."""

    if bool(getattr(main_window, "_privacygate_mockup_global_visual_system_2026", False)):
        return
    main_window._privacygate_mockup_global_visual_system_2026 = True

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is not None:
        _install_navigation_layout(controller)

    _hide_duplicate_organization_navigation(main_window)

    # Protect is deliberately excluded from this broad pass. Its document/pipeline
    # surface is handled separately after the lower-risk pages are visually stable.
    for attribute in (
        "library_page",
        "restore_page",
        "local_automation_page",
        "cloud_automation_page",
        "apps_hub_page",
        "governance_page",
        "settings_page",
        "contact_page",
        "team_page",
    ):
        _polish_page(getattr(main_window, attribute, None))

    _install_activity_dialog_polish()
