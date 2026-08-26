from __future__ import annotations

from time import monotonic

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidgetAction


NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#64788A"


def _menu_width(controller) -> int:
    sidebar = getattr(controller.main_window, "sidebar", None)
    if sidebar is None:
        return max(210, controller.button.width())
    # Keep the popup visually inside the sidebar instead of letting the account
    # card spill over the content area. Ten pixels of breathing room per side is
    # enough to preserve the rounded-card treatment.
    return max(210, int(sidebar.width()) - 20)


def _header_action(controller, menu: QMenu, width: int) -> QWidgetAction:
    action = QWidgetAction(menu)
    panel = QFrame()
    panel.setFixedWidth(max(180, width - 16))
    panel.setStyleSheet(
        "QFrame{background:#F7FAFC;border:1px solid #E1E9ED;border-radius:11px;}"
    )
    row = QHBoxLayout(panel)
    row.setContentsMargins(11, 11, 11, 11)
    row.setSpacing(9)

    avatar = QLabel(controller._initials())
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    avatar.setFixedSize(38, 38)
    avatar.setStyleSheet(
        "background:#0B7180;color:#FFFFFF;border:none;border-radius:19px;"
        "font-size:10px;font-weight:900;"
    )
    row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

    text = QVBoxLayout()
    text.setSpacing(2)
    name = QLabel(controller._display_name())
    name.setWordWrap(True)
    name.setStyleSheet(
        f"color:{NAVY};font-size:12px;font-weight:900;border:none;background:transparent;"
    )
    email = QLabel(controller.email or "Not signed in")
    email.setWordWrap(True)
    email.setStyleSheet(
        f"color:{MUTED};font-size:8px;border:none;background:transparent;"
    )
    plan = QLabel(controller._plan_line().upper())
    plan.setWordWrap(True)
    plan.setStyleSheet(
        f"color:{TEAL};font-size:8px;font-weight:900;border:none;background:transparent;"
    )
    text.addWidget(name)
    text.addWidget(email)
    text.addWidget(plan)
    if controller.state.organization_name:
        org = QLabel(controller.state.organization_name)
        org.setWordWrap(True)
        org.setStyleSheet(
            f"color:{MUTED};font-size:8px;border:none;background:transparent;"
        )
        text.addWidget(org)
    row.addLayout(text, 1)
    action.setDefaultWidget(panel)
    return action


def _build_menu(controller) -> QMenu:
    width = _menu_width(controller)
    menu = QMenu(controller.main_window)
    menu.setObjectName("AccountPopup2026")
    menu.setFixedWidth(width)
    menu.setStyleSheet(
        "QMenu#AccountPopup2026{background:#FFFFFF;color:#062B4F;border:1px solid #D7E2E8;"
        "border-radius:13px;padding:7px;}"
        "QMenu#AccountPopup2026::item{padding:9px 12px;border-radius:8px;font-size:10px;font-weight:750;}"
        "QMenu#AccountPopup2026::item:selected{background:#EAF7F7;color:#062B4F;}"
        "QMenu#AccountPopup2026::separator{height:1px;background:#E2E9ED;margin:6px 4px;}"
    )
    menu.addAction(_header_action(controller, menu, width))
    menu.addSeparator()

    plan_action = menu.addAction("Plan & Account")
    apps_action = menu.addAction("Connected Apps")
    settings_action = menu.addAction("Settings")
    organization_action = None
    if controller.state.organization_id:
        organization_action = menu.addAction("Organization")
    edit_name_action = menu.addAction("Edit display name")
    menu.addSeparator()
    sign_out_action = menu.addAction("Sign out")

    plan_action.triggered.connect(controller._open_settings)
    settings_action.triggered.connect(controller._open_settings)
    apps_action.triggered.connect(controller._open_apps)
    if organization_action is not None:
        organization_action.triggered.connect(controller._open_organization)
    edit_name_action.triggered.connect(controller._edit_display_name)
    sign_out_action.triggered.connect(controller._sign_out)
    return menu


def _show_account_menu(controller) -> None:
    # The collapsed sidebar is intentionally expanded first: a 56px popup is not
    # useful, and this keeps the account card aligned to the normal sidebar width.
    if not bool(getattr(controller.main_window, "sidebar_expanded", True)):
        controller.main_window._set_sidebar_expanded(True)
        QTimer.singleShot(0, lambda: _show_account_menu(controller))
        return

    menu = _build_menu(controller)
    controller._privacygate_account_popup_menu = menu

    def dismissed() -> None:
        controller._privacygate_account_menu_dismissed_at = monotonic()
        QTimer.singleShot(
            0,
            lambda: setattr(controller, "_privacygate_account_popup_menu", None)
            if getattr(controller, "_privacygate_account_popup_menu", None) is menu
            else None,
        )

    menu.aboutToHide.connect(dismissed)
    menu.ensurePolished()
    menu.adjustSize()
    width = _menu_width(controller)
    height = menu.sizeHint().height()
    menu.resize(width, height)

    sidebar = getattr(controller.main_window, "sidebar", None)
    if sidebar is not None:
        left = sidebar.mapToGlobal(QPoint(10, 0)).x()
    else:
        left = controller.button.mapToGlobal(QPoint(0, 0)).x()
    button_top = controller.button.mapToGlobal(QPoint(0, 0)).y()
    top = button_top - height - 7
    menu.popup(QPoint(left, top))


def _toggle_account_menu(controller) -> None:
    active = getattr(controller, "_privacygate_account_popup_menu", None)
    if active is not None and active.isVisible():
        # Clicking ACCOUNT while the card is open acts as a true toggle.
        active.close()
        return

    # QMenu closes itself when the user clicks outside. On some Qt/Windows builds
    # that same click can then reach the underlying Account button; suppress the
    # immediate reopen so one click on Account still means "close".
    dismissed_at = float(getattr(controller, "_privacygate_account_menu_dismissed_at", 0.0) or 0.0)
    if monotonic() - dismissed_at < 0.20:
        return
    _show_account_menu(controller)


def apply_account_menu_popup_2026(main_window) -> None:
    controller = getattr(main_window, "_privacygate_account_menu_controller", None)
    if controller is None or bool(getattr(controller, "_privacygate_account_popup_2026", False)):
        return

    try:
        controller.button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    controller.button.clicked.connect(lambda _checked=False: _toggle_account_menu(controller))
    controller._privacygate_account_popup_menu = None
    controller._privacygate_account_menu_dismissed_at = 0.0
    controller._privacygate_account_popup_2026 = True
