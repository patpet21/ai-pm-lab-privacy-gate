from __future__ import annotations

import hashlib
import platform

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QTableWidget

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.ui.mockup_organization_overview_final_2026 import OrganizationOverviewFinal
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage


_COVERAGE_LABELS = {
    "Sensitive-data rules": "Data · Sensitive-data rules",
    "AI controls": "AI · Destination controls",
    "Connected-app controls": "Apps · Connected-app controls",
    "Managed-device compliance": "Devices · Managed-device compliance",
}


def _reconcile_current_member(state, members, *, user_id: str, email: str):
    """Keep the authenticated membership represented in management rosters.

    TeamState is loaded from the authenticated user's real active row in
    privacy_gate_memberships. Reconcile only that already-authoritative current
    membership; never invent other users or consume an extra seat.
    """

    rows = [dict(row) for row in (members or [])]
    current_user_id = str(user_id or "").strip()
    if not current_user_id or not getattr(state, "organization_id", None):
        return rows
    if str(getattr(state, "membership_status", "") or "").lower() != "active":
        return rows
    if any(str(row.get("user_id") or "") == current_user_id for row in rows):
        return rows

    rows.insert(
        0,
        {
            "user_id": current_user_id,
            "email": str(email or "").strip(),
            "role": str(getattr(state, "role", "") or "member").lower(),
            "status": "active",
            "joined_at": "",
        },
    )
    return rows


def _reconcile_current_device(team_page: TeamPage, state, devices):
    """Represent this endpoint after a successful managed-workspace snapshot.

    fetch_workspace_state synchronizes this installation before it returns the
    TeamState. If the management-list response is temporarily empty/stale, use the
    same local installation identity and policy version instead of presenting a
    false "No devices" state. No remote device is fabricated.
    """

    rows = [dict(row) for row in (devices or [])]
    current_user_id = str(getattr(team_page.account_client, "current_user_id", "") or "").strip()
    if not current_user_id or not getattr(state, "organization_id", None):
        return rows
    if str(getattr(state, "membership_status", "") or "").lower() != "active":
        return rows
    if not str(getattr(state, "synced_at", "") or "").strip():
        return rows

    try:
        identity = team_page.identity_store.load_or_create()
        installation_hash = hashlib.sha256(identity.installation_id.encode("ascii")).hexdigest()
    except Exception:
        return rows

    if any(str(row.get("installation_hash") or "") == installation_hash for row in rows):
        return rows

    policy = getattr(state, "policy", None)
    rows.insert(
        0,
        {
            "user_id": current_user_id,
            "email": str(getattr(team_page.account_client, "current_email", "") or "").strip(),
            "installation_hash": installation_hash,
            "display_name": str(getattr(identity, "display_name", "") or "This PC"),
            "platform": platform.system().lower(),
            "app_version": __version__,
            "status": "active",
            "last_policy_version": getattr(policy, "version", None),
            "last_policy_sync_at": str(getattr(state, "synced_at", "") or ""),
        },
    )
    return rows


def reconcile_team_management_snapshot_2026(team_page: TeamPage) -> None:
    """Normalize the local management snapshot against proven current identity."""

    state = team_page.state
    if not getattr(state, "organization_id", None):
        return

    team_page._members = _reconcile_current_member(
        state,
        list(getattr(team_page, "_members", ()) or ()),
        user_id=str(getattr(team_page.account_client, "current_user_id", "") or ""),
        email=str(getattr(team_page.account_client, "current_email", "") or ""),
    )
    team_page._devices = _reconcile_current_device(
        team_page,
        state,
        list(getattr(team_page, "_devices", ()) or ()),
    )


