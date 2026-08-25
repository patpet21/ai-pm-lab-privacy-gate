from __future__ import annotations

from collections import OrderedDict

from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage


_INSTALLED = False
_LOCAL_FILES = "__local_files__"
_LOCAL_TEXT = "__local_text__"
_LEGACY_PREFIX = "__legacy_provider__:"


def _source_group(source_name: str) -> str:
    value = (source_name or "").strip()
    if " • " in value:
        provider = value.split(" • ", 1)[0].strip()
        if provider:
            return provider
    if value.lower() == "pasted text":
        return "Local / pasted text"
    return "Local files"


def _legacy_account_label(source_name: str) -> str:
    parts = [part.strip() for part in (source_name or "").split(" • ") if part.strip()]
    # New connector source_name values include Provider • Account • Item. Old
    # connector documents used Provider • Item and therefore cannot reliably
    # reveal which account supplied them.
    return parts[1] if len(parts) >= 3 else ""


def _connected_apps_service(page: LibraryPage):
    """Use the existing connection service; never create or reconnect anything."""
    try:
        window = page.window()
    except Exception:
        return None
    cloud_page = getattr(window, "cloud_automation_page", None)
    return getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None


def _provider_catalog(service) -> dict[str, str]:
    catalog = getattr(service, "PROVIDERS", None) if service is not None else None
    if not isinstance(catalog, dict):
        catalog = ConnectedAppsService.PROVIDERS
    return {str(key): str(value) for key, value in catalog.items()}


def _provider_from_label(service, label: str) -> str:
    needle = label.strip().casefold()
    for provider, display in _provider_catalog(service).items():
        if display.strip().casefold() == needle:
            return provider
    return ""


