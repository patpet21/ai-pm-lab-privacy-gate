from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.organization_workspace_suite import WorkspaceConsentDialog


_INSTALLED = False
_CONSENT_PATCHED = False
NAVY = "#062B4F"
TEAL = "#0B7180"
MUTED = "#61798A"
RED = "#B54747"


def _find_layout_containing(layout, widget):
    if layout is None:
        return None
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return layout
        child = item.layout()
        found = _find_layout_containing(child, widget) if child is not None else None
        if found is not None:
            return found
    return None


def _patch_live_workspace_consent_dialog() -> None:
    """Add immediate managed-workspace revocation to the Organization dialog actually in use."""
    global _CONSENT_PATCHED
    if _CONSENT_PATCHED:
        return
    _CONSENT_PATCHED = True
    original_init = WorkspaceConsentDialog.__init__

    def init(self: WorkspaceConsentDialog, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return

        privacy = QLabel(
            "PROVENANCE · LOCAL ONLY  •  Granting workspace access never shares document titles, "
            "source-item lists or OAuth credentials with Organization."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            "background:#F2FAFA;color:#0B7180;border:1px solid #CDE7E9;"
            "border-radius:9px;padding:8px 10px;font-size:8px;font-weight:850;"
        )

        revoke = QPushButton("Revoke all company workspace access now")
        revoke.setToolTip(
            "Keep this connected account in Personal and immediately remove every local company-workspace binding."
        )
        revoke.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#B54747;border:1px solid #F1C1C1;"
            "border-radius:8px;padding:7px 11px;font-size:9px;font-weight:850;}"
            "QPushButton:hover{background:#FFF5F5;border-color:#E69999;}"
        )

        insert_at = max(0, root.count() - 2)
        root.insertWidget(insert_at, privacy)
        root.insertWidget(insert_at + 1, revoke, 0, Qt.AlignmentFlag.AlignLeft)

        def revoke_company_access() -> None:
            context = self.context_store.load()
            selected = [
                key
                for key, descriptor in context.workspaces.items()
                if descriptor.personal
            ]
            if "personal" in context.workspaces and "personal" not in selected:
                selected.insert(0, "personal")
            self.context_store.bind_account(self.provider, self.account_id, selected)
            for key, check in self.checks.items():
                descriptor = context.workspaces.get(key)
                personal = bool(descriptor is not None and descriptor.personal)
                check.setChecked(personal)
            QMessageBox.information(
                self,
                "Company workspace access revoked",
                "This account is now available only in Personal. The change is local and immediate; "
                "no OAuth token, document or source content was sent to Organization.",
            )

        revoke.clicked.connect(revoke_company_access)

    WorkspaceConsentDialog.__init__ = init


def _polish_live_apps_workspace(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    view = getattr(dashboard, "_workspace_suite_apps", None) if dashboard is not None else None
    if view is None or bool(getattr(view, "_privacygate_governance_polished", False)):
        return
    view._privacygate_governance_polished = True

    cue = QLabel()
    cue.setWordWrap(True)
    cue.setStyleSheet(
        "background:#F7FAFC;color:#61798A;border:1px solid #D7E2EA;"
        "border-radius:8px;padding:7px 9px;font-size:8px;font-weight:800;"
    )
    root = view.layout()
    if isinstance(root, QVBoxLayout):
        root.insertWidget(2, cue)

    def update_context_cue(*_args) -> None:
        try:
            context = view.store.load()
            descriptor = context.workspaces.get(context.active_key)
        except Exception:
            return
        if descriptor is None:
            return
        if descriptor.personal:
            view.workspace_combo.setStyleSheet(
                "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #AFCFD3;"
                "border-radius:9px;padding:7px 10px;font-weight:850;}"
            )
            cue.setText(
                "PERSONAL CONTEXT · Connected accounts stay available to you. Company policy is not applied."
            )
            cue.setStyleSheet(
                "background:#F2FAFA;color:#0B7180;border:1px solid #CDE7E9;"
                "border-radius:8px;padding:7px 9px;font-size:8px;font-weight:850;"
            )
        else:
            state = view.store.cached_state(context.active_key)
            if state is None and getattr(team_page, "state", None) is not None:
                state = team_page.state
            policy = getattr(state, "policy", None) if state is not None else None
            version = f"v{policy.version}" if policy is not None else "not synced"
            view.workspace_combo.setStyleSheet(
                "QComboBox{background:#EAF2F7;color:#062B4F;border:2px solid #2F6F91;"
                "border-radius:9px;padding:6px 9px;font-weight:950;}"
            )
            cue.setText(
                f"COMPANY CONTEXT · {descriptor.name} · Policy {version} · Account access is explicit per workspace."
            )
            cue.setStyleSheet(
                "background:#EAF2F7;color:#062B4F;border:1px solid #B8CBD8;"
                "border-radius:8px;padding:7px 9px;font-size:8px;font-weight:900;"
            )

    view.workspace_combo.currentIndexChanged.connect(update_context_cue)
    if team_page is not None:
        team_page.state_changed.connect(update_context_cue)
    update_context_cue()


def _expose_policy_history_in_live_policy_page(main_window) -> None:
    team_page = getattr(main_window, "team_page", None)
    dashboard = getattr(team_page, "_privacygate_premium_dashboard", None) if team_page is not None else None
    view = getattr(dashboard, "_workspace_suite_policy", None) if dashboard is not None else None
    if view is None or bool(getattr(view, "_privacygate_policy_history_visible", False)):
        return
    view._privacygate_policy_history_visible = True

    live_button = QPushButton("Policy history")
    live_button.setToolTip(
        "Compare immutable company-policy versions or republish an older version as a new version."
    )
    live_button.setMinimumHeight(36)
    live_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;"
        "border-radius:8px;padding:7px 11px;font-size:9px;font-weight:850;}"
        "QPushButton:hover{background:#F2FAFA;border-color:#96C9CD;color:#0B7180;}"
    )

    target_layout = _find_layout_containing(view.layout(), getattr(view, "edit_button", None))
    if target_layout is not None:
        position = target_layout.indexOf(view.edit_button)
        target_layout.insertWidget(max(0, position), live_button)

    def hidden_history_button():
        if team_page is None:
            return None
        candidates = [
            button
            for button in team_page.findChildren(QPushButton)
            if button is not live_button and button.text().strip() == "Policy history"
        ]
        return candidates[0] if candidates else None

    def open_history() -> None:
        source = hidden_history_button()
        if source is None:
            QMessageBox.information(
                view,
                "Policy history",
                "Policy history is not available until an organization policy is active and synchronized.",
            )
            return
        source.click()

    live_button.clicked.connect(open_history)

    def update_visibility(*_args) -> None:
        state = getattr(team_page, "state", None)
        live_button.setVisible(
            bool(
                state is not None
                and state.organization_id
                and state.policy is not None
                and state.role in {"owner", "admin"}
            )
        )

    if team_page is not None:
        team_page.state_changed.connect(update_visibility)
    update_visibility()


def apply_governance_release_polish_2026(main_window) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _patch_live_workspace_consent_dialog()
    _polish_live_apps_workspace(main_window)
    _expose_policy_history_in_live_policy_page(main_window)
