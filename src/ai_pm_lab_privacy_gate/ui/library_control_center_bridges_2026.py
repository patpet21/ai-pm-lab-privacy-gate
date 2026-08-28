from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.infrastructure.storage.governance_repository import (
    DocumentGovernanceRepository,
)
from ai_pm_lab_privacy_gate.ui import library_control_center_2026 as _control
from ai_pm_lab_privacy_gate.ui import library_document_actions_2026 as _actions
from ai_pm_lab_privacy_gate.ui.restore_page_v2 import RestorePage


_INSTALLED = False


def install_library_control_center_bridges_2026() -> None:
    """Small compatibility bridges for the final Library control-center layer."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # Keep one-click Library -> Restore on the exact same local integrity boundary
    # as manual Restore. This class-level guard is installed before MainWindow is
    # constructed, so every later caller (including the automatic Library flow)
    # resolves the protected implementation.
    previous_restore = RestorePage._restore

    def guarded_restore(self: RestorePage) -> None:
        document_id = str(self.document_combo.currentData() or "")
        if document_id:
            try:
                result = DocumentGovernanceRepository(self.library).verify(document_id)
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Restore blocked by local integrity check",
                    f"PrivacyGate could not verify the selected local restore mapping.\n\n{error}",
                )
                return
            if not result.ok:
                QMessageBox.critical(
                    self,
                    "Restore blocked by local integrity check",
                    result.message,
                )
                return
        previous_restore(self)

    RestorePage._restore = guarded_restore

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
