from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QTableWidget

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
    privacy_gate_memberships. The management RPC should return that same row, but
    older/deployed RPC variants can temporarily omit it. Reconcile only that
    already-authoritative current membership; never invent other users or seats.
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


def install_team_member_consistency_2026() -> None:
    """Reconcile only the signed-in user's proven organization membership."""

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
        return original_apply_state(self, state, members, devices)

    TeamPage._apply_state = apply_state_with_member_consistency
    TeamPage._privacygate_member_consistency_2026 = True


def _fit_risks(view: OrganizationOverviewFinal) -> None:
    table = getattr(view, "risks_table", None)
    if not isinstance(table, QTableWidget):
        return

    table.resizeRowsToContents()
    header_height = max(28, table.horizontalHeader().sizeHint().height())
    rows_height = sum(max(30, table.rowHeight(index)) for index in range(table.rowCount()))
    target = max(72, min(218, header_height + rows_height + 8))
    table.setMinimumHeight(target)
    table.setMaximumHeight(target)

    card = view.findChild(QFrame, "OrgFinalRisks")
    if card is not None:
        card.setMinimumHeight(0)
        card.setMaximumHeight(330)
        card.updateGeometry()


def _fit_team(view: OrganizationOverviewFinal) -> None:
    card = view.findChild(QFrame, "OrgFinalTeam")
    if card is not None:
        card.setMinimumHeight(0)
        card.setMaximumHeight(410)
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
    """Install compact, content-driven sizing before the final view is built."""

    if bool(getattr(OrganizationOverviewFinal, "_privacygate_polish_2026", False)):
        return

    original_render_risks = OrganizationOverviewFinal._render_risks
    original_render_roster = OrganizationOverviewFinal._render_roster

    def render_risks_with_fit(self, *args, **kwargs):
        result = original_render_risks(self, *args, **kwargs)
        _fit_risks(self)
        return result

    def render_roster_with_fit(self, *args, **kwargs):
        result = original_render_roster(self, *args, **kwargs)
        _fit_team(self)
        return result

    OrganizationOverviewFinal._render_risks = render_risks_with_fit
    OrganizationOverviewFinal._render_roster = render_roster_with_fit
    OrganizationOverviewFinal._privacygate_polish_2026 = True


def apply_organization_overview_polish_2026(view: OrganizationOverviewFinal) -> None:
    """Apply final snapshot-coverage labels and compact card geometry."""

    _polish_coverage(view)
    _fit_risks(view)
    _fit_team(view)
    QTimer.singleShot(0, lambda: (_fit_risks(view), _fit_team(view)))
