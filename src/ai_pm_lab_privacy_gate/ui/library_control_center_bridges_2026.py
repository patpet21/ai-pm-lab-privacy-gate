from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.infrastructure.storage.governance_repository import (
    DocumentGovernanceRepository,
)
from ai_pm_lab_privacy_gate.ui import library_control_center_2026 as _control
from ai_pm_lab_privacy_gate.ui import library_document_actions_2026 as _actions


_INSTALLED = False


def install_library_control_center_bridges_2026() -> None:
    """Small compatibility bridges for the final Library control-center layer."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # The AI handoff controller intentionally remains authoritative. We only
    # observe the user's accepted Preflight so the metadata-only document timeline
    # can say "Used with AI"; no protected content or destination URL is persisted.
    original_dialog = _actions.LibraryPrivacyPreflightDialog

    class TrackedLibraryPrivacyPreflightDialog(original_dialog):
        def accept(self) -> None:
            page = self.parentWidget()
            if page is not None:
                try:
                    document = page._current()
                    hook = getattr(page, "_library_ai_activity_hook_2026", None)
                    if document is not None and callable(hook):
                        hook(
                            document,
                            SimpleNamespace(
                                label=str(getattr(self.snapshot, "destination", "") or "")
                            ),
                        )
                except Exception:
                    # Activity decoration must never block an approved AI handoff.
                    pass
            super().accept()

    _actions.LibraryPrivacyPreflightDialog = TrackedLibraryPrivacyPreflightDialog

    # If a workspace switch makes a workspace-specific smart collection invalid
    # (Legacy local exists only in Personal; Policy review exists only in managed
    # workspaces), the base layer clears the key. Re-apply filters immediately so
    # the new workspace never appears empty until a second refresh.
    original_counts = _control._update_smart_counts

    def update_smart_counts(page) -> None:
        before = str(getattr(page, "_library_smart_collection_2026", "") or "")
        original_counts(page)
        after = str(getattr(page, "_library_smart_collection_2026", "") or "")
        if before and not after:
            try:
                page._apply_library_final_filters()
            except Exception:
                pass

    _control._update_smart_counts = update_smart_counts


def apply_library_control_center_bridges_2026(main_window) -> None:
    """Keep automatic Library -> Restore on the same integrity boundary as manual Restore."""
    restore_page = getattr(main_window, "restore_page", None)
    library = getattr(main_window, "library", None)
    if (
        restore_page is None
        or library is None
        or bool(getattr(restore_page, "_library_auto_restore_integrity_2026", False))
    ):
        return

    restore_page._library_auto_restore_integrity_2026 = True
    repository = DocumentGovernanceRepository(library)
    previous_restore = restore_page._restore

    def guarded_restore() -> None:
        document_id = str(restore_page.document_combo.currentData() or "")
        if document_id:
            try:
                result = repository.verify(document_id)
            except Exception as error:
                QMessageBox.critical(
                    restore_page,
                    "Restore blocked by local integrity check",
                    f"PrivacyGate could not verify the selected local restore mapping.\n\n{error}",
                )
                return
            if not result.ok:
                QMessageBox.critical(
                    restore_page,
                    "Restore blocked by local integrity check",
                    result.message,
                )
                return
        previous_restore()

    # Direct Library restore resolves this instance attribute when it starts the
    # worker, so the one-click flow can stay automatic without bypassing governance.
    restore_page._restore = guarded_restore
