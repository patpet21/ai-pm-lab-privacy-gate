from __future__ import annotations

from PySide6.QtWidgets import QInputDialog

from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def install_source_metadata() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_clear = ProtectionPage.clear
    original_browse = ProtectionPage._browse_document
    original_save = ProtectionPage._save_to_library

    def clear(self: ProtectionPage) -> None:
        if hasattr(self, "_external_source_name"):
            delattr(self, "_external_source_name")
        original_clear(self)

    def browse(self: ProtectionPage) -> None:
        if hasattr(self, "_external_source_name"):
            delattr(self, "_external_source_name")
        original_browse(self)

    def save_to_library(self: ProtectionPage):
        if self.current_document is None or self.current_result is None:
            return None
        external = str(getattr(self, "_external_source_name", "") or "").strip()
        if not external:
            return original_save(self)

        title, ok = QInputDialog.getText(
            self,
            "Save to local library",
            "Document title:",
            text=self._derive_title(),
        )
        if not ok:
            return None
        labels = tuple(
            part.strip() for part in self.labels_input.text().split(",") if part.strip()
        )
        document = self.library.save(
            title=title,
            source_kind=self.current_document.source_kind,
            source_name=external,
            profile_key=self.profile_combo.currentData(),
            result=self.current_result,
            labels=labels,
        )
        self.library_changed.emit(document.document_id)
        return document

    ProtectionPage.clear = clear
    ProtectionPage._browse_document = browse
    ProtectionPage._save_to_library = save_to_library
