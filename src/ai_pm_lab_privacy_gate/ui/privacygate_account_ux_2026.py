from __future__ import annotations

import json
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    AccountSession,
    SupabaseAccountClient,
)
from ai_pm_lab_privacy_gate.infrastructure.mcp.autostart import set_mcp_autostart
from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"


class PrivacyGateAccountDialog(QDialog):
    """One account surface shared by startup, Settings and Remote MCP."""

    def __init__(
        self,
        parent: QWidget,
        account_client: SupabaseAccountClient,
        *,
        context: str = "general",
        initial_mode: str = "choose",
    ) -> None:
        super().__init__(parent)
        self.account_client = account_client
        self.context = context
        self.session: AccountSession | None = None
        self.continued_without_account = False
        self.setObjectName("PrivacyGateAccountDialog")
        self.setWindowTitle("PrivacyGate Account")
        self.setModal(True)
        self.resize(610, 500)
        self.setMinimumWidth(560)
        self.setStyleSheet(
            "QDialog#PrivacyGateAccountDialog{background:#F7FAFC;}"
            "QLabel{background:transparent;border:none;}"
            "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
            "border-radius:10px;padding:10px 11px;font-size:10px;}"
            "QLineEdit:focus{border:1px solid #0B7F89;}"
            "QPushButton{border-radius:10px;padding:10px 14px;font-size:10px;font-weight:850;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(25, 23, 25, 22)
        root.setSpacing(15)

        eyebrow = QLabel("PRIVACYGATE ACCOUNT")
        eyebrow.setStyleSheet(
            f"color:{TEAL};font-size:8px;font-weight:900;letter-spacing:1px;"
        )
        root.addWidget(eyebrow)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)
        self.choice_page = self._build_choice_page()
        self.form_page = self._build_form_page()
        self.stack.addWidget(self.choice_page)
        self.stack.addWidget(self.form_page)

        if initial_mode in {"create", "sign_in"}:
            self._show_form(initial_mode)
        else:
            self.stack.setCurrentWidget(self.choice_page)

    def _heading_copy(self) -> tuple[str, str, str]:
        if self.context == "startup":
            return (
                "Start PrivacyGate",
                "Create one free PrivacyGate account for Remote MCP and future multi-device features, "
                "sign in to an existing account, or continue using PrivacyGate locally without registration.",
                "Continue without account",
            )
        if self.context == "remote_mcp":
            return (
                "Remote MCP needs your PrivacyGate Account",
                "Use the same PrivacyGate account across Remote MCP and future account-based services. "
                "There is no separate MCP account.",
                "Not now",
            )
        return (
            "Your PrivacyGate Account",
            "One account for Remote MCP and future multi-device services. Local protection remains available without signing in.",
            "Continue without account",
        )

    def _build_choice_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(13)

        title_text, detail_text, continue_text = self._heading_copy()
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:950;")
        detail = QLabel(detail_text)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color:{MUTED};font-size:10px;")
        box.addWidget(title)
        box.addWidget(detail)

        privacy = QFrame(objectName="AccountPrivacyBoundary")
        privacy.setStyleSheet(
            "QFrame#AccountPrivacyBoundary{background:#EEF9F8;border:1px solid #CFE8E6;border-radius:12px;}"
        )
        privacy_box = QVBoxLayout(privacy)
        privacy_box.setContentsMargins(13, 11, 13, 11)
        privacy_box.setSpacing(3)
        privacy_title = QLabel("LOCAL-FIRST ACCOUNT BOUNDARY")
        privacy_title.setStyleSheet(f"color:{TEAL};font-size:8px;font-weight:900;")
        privacy_text = QLabel(
            "The account stores identity and minimal device metadata. Documents, original PII, protected Library content "
            "and restore mappings are not uploaded to Supabase."
        )
        privacy_text.setWordWrap(True)
        privacy_text.setStyleSheet(f"color:{NAVY};font-size:9px;")
        privacy_box.addWidget(privacy_title)
        privacy_box.addWidget(privacy_text)
        box.addWidget(privacy)

        create_button = QPushButton("Create free account")
        create_button.setObjectName("AccountPrimary")
        create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        create_button.setStyleSheet(
            "QPushButton#AccountPrimary{background:#0B7F89;color:#FFFFFF;border:none;}"
            "QPushButton#AccountPrimary:hover{background:#096D76;}"
        )
        sign_in_button = QPushButton("Sign in")
        sign_in_button.setCursor(Qt.CursorShape.PointingHandCursor)
        sign_in_button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #BFD0DA;}"
            "QPushButton:hover{background:#F1FBFB;border-color:#8DBFC3;}"
        )
        continue_button = QPushButton(continue_text)
        continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        continue_button.setStyleSheet(
            "QPushButton{background:transparent;color:#61798A;border:1px solid #DCE5EA;}"
            "QPushButton:hover{background:#FFFFFF;color:#062B4F;}"
        )

        create_button.clicked.connect(lambda: self._show_form("create"))
        sign_in_button.clicked.connect(lambda: self._show_form("sign_in"))
        continue_button.clicked.connect(self._continue_without_account)
        box.addWidget(create_button)
        box.addWidget(sign_in_button)
        box.addWidget(continue_button)

        local_note = QLabel(
            "Without an account: Protect, Restore, Library, Settings and the local browser extension continue to work normally."
        )
        local_note.setWordWrap(True)
        local_note.setStyleSheet(f"color:{MUTED};font-size:8px;")
        box.addWidget(local_note)
        box.addStretch(1)
        return page

    def _build_form_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)

        self.form_title = QLabel("")
        self.form_title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:950;")
        self.form_detail = QLabel("")
        self.form_detail.setWordWrap(True)
        self.form_detail.setStyleSheet(f"color:{MUTED};font-size:9px;")
        box.addWidget(self.form_title)
        box.addWidget(self.form_detail)

        box.addSpacing(4)
        email_label = QLabel("Email")
        email_label.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;")
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")
        password_label = QLabel("Password")
        password_label.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password (minimum 8 characters)")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self._submit)
        box.addWidget(email_label)
        box.addWidget(self.email)
        box.addWidget(password_label)
        box.addWidget(self.password)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(35)
        self.status.setStyleSheet(f"color:{MUTED};font-size:9px;")
        box.addWidget(self.status)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#61798A;border:1px solid #DCE5EA;}"
        )
        self.submit_button = QPushButton("")
        self.submit_button.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;}"
            "QPushButton:hover{background:#096D76;}"
        )
        self.back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.choice_page))
        self.submit_button.clicked.connect(self._submit)
        actions.addWidget(self.back_button)
        actions.addStretch(1)
        actions.addWidget(self.submit_button)
        box.addLayout(actions)
        box.addStretch(1)
        self._form_mode = "sign_in"
        return page

    def _show_form(self, mode: str) -> None:
        self._form_mode = mode
        self.status.clear()
        if mode == "create":
            self.form_title.setText("Create your PrivacyGate Account")
            self.form_detail.setText(
                "This free account is used for Remote MCP now and can identify your authorized PrivacyGate devices in future releases."
            )
            self.submit_button.setText("Create free account")
        else:
            self.form_title.setText("Sign in to PrivacyGate")
            self.form_detail.setText(
                "Use the same PrivacyGate Account you use for Remote MCP. No separate MCP login is created."
            )
            self.submit_button.setText("Sign in")
        self.stack.setCurrentWidget(self.form_page)
        self.email.setFocus()

    def _valid_fields(self) -> bool:
        if "@" not in self.email.text().strip():
            self.status.setText("Enter a valid email address.")
            return False
        if len(self.password.text()) < 8:
            self.status.setText("Use a password with at least 8 characters.")
            return False
        return True

    def _set_busy(self, busy: bool) -> None:
        self.submit_button.setEnabled(not busy)
        self.back_button.setEnabled(not busy)
        self.email.setEnabled(not busy)
        self.password.setEnabled(not busy)
        if busy:
            self.status.setText("Connecting securely…")
        QApplication.processEvents()

    def _submit(self) -> None:
        if not self._valid_fields():
            return
        self._set_busy(True)
        try:
            if self._form_mode == "create":
                registration = self.account_client.register(
                    self.email.text(), self.password.text()
                )
                if registration.confirmation_required:
                    self._set_busy(False)
                    self.password.clear()
                    self._show_form("sign_in")
                    self.status.setText(
                        "Account created. Check your email and confirm the address, then sign in here."
                    )
                    return
                self.session = registration.session
            else:
                self.session = self.account_client.sign_in(
                    self.email.text(), self.password.text()
                )
        except Exception as error:
            self._set_busy(False)
            self.status.setText(str(error))
            return
        self._set_busy(False)
        if self.session is not None:
            self.accept()

    def _continue_without_account(self) -> None:
        self.continued_without_account = True
        self.reject()