def install_library_source_folders() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = LibraryPage.__init__
    original_refresh = LibraryPage.refresh

    def init(self: LibraryPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self._source_metadata_repository = DocumentSourceMetadataRepository(self.library.db_path)
        self._source_metadata_map = self._source_metadata_repository.list_for_documents(
            [document.document_id for document in self._documents]
        )

        root = self.layout()
        bar = QFrame(objectName="LibrarySourceNavigator")
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(13, 10, 13, 10)
        outer.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)
        heading = QLabel("Browse library")
        heading.setStyleSheet("color:#17384E;font-weight:900;font-size:12px;")
        count_badge = QLabel()
        count_badge.setObjectName("LibrarySourceCount")
        count_badge.setStyleSheet(
            "QLabel#LibrarySourceCount{background:#EAF5F6;color:#0B7180;border:1px solid #C5E0E3;"
            "border-radius:9px;padding:3px 8px;font-size:9px;font-weight:850;}"
        )
        auto_hint = QLabel("Connected sources and accounts appear automatically")
        auto_hint.setStyleSheet("color:#61798A;font-size:9px;")
        header.addWidget(heading)
        header.addWidget(count_badge)
        header.addStretch(1)
        header.addWidget(auto_hint)
        outer.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        source_label = QLabel("Source")
        source_label.setStyleSheet("color:#61798A;font-size:9px;font-weight:800;")
        source_combo = QComboBox()
        source_combo.setMinimumWidth(220)
        source_combo.setMinimumHeight(36)

        account_label = QLabel("Account")
        account_label.setStyleSheet("color:#61798A;font-size:9px;font-weight:800;")
        account_combo = QComboBox()
        account_combo.setMinimumWidth(260)
        account_combo.setMinimumHeight(36)

        reset = QPushButton("Show all")
        reset.setMinimumHeight(34)
        reset.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#365469;border:1px solid #C9D7E1;"
            "border-radius:8px;padding:6px 11px;font-size:9px;font-weight:800;}"
            "QPushButton:hover{background:#F3F8FA;border-color:#9EBBC7;}"
        )

        combo_style = (
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
            "border-radius:8px;padding:6px 10px;font-weight:750;}"
            "QComboBox:hover{border-color:#8FB8BF;}"
            "QComboBox:focus{border-color:#1595A3;}"
            "QComboBox:disabled{background:#F2F5F7;color:#8A9BA7;}"
        )
        source_combo.setStyleSheet(combo_style)
        account_combo.setStyleSheet(combo_style)

        filters.addWidget(source_label)
        filters.addWidget(source_combo)
        filters.addSpacing(6)
        filters.addWidget(account_label)
        filters.addWidget(account_combo)
        filters.addWidget(reset)
        filters.addStretch(1)
        outer.addLayout(filters)

        bar.setStyleSheet(
            "QFrame#LibrarySourceNavigator{background:#F8FBFC;border:1px solid #D7E2EA;border-radius:10px;}"
        )
        root.insertWidget(2, bar)

        self._source_folder_combo = source_combo
        self._source_account_combo = account_combo
        self._source_folder_bar = bar
        self._source_count_badge = count_badge
        self._source_reset_button = reset

        source_combo.currentIndexChanged.connect(
            lambda _index: self._source_folder_changed()
        )
        account_combo.currentIndexChanged.connect(
            lambda _index: self._apply_source_folder_filter()
        )
        reset.clicked.connect(lambda _checked=False: self._reset_source_filters())
        self._sync_source_folders()
        self._sync_source_accounts()
        self._apply_source_folder_filter()

    def source_for_document(self: LibraryPage, document) -> tuple[str, str]:
        metadata = getattr(self, "_source_metadata_map", {}).get(document.document_id)
        if metadata is not None and metadata.provider.strip():
            return metadata.provider.strip(), metadata.provider_label.strip() or metadata.provider.strip()

        group = _source_group(document.source_name)
        if group == "Local files":
            return _LOCAL_FILES, group
        if group == "Local / pasted text":
            return _LOCAL_TEXT, group

        service = _connected_apps_service(self)
        provider = _provider_from_label(service, group)
        if provider:
            return provider, group
        return f"{_LEGACY_PREFIX}{group.casefold()}", group

    def account_for_document(self: LibraryPage, document) -> tuple[str, str]:
        metadata = getattr(self, "_source_metadata_map", {}).get(document.document_id)
        if metadata is not None:
            if metadata.account_id.strip():
                display = metadata.account_label.strip() or "Connected account"
                return f"id:{metadata.account_id.strip()}", display
            if metadata.account_label.strip():
                value = metadata.account_label.strip()
                return f"label:{value.casefold()}", value

        fallback = _legacy_account_label(document.source_name)
        if fallback:
            return f"label:{fallback.casefold()}", fallback

        source_key, _source_label = self._source_for_document(document)
        if source_key in {_LOCAL_FILES, _LOCAL_TEXT}:
            return "", ""
        return "__legacy__", "Legacy / unknown account"

    def connected_sources(self: LibraryPage) -> OrderedDict[str, str]:
        service = _connected_apps_service(self)
        result: OrderedDict[str, str] = OrderedDict()
        if service is None:
            return result
        for provider, display in _provider_catalog(service).items():
            try:
                connected = bool(service.is_connected(provider))
            except Exception:
                connected = False
            if connected:
                result[provider] = display
        return result

    def source_documents(self: LibraryPage) -> dict[str, int]:
        counts: dict[str, int] = {}
        for document in self._documents:
            key, _label = self._source_for_document(document)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def sync_folders(self: LibraryPage) -> None:
        combo = getattr(self, "_source_folder_combo", None)
        if combo is None:
            return
        selected = str(combo.currentData() or "")
        connected = self._connected_sources()
        counts = self._source_documents()

        labels: OrderedDict[str, str] = OrderedDict(connected)
        for document in self._documents:
            key, label = self._source_for_document(document)
            labels.setdefault(key, label)

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All sources", "")
        for key, label in labels.items():
            count = counts.get(key, 0)
            if count:
                text = f"{label}   ·   {count}"
            elif key in connected:
                text = f"{label}   ·   connected"
            else:
                text = label
            combo.addItem(text, key)

        target = combo.findData(selected)
        combo.setCurrentIndex(target if target >= 0 else 0)
        combo.blockSignals(False)
        badge = getattr(self, "_source_count_badge", None)
        if badge is not None:
            total = len(self._documents)
            badge.setText(f"{total} protected item{'s' if total != 1 else ''}")

    def connected_accounts(self: LibraryPage, provider: str) -> OrderedDict[str, str]:
        result: OrderedDict[str, str] = OrderedDict()
        service = _connected_apps_service(self)
        if service is None or not provider or provider.startswith(_LEGACY_PREFIX):
            return result
        if provider in {_LOCAL_FILES, _LOCAL_TEXT}:
            return result
        try:
            if not hasattr(service, "list_connected_accounts"):
                return result
            for account in service.list_connected_accounts(provider):
                account_id = str(getattr(account, "account_id", "") or "").strip()
                if not account_id:
                    continue
                label = str(getattr(account, "label", "") or "").strip()
                subtitle = str(getattr(account, "subtitle", "") or "").strip()
                result[f"id:{account_id}"] = label or subtitle or "Connected account"
        except Exception:
            return result
        return result

    def sync_accounts(self: LibraryPage) -> None:
        combo = getattr(self, "_source_account_combo", None)
        source_combo = getattr(self, "_source_folder_combo", None)
        if combo is None or source_combo is None:
            return
        selected_source = str(source_combo.currentData() or "")
        previous = str(combo.currentData() or "")

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All accounts", "")

        if not selected_source or selected_source in {_LOCAL_FILES, _LOCAL_TEXT}:
            combo.setCurrentIndex(0)
            combo.setEnabled(False)
            combo.blockSignals(False)
            return

        accounts: OrderedDict[str, str] = self._connected_accounts(selected_source)
        account_counts: dict[str, int] = {}
        for document in self._documents:
            document_source, _display = self._source_for_document(document)
            if document_source != selected_source:
                continue
            key, display = self._account_for_document(document)
            if key and display:
                accounts.setdefault(key, display)
                account_counts[key] = account_counts.get(key, 0) + 1

        for key, display in accounts.items():
            count = account_counts.get(key, 0)
            text = f"{display}   ·   {count}" if count else f"{display}   ·   connected"
            combo.addItem(text, key)

        target = combo.findData(previous)
        combo.setCurrentIndex(target if target >= 0 else 0)
        combo.setEnabled(bool(accounts))
        combo.blockSignals(False)

    def source_changed(self: LibraryPage) -> None:
        self._sync_source_accounts()
        self._apply_source_folder_filter()

    def reset_filters(self: LibraryPage) -> None:
        source_combo = getattr(self, "_source_folder_combo", None)
        account_combo = getattr(self, "_source_account_combo", None)
        if source_combo is None or account_combo is None:
            return
        source_combo.setCurrentIndex(0)
        account_combo.setCurrentIndex(0)
        self._apply_source_folder_filter()

    def apply_filter(self: LibraryPage) -> None:
        source_combo = getattr(self, "_source_folder_combo", None)
        account_combo = getattr(self, "_source_account_combo", None)
        if source_combo is None or account_combo is None:
            return
        selected_source = str(source_combo.currentData() or "")
        selected_account = str(account_combo.currentData() or "")

        first_visible = -1
        for row, document in enumerate(self._documents):
            document_source, _source_display = self._source_for_document(document)
            document_account, _account_display = self._account_for_document(document)
            hidden = bool(selected_source and document_source != selected_source)
            if not hidden and selected_account:
                hidden = document_account != selected_account
            self.table.setRowHidden(row, hidden)
            if not hidden and first_visible < 0:
                first_visible = row

        if first_visible >= 0:
            self.table.selectRow(first_visible)
            return

        if selected_source:
            self.table.clearSelection()
            self.preview.clear()
            self.preview_title.setText("No protected documents in this view")
            self.meta.setText(
                "This source/account is available, but no protected Library item matches the current filter yet."
            )
            self._set_actions(False)

    def refresh(self: LibraryPage, *args) -> None:
        original_refresh(self, *args)
        if not hasattr(self, "_source_metadata_repository"):
            return
        # Re-create this lightweight local helper after every Library refresh.
        # This also recreates its optional table after restoring an older backup
        # that predates structured source provenance.
        repository = DocumentSourceMetadataRepository(self.library.db_path)
        self._source_metadata_repository = repository
        self._source_metadata_map = repository.list_for_documents(
            [document.document_id for document in self._documents]
        )
        if hasattr(self, "_source_folder_combo"):
            self._sync_source_folders()
            self._sync_source_accounts()
            self._apply_source_folder_filter()

    LibraryPage.__init__ = init
    LibraryPage.refresh = refresh
    LibraryPage._source_for_document = source_for_document  # type: ignore[attr-defined]
    LibraryPage._account_for_document = account_for_document  # type: ignore[attr-defined]
    LibraryPage._connected_sources = connected_sources  # type: ignore[attr-defined]
    LibraryPage._source_documents = source_documents  # type: ignore[attr-defined]
    LibraryPage._connected_accounts = connected_accounts  # type: ignore[attr-defined]
    LibraryPage._sync_source_folders = sync_folders  # type: ignore[attr-defined]
    LibraryPage._sync_source_accounts = sync_accounts  # type: ignore[attr-defined]
    LibraryPage._source_folder_changed = source_changed  # type: ignore[attr-defined]
    LibraryPage._reset_source_filters = reset_filters  # type: ignore[attr-defined]
    LibraryPage._apply_source_folder_filter = apply_filter  # type: ignore[attr-defined]
