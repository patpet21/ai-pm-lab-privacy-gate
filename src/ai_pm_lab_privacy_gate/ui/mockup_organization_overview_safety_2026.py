from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidgetItem

from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import AMBER, RED
from ai_pm_lab_privacy_gate.ui.mockup_organization_overview_final_2026 import (
    OrganizationOverviewFinal,
    _format_when,
    apply_mockup_organization_overview_final_2026,
)
from ai_pm_lab_privacy_gate.ui.mockup_organization_overview_polish_2026 import (
    apply_organization_overview_polish_2026,
    install_organization_overview_polish_2026,
    install_team_member_consistency_2026,
)
from ai_pm_lab_privacy_gate.ui.mockup_team_members_2026 import apply_mockup_team_members_2026


def _safe_render_risks(
    self,
    *,
    policy,
    coverage: dict[str, int | None],
    active_members: list[dict[str, object]],
    inactive_members: int,
    devices: list[dict[str, object]],
    blocked: int,
    activity_rows: list[dict[str, object]],
) -> None:
    """Qt-version-safe risk renderer used before the final view is instantiated."""

    risks: list[tuple[str, str, str, str, str]] = []
    observed = _format_when(activity_rows[0].get("created_at")) if activity_rows else "Current"

    if policy is None:
        risks.append(("Company policy unavailable", "Policy", "High", "Action required", "Current"))
    else:
        if int(coverage.get("data") or 0) < 100:
            risks.append(("Sensitive-data policy scope incomplete", "Data", "Medium", "Review", "Current"))
        if int(coverage.get("ai") or 0) < 100:
            risks.append(("AI control scope incomplete", "AI", "Medium", "Review", "Current"))
        device_pct = coverage.get("devices")
        if device_pct is not None and device_pct < 100:
            risks.append(
                (
                    "Managed devices not fully synced",
                    "Endpoint",
                    "High" if device_pct < 70 else "Medium",
                    "Active",
                    "Current",
                )
            )

    if inactive_members:
        risks.append((f"{inactive_members} disabled/revoked membership(s)", "Access", "Medium", "Review", "Current"))

    limit = self.team_page.state.seat_limit
    if limit:
        usage = len(active_members) / max(1, int(limit))
        if usage >= 0.9:
            risks.append(("Organization seats nearly full", "Capacity", "Medium", "Monitor", "Current"))

    inactive_devices = sum(
        1 for row in devices if str(row.get("status") or "active").lower() != "active"
    )
    if inactive_devices:
        risks.append((f"{inactive_devices} managed device(s) inactive", "Endpoint", "Medium", "Review", "Current"))
    if blocked:
        risks.append((f"{blocked} blocked/failed local event(s)", "Activity", "Medium", "Monitor", observed))
    if not risks:
        risks.append(("No elevated risk derived from current metadata", "Workspace", "Low", "Normal", "Current"))

    self.risks_table.setRowCount(min(5, len(risks)))
    for row_index, values in enumerate(risks[:5]):
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 2:
                if value == "High":
                    item.setForeground(QBrush(QColor(RED)))
                elif value == "Medium":
                    item.setForeground(QBrush(QColor(AMBER)))
            self.risks_table.setItem(row_index, column, item)


def apply_mockup_organization_overview_safe_2026(main_window):
    # TeamState is authoritative for the signed-in user's real membership. If an
    # older/deployed management RPC omits that same row, reconcile it before any
    # dashboard or Team-page counts are rendered instead of hardcoding a seat.
    install_team_member_consistency_2026()

    # Patch before construction because OrganizationOverviewFinal renders once in
    # __init__. This keeps the final dashboard compatible across supported PySide6
    # builds without moving any organization/business logic.
    OrganizationOverviewFinal._render_risks = _safe_render_risks
    install_organization_overview_polish_2026()

    view = apply_mockup_organization_overview_final_2026(main_window)
    if view is not None:
        apply_organization_overview_polish_2026(view)

    # Team/Members is also replaced only at the presentation layer. Existing
    # TeamPage methods still own invitations, role changes and access mutations.
    apply_mockup_team_members_2026(main_window)
    return view
