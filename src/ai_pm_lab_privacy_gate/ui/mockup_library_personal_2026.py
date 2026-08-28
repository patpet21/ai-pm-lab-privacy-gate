from __future__ import annotations

from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    document_workspace_label,
)


def _set_metric(page, index: int, *, label: str, value: str, note: str) -> None:
    widgets = getattr(page, "_library_metric_widgets", ())
    if index >= len(widgets):
        return
    title, number, detail = widgets[index]
    title.setText(label)
    number.setText(value)
    detail.setText(note)


def render_personal_library_context(page, context, documents) -> None:
    page._library_final_title.setText("Local Library")
    page._library_final_subtitle.setText(
        "Your private local-first document hub. Protected copies and encrypted restore mappings stay on this PC."
    )
    page._library_final_context_badge.setText(f"PERSONAL · {context.plan_label.upper()}")
    page._library_final_context_badge.setStyleSheet(
        "background:#EEF4FF;color:#2563EB;border:1px solid #D6E4FF;border-radius:9px;"
        "padding:5px 9px;font-size:7.5px;font-weight:900;"
    )

    metadata_map = getattr(page, "_library_workspace_metadata_map", {})
    restorable = sum(1 for document in documents if document.has_mapping)
    ai_access = sum(1 for document in documents if document.mcp_shared)
    legacy = sum(
        1
        for document in documents
        if document_workspace_label(context, metadata_map.get(document.document_id))
        == "Legacy local"
    )

    _set_metric(
        page,
        0,
        label="Documents",
        value=str(len(documents)),
        note="Protected copies in Personal",
    )
    _set_metric(
        page,
        1,
        label="Restorable",
        value=str(restorable),
        note="Encrypted mappings available",
    )
    _set_metric(
        page,
        2,
        label="AI / MCP access",
        value=str(ai_access),
        note="Protected copies currently allowed",
    )
    _set_metric(
        page,
        3,
        label="Workspace",
        value="Personal",
        note=(
            f"{context.plan_label} · {legacy} legacy local item{'s' if legacy != 1 else ''}"
            if legacy
            else f"{context.plan_label} · local-first"
        ),
    )
