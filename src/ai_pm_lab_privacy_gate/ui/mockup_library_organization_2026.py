from __future__ import annotations

from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import policy_status_text


def _set_metric(page, index: int, *, label: str, value: str, note: str) -> None:
    widgets = getattr(page, "_library_metric_widgets", ())
    if index >= len(widgets):
        return
    title, number, detail = widgets[index]
    title.setText(label)
    number.setText(value)
    detail.setText(note)


def render_organization_library_context(page, context, documents) -> None:
    page._library_final_title.setText(f"{context.name} Library")
    page._library_final_subtitle.setText(
        "Organization-scoped local document hub. Only protected items saved in this workspace are shown; document contents never become a team cloud drive."
    )
    page._library_final_context_badge.setText(
        f"MANAGED BY {context.name.upper()} · {context.plan_label.upper()}"
    )
    page._library_final_context_badge.setStyleSheet(
        "background:#ECFDF3;color:#15803D;border:1px solid #BBF7D0;border-radius:9px;"
        "padding:5px 9px;font-size:7.5px;font-weight:900;"
    )

    restorable = sum(1 for document in documents if document.has_mapping)
    ai_access = sum(1 for document in documents if document.mcp_shared)
    policy = policy_status_text(context)
    role = context.role.title() if context.role else "Member"

    _set_metric(
        page,
        0,
        label="Organization documents",
        value=str(len(documents)),
        note="Local items in active workspace",
    )
    _set_metric(
        page,
        1,
        label="Restorable",
        value=str(restorable),
        note="Encrypted mappings available locally",
    )
    _set_metric(
        page,
        2,
        label="AI / MCP access",
        value=str(ai_access),
        note="Local protected copies currently allowed",
    )
    _set_metric(
        page,
        3,
        label="Governance",
        value=("Active" if context.policy is not None else "—"),
        note=f"{policy} · {role}",
    )
