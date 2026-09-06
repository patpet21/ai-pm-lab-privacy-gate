from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.privacygate_account_ux_2026 import PrivacyGateAccountDialog

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"


def _button_by_text(root, text: str) -> QPushButton | None:
    for button in root.findChildren(QPushButton):
        if button.text().strip() == text:
            return button
    return None


def _install_dialog_polish() -> None:
    if bool(getattr(PrivacyGateAccountDialog, "_privacygate_release_polish", False)):
        return
    original_init = PrivacyGateAccountDialog.__init__

    def polished_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.resize(590, 470)
        self.setMinimumWidth(550)
        self.setStyleSheet(
            "QDialog#PrivacyGateAccountDialog{background:#F7FAFC;}"
            "QLabel{background:transparent;border:none;}"
            "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #C8D7E0;"
            "border-radius:10px;padding:10px 11px;font-size:10px;}"
            "QLineEdit:focus{border:1px solid #0B7F89;}"
            "QPushButton{min-height:38px;border-radius:10px;padding:8px 14px;"
            "font-size:10px;font-weight:850;}"
        )

        for label in self.findChildren(QLabel):
            text = label.text().strip()
            if text == "PRIVACYGATE ACCOUNT":
                label.setText("PRIVACYGATE  ·  LOCAL-FIRST ACCOUNT")
                label.setStyleSheet(
                    f"color:{TEAL};font-size:8px;font-weight:900;letter-spacing:1px;"
                )
            elif text.startswith("Without an account:"):
                label.setText(
                    "No account required for local Protect, Restore, Library, Settings or browser protection."
                )
                label.setStyleSheet(f"color:{MUTED};font-size:8px;")
            elif text == "LOCAL-FIRST ACCOUNT BOUNDARY":
                label.setText("LOCAL-FIRST PRIVACY")
            elif text.startswith("The account stores identity and minimal device metadata."):
                label.setText(
                    "Only account identity and minimal device metadata are stored online. "
                    "Documents, original PII and restore mappings remain on your device."
                )

        privacy = self.findChild(QFrame, "AccountPrivacyBoundary")
        if privacy is not None:
            privacy.setStyleSheet(
                "QFrame#AccountPrivacyBoundary{background:#F0FAF9;"
                "border:1px solid #CDE8E5;border-radius:12px;}"
            )

        create = _button_by_text(self, "Create free account")
        sign_in = _button_by_text(self, "Sign in")
        continue_button = _button_by_text(self, "Continue without account")
        not_now = _button_by_text(self, "Not now")

        if create is not None:
            create.setStyleSheet(
                "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;}"
                "QPushButton:hover{background:#096D76;}"
            )
        if sign_in is not None:
            sign_in.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #BFD0DA;}"
                "QPushButton:hover{background:#F1FBFB;border-color:#8DBFC3;}"
            )
        if continue_button is not None:
            continue_button.setText("Continue locally")
            continue_button.setStyleSheet(
                "QPushButton{background:transparent;color:#526C7C;border:1px solid #D5E0E6;}"
                "QPushButton:hover{background:#FFFFFF;color:#062B4F;}"
            )
        if not_now is not None:
            not_now.setStyleSheet(
                "QPushButton{background:transparent;color:#61798A;border:1px solid #D5E0E6;}"
                "QPushButton:hover{background:#FFFFFF;color:#062B4F;}"
            )

    PrivacyGateAccountDialog.__init__ = polished_init
    PrivacyGateAccountDialog._privacygate_release_polish = True


