from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.security.temporary_workspace import (
    cleanup_stale_managed_sessions,
    delete_managed_path,
    is_managed_path,
    mark_for_cleanup,
    retry_pending_cleanup,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _source_path(page: ProtectionPage) -> Path | None:
    document = getattr(page, "current_document", None)
    path = getattr(document, "source_path", None) if document is not None else None
    if path and is_managed_path(path):
        return Path(path)
    try:
        pending = page.pdf_path.text().strip()
    except Exception:
        pending = ""
    if pending and is_managed_path(pending):
        return Path(pending)
    return None


def install_automatic_temp_cleanup() -> None:
    """Attach automatic cleanup only to PrivacyGate-owned temporary sources.

    User-selected local files, Library data, Restore mappings and connector/MCP
    credentials are outside the managed temp root and cannot be deleted here.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # Only the new managed workspace is eligible. Historical legacy temp folders
    # are deliberately left untouched so users can inspect/remove them once.
    cleanup_stale_managed_sessions()

    previous_save = ProtectionPage._save_to_library
    previous_save_copy = ProtectionPage._save_and_copy
    previous_save_download = ProtectionPage._save_and_download
    previous_clear = ProtectionPage.clear

    def save_to_library(self: ProtectionPage):
        # Record success, but do not delete yet: Save+Download still needs the
        # source file to generate the protected output after the Library commit.
        self._managed_temp_saved_ok = False
        self._managed_temp_saved_path = _source_path(self)
        document = previous_save(self)
        if document is not None:
            self._managed_temp_saved_ok = True
        return document

    def _cleanup_after_completed_save(self: ProtectionPage) -> None:
        if not getattr(self, "_managed_temp_saved_ok", False):
            return
        path = getattr(self, "_managed_temp_saved_path", None)
        if path and is_managed_path(path):
            # Qt may still hold the original PDF open for the comparison preview.
            # Try now; if Windows refuses, queue it for Clear/Quit instead of
            # breaking the live preview or touching an unrelated user file.
            if not delete_managed_path(path):
                mark_for_cleanup(path)
        retry_pending_cleanup()

    def save_and_copy(self: ProtectionPage) -> None:
        self._managed_temp_saved_ok = False
        self._managed_temp_saved_path = _source_path(self)
        previous_save_copy(self)
        _cleanup_after_completed_save(self)

    def save_and_download(self: ProtectionPage) -> None:
        self._managed_temp_saved_ok = False
        self._managed_temp_saved_path = _source_path(self)
        previous_save_download(self)
        _cleanup_after_completed_save(self)

    def clear(self: ProtectionPage) -> None:
        path = _source_path(self)
        previous_clear(self)
        if path:
            delete_managed_path(path)
        retry_pending_cleanup()

    ProtectionPage._save_to_library = save_to_library  # type: ignore[method-assign]
    ProtectionPage._save_and_copy = save_and_copy  # type: ignore[method-assign]
    ProtectionPage._save_and_download = save_and_download  # type: ignore[method-assign]
    ProtectionPage.clear = clear  # type: ignore[method-assign]
