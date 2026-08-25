from __future__ import annotations

from PySide6.QtWidgets import QInputDialog

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _clear_external_source(page: ProtectionPage) -> None:
    for attribute in ("_external_source_name", "_external_source_metadata"):
        if hasattr(page, attribute):
            delattr(page, attribute)


def install_source_metadata() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_clear = ProtectionPage.clear
    original_browse = ProtectionPage._browse_document
    original_save = ProtectionPage._save_to_library

    def clear(self: ProtectionPage) -> None:
        _clear_external_source(self)
        original_clear(self)

    def browse(self: ProtectionPage) -> None:
        _clear_external_source(self)
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

        metadata = dict(getattr(self, "_external_source_metadata", {}) or {})
        provider = str(metadata.get("provider", "") or "").strip()
        if provider:
            try:
                DocumentSourceMetadataRepository(self.library.db_path).upsert(
                    document_id=document.document_id,
                    provider=provider,
                    provider_label=str(metadata.get("provider_label", "") or provider),
                    account_id=str(metadata.get("account_id", "") or ""),
                    account_label=str(metadata.get("account_label", "") or ""),
                    item_id=str(metadata.get("item_id", "") or ""),
                    item_title=str(metadata.get("item_title", "") or ""),
                    item_kind=str(metadata.get("item_kind", "") or ""),
                )
            except Exception:
                # Provenance metadata must never make a successful local Library
                # save fail. The protected document and restore mapping are the
                # primary durable records; metadata can be rebuilt/fixed later.
                pass

        # The automatic managed-temp wrapper runs outside this method. Mark a
        # successful external-source save so Save+Copy/Save+Download can release
        # the PrivacyGate-owned working file immediately after the operation.
        if hasattr(self, "_managed_temp_saved_ok"):
            self._managed_temp_saved_ok = True

        self.library_changed.emit(document.document_id)
        return document

    ProtectionPage.clear = clear
    ProtectionPage._browse_document = browse
    ProtectionPage._save_to_library = save_to_library
