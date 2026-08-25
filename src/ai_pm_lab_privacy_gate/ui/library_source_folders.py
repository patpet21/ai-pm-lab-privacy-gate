from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage


_INSTALLED = False


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
        bar = QFrame(objectName="LibrarySourceFolders")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(9)

        label = QLabel("Library folders")
        label.setStyleSheet("color:#17384E;font-weight:850;font-size:11px;")

        source_label = QLabel("Source")
        source_label.setStyleSheet("color:#61798A;font-size:10px;font-weight:700;")
        source_combo = QComboBox()
        source_combo.setMinimumWidth(180)
        source_combo.setMinimumHeight(34)

        account_label = QLabel("Account")
        account_label.setStyleSheet("color:#61798A;font-size:10px;font-weight:700;")
        account_combo = QComboBox()
        account_combo.setMinimumWidth(220)
        account_combo.setMinimumHeight(34)
        account_combo.setEnabled(False)

        combo_style = (
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
            "border-radius:8px;padding:6px 10px;font-weight:700;}"
            "QComboBox:hover{border-color:#8FB8BF;}"
            "QComboBox:disabled{background:#F2F5F7;color:#8A9BA7;}"
        )
        source_combo.setStyleSheet(combo_style)
        account_combo.setStyleSheet(combo_style)

        hint = QLabel(
            "Organize protected Library items by connector and the connected account that supplied them."
        )
        hint.setStyleSheet("color:#61798A;font-size:10px;")
        hint.setWordWrap(True)

        row.addWidget(label)
        row.addWidget(source_label)
        row.addWidget(source_combo)
        row.addWidget(account_label)
        row.addWidget(account_combo)
        row.addWidget(hint, 1)
        bar.setStyleSheet(
            "QFrame#LibrarySourceFolders{background:#F8FBFC;border:1px solid #D7E2EA;border-radius:9px;}"
        )
        root.insertWidget(2, bar)

        self._source_folder_combo = source_combo
        self._source_account_combo = account_combo
        self._source_folder_bar = bar

        source_combo.currentIndexChanged.connect(
            lambda _index: self._source_folder_changed()
        )
        account_combo.currentIndexChanged.connect(
            lambda _index: self._apply_source_folder_filter()
        )
        self._sync_source_folders()
        self._sync_source_accounts()
        self._apply_source_folder_filter()

    def source_for_document(self: LibraryPage, document) -> str:
        metadata = getattr(self, "_source_metadata_map", {}).get(document.document_id)
        if metadata is not None and metadata.provider_label.strip():
            return metadata.provider_label.strip()
        return _source_group(document.source_name)

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

        source = self._source_for_document(document)
        if source in {"Local files", "Local / pasted text"}:
            return "", ""
        return "__legacy__", "Legacy / unknown account"

    def sync_folders(self: LibraryPage) -> None:
        combo = getattr(self, "_source_folder_combo", None)
        if combo is None:
            return
        selected = str(combo.currentData() or "")
        groups = sorted({self._source_for_document(doc) for doc in self._documents})
        preferred = [
            "Google Drive",
            "Gmail",
            "ClickUp",
            "Asana",
            "Trello",
            "monday.com",
            "Jira",
            "Notion",
            "OneDrive / SharePoint",
            "Dropbox",
            "Slack",
            "Local files",
            "Local / pasted text",
        ]
        ordered = [item for item in preferred if item in groups]
        ordered.extend(item for item in groups if item not in ordered)
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All sources", "")
        for group in ordered:
            combo.addItem(group, group)
        target = combo.findData(selected)
        combo.setCurrentIndex(target if target >= 0 else 0)
        combo.blockSignals(False)

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

        if not selected_source:
            combo.setCurrentIndex(0)
            combo.setEnabled(False)
            combo.blockSignals(False)
            return

        accounts: dict[str, str] = {}
        for document in self._documents:
            if self._source_for_document(document) != selected_source:
                continue
            key, display = self._account_for_document(document)
            if key and display:
                accounts.setdefault(key, display)

        for key, display in sorted(accounts.items(), key=lambda item: item[1].casefold()):
            combo.addItem(display, key)

        target = combo.findData(previous)
        combo.setCurrentIndex(target if target >= 0 else 0)
        combo.setEnabled(bool(accounts))
        combo.blockSignals(False)

    def source_changed(self: LibraryPage) -> None:
        self._sync_source_accounts()
        self._apply_source_folder_filter()

    def apply_filter(self: LibraryPage) -> None:
        source_combo = getattr(self, "_source_folder_combo", None)
        account_combo = getattr(self, "_source_account_combo", None)
        if source_combo is None or account_combo is None:
            return
        selected_source = str(source_combo.currentData() or "")
        selected_account = str(account_combo.currentData() or "")

        for row, document in enumerate(self._documents):
            document_source = self._source_for_document(document)
            document_account, _display = self._account_for_document(document)
            hidden = bool(selected_source and document_source != selected_source)
            if not hidden and selected_account:
                hidden = document_account != selected_account
            self.table.setRowHidden(row, hidden)

        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.selectRow(row)
                break

    def refresh(self: LibraryPage, *args) -> None:
        original_refresh(self, *args)
        repository = getattr(self, "_source_metadata_repository", None)
        if repository is None:
            return
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
    LibraryPage._sync_source_folders = sync_folders  # type: ignore[attr-defined]
    LibraryPage._sync_source_accounts = sync_accounts  # type: ignore[attr-defined]
    LibraryPage._source_folder_changed = source_changed  # type: ignore[attr-defined]
    LibraryPage._apply_source_folder_filter = apply_filter  # type: ignore[attr-defined]
