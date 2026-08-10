from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


class LibraryPage(QWidget):
    restore_requested = Signal(str)

    def __init__(self, library: LibraryRepository) -> None:
        super().__init__()
        self.library = library
        self._documents = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(QLabel("Local library", objectName="PageTitle"))
        root.addWidget(
            QLabel("Protected documents and encrypted restore mappings stored only on this PC.", objectName="Muted")
        )

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by title, source file or label")
        self.favorites_only = QCheckBox("Favorites")
        self.show_trash = QCheckBox("Trash")
        self.refresh_button = QPushButton("Refresh", objectName="Secondary")
        self.backup_button = QPushButton("Backup library", objectName="Secondary")
        self.import_backup_button = QPushButton("Restore backup", objectName="Secondary")
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.favorites_only)
        toolbar.addWidget(self.show_trash)
        toolbar.addWidget(self.backup_button)
        toolbar.addWidget(self.import_backup_button)
        toolbar.addWidget(self.refresh_button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        table_card = QFrame(objectName="Card")
        table_layout = QVBoxLayout(table_card)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["★", "MCP", "Title", "Profile", "Restore", "Updated"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in range(3, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        table_layout.addWidget(self.table)

        preview_card = QFrame(objectName="Card")
        preview_layout = QVBoxLayout(preview_card)
        self.preview_title = QLabel("Select a document", objectName="SectionTitle")
        self.meta = QLabel(objectName="Muted")
        self.meta.setWordWrap(True)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.meta)
        preview_layout.addWidget(self.preview, 1)
        action_row = QHBoxLayout()
        self.copy_button = QPushButton("Copy", objectName="Secondary")
        self.export_button = QPushButton("Export text", objectName="Secondary")
        self.edit_button = QPushButton("Rename / Tags", objectName="Secondary")
        self.favorite_button = QPushButton("Favorite", objectName="Secondary")
        self.mcp_button = QPushButton("Share with MCP", objectName="Secondary")
        self.restore_button = QPushButton("Restore AI result", objectName="Primary")
        self.restore_trash_button = QPushButton("Restore from trash", objectName="Primary")
        self.delete_button = QPushButton("Move to trash", objectName="Danger")
        action_row.addWidget(self.copy_button)
        action_row.addWidget(self.export_button)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.favorite_button)
        action_row.addWidget(self.mcp_button)
        action_row.addStretch(1)
        action_row.addWidget(self.restore_button)
        action_row.addWidget(self.restore_trash_button)
        action_row.addWidget(self.delete_button)
        preview_layout.addLayout(action_row)

        splitter.addWidget(table_card)
        splitter.addWidget(preview_card)
        splitter.setSizes([650, 520])
        root.addWidget(splitter, 1)

        self.search.textChanged.connect(self.refresh)
        self.favorites_only.toggled.connect(self.refresh)
        self.show_trash.toggled.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.backup_button.clicked.connect(self._backup)
        self.import_backup_button.clicked.connect(self._restore_backup)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.copy_button.clicked.connect(self._copy)
        self.export_button.clicked.connect(self._export)
        self.edit_button.clicked.connect(self._edit_metadata)
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.mcp_button.clicked.connect(self._toggle_mcp_share)
        self.restore_button.clicked.connect(self._restore)
        self.restore_trash_button.clicked.connect(self._restore_from_trash)
        self.delete_button.clicked.connect(self._delete)
        self._set_actions(False)

    def refresh(self, *_args) -> None:
        self._documents = self.library.list_documents(
            self.search.text(),
            include_deleted=self.show_trash.isChecked(),
            favorites_only=self.favorites_only.isChecked(),
        )
        self.table.setRowCount(len(self._documents))
        for row, document in enumerate(self._documents):
            favorite = QTableWidgetItem("★" if document.favorite else "")
            favorite.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, favorite)
            mcp_access = QTableWidgetItem("Shared" if document.mcp_shared else "—")
            mcp_access.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, mcp_access)
            title = QTableWidgetItem(document.title)
            title.setData(Qt.ItemDataRole.UserRole, document.document_id)
            self.table.setItem(row, 2, title)
            self.table.setItem(row, 3, QTableWidgetItem(document.profile_key.replace("_", " ").title()))
            self.table.setItem(row, 4, QTableWidgetItem("Yes" if document.has_mapping else "—"))
            self.table.setItem(row, 5, QTableWidgetItem(document.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")))
        if self._documents:
            self.table.selectRow(0)
        else:
            self.preview.clear()
            self.preview_title.setText("No protected documents yet")
            self.meta.setText("Use Save + Copy or Save + Download from the Protect page.")
            self._set_actions(False)

    def select_document(self, document_id: str) -> None:
        self.refresh()
        for row in range(self.table.rowCount()):
            if self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) == document_id:
                self.table.selectRow(row)
                break

    def _current(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        document_id = self.table.item(row, 2).data(Qt.ItemDataRole.UserRole)
        return self.library.get(document_id)

    def _selection_changed(self) -> None:
        document = self._current()
        if document is None:
            self._set_actions(False)
            return
        self.preview_title.setText(document.title)
        labels = ", ".join(document.labels) if document.labels else "No labels"
        self.meta.setText(
            f"{document.source_name}  •  {document.findings_count} findings  •  {labels}  •  {document.replacement_mode}"
        )
        self.preview.setPlainText(document.protected_text)
        self._set_actions(True)
        self.restore_button.setEnabled(document.has_mapping)
        self.favorite_button.setText("Unfavorite" if document.favorite else "Favorite")
        self.mcp_button.setText("Stop MCP sharing" if document.mcp_shared else "Share with MCP")
        trashed = document.deleted_at is not None
        self.copy_button.setEnabled(not trashed)
        self.export_button.setEnabled(not trashed)
        self.edit_button.setEnabled(not trashed)
        self.favorite_button.setEnabled(not trashed)
        self.mcp_button.setEnabled(not trashed)
        self.restore_button.setVisible(not trashed)
        self.restore_trash_button.setVisible(trashed)
        self.delete_button.setText("Delete permanently" if trashed else "Move to trash")

    def _copy(self) -> None:
        document = self._current()
        if document:
            QApplication.clipboard().setText(document.protected_text)

    def _export(self) -> None:
        document = self._current()
        if not document:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export protected document",
            f"{document.title}_protected.txt",
            "Text files (*.txt);;JSON files (*.json)",
        )
        if path:
            if selected_filter.startswith("JSON"):
                destination = Path(path if path.lower().endswith(".json") else path + ".json")
                destination.write_text(
                    json.dumps(
                        {
                            "document_id": document.document_id,
                            "title": document.title,
                            "source": document.source_name,
                            "profile": document.profile_key,
                            "labels": document.labels,
                            "replacement_mode": document.replacement_mode,
                            "protected_text": document.protected_text,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            else:
                Path(path if path.lower().endswith(".txt") else path + ".txt").write_text(document.protected_text, encoding="utf-8")

    def _edit_metadata(self) -> None:
        document = self._current()
        if not document:
            return
        title, ok = QInputDialog.getText(self, "Rename document", "Title:", text=document.title)
        if not ok:
            return
        labels, ok = QInputDialog.getText(
            self,
            "Edit labels",
            "Comma-separated labels:",
            text=", ".join(document.labels),
        )
        if not ok:
            return
        self.library.update_metadata(
            document.document_id,
            title=title,
            labels=tuple(item.strip() for item in labels.split(",") if item.strip()),
        )
        self.select_document(document.document_id)

    def _toggle_favorite(self) -> None:
        document = self._current()
        if document:
            self.library.set_favorite(document.document_id, not document.favorite)
            self.select_document(document.document_id)

    def _toggle_mcp_share(self) -> None:
        document = self._current()
        if not document:
            return
        enable = not document.mcp_shared
        if enable:
            answer = QMessageBox.question(
                self,
                "Share protected copy with MCP",
                "Only this protected copy will become readable through the local MCP server. "
                "Original PII and encrypted restore mappings remain blocked.\n\n"
                "Your connected AI client may send the protected text to its provider. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.library.set_mcp_shared(document.document_id, enable)
        self.select_document(document.document_id)

    def _backup(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create encrypted library backup",
            "AI_PM_LAB_Privacy_Gate_Library.pgbackup",
            "Privacy Gate backup (*.pgbackup)",
        )
        if not path:
            return
        try:
            destination = self.library.create_backup(
                path if path.lower().endswith(".pgbackup") else path + ".pgbackup"
            )
            QMessageBox.information(
                self,
                "Backup created",
                f"Encrypted backup saved to:\n{destination}\n\nIt can be restored only by the same Windows user account.",
            )
        except Exception as error:
            QMessageBox.critical(self, "Backup failed", str(error))

    def _restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore encrypted library backup",
            "",
            "Privacy Gate backup (*.pgbackup)",
        )
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "Restore library backup",
            "Privacy Gate will first create a safety backup, then replace the current library. Continue?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            safety_backup = self.library.restore_backup(path)
            self.refresh()
            QMessageBox.information(
                self,
                "Library restored",
                f"The backup was restored. A safety copy of the previous library is at:\n{safety_backup}",
            )
        except Exception as error:
            QMessageBox.critical(self, "Restore failed", str(error))

    def _restore(self) -> None:
        document = self._current()
        if document:
            self.restore_requested.emit(document.document_id)

    def _delete(self) -> None:
        document = self._current()
        if not document:
            return
        permanent = document.deleted_at is not None
        answer = QMessageBox.question(
            self,
            "Delete permanently" if permanent else "Move document to trash",
            (
                f"Permanently delete ‘{document.title}’ and its encrypted restore mapping? This cannot be undone."
                if permanent
                else f"Move ‘{document.title}’ to the recoverable local trash?"
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            if permanent:
                self.library.delete_permanently(document.document_id)
            else:
                self.library.move_to_trash(document.document_id)
            self.refresh()

    def _restore_from_trash(self) -> None:
        document = self._current()
        if document:
            self.library.restore_from_trash(document.document_id)
            self.refresh()

    def _set_actions(self, enabled: bool) -> None:
        for widget in (
            self.copy_button,
            self.export_button,
            self.edit_button,
            self.favorite_button,
            self.mcp_button,
            self.restore_button,
            self.restore_trash_button,
            self.delete_button,
        ):
            widget.setEnabled(enabled)
        self.restore_trash_button.setVisible(False)
