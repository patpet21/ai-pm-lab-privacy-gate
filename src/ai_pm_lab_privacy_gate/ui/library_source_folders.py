from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel

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


def install_library_source_folders() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = LibraryPage.__init__
    original_refresh = LibraryPage.refresh

    def init(self: LibraryPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        bar = QFrame(objectName="LibrarySourceFolders")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(9)
        label = QLabel("Library folders")
        label.setStyleSheet("color:#17384E;font-weight:850;font-size:11px;")
        combo = QComboBox()
        combo.setMinimumWidth(210)
        combo.setMinimumHeight(34)
        combo.addItem("All sources", "")
        combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
            "border-radius:8px;padding:6px 10px;font-weight:700;}"
            "QComboBox:hover{border-color:#8FB8BF;}"
        )
        hint = QLabel("Protected documents stay encrypted locally; folders are an organizational view by connector source.")
        hint.setStyleSheet("color:#61798A;font-size:10px;")
        hint.setWordWrap(True)
        row.addWidget(label)
        row.addWidget(combo)
        row.addWidget(hint, 1)
        bar.setStyleSheet(
            "QFrame#LibrarySourceFolders{background:#F8FBFC;border:1px solid #D7E2EA;border-radius:9px;}"
        )
        root.insertWidget(2, bar)
        self._source_folder_combo = combo
        self._source_folder_bar = bar
        combo.currentIndexChanged.connect(lambda _index: self._apply_source_folder_filter())
        self._sync_source_folders()
        self._apply_source_folder_filter()

    def sync_folders(self: LibraryPage) -> None:
        combo = getattr(self, "_source_folder_combo", None)
        if combo is None:
            return
        selected = str(combo.currentData() or "")
        groups = sorted({_source_group(doc.source_name) for doc in self._documents})
        preferred = [
            "Google Drive",
            "Gmail",
            "ClickUp",
            "Asana",
            "Trello",
            "OneDrive / SharePoint",
            "Notion",
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

    def apply_filter(self: LibraryPage) -> None:
        combo = getattr(self, "_source_folder_combo", None)
        if combo is None:
            return
        selected = str(combo.currentData() or "")
        for row, document in enumerate(self._documents):
            hidden = bool(selected and _source_group(document.source_name) != selected)
            self.table.setRowHidden(row, hidden)
        # Select the first visible row after filtering.
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.selectRow(row)
                break

    def refresh(self: LibraryPage, *args) -> None:
        original_refresh(self, *args)
        if hasattr(self, "_source_folder_combo"):
            self._sync_source_folders()
            self._apply_source_folder_filter()

    LibraryPage.__init__ = init
    LibraryPage.refresh = refresh
    LibraryPage._sync_source_folders = sync_folders  # type: ignore[attr-defined]
    LibraryPage._apply_source_folder_filter = apply_filter  # type: ignore[attr-defined]