class PrivacyGateAccountUxController:
    """Makes Supabase identity a product-level account without changing MCP core."""

    ONBOARDING_VERSION = 1

    def __init__(self, main_window, account_menu_controller) -> None:
        self.main_window = main_window
        self.menu_controller = account_menu_controller
        self.account_client = account_menu_controller.account_client
        self.state_path = Path(main_window.library.data_dir) / "account_ux.json"
        self._onboarding_started = False
        self._original_menu_render = account_menu_controller._render
        self._install_account_button_render()
        self._enhance_settings_account_panel()
        self._patch_mcp_account_surface()
        if self.account_client.current_user_id:
            self._mark_onboarding_complete()
        self.refresh_surfaces()
        QTimer.singleShot(0, self._maybe_show_startup_onboarding)

    def _install_account_button_render(self) -> None:
        ux = self

        def render(controller) -> None:
            signed_in = bool(controller.account_client.current_user_id)
            if signed_in:
                ux._original_menu_render()
                return
            expanded = bool(getattr(controller.main_window, "sidebar_expanded", True))
            if expanded:
                controller.button.setText("  PrivacyGate Account\n  Sign in optional")
                controller.button.setToolTip(
                    "PrivacyGate Account\nSign in for Remote MCP and future multi-device services."
                )
                controller.button.setMinimumHeight(58)
            else:
                controller.button.setText("")
                controller.button.setToolTip("PrivacyGate Account — sign in optional")
                controller.button.setMinimumHeight(46)

        self.menu_controller._render = MethodType(render, self.menu_controller)

    def _enhance_settings_account_panel(self) -> None:
        settings = getattr(self.main_window, "settings_page", None)
        panel = getattr(settings, "_privacygate_plan_account_panel", None) if settings else None
        if panel is None or bool(getattr(panel, "_privacygate_account_ux_2026", False)):
            return
        panel._privacygate_account_ux_2026 = True
        for label in panel.findChildren(QLabel):
            if label.text().strip() == "Your account":
                label.setText("PrivacyGate Account")
                break

        row_widget = QFrame(panel)
        row_widget.setObjectName("PrivacyGateAccountActions")
        row_widget.setStyleSheet(
            "QFrame#PrivacyGateAccountActions{background:#F7FAFC;border:1px solid #E1E9ED;border-radius:11px;}"
        )
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(10, 9, 10, 9)
        row.setSpacing(8)

        self.settings_device = QLabel("")
        self.settings_device.setWordWrap(True)
        self.settings_device.setStyleSheet(f"color:{MUTED};font-size:8px;")
        row.addWidget(self.settings_device, 1)

        self.settings_create = QPushButton("Create free account")
        self.settings_sign_in = QPushButton("Sign in")
        self.settings_sign_out = QPushButton("Sign out")
        for button in (self.settings_create, self.settings_sign_in, self.settings_sign_out):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(34)
        self.settings_create.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:9px;padding:7px 11px;font-weight:850;}"
        )
        self.settings_sign_in.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #C9D7E0;border-radius:9px;padding:7px 11px;font-weight:800;}"
        )
        self.settings_sign_out.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#8A3B3B;border:1px solid #E4CACA;border-radius:9px;padding:7px 11px;font-weight:800;}"
        )
        self.settings_create.clicked.connect(lambda: self.open_account(initial_mode="create"))
        self.settings_sign_in.clicked.connect(lambda: self.open_account(initial_mode="sign_in"))
        self.settings_sign_out.clicked.connect(self.sign_out)
        row.addWidget(self.settings_create)
        row.addWidget(self.settings_sign_in)
        row.addWidget(self.settings_sign_out)

        layout = panel.layout()
        if isinstance(layout, QVBoxLayout):
            layout.addWidget(row_widget)
        self.settings_panel = panel

        team_page = getattr(self.main_window, "team_page", None)
        state_changed = getattr(team_page, "state_changed", None)
        if state_changed is not None:
            state_changed.connect(lambda _state: QTimer.singleShot(0, self.refresh_surfaces))

    def _patch_mcp_account_surface(self) -> None:
        if not bool(getattr(ConnectionsPage, "_privacygate_account_dialog_patched", False)):
            original_dialog = ConnectionsPage._mcp_account_dialog
            original_remote = ConnectionsPage._remote_mcp_setup

            def account_dialog(page, account_client):
                window = page.window()
                ux = getattr(window, "_privacygate_account_ux_controller", None)
                if isinstance(ux, PrivacyGateAccountUxController):
                    return ux.open_account(
                        context="remote_mcp",
                        initial_mode="choose",
                        account_client=account_client,
                    )
                return original_dialog(page, account_client)

            def remote_setup(page):
                relabel_timer = QTimer(page)

                def relabel() -> None:
                    for widget in QApplication.topLevelWidgets():
                        if not isinstance(widget, QDialog):
                            continue
                        if widget.windowTitle() != "ChatGPT & Claude connection":
                            continue
                        for label in widget.findChildren(QLabel):
                            text = label.text()
                            if text.startswith("MCP account:"):
                                label.setText(
                                    "PrivacyGate account:" + text[len("MCP account:"):]
                                )
                                label.setToolTip(
                                    "This is your single PrivacyGate Account, not a separate MCP account."
                                )
                        relabel_timer.stop()
                        return

                relabel_timer.timeout.connect(relabel)
                relabel_timer.start(25)
                try:
                    return original_remote(page)
                finally:
                    relabel_timer.stop()
                    relabel_timer.deleteLater()
                    window = page.window()
                    ux = getattr(window, "_privacygate_account_ux_controller", None)
                    if isinstance(ux, PrivacyGateAccountUxController):
                        ux.refresh_surfaces()

            ConnectionsPage._mcp_account_dialog = account_dialog
            ConnectionsPage._remote_mcp_setup = remote_setup
            ConnectionsPage._privacygate_account_dialog_patched = True

    def open_account(
        self,
        *,
        context: str = "general",
        initial_mode: str = "choose",
        account_client: SupabaseAccountClient | None = None,
    ) -> AccountSession | None:
        client = account_client or self.account_client
        if client.current_user_id:
            try:
                session = client.restore_session()
            except Exception:
                session = None
            if session is not None:
                self._session_accepted(session)
                return session

        dialog = PrivacyGateAccountDialog(
            self.main_window,
            client,
            context=context,
            initial_mode=initial_mode,
        )
        dialog.exec()
        if dialog.session is not None:
            self._session_accepted(dialog.session)
            return dialog.session
        if context == "startup" and dialog.continued_without_account:
            self._mark_onboarding_complete()
        return None

    def sign_out(self) -> None:
        if not self.account_client.current_user_id:
            self.refresh_surfaces()
            return
        answer = QMessageBox.question(
            self.main_window,
            "Sign out of PrivacyGate?",
            "Sign out of this PrivacyGate Account? Remote MCP will be taken offline. "
            "Your local Library, documents and restore mappings will not be deleted.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.main_window.remote_mcp.stop()
            self.main_window.connection_identity.set_remote_enabled(False)
            set_mcp_autostart(False)
        except Exception:
            pass
        self.account_client.sign_out()
        self.menu_controller.email = ""
        self.menu_controller.profile = None
        self.refresh_surfaces()
        QMessageBox.information(
            self.main_window,
            "Signed out",
            "You are signed out. Protect, Restore, Library and the local browser extension remain available on this device.",
        )

    def _session_accepted(self, session: AccountSession) -> None:
        self._mark_onboarding_complete()
        self.menu_controller.email = session.email
        self.menu_controller.profile = None
        self.refresh_surfaces()
        self.menu_controller.refresh_profile()
        team_page = getattr(self.main_window, "team_page", None)
        refresh = getattr(team_page, "refresh_silent", None)
        if callable(refresh):
            QTimer.singleShot(0, refresh)

    def refresh_surfaces(self) -> None:
        signed_in = bool(self.account_client.current_user_id)
        self.menu_controller.email = self.account_client.current_email or ""
        self.menu_controller._render()
        panel = getattr(self, "settings_panel", None)
        if panel is None:
            return
        try:
            identity = self.main_window.connection_identity.load_or_create()
            device_name = identity.display_name
        except Exception:
            device_name = "This device"

        if signed_in:
            panel.account_type.setText(self.account_client.current_email or "PrivacyGate Account")
            panel.account_detail.setText("Signed in · one PrivacyGate Account")
            self.settings_device.setText(
                f"Current device: {device_name}  •  Remote MCP can use this account. "
                "Documents and restore mappings stay local."
            )
            self.settings_create.hide()
            self.settings_sign_in.hide()
            self.settings_sign_out.show()
        else:
            panel.account_type.setText("Not signed in")
            panel.account_detail.setText("Local PrivacyGate remains fully available")
            self.settings_device.setText(
                f"Current device: {device_name}  •  Sign in only when you need Remote MCP or future account-based services."
            )
            self.settings_create.show()
            self.settings_sign_in.show()
            self.settings_sign_out.hide()

    def _read_onboarding_state(self) -> bool:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return False
        return int(payload.get("version", 0) or 0) >= self.ONBOARDING_VERSION

    def _mark_onboarding_complete(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"version": self.ONBOARDING_VERSION, "completed": True}, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _maybe_show_startup_onboarding(self) -> None:
        if self._onboarding_started:
            return
        if self.account_client.current_user_id:
            self._mark_onboarding_complete()
            return
        if self._read_onboarding_state():
            return
        if not self.main_window.isVisible() or not bool(
            getattr(self.main_window, "_privacygate_startup_ready", False)
        ):
            QTimer.singleShot(150, self._maybe_show_startup_onboarding)
            return
        self._onboarding_started = True
        try:
            self.open_account(context="startup", initial_mode="choose")
        finally:
            self._mark_onboarding_complete()


def install_privacygate_account_ux_2026(main_window, account_menu_controller):
    existing = getattr(main_window, "_privacygate_account_ux_controller", None)
    if isinstance(existing, PrivacyGateAccountUxController):
        return existing
    controller = PrivacyGateAccountUxController(main_window, account_menu_controller)
    main_window._privacygate_account_ux_controller = controller
    return controller
