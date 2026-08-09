from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
        self.refresh_button = QPushButton("Refresh", objectName="Secondary")
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.refresh_button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        table_card = QFrame(objectName="Card")
        table_layout = QVBoxLayout(table_card)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Title", "Profile", "Source", "Findings", "Restore", "Updated"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
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
        self.restore_button = QPushButton("Restore AI result", objectName="Primary")
        self.delete_button = QPushButton("Delete", objectName="Danger")
        action_row.addWidget(self.copy_button)
        action_row.addWidget(self.export_button)
        action_row.addStretch(1)
        action_row.addWidget(self.restore_button)
        action_row.addWidget(self.delete_button)
        preview_layout.addLayout(action_row)

        splitter.addWidget(table_card)
        splitter.addWidget(preview_card)
        splitter.setSizes([650, 520])
        root.addWidget(splitter, 1)

        self.search.textChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.copy_button.clicked.connect(self._copy)
        self.export_button.clicked.connect(self._export)
        self.restore_button.clicked.connect(self._restore)
        self.delete_button.clicked.connect(self._delete)
        self._set_actions(False)

    def refresh(self, *_args) -> None:
        self._documents = self.library.list_documents(self.search.text())
        self.table.setRowCount(len(self._documents))
        for row, document in enumerate(self._documents):
            title = QTableWidgetItem(document.title)
            title.setData(Qt.ItemDataRole.UserRole, document.document_id)
            self.table.setItem(row, 0, title)
            self.table.setItem(row, 1, QTableWidgetItem(document.profile_key.replace("_", " ").title()))
            self.table.setItem(row, 2, QTableWidgetItem(document.source_kind.upper()))
            self.table.setItem(row, 3, QTableWidgetItem(str(document.findings_count)))
            self.table.setItem(row, 4, QTableWidgetItem("Available" if document.has_mapping else "—"))
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
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == document_id:
                self.table.selectRow(row)
                break

    def _current(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        document_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
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

    def _copy(self) -> None:
        document = self._current()
        if document:
            QApplication.clipboard().setText(document.protected_text)

    def _export(self) -> None:
        document = self._current()
        if not document:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export protected text", f"{document.title}_protected.txt", "Text files (*.txt)")
        if path:
            from pathlib import Path

            Path(path if path.lower().endswith(".txt") else path + ".txt").write_text(document.protected_text, encoding="utf-8")

    def _restore(self) -> None:
        document = self._current()
        if document:
            self.restore_requested.emit(document.document_id)

    def _delete(self) -> None:
        document = self._current()
        if not document:
            return
        answer = QMessageBox.question(
            self,
            "Delete local document",
            f"Delete ‘{document.title}’ and its encrypted restore mapping from this PC?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.library.delete(document.document_id)
            self.refresh()

    def _set_actions(self, enabled: bool) -> None:
        for widget in (self.copy_button, self.export_button, self.restore_button, self.delete_button):
            widget.setEnabled(enabled)
