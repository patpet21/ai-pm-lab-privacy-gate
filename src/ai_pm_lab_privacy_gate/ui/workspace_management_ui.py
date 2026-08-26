from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import AccountSession
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import TeamServiceError
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
TEAL_BRIGHT = "#10A7A3"
MUTED = "#61798A"
GREEN = "#23824B"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"
WHITE = "#FFFFFF"


def _secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(36)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:10px;padding:8px 12px;font-size:10px;font-weight:800;}"
        "QPushButton:hover{background:#EFF9F9;color:#0B7F89;border-color:#93C9CD;}"
        "QPushButton:pressed{background:#E4F4F4;}"
    )
    return button


def _primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(38)
    button.setStyleSheet(
        "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:10px;"
        "padding:9px 14px;font-size:10px;font-weight:850;}"
        "QPushButton:hover{background:#0A6F78;}"
        "QPushButton:pressed{background:#075F67;}"
        "QPushButton:disabled{background:#DCE6E9;color:#91A0AA;}"
    )
    return button


class WorkspaceSettingsPanel(QFrame):
    """Compact Settings surface for multi-workspace enrollment and activation.

    The control-plane already supports multiple company memberships. This panel
    exposes that existing flow in a place users can discover from the sidebar:
    join an existing company with its one-time invitation code or create another
    Business workspace. The invitation code is not a connector/OAuth token.
    """

    def __init__(self, main_window, team_page, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.team_page = team_page
        self.store = team_page._privacygate_workspace_store
        self.setObjectName("WorkspaceSettingsPanel")
        self.setStyleSheet(
            "QFrame#WorkspaceSettingsPanel{background:#FFFFFF;border:1px solid #D7E4E8;"
            "border-radius:16px;}"
        )
        self._build()
        self.team_page.state_changed.connect(lambda _state: self.refresh())
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        bubble = QLabel()
        bubble.setFixedSize(42, 42)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon("workflow", color=TEAL, size=23).pixmap(23, 23))
        bubble.setStyleSheet("background:#E8F7F7;border:none;border-radius:21px;")
        header.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel("Workspace settings")
        title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;")
        subtitle = QLabel(
            "Add company workspaces and choose where PrivacyGate is working. The active workspace controls "
            "which company policy and approved app permissions are applied in Protect and Apps & AI."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)

        self.active_badge = QLabel("ACTIVE")
        self.active_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_badge.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B7E1E2;border-radius:10px;"
            "padding:6px 9px;font-size:8px;font-weight:900;"
        )
        header.addWidget(self.active_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#EEF2F4;border:none;")
        root.addWidget(divider)

        body = QHBoxLayout()
        body.setSpacing(14)

        # Existing workspaces / active context.
        current_card = QFrame(objectName="WorkspaceCurrentCard")
        current_card.setStyleSheet(
            "QFrame#WorkspaceCurrentCard{background:#F8FBFC;border:1px solid #E1E9ED;border-radius:12px;}"
        )
        current = QVBoxLayout(current_card)
        current.setContentsMargins(14, 12, 14, 12)
        current.setSpacing(7)
        heading = QLabel("Where you are working")
        heading.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:900;border:none;")
        note = QLabel(
            "Switching here is the same as using the workspace selector in the sidebar. It changes context, not your PrivacyGate account."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        current.addWidget(heading)
        current.addWidget(note)

        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumHeight(40)
        self.workspace_combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C8D7DF;border-radius:10px;"
            "padding:7px 10px;font-size:10px;font-weight:750;}"
            "QComboBox:hover{border-color:#91C8CC;}"
            "QComboBox:focus{border-color:#0B7F89;}"
            "QComboBox::drop-down{border:none;width:26px;}"
            "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D7E2E8;"
            "selection-background-color:#E8F7F7;selection-color:#062B4F;padding:5px;outline:0;}"
        )
        current.addWidget(self.workspace_combo)

        row = QHBoxLayout()
        self.use_button = _primary_button("Use selected workspace")
        self.refresh_button = _secondary_button("Refresh")
        row.addWidget(self.use_button)
        row.addWidget(self.refresh_button)
        current.addLayout(row)

        self.current_note = QLabel("")
        self.current_note.setWordWrap(True)
        self.current_note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        current.addWidget(self.current_note)
        body.addWidget(current_card, 5)

        # Enrollment / creation.
        add_card = QFrame(objectName="WorkspaceAddCard")
        add_card.setStyleSheet(
            "QFrame#WorkspaceAddCard{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:12px;}"
        )
        add = QVBoxLayout(add_card)
        add.setContentsMargins(14, 12, 14, 12)
        add.setSpacing(7)

        add_title = QLabel("Add Workspace")
        add_title.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:900;border:none;")
        add_note = QLabel(
            "Joining a company uses the one-time invitation code created by its PrivacyGate Owner/Admin. "
            "You may see it described as a workspace token; it is not a Google, Microsoft or connector OAuth token."
        )
        add_note.setWordWrap(True)
        add_note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        add.addWidget(add_title)
        add.addWidget(add_note)

        self.invitation_input = QLineEdit()
        self.invitation_input.setPlaceholderText("Paste invitation code / workspace token")
        self.invitation_input.setClearButtonEnabled(True)
        self.invitation_input.setMinimumHeight(40)
        self.invitation_input.setStyleSheet(
            "QLineEdit{background:#F8FBFC;color:#17384E;border:1px solid #C8D7DF;border-radius:10px;"
            "padding:8px 10px;font-size:10px;}"
            "QLineEdit:focus{background:#FFFFFF;border-color:#0B7F89;}"
        )
        add.addWidget(self.invitation_input)

        actions = QHBoxLayout()
        self.join_button = _primary_button("Join workspace")
        self.create_button = _secondary_button("Create Business workspace")
        actions.addWidget(self.join_button)
        actions.addWidget(self.create_button)
        add.addLayout(actions)

        hint = QLabel("Invitation codes are one-time and expire automatically. After joining, the new workspace is added to the sidebar selector.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "background:#F0FAFA;color:#426675;border:none;border-radius:9px;padding:8px;"
            "font-size:8px;"
        )
        add.addWidget(hint)
        body.addWidget(add_card, 6)
        root.addLayout(body)

        self.use_button.clicked.connect(self._activate_selected)
        self.refresh_button.clicked.connect(self.team_page.refresh_silent)
        self.join_button.clicked.connect(self._join_workspace)
        self.create_button.clicked.connect(self._create_workspace)
        self.invitation_input.returnPressed.connect(self._join_workspace)

    def refresh(self) -> None:
        context = self.store.load()
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        for key, descriptor in context.workspaces.items():
            if descriptor.personal:
                label = f"Personal  ·  {descriptor.plan.label}"
            else:
                role = descriptor.role.title() if descriptor.role else "Member"
                label = f"{descriptor.name}  ·  {descriptor.plan.label}  ·  {role}"
            self.workspace_combo.addItem(label, key)
        index = self.workspace_combo.findData(context.active_key)
        self.workspace_combo.setCurrentIndex(max(0, index))
        self.workspace_combo.blockSignals(False)

        descriptor = context.workspaces.get(context.active_key)
        if descriptor is None:
            self.active_badge.setText("NO WORKSPACE")
            self.current_note.setText("No active workspace is available yet.")
            return
        if descriptor.personal:
            self.active_badge.setText("PERSONAL ACTIVE")
            self.active_badge.setStyleSheet(
                "background:#EEF4F7;color:#425D70;border:1px solid #D5E0E6;border-radius:10px;"
                "padding:6px 9px;font-size:8px;font-weight:900;"
            )
            self.current_note.setText(
                "Personal is active. Company policy is not applied; your local PrivacyGate rules and connected accounts remain yours."
            )
        else:
            self.active_badge.setText("COMPANY ACTIVE")
            self.active_badge.setStyleSheet(
                "background:#E9F8F1;color:#23824B;border:1px solid #B9DECD;border-radius:10px;"
                "padding:6px 9px;font-size:8px;font-weight:900;"
            )
            policy = self.store.cached_state(context.active_key)
            version = getattr(getattr(policy, "policy", None), "version", None) if policy is not None else None
            suffix = f" Policy v{version} is applied locally." if version else " Company policy applies when synced."
            self.current_note.setText(
                f"{descriptor.name} is active. Protect, Apps & AI and workspace permissions use this company context.{suffix}"
            )

    def focus_add_workspace(self) -> None:
        self.refresh()
        self.setStyleSheet(
            "QFrame#WorkspaceSettingsPanel{background:#FFFFFF;border:2px solid #44B8B3;border-radius:16px;}"
        )
        self.invitation_input.setFocus()
        QTimer.singleShot(
            1000,
            lambda: self.setStyleSheet(
                "QFrame#WorkspaceSettingsPanel{background:#FFFFFF;border:1px solid #D7E4E8;border-radius:16px;}"
            ),
        )

    def _activate_selected(self) -> None:
        key = str(self.workspace_combo.currentData() or "")
        if not key:
            return
        sidebar_combo = getattr(self.main_window, "workspace_sidebar_combo", None)
        if sidebar_combo is not None:
            index = sidebar_combo.findData(key)
            if index >= 0:
                sidebar_combo.setCurrentIndex(index)
                return
        selector = getattr(self.team_page, "workspace_selector", None)
        if selector is not None:
            index = selector.findData(key)
            if index >= 0:
                selector.setCurrentIndex(index)
                return
        try:
            self.store.set_active(key)
        except KeyError:
            return
        self.team_page.refresh_silent()

    def _require_signed_in(self) -> bool:
        require = getattr(self.team_page, "_require_signed_in", None)
        return bool(require()) if callable(require) else False

    def _cache_and_activate_state(self, session: AccountSession, state: TeamState) -> TeamState:
        individual = self.team_page.team_client._individual_state(session)
        descriptors = tuple(self.team_page.team_client.list_workspace_descriptors(session))
        context = self.store.cache_workspaces(descriptors, personal_plan=individual.plan)
        key = f"org:{state.organization_id}" if state.organization_id else "personal"
        self.store.cache_state(key, state)
        if key in context.workspaces:
            self.store.set_active(key)
        return state

    def _join_workspace(self) -> None:
        code = self.invitation_input.text().strip()
        if not code:
            QMessageBox.information(
                self,
                "Invitation code needed",
                "Paste the one-time invitation code / workspace token you received from the company Owner or Admin.",
            )
            self.invitation_input.setFocus()
            return
        if not self._require_signed_in():
            return

        def operation(session: AccountSession):
            state = self.team_page.team_client.accept_invitation(session, code)
            return self._cache_and_activate_state(session, state)

        self.join_button.setEnabled(False)
        self.team_page._run_team_action(
            operation,
            success_message="Workspace added. It is now available in the workspace selector.",
            refresh_after=True,
        )
        self.invitation_input.clear()
        QTimer.singleShot(700, lambda: self.join_button.setEnabled(True))
        QTimer.singleShot(900, self.refresh)

    def _create_workspace(self) -> None:
        if not self._require_signed_in():
            return
        name, ok = QInputDialog.getText(
            self,
            "Create Business workspace",
            "Company / organization name:",
        )
        if not ok or not name.strip():
            return
        seats, ok = QInputDialog.getInt(
            self,
            "Business seats",
            "Initial seat limit:",
            5,
            2,
            100,
            1,
        )
        if not ok:
            return

        def operation(session: AccountSession):
            try:
                state = self.team_page.team_client.create_business_workspace(
                    session, name.strip(), seat_limit=seats
                )
            except TeamServiceError:
                raise
            return self._cache_and_activate_state(session, state)

        self.create_button.setEnabled(False)
        self.team_page._run_team_action(
            operation,
            success_message="Business workspace created and added to your workspace selector.",
            refresh_after=True,
        )
        QTimer.singleShot(700, lambda: self.create_button.setEnabled(True))
        QTimer.singleShot(900, self.refresh)


def _install_settings_panel(main_window, team_page) -> WorkspaceSettingsPanel | None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return None
    existing = getattr(settings, "_privacygate_workspace_settings_panel", None)
    if existing is not None:
        return existing
    root = settings.layout()
    if root is None:
        return None
    panel = WorkspaceSettingsPanel(main_window, team_page, settings)
    # The Account/plan panel is inserted near the top by Organization polish. Put
    # Workspace settings directly below it and before the general desktop cards.
    root.insertWidget(min(2, root.count()), panel)
    settings._privacygate_workspace_settings_panel = panel
    return panel


def _polish_sidebar_switcher(main_window, team_page, panel: WorkspaceSettingsPanel) -> None:
    card = getattr(main_window, "workspace_sidebar_card", None)
    combo = getattr(main_window, "workspace_sidebar_combo", None)
    if card is None or combo is None:
        return
    if bool(getattr(card, "_privacygate_working_context_polished", False)):
        return
    card._privacygate_working_context_polished = True

    outer = card.layout()
    if outer is None or outer.count() < 2:
        return
    icon_label = outer.itemAt(0).widget()
    text_box = outer.itemAt(1).layout()
    if text_box is None:
        return
    title = text_box.itemAt(0).widget() if text_box.count() else None

    card.setStyleSheet(
        "QFrame#WorkspaceSwitcherCard{"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #083F59,stop:1 #0B6171);"
        "border:1px solid #2C8C9A;border-radius:13px;}"
    )
    card.setMinimumHeight(96)
    card.setMaximumHeight(108)
    outer.setContentsMargins(10, 9, 9, 9)
    outer.setSpacing(9)

    if isinstance(icon_label, QLabel):
        icon_label.setPixmap(icon("workflow", color=TEAL, size=20).pixmap(20, 20))
        icon_label.setFixedSize(30, 30)
        icon_label.setStyleSheet(
            "background:#E8F7F7;border:1px solid #B7E1E2;border-radius:9px;"
        )

    if isinstance(title, QLabel):
        title.setText("WORKING IN")
        title.setStyleSheet(
            "color:#B8E5E7;font-size:7px;font-weight:900;letter-spacing:1px;"
            "border:none;background:transparent;"
        )

    combo.setMinimumHeight(30)
    combo.setStyleSheet(
        "QComboBox{background:transparent;color:#FFFFFF;border:none;padding:1px 22px 1px 0;"
        "font-size:11px;font-weight:900;}"
        "QComboBox::drop-down{border:none;width:20px;}"
        "QComboBox::down-arrow{width:9px;height:9px;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;"
        "selection-background-color:#EAF7F7;selection-color:#062B4F;padding:5px;outline:0;}"
    )

    footer = QHBoxLayout()
    footer.setSpacing(5)
    mode = QLabel("PERSONAL")
    mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mode.setStyleSheet(
        "background:#FFFFFF;color:#476475;border:none;border-radius:7px;"
        "padding:3px 6px;font-size:7px;font-weight:900;"
    )
    add_button = QPushButton("+ Workspace")
    add_button.setCursor(Qt.CursorShape.PointingHandCursor)
    add_button.setMinimumHeight(26)
    add_button.setStyleSheet(
        "QPushButton{background:rgba(255,255,255,0.10);color:#FFFFFF;border:1px solid rgba(255,255,255,0.28);"
        "border-radius:7px;padding:4px 7px;font-size:8px;font-weight:850;}"
        "QPushButton:hover{background:rgba(255,255,255,0.18);border-color:#B7E1E2;}"
    )
    add_button.setToolTip("Add a company workspace with an invitation code, or create a Business workspace")
    footer.addWidget(mode)
    footer.addStretch(1)
    footer.addWidget(add_button)
    text_box.addLayout(footer)

    main_window.workspace_mode_badge = mode
    main_window.workspace_add_button = add_button
    main_window.workspace_switcher_text_layout = text_box

    def open_workspace_settings() -> None:
        settings = getattr(main_window, "settings_page", None)
        pages = getattr(main_window, "pages", None)
        if settings is not None and pages is not None:
            index = pages.indexOf(settings)
            if index >= 0:
                main_window._show_page(index)
        QTimer.singleShot(40, panel.focus_add_workspace)

    add_button.clicked.connect(open_workspace_settings)

    def refresh_visual(*_args) -> None:
        context = team_page._privacygate_workspace_store.load()
        descriptor = context.workspaces.get(context.active_key)
        if isinstance(title, QLabel):
            title.setText("WORKING IN")
        if descriptor is None:
            mode.setText("NO WORKSPACE")
            mode.setStyleSheet(
                "background:#FFF4E8;color:#9A5A14;border:none;border-radius:7px;"
                "padding:3px 6px;font-size:7px;font-weight:900;"
            )
            if isinstance(icon_label, QLabel):
                icon_label.setToolTip("No active workspace")
            return
        if descriptor.personal:
            mode.setText("PERSONAL")
            mode.setStyleSheet(
                "background:#FFFFFF;color:#476475;border:none;border-radius:7px;"
                "padding:3px 6px;font-size:7px;font-weight:900;"
            )
            tip = "Working in Personal. Company policy is not applied."
        else:
            mode.setText("COMPANY POLICY")
            mode.setStyleSheet(
                "background:#E8F7F0;color:#23824B;border:none;border-radius:7px;"
                "padding:3px 6px;font-size:7px;font-weight:900;"
            )
            tip = f"Working in {descriptor.name}. Company policy and workspace permissions are active."
        card.setToolTip(tip + "\nUse + Workspace to join or create another workspace.")
        combo.setToolTip(tip)
        if isinstance(icon_label, QLabel):
            icon_label.setToolTip(tip)
        panel.refresh()

    combo.currentIndexChanged.connect(lambda _index: QTimer.singleShot(0, refresh_visual))
    team_page.state_changed.connect(refresh_visual)
    refresh_visual()

    # Make the switcher become an icon-only context marker when navigation is
    # collapsed, while keeping the normal expanded experience unchanged.
    previous_sidebar = main_window._set_sidebar_expanded

    def set_sidebar_expanded(expanded: bool) -> None:
        previous_sidebar(expanded)
        if expanded:
            card.setMinimumHeight(96)
            card.setMaximumHeight(108)
            if isinstance(text_box, QHBoxLayout):
                pass
            for index in range(text_box.count()):
                item = text_box.itemAt(index)
                widget = item.widget()
                layout = item.layout()
                if widget is not None:
                    widget.show()
                elif layout is not None:
                    for child_index in range(layout.count()):
                        child = layout.itemAt(child_index).widget()
                        if child is not None:
                            child.show()
        else:
            card.setMinimumHeight(48)
            card.setMaximumHeight(48)
            for index in range(text_box.count()):
                item = text_box.itemAt(index)
                widget = item.widget()
                layout = item.layout()
                if widget is not None:
                    widget.hide()
                elif layout is not None:
                    for child_index in range(layout.count()):
                        child = layout.itemAt(child_index).widget()
                        if child is not None:
                            child.hide()
        refresh_visual()

    main_window._set_sidebar_expanded = set_sidebar_expanded
    set_sidebar_expanded(bool(getattr(main_window, "sidebar_expanded", True)))


def apply_workspace_management_ui(main_window) -> None:
    """Clarify workspace context and expose multi-workspace enrollment in Settings."""
    team_page = getattr(main_window, "team_page", None)
    if team_page is None or not hasattr(team_page, "_privacygate_workspace_store"):
        return
    if bool(getattr(main_window, "_privacygate_workspace_management_ui", False)):
        return
    main_window._privacygate_workspace_management_ui = True

    panel = _install_settings_panel(main_window, team_page)
    if panel is None:
        return
    _polish_sidebar_switcher(main_window, team_page, panel)
