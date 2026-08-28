from __future__ import annotations

from time import monotonic
from types import MethodType

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidgetAction,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_shell_refinement_2026 import _show_account_popup


BLUE = "#2563EB"
INK = "#101828"
MUTED = "#667085"
BORDER = "#E4E7EC"


def _toggle_account_popup(controller) -> None:
    """Make the redesigned Account launcher behave like a true toggle.

    QMenu closes itself before an outside mouse click reaches the Account button on
    some Qt/Windows builds. Remember that dismissal briefly so the same physical
    click cannot immediately reopen the popup.
    """

    active = getattr(controller, "_mockup_account_popup", None)
    if active is not None and active.isVisible():
        controller._mockup_account_dismissed_at = monotonic()
        active.close()
        return

    dismissed_at = float(getattr(controller, "_mockup_account_dismissed_at", 0.0) or 0.0)
    if monotonic() - dismissed_at < 0.28:
        return

    _show_account_popup(controller)
    menu = getattr(controller, "_mockup_account_popup", None)
    if menu is not None:
        menu.aboutToHide.connect(
            lambda: setattr(controller, "_mockup_account_dismissed_at", monotonic())
        )


def _menu_header(menu: QMenu) -> QWidgetAction:
    action = QWidgetAction(menu)
    label = QLabel("WORKSPACES")
    label.setStyleSheet(
        "color:#98A2B3;font-size:7px;font-weight:900;letter-spacing:1px;"
        "padding:7px 10px 4px;background:transparent;border:none;"
    )
    action.setDefaultWidget(label)
    return action


def _workspace_action(controller, menu: QMenu, key: str, descriptor, active_key: str) -> QWidgetAction:
    action = QWidgetAction(menu)
    panel = QFrame()
    panel.setStyleSheet("QFrame{background:transparent;border:none;}")
    row = QHBoxLayout(panel)
    row.setContentsMargins(4, 2, 4, 2)
    row.setSpacing(6)

    personal = bool(getattr(descriptor, "personal", False))
    title = "Personal" if personal else str(getattr(descriptor, "name", "Organization") or "Organization")
    plan = str(getattr(getattr(descriptor, "plan", None), "label", "") or "")
    role = str(getattr(descriptor, "role", "") or "")
    kind = "Personal workspace" if personal else "Organization workspace"
    detail = " · ".join(part for part in (kind, plan, role.title() if role else "") if part)

    button = QPushButton(f"{title}\n{detail}")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setIcon(icon("contact" if personal else "protect", color=BLUE, size=19))
    button.setIconSize(QSize(19, 19))
    button.setMinimumHeight(52)
    button.setStyleSheet(
        "QPushButton{background:transparent;color:#101828;border:none;border-radius:10px;"
        "padding:7px 8px;text-align:left;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F2F4F7;}"
    )
    row.addWidget(button, 1)

    selected = key == active_key
    check = QLabel("✓" if selected else "")
    check.setFixedWidth(22)
    check.setAlignment(Qt.AlignmentFlag.AlignCenter)
    check.setStyleSheet(
        f"color:{BLUE};font-size:13px;font-weight:900;background:transparent;border:none;"
    )
    row.addWidget(check)

    def choose() -> None:
        menu.close()
        controller._select_workspace(key)

    button.clicked.connect(choose)
    action.setDefaultWidget(panel)
    return action


def _install_workspace_menu(controller) -> None:
    menu = controller.workspace_menu
    menu.setMinimumWidth(320)
    menu.setStyleSheet(
        "QMenu{background:#FFFFFF;color:#101828;border:1px solid #D0D5DD;"
        "border-radius:16px;padding:8px;}"
        "QMenu::separator{height:1px;background:#EAECF0;margin:6px 5px;}"
    )

    def rebuild_workspace_menu(self) -> None:
        menu.clear()
        context = self._workspace_context()
        if context is None:
            disabled = menu.addAction("No workspace information available")
            disabled.setEnabled(False)
            return

        menu.addAction(_menu_header(menu))
        for key, descriptor in context.workspaces.items():
            menu.addAction(_workspace_action(self, menu, key, descriptor, context.active_key))

        if len(context.workspaces) > 1:
            menu.addSeparator()
            hint = QWidgetAction(menu)
            label = QLabel("Switching workspace changes the active privacy and policy context.")
            label.setWordWrap(True)
            label.setStyleSheet(
                "color:#667085;font-size:7.5px;padding:5px 10px 7px;"
                "background:transparent;border:none;"
            )
            hint.setDefaultWidget(label)
            menu.addAction(hint)

    controller._rebuild_workspace_menu = MethodType(rebuild_workspace_menu, controller)
    try:
        menu.aboutToShow.disconnect()
    except (RuntimeError, TypeError):
        pass
    menu.aboutToShow.connect(controller._rebuild_workspace_menu)


def apply_mockup_interaction_polish_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_interaction_polish_2026", False)):
        return
    main_window._privacygate_mockup_interaction_polish_2026 = True

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return

    account = controller.account_button
    try:
        account.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    controller._mockup_account_dismissed_at = 0.0
    account.clicked.connect(lambda _checked=False: _toggle_account_popup(controller))

    _install_workspace_menu(controller)
