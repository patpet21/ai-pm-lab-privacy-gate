from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidgetAction,
)


BLUE = "#2563EB"
INK = "#101828"
MUTED = "#667085"


def _avatar_icon(initials: str, size: int = 36) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#7C3AED"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont()
    font.setBold(True)
    font.setPointSize(max(7, int(size * 0.24)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initials[:2])
    painter.end()
    return QIcon(pixmap)


def _account_values(main_window) -> tuple[str, str, str, str, str]:
    legacy = getattr(main_window, "_privacygate_account_menu_controller", None)
    if legacy is None:
        return "Account", "PG", "", "PrivacyGate", ""
    try:
        return (
            legacy._display_name(),
            legacy._initials(),
            legacy.email or "",
            legacy._plan_line(),
            legacy.state.organization_name or "",
        )
    except Exception:
        return "Account", "PG", "", "PrivacyGate", ""


def _account_header(main_window, menu: QMenu, width: int) -> QWidgetAction:
    name, initials, email, plan, org = _account_values(main_window)
    action = QWidgetAction(menu)
    panel = QFrame()
    panel.setFixedWidth(max(230, width - 16))
    panel.setStyleSheet("QFrame{background:#F9FAFB;border:1px solid #EAECF0;border-radius:13px;}")
    row = QHBoxLayout(panel)
    row.setContentsMargins(12, 11, 12, 11)
    row.setSpacing(10)

    avatar = QLabel()
    avatar.setFixedSize(40, 40)
    avatar.setPixmap(_avatar_icon(initials, 40).pixmap(40, 40))
    row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(1)
    title = QLabel(name)
    title.setWordWrap(True)
    title.setStyleSheet(f"color:{INK};font-size:11px;font-weight:900;border:none;background:transparent;")
    copy.addWidget(title)
    if email:
        email_label = QLabel(email)
        email_label.setWordWrap(True)
        email_label.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;background:transparent;")
        copy.addWidget(email_label)
    plan_label = QLabel(plan)
    plan_label.setWordWrap(True)
    plan_label.setStyleSheet(f"color:{BLUE};font-size:8px;font-weight:850;border:none;background:transparent;")
    copy.addWidget(plan_label)
    if org:
        org_label = QLabel(org)
        org_label.setWordWrap(True)
        org_label.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;background:transparent;")
        copy.addWidget(org_label)
    row.addLayout(copy, 1)
    action.setDefaultWidget(panel)
    return action


def _show_account_popup(sidebar_controller) -> None:
    main_window = sidebar_controller.main_window
    legacy = getattr(main_window, "_privacygate_account_menu_controller", None)
    if legacy is None:
        sidebar_controller._open_page("settings_page")
        return

    active = getattr(sidebar_controller, "_mockup_account_popup", None)
    if active is not None and active.isVisible():
        active.close()
        return

    width = 286
    menu = QMenu(main_window)
    menu.setObjectName("MockupAccountPopup")
    menu.setFixedWidth(width)
    menu.setStyleSheet(
        "QMenu#MockupAccountPopup{background:#FFFFFF;color:#101828;border:1px solid #D0D5DD;"
        "border-radius:18px;padding:8px;}"
        "QMenu#MockupAccountPopup::item{padding:10px 13px;border-radius:9px;font-size:10px;font-weight:700;}"
        "QMenu#MockupAccountPopup::item:selected{background:#F2F4F7;color:#101828;}"
        "QMenu#MockupAccountPopup::separator{height:1px;background:#EAECF0;margin:7px 5px;}"
    )
    menu.addAction(_account_header(main_window, menu, width))
    menu.addSeparator()

    plan_action = menu.addAction("Plan & account")
    apps_action = menu.addAction("Connected Apps")
    settings_action = menu.addAction("Settings")
    organization_action = None
    if getattr(legacy.state, "organization_id", ""):
        organization_action = menu.addAction("Organization")
    edit_action = menu.addAction("Edit display name")
    menu.addSeparator()
    signout_action = menu.addAction("Sign out")

    plan_action.triggered.connect(legacy._open_settings)
    apps_action.triggered.connect(legacy._open_apps)
    settings_action.triggered.connect(legacy._open_settings)
    if organization_action is not None:
        organization_action.triggered.connect(legacy._open_organization)
    edit_action.triggered.connect(legacy._edit_display_name)
    signout_action.triggered.connect(legacy._sign_out)

    sidebar_controller._mockup_account_popup = menu
    menu.aboutToHide.connect(
        lambda: QTimer.singleShot(
            0,
            lambda: setattr(sidebar_controller, "_mockup_account_popup", None),
        )
    )
    menu.ensurePolished()
    menu.adjustSize()
    height = menu.sizeHint().height()
    button = sidebar_controller.account_button
    point = button.mapToGlobal(QPoint(0, 0))
    menu.popup(QPoint(point.x(), max(8, point.y() - height - 8)))


def _polish_mcp_copy(main_window) -> None:
    page = getattr(main_window, "cloud_automation_page", None)
    if page is None:
        return
    replacements = {
        "MCP Connections": "MCP & AI Direct Connections",
        "Connect approved AI clients to protected PrivacyGate data through controlled MCP access. AI providers themselves are managed in Apps; this page is only for MCP connectivity, permissions and client-ready MCP solutions.":
            "Connect PrivacyGate directly to ChatGPT, Claude and other compatible MCP clients. Apps manages provider accounts; this page manages the secure MCP connection, permissions and client-ready direct AI access.",
        "Remote MCP": "ChatGPT / Claude via Remote MCP",
    }
    for label in page.findChildren(QLabel):
        current = label.text()
        replacement = replacements.get(current)
        if replacement:
            label.setText(replacement)
            label.setWordWrap(True)


class _ResponsiveShell(QObject):
    def __init__(self, main_window, controller, toggle_button: QPushButton) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.controller = controller
        self.toggle_button = toggle_button
        self.mode = ""
        self.manual_mode: str | None = None
        main_window.installEventFilter(self)

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        if watched is self.main_window and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.apply)
        return False

    def toggle(self) -> None:
        collapsed = self.mode in {"compact", "manual-compact"}
        self.manual_mode = "expanded" if collapsed else "collapsed"
        self.apply()

    @staticmethod
    def _full_text(button: QPushButton) -> str:
        stored = button.property("mockupFullText")
        if stored:
            return str(stored)
        text = button.text()
        button.setProperty("mockupFullText", text)
        return text

    def _set_section_labels_visible(self, visible: bool) -> None:
        for label in self.controller.nav_host.findChildren(QLabel):
            label.setVisible(visible)

    def _restore_navigation(self) -> None:
        self._set_section_labels_visible(True)
        for button in getattr(self.controller, "_buttons", []):
            full = self._full_text(button)
            button.setText(full)
            button.setToolTip(full.replace("   ▾", "").replace("   ⌃", ""))
            button.show()

    def _compact_navigation(self) -> None:
        self._set_section_labels_visible(False)
        for button in getattr(self.controller, "_buttons", []):
            full = self._full_text(button)
            button.setToolTip(full.replace("   ▾", "").replace("   ⌃", ""))
            if button.objectName() == "RedesignSubNavButton":
                button.hide()
                continue
            if button.isCheckable() and "Team" in full:
                try:
                    button.setChecked(False)
                except Exception:
                    pass
            button.setText("")

    def _update_account(self, compact: bool) -> None:
        name, initials, _email, plan, _org = _account_values(self.main_window)
        button = self.controller.account_button
        button.setIcon(_avatar_icon(initials, 36))
        button.setIconSize(QSize(36, 36))
        button.setToolTip(f"{name} · {plan}")
        if compact:
            button.setText("")
            button.setMinimumHeight(50)
        else:
            button.setText(f"{name}\n{plan}")
            button.setMinimumHeight(58)

    def _apply_compact(self, *, manual: bool) -> None:
        widget = self.controller.widget
        layout = widget.layout()
        workspace = self.controller.workspace_button
        context = self.controller.context_note
        widget.setFixedWidth(82)
        if layout is not None:
            layout.setContentsMargins(8, 10, 8, 10)
            layout.setSpacing(7)
        context.hide()
        workspace.setText("")
        workspace.setToolTip("Switch workspace")
        workspace.setMinimumHeight(50)
        self._compact_navigation()
        self._update_account(True)
        self.toggle_button.setText("›")
        self.toggle_button.setToolTip("Expand sidebar")
        self.mode = "manual-compact" if manual else "compact"

    def _apply_expanded(self, width: int) -> None:
        widget = self.controller.widget
        layout = widget.layout()
        workspace = self.controller.workspace_button
        context = self.controller.context_note
        medium = width < 1320
        widget.setFixedWidth(238 if medium else 286)
        if layout is not None:
            layout.setContentsMargins(10, 12, 10, 12) if medium else layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8 if medium else 10)
        self.controller._update_workspace_copy()
        context.setVisible(not medium)
        workspace.setMinimumHeight(56 if medium else 58)
        self._restore_navigation()
        self._update_account(False)
        self.toggle_button.setText("‹")
        self.toggle_button.setToolTip("Collapse sidebar")
        self.mode = "medium" if medium else "wide"

    def apply(self) -> None:
        width = int(self.main_window.width())
        if self.manual_mode == "collapsed":
            self._apply_compact(manual=True)
            return
        if self.manual_mode == "expanded":
            self._apply_expanded(width)
            return
        if width < 1040:
            self._apply_compact(manual=False)
        else:
            self._apply_expanded(width)


