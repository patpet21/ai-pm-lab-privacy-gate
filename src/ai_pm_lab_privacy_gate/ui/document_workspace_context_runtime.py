from __future__ import annotations

"""Attach the active PrivacyGate workspace to new Library items locally.

Installed after the branded Library save runtime. It wraps the existing save
method rather than replacing any save/protection semantics.
"""

from ai_pm_lab_privacy_gate.infrastructure.storage.document_workspace_metadata import (
    DocumentWorkspaceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _active_workspace(page: ProtectionPage) -> tuple[str, str, bool]:
    try:
        main_window = page.window()
        sidebar = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
        context = sidebar._workspace_context() if sidebar is not None else None
        if context is None:
            return "personal", "Personal", True
        descriptor = context.workspaces.get(context.active_key)
        if descriptor is None:
            return str(context.active_key or "personal"), "Personal", True
        return (
            str(context.active_key or "personal"),
            "Personal" if descriptor.personal else str(descriptor.name or "Organization"),
            bool(descriptor.personal),
        )
    except Exception:
        return "personal", "Personal", True


def install_document_workspace_context_runtime() -> None:
    """Record workspace context only after the existing local save succeeds."""

    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_save = ProtectionPage._save_to_library

    def save_with_workspace(self: ProtectionPage):
        document = previous_save(self)
        if document is None:
            return None
        try:
            workspace_key, workspace_name, personal = _active_workspace(self)
            DocumentWorkspaceMetadataRepository(self.library.db_path).upsert(
                document_id=document.document_id,
                workspace_key=workspace_key,
                workspace_name=workspace_name,
                personal=personal,
            )
        except Exception:
            # Workspace enrichment must never invalidate a successful local save.
            pass
        return document

    ProtectionPage._save_to_library = save_with_workspace  # type: ignore[method-assign]
