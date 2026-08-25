from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QInputDialog

from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _clear_external_source(page: ProtectionPage) -> None:
    for attribute in ("_external_source_name", "_external_source_metadata"):
        if hasattr(page, attribute):
            delattr(page, attribute)


def _connected_apps_service(page: ProtectionPage):
    """Return the already-created connector service without changing connector state."""
    try:
        window = page.window()
    except Exception:
        return None
    cloud_page = getattr(window, "cloud_automation_page", None)
    return getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None


def _provider_from_label(service, provider_label: str) -> str:
    label = provider_label.strip().casefold()
    catalog = getattr(service, "PROVIDERS", None) if service is not None else None
    if not isinstance(catalog, dict):
        catalog = ConnectedAppsService.PROVIDERS
    for provider, display in catalog.items():
        if str(display).strip().casefold() == label:
            return str(provider)
    return ""


def _active_account(service, provider: str) -> tuple[str, str]:
    """Resolve the selected account only from the local account registry.

    No provider request is made here.  This keeps Library saves fast and avoids
    changing any existing connector/OAuth behavior.
    """
    if service is None or not provider:
        return "", ""
    active_id = ""
    try:
        if hasattr(service, "active_account_id"):
            active_id = str(service.active_account_id(provider) or "")
    except Exception:
        active_id = ""
    if not active_id:
        return "", ""

    try:
        if hasattr(service, "list_connected_accounts"):
            for account in service.list_connected_accounts(provider):
                if str(getattr(account, "account_id", "") or "") != active_id:
                    continue
                label = str(getattr(account, "label", "") or "").strip()
                subtitle = str(getattr(account, "subtitle", "") or "").strip()
                return active_id, label or subtitle
    except Exception:
        pass
    return active_id, ""


def resolve_external_source(
    page: ProtectionPage,
    external: str,
    supplied_metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str]]:
    """Normalize connector provenance for every current/future connected source.

    Existing connector-specific metadata wins.  Otherwise the provider is
    inferred from the provider catalog and the account is read from the local
    multi-account registry.  Import/browser functions do not need to change.
    """
    metadata = dict(supplied_metadata or {})
    parts = [part.strip() for part in external.split(" • ") if part.strip()]
    service = _connected_apps_service(page)

    provider = str(metadata.get("provider", "") or "").strip()
    provider_label = str(metadata.get("provider_label", "") or "").strip()
    if not provider_label and parts:
        provider_label = parts[0]
    if not provider and provider_label:
        provider = _provider_from_label(service, provider_label)
    if provider and not provider_label:
        try:
            provider_label = str(service.provider_name(provider)) if service is not None else ""
        except Exception:
            provider_label = ""
        provider_label = provider_label or str(ConnectedAppsService.provider_name(provider))

    account_id = str(metadata.get("account_id", "") or "").strip()
    account_label = str(metadata.get("account_label", "") or "").strip()
    if provider and (not account_id or not account_label):
        resolved_id, resolved_label = _active_account(service, provider)
        account_id = account_id or resolved_id
        account_label = account_label or resolved_label

    item_title = str(metadata.get("item_title", "") or "").strip()
    if not item_title:
        if len(parts) >= 3 and account_label and parts[1].casefold() == account_label.casefold():
            item_title = " • ".join(parts[2:])
        elif len(parts) >= 2:
            item_title = " • ".join(parts[1:])
        elif parts:
            item_title = parts[-1]

    item_kind = str(metadata.get("item_kind", "") or "").strip()
    if not item_kind:
        document = getattr(page, "current_document", None)
        item_kind = str(getattr(document, "source_kind", "") or "")

    normalized = {
        "provider": provider,
        "provider_label": provider_label,
        "account_id": account_id,
        "account_label": account_label,
        "item_id": str(metadata.get("item_id", "") or "").strip(),
        "item_title": item_title,
        "item_kind": item_kind,
    }

    source_name_parts = [provider_label] if provider_label else []
    if account_label:
        source_name_parts.append(account_label)
    if item_title:
        source_name_parts.append(item_title)
    canonical_name = " • ".join(source_name_parts) or external
    return canonical_name, normalized


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

        source_name, metadata = resolve_external_source(
            self,
            external,
            dict(getattr(self, "_external_source_metadata", {}) or {}),
        )

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
            source_name=source_name,
            profile_key=self.profile_combo.currentData(),
            result=self.current_result,
            labels=labels,
        )

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
