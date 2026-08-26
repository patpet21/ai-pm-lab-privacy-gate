from __future__ import annotations

from PySide6.QtCore import QPoint, QThreadPool, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ai_pm_lab_privacy_gate.infrastructure.auth.account_profile import (
    AccountProfile,
    AccountProfileClient,
)
from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import SupabaseAccountClient
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.ui.resources import resource_path
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#8EA6B8"
WHITE = "#FFFFFF"


class AccountMenuController:
    """Professional account card anchored at the bottom of the PrivacyGate sidebar."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.team_page = getattr(main_window, "team_page", None)
        identity_store = getattr(main_window, "connection_identity")
        self.account_client = (
            getattr(self.team_page, "account_client", None)
            or SupabaseAccountClient(identity_store)
        )
        self.profile_client = AccountProfileClient(self.account_client)
        self.thread_pool = QThreadPool.globalInstance()
        self.profile: AccountProfile | None = None
        self.email = self.account_client.current_email or ""
        self.state = getattr(self.team_page, "state", TeamState())
        self._profile_worker: FunctionWorker | None = None
        self._prompted_for_name = False
        self._build_button()
        self._connect_state()
        self._render()
        QTimer.singleShot(1100, self.refresh_profile)

    def _build_button(self) -> None:
        self.button = QPushButton(objectName="AccountMenuButton")
        self.button.setToolTip("Your Account")
        self.button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.button.setMinimumHeight(58)
        icon_path = resource_path("resources", "branding", "nav-account.svg")
        if icon_path.exists():
            self.button.setIcon(QIcon(str(icon_path)))
        self.button.setStyleSheet(
            "QPushButton#AccountMenuButton{"
            "background:#FFFFFF;color:#062B4F;border:1px solid #D7E2E8;"
            "border-radius:11px;text-align:left;padding:8px 11px;font-weight:800;}"
            "QPushButton#AccountMenuButton:hover{background:#F2FAFA;border-color:#86C5CA;}"
        )
        self.button.clicked.connect(self._show_menu)

        layout = self.main_window.side_layout
        privacy_note = getattr(self.main_window, "privacy_note", None)
        target = layout.indexOf(privacy_note) if privacy_note is not None else layout.count()
        layout.insertWidget(max(0, target), self.button)

        original_set_sidebar = self.main_window._set_sidebar_expanded

        def set_sidebar_expanded(expanded: bool) -> None:
            original_set_sidebar(expanded)
            self._render()

        self.main_window._set_sidebar_expanded = set_sidebar_expanded

    def _connect_state(self) -> None:
        if self.team_page is None:
            return
        signal = getattr(self.team_page, "state_changed", None)
        if signal is not None:
            signal.connect(self._state_changed)

    def _state_changed(self, state: TeamState) -> None:
        self.state = state
        self._render()

    def _display_name(self) -> str:
        if self.profile and self.profile.display_name:
            return self.profile.display_name
        return "Your Account"

    def _plan_line(self) -> str:
        plan = self.state.plan.label
        if self.state.organization_id and self.state.role:
            return f"{plan} • {self.state.role.title()}"
        return plan

    def _render(self) -> None:
        expanded = bool(getattr(self.main_window, "sidebar_expanded", True))
        if expanded:
            self.button.setText(f"  {self._display_name()}\n  {self._plan_line()}")
            self.button.setToolTip(
                f"{self._display_name()} — {self._plan_line()}"
                + (f"\n{self.email}" if self.email else "")
            )
            self.button.setMinimumHeight(58)
        else:
            self.button.setText("")
            self.button.setToolTip(
                f"Your Account\n{self._display_name()}\n{self._plan_line()}"
            )
            self.button.setMinimumHeight(46)

    def refresh_profile(self) -> None:
        if self._profile_worker is not None:
            return

        def task():
            session = self.account_client.restore_session()
            if session is None:
                return None
            return session, self.profile_client.fetch(session)

        worker = FunctionWorker(task)
        self._profile_worker = worker
        worker.signals.result.connect(self._profile_ready)
        worker.signals.finished.connect(self._profile_finished)
        self.thread_pool.start(worker)

    def _profile_finished(self) -> None:
        self._profile_worker = None

    def _profile_ready(self, payload: object) -> None:
        if payload is None:
            self.email = ""
            self.profile = None
            self._render()
            return
        session, profile = payload
        self.email = session.email
        self.profile = profile
        self._render()
        if profile is not None and not profile.display_name and not self._prompted_for_name:
            self._prompted_for_name = True
            QTimer.singleShot(250, self._prompt_for_display_name)

    def _prompt_for_display_name(self) -> None:
        name, ok = QInputDialog.getText(
            self.main_window,
            "Complete your PrivacyGate account",
            "Name or professional display name:\n\n"
            "PrivacyGate stores only this name with your account so your plan and devices "
            "are easier to identify. Your documents and connector data remain local.",
        )
        if not ok or not name.strip():
            return
        self._save_display_name(name)

    def _edit_display_name(self) -> None:
        current = self.profile.display_name if self.profile else ""
        name, ok = QInputDialog.getText(
            self.main_window,
            "Account display name",
            "Name or professional display name:",
            text=current,
        )
        if ok and name.strip() and name.strip() != current:
            self._save_display_name(name)

    def _save_display_name(self, name: str) -> None:
        if self._profile_worker is not None:
            return

        def task():
            session = self.account_client.restore_session()
            if session is None:
                raise RuntimeError("Sign in to your PrivacyGate account first.")
            return session, self.profile_client.update_display_name(session, name)

        worker = FunctionWorker(task)
        self._profile_worker = worker
        worker.signals.result.connect(self._profile_ready)
        worker.signals.error.connect(
            lambda message: QMessageBox.warning(
                self.main_window,
                "Account update unavailable",
                message,
            )
        )
        worker.signals.finished.connect(self._profile_finished)
        self.thread_pool.start(worker)

    def _header_action(self, menu: QMenu) -> QWidgetAction:
        action = QWidgetAction(menu)
        panel = QFrame()
        panel.setMinimumWidth(290)
        panel.setStyleSheet("QFrame{background:#F7FAFC;border:none;border-radius:8px;}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)
        name = QLabel(self._display_name())
        name.setStyleSheet(f"color:{NAVY};font-size:14px;font-weight:900;")
        email = QLabel(self.email or "Not signed in")
        email.setStyleSheet("color:#61798A;font-size:9px;")
        plan = QLabel(self._plan_line().upper())
        plan.setStyleSheet(f"color:{TEAL};font-size:9px;font-weight:900;")
        layout.addWidget(name)
        layout.addWidget(email)
        layout.addWidget(plan)
        if self.state.organization_name:
            org = QLabel(self.state.organization_name)
            org.setStyleSheet("color:#61798A;font-size:9px;")
            layout.addWidget(org)
        action.setDefaultWidget(panel)
        return action

    def _show_menu(self) -> None:
        menu = QMenu(self.main_window)
        menu.setStyleSheet(
            "QMenu{background:#FFFFFF;color:#062B4F;border:1px solid #D7E2E8;"
            "border-radius:10px;padding:7px;}"
            "QMenu::item{padding:9px 24px 9px 12px;border-radius:6px;}"
            "QMenu::item:selected{background:#EAF6F6;color:#062B4F;}"
            "QMenu::separator{height:1px;background:#E2E9ED;margin:6px 4px;}"
        )
        menu.addAction(self._header_action(menu))
        menu.addSeparator()

        plan_action = menu.addAction("Plan & Account")
        apps_action = menu.addAction("Connected Apps")
        settings_action = menu.addAction("Settings")
        organization_action = None
        if self.state.organization_id:
            organization_action = menu.addAction("Organization")
        edit_name_action = menu.addAction("Edit display name")
        menu.addSeparator()
        sign_out_action = menu.addAction("Sign out")

        chosen = menu.exec(
            self.button.mapToGlobal(QPoint(0, -max(10, menu.sizeHint().height())))
        )
        if chosen is plan_action or chosen is settings_action:
            self._open_settings()
        elif chosen is apps_action:
            self._open_apps()
        elif organization_action is not None and chosen is organization_action:
            self._open_organization()
        elif chosen is edit_name_action:
            self._edit_display_name()
        elif chosen is sign_out_action:
            self._sign_out()

    def _open_settings(self) -> None:
        page = getattr(self.main_window, "settings_page", None)
        if page is not None:
            self.main_window._show_page(self.main_window.pages.indexOf(page))

    def _open_apps(self) -> None:
        index = getattr(self.main_window, "apps_page_index", None)
        if index is not None:
            self.main_window._show_page(index)

    def _open_organization(self) -> None:
        page = getattr(self.main_window, "team_page", None)
        if page is not None:
            self.main_window._show_page(self.main_window.pages.indexOf(page))

    def _sign_out(self) -> None:
        answer = QMessageBox.question(
            self.main_window,
            "Sign out of PrivacyGate?",
            "Sign out of this PrivacyGate account? Your local Library and documents will not be deleted.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.account_client.sign_out()
        self.email = ""
        self.profile = None
        self._render()
        QMessageBox.information(
            self.main_window,
            "Signed out",
            "You are signed out. Local PrivacyGate data remains on this device.",
        )


def apply_account_menu(main_window) -> AccountMenuController | None:
    if getattr(main_window, "_privacygate_account_menu_controller", None) is not None:
        return main_window._privacygate_account_menu_controller
    if not hasattr(main_window, "side_layout"):
        return None
    controller = AccountMenuController(main_window)
    main_window._privacygate_account_menu_controller = controller
    return controller