def install_team_member_consistency_2026() -> None:
    """Reconcile signed-in member/device data on every authoritative state apply."""

    if bool(getattr(TeamPage, "_privacygate_member_consistency_2026", False)):
        return

    original_apply_state = TeamPage._apply_state

    def apply_state_with_member_consistency(self, state, members=None, devices=None):
        if members is not None:
            members = _reconcile_current_member(
                state,
                members,
                user_id=str(getattr(self.account_client, "current_user_id", "") or ""),
                email=str(getattr(self.account_client, "current_email", "") or ""),
            )
        if devices is not None:
            devices = _reconcile_current_device(self, state, devices)
        result = original_apply_state(self, state, members, devices)
        reconcile_team_management_snapshot_2026(self)
        return result

    TeamPage._apply_state = apply_state_with_member_consistency
    TeamPage._privacygate_member_consistency_2026 = True


def _fit_risks(view: OrganizationOverviewFinal) -> None:
    table = getattr(view, "risks_table", None)
    if not isinstance(table, QTableWidget):
        return

    table.resizeRowsToContents()
    header_height = max(28, table.horizontalHeader().sizeHint().height())
    rows_height = sum(max(30, table.rowHeight(index)) for index in range(table.rowCount()))
    table_target = max(72, min(218, header_height + rows_height + 8))
    table.setMinimumHeight(table_target)
    table.setMaximumHeight(table_target)

    card = view.findChild(QFrame, "OrgFinalRisks")
    if card is not None:
        card_target = max(172, min(318, table_target + 94))
        card.setMinimumHeight(card_target)
        card.setMaximumHeight(card_target)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        parent_layout = card.parentWidget().layout() if card.parentWidget() is not None else None
        if parent_layout is not None:
            try:
                parent_layout.setAlignment(card, Qt.AlignmentFlag.AlignTop)
            except (AttributeError, TypeError):
                pass
        card.updateGeometry()


def _fit_team(view: OrganizationOverviewFinal) -> None:
    card = view.findChild(QFrame, "OrgFinalTeam")
    if card is not None:
        card.setMinimumHeight(0)
        card.setMaximumHeight(410)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        parent_layout = card.parentWidget().layout() if card.parentWidget() is not None else None
        if parent_layout is not None:
            try:
                parent_layout.setAlignment(card, Qt.AlignmentFlag.AlignTop)
            except (AttributeError, TypeError):
                pass
        card.updateGeometry()


def _polish_coverage(view: OrganizationOverviewFinal) -> None:
    card = view.findChild(QFrame, "OrgFinalCoverage")
    if card is None:
        return
    card.setMinimumHeight(292)
    card.setMaximumHeight(360)
    view.coverage_plot.setMinimumHeight(122)

    for label in card.findChildren(QLabel):
        replacement = _COVERAGE_LABELS.get(label.text().strip())
        if replacement:
            label.setText(replacement)


def install_organization_overview_polish_2026() -> None:
    """Install live snapshot reconciliation and compact content-driven sizing."""

    if bool(getattr(OrganizationOverviewFinal, "_privacygate_polish_2026", False)):
        return

    original_render = OrganizationOverviewFinal.render
    original_render_risks = OrganizationOverviewFinal._render_risks
    original_render_roster = OrganizationOverviewFinal._render_roster

    def render_with_snapshot_consistency(self, *args, **kwargs):
        reconcile_team_management_snapshot_2026(self.team_page)
        return original_render(self, *args, **kwargs)

    def render_risks_with_fit(self, *args, **kwargs):
        result = original_render_risks(self, *args, **kwargs)
        _fit_risks(self)
        return result

    def render_roster_with_fit(self, *args, **kwargs):
        result = original_render_roster(self, *args, **kwargs)
        _fit_team(self)
        return result

    OrganizationOverviewFinal.render = render_with_snapshot_consistency
    OrganizationOverviewFinal._render_risks = render_risks_with_fit
    OrganizationOverviewFinal._render_roster = render_roster_with_fit
    OrganizationOverviewFinal._privacygate_polish_2026 = True


def apply_organization_overview_polish_2026(view: OrganizationOverviewFinal) -> None:
    """Apply final snapshot-coverage labels and compact card geometry."""

    reconcile_team_management_snapshot_2026(view.team_page)
    _polish_coverage(view)
    _fit_risks(view)
    _fit_team(view)
    QTimer.singleShot(0, lambda: (_fit_risks(view), _fit_team(view)))