def apply_mockup_shell_refinement_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_mockup_shell_refinement_2026", False)):
        return
    main_window._privacygate_mockup_shell_refinement_2026 = True

    main_window.setMinimumSize(900, 620)
    _polish_mcp_copy(main_window)

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if controller is None:
        return

    status = controller.widget.findChild(QFrame, "RedesignStatusCard")
    if status is not None:
        status.hide()
        status.setMaximumHeight(0)

    root = controller.widget.layout()
    toggle = QPushButton("‹")
    toggle.setObjectName("MockupSidebarToggle")
    toggle.setFixedSize(34, 34)
    toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    toggle.setToolTip("Collapse sidebar")
    toggle.setStyleSheet(
        "QPushButton#MockupSidebarToggle{background:transparent;color:#475467;border:none;border-radius:8px;"
        "font-size:20px;font-weight:700;}"
        "QPushButton#MockupSidebarToggle:hover{background:#F2F4F7;color:#101828;}"
    )
    if root is not None:
        root.insertWidget(0, toggle, 0, Qt.AlignmentFlag.AlignRight)

    account = controller.account_button
    account.setStyleSheet(
        "QPushButton#RedesignAccountButton{background:#F2F2F2;color:#101828;border:none;border-radius:12px;"
        "padding:8px 10px;text-align:left;font-size:9px;font-weight:750;}"
        "QPushButton#RedesignAccountButton:hover{background:#E9E9E9;}"
    )
    try:
        account.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    account.clicked.connect(lambda _checked=False: _show_account_popup(controller))

    responsive = _ResponsiveShell(main_window, controller, toggle)
    main_window._privacygate_responsive_shell_2026 = responsive
    toggle.clicked.connect(lambda _checked=False: responsive.toggle())

    original_rebuild = controller.rebuild

    def rebuild(self) -> None:
        original_rebuild()
        QTimer.singleShot(0, responsive.apply)

    controller.rebuild = MethodType(rebuild, controller)

    legacy = getattr(main_window, "_privacygate_account_menu_controller", None)
    if legacy is not None and not bool(getattr(legacy, "_mockup_account_render_hook", False)):
        original_render = legacy._render

        def render(self) -> None:
            original_render()
            QTimer.singleShot(0, responsive.apply)

        legacy._render = MethodType(render, legacy)
        legacy._mockup_account_render_hook = True

    responsive.apply()