def _polish_sidebar(main_window, account_controller) -> None:
    if bool(getattr(account_controller, "_privacygate_release_sidebar_polish", False)):
        account_controller._render()
        return

    original_render = account_controller._render

    def render(controller) -> None:
        signed_in = bool(controller.account_client.current_user_id)
        if signed_in:
            original_render()
            return
        expanded = bool(getattr(controller.main_window, "sidebar_expanded", True))
        if expanded:
            controller.button.setText("  PrivacyGate Account\n  Local mode")
            controller.button.setToolTip(
                "PrivacyGate Account\nLocal mode — sign in only for Remote MCP "
                "and future account-based services."
            )
            controller.button.setMinimumHeight(58)
        else:
            controller.button.setText("")
            controller.button.setToolTip("PrivacyGate Account — Local mode")
            controller.button.setMinimumHeight(46)

    account_controller._render = MethodType(render, account_controller)
    account_controller._privacygate_release_sidebar_polish = True
    account_controller._render()


def _ensure_settings_footer(main_window, controls):
    footer = controls.findChild(QFrame, "PrivacyGateAccountReleaseFooter")
    if footer is not None:
        return footer

    footer = QFrame(controls)
    footer.setObjectName("PrivacyGateAccountReleaseFooter")
    footer.setStyleSheet(
        "QFrame#PrivacyGateAccountReleaseFooter{background:#F7FAFC;"
        "border:1px solid #E0E9ED;border-radius:12px;}"
    )
    root = QVBoxLayout(footer)
    root.setContentsMargins(12, 10, 12, 10)
    root.setSpacing(8)

    device = QLabel("")
    device.setObjectName("PrivacyGateAccountReleaseDevice")
    device.setWordWrap(True)
    device.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
    root.addWidget(device)

    row = QHBoxLayout()
    row.setSpacing(8)
    create = QPushButton("Create free account")
    create.setObjectName("PrivacyGateAccountCreate")
    create.setCursor(Qt.CursorShape.PointingHandCursor)
    create.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:9px;"
        "padding:8px 12px;font-weight:850;}QPushButton:hover{background:#096D76;}"
    )
    sign_in = QPushButton("Sign in")
    sign_in.setObjectName("PrivacyGateAccountSignIn")
    sign_in.setCursor(Qt.CursorShape.PointingHandCursor)
    sign_in.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #C9D7E0;"
        "border-radius:9px;padding:8px 12px;font-weight:800;}"
    )
    manage = QPushButton("Manage plan")
    manage.setObjectName("PrivacyGateAccountManagePlan")
    manage.setCursor(Qt.CursorShape.PointingHandCursor)
    manage.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #C9D7E0;"
        "border-radius:9px;padding:8px 12px;font-weight:800;}"
    )
    sign_out = QPushButton("Sign out")
    sign_out.setObjectName("PrivacyGateAccountSignOut")
    sign_out.setCursor(Qt.CursorShape.PointingHandCursor)
    sign_out.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#8A3B3B;border:1px solid #E4CACA;"
        "border-radius:9px;padding:8px 12px;font-weight:800;}"
    )

    ux = getattr(main_window, "_privacygate_account_ux_controller", None)
    if ux is not None:
        create.clicked.connect(lambda: ux.open_account(initial_mode="create"))
        sign_in.clicked.connect(lambda: ux.open_account(initial_mode="sign_in"))
        sign_out.clicked.connect(ux.sign_out)

    hidden_panel = getattr(
        getattr(main_window, "settings_page", None), "_privacygate_plan_account_panel", None
    )

    def open_plan() -> None:
        if hidden_panel is None:
            return
        update = _button_by_text(hidden_panel, "Update plan")
        if update is not None:
            update.click()

    manage.clicked.connect(open_plan)
    row.addWidget(create)
    row.addWidget(sign_in)
    row.addWidget(manage)
    row.addWidget(sign_out)
    row.addStretch(1)
    root.addLayout(row)

    layout = controls.layout()
    if isinstance(layout, QVBoxLayout):
        layout.addWidget(footer)

    footer._privacygate_device_label = device
    footer._privacygate_create_button = create
    footer._privacygate_sign_in_button = sign_in
    footer._privacygate_manage_button = manage
    footer._privacygate_sign_out_button = sign_out
    return footer


def _render_settings(main_window, account_controller) -> None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return
    controls = settings.findChild(QFrame, "SettingsAccountControls")
    if controls is None:
        return

    duplicate = getattr(settings, "_privacygate_plan_account_panel", None)
    if duplicate is not None:
        duplicate.hide()

    footer = _ensure_settings_footer(main_window, controls)
    signed_in = bool(account_controller.account_client.current_user_id)

    labels = controls.findChildren(QLabel)
    header = next(
        (
            label
            for label in labels
            if label.text().strip() in {"Account identity", "PrivacyGate Account"}
        ),
        None,
    )
    if header is not None:
        header.setText("PrivacyGate Account")

    edit = _button_by_text(controls, "Edit display name")
    refresh = _button_by_text(controls, "Refresh profile")
    apps = _button_by_text(controls, "Connected apps")

    try:
        identity = main_window.connection_identity.load_or_create()
        device_name = identity.display_name
    except Exception:
        device_name = "This PC"

    if signed_in:
        display = account_controller._display_name()
        email = account_controller.account_client.current_email or account_controller.email or ""
        controls.name.setText(
            display if display != "Your Account" else (email or "PrivacyGate Account")
        )
        controls.email.setText(email or "Signed in")
        controls.plan_badge.setText(account_controller._plan_line().upper())
        for button in (edit, refresh, apps):
            if button is not None:
                button.show()
        footer._privacygate_device_label.setText(
            f"Current device: {device_name}  •  Signed in securely. "
            "Documents, Library content and restore mappings remain local."
        )
        footer._privacygate_create_button.hide()
        footer._privacygate_sign_in_button.hide()
        footer._privacygate_manage_button.show()
        footer._privacygate_sign_out_button.show()
    else:
        controls.name.setText("Not signed in")
        controls.email.setText("PrivacyGate remains fully available locally.")
        controls.plan_badge.setText("LOCAL")
        for button in (edit, refresh, apps):
            if button is not None:
                button.hide()
        footer._privacygate_device_label.setText(
            f"Current device: {device_name}  •  Create or sign in to one PrivacyGate Account "
            "only when you need Remote MCP or future multi-device services."
        )
        footer._privacygate_create_button.show()
        footer._privacygate_sign_in_button.show()
        footer._privacygate_manage_button.hide()
        footer._privacygate_sign_out_button.hide()


def _install_settings_refresh(main_window, account_controller) -> None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return
    controls = settings.findChild(QFrame, "SettingsAccountControls")
    if controls is None:
        QTimer.singleShot(
            120, lambda: _install_settings_refresh(main_window, account_controller)
        )
        return

    if not bool(getattr(controls, "_privacygate_release_refresh_patch", False)):
        original_refresh = controls.refresh

        def refresh(instance) -> None:
            original_refresh()
            _render_settings(main_window, account_controller)

        controls.refresh = MethodType(refresh, controls)
        controls._privacygate_release_refresh_patch = True

    ux = getattr(main_window, "_privacygate_account_ux_controller", None)
    if ux is not None and not bool(
        getattr(ux, "_privacygate_release_refresh_patch", False)
    ):
        original_ux_refresh = ux.refresh_surfaces

        def refresh_surfaces(instance) -> None:
            original_ux_refresh()
            _polish_sidebar(main_window, account_controller)
            _render_settings(main_window, account_controller)

        ux.refresh_surfaces = MethodType(refresh_surfaces, ux)
        ux._privacygate_release_refresh_patch = True

    _polish_sidebar(main_window, account_controller)
    _render_settings(main_window, account_controller)


def install_account_release_polish_2026(main_window, account_controller) -> None:
    """Final release-only presentation layer for the single PrivacyGate Account."""

    _install_dialog_polish()
    if bool(getattr(main_window, "_privacygate_account_release_polish_2026", False)):
        return
    main_window._privacygate_account_release_polish_2026 = True

    # Dedicated Settings service pages are assembled later in MainWindow setup.
    # Run after construction so duplicate account presentation can be removed
    # without changing auth, plan, Library or MCP controllers.
    QTimer.singleShot(
        0, lambda: _install_settings_refresh(main_window, account_controller)
    )
