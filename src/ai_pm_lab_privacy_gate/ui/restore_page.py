from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository


class RestorePage(QWidget):
    def __init__(self, service: PrivacyGateService, library: LibraryRepository) -> None:
        super().__init__()
        self.service = service
        self.library = library
        self._documents = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(QLabel("Restore an AI result", objectName="PageTitle"))
        root.addWidget(
            QLabel("Paste an AI response containing Privacy Gate placeholders. Real values are restored locally.", objectName="Muted")
        )

        selector = QFrame(objectName="Card")
        selector_layout = QHBoxLayout(selector)
        selector_layout.addWidget(QLabel("Source mapping", objectName="FieldLabel"))
        self.document_combo = QComboBox()
        selector_layout.addWidget(self.document_combo, 1)
        self.load_protected_button = QPushButton("Load protected text", objectName="Secondary")
        selector_layout.addWidget(self.load_protected_button)
        root.addWidget(selector)

        editors = QHBoxLayout()
        input_card = QFrame(objectName="Card")
        input_layout = QVBoxLayout(input_card)
        input_layout.addWidget(QLabel("AI response with placeholders", objectName="SectionTitle"))
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText("Paste the response from ChatGPT or another AI service here.")
        input_layout.addWidget(self.input_text)
        output_card = QFrame(objectName="Card")
        output_layout = QVBoxLayout(output_card)
        output_layout.addWidget(QLabel("Locally restored result", objectName="SectionTitle"))
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        editors.addWidget(input_card, 1)
        editors.addWidget(output_card, 1)
        root.addLayout(editors, 1)

        actions = QHBoxLayout()
        self.restore_button = QPushButton("Restore locally", objectName="Primary")
        self.copy_button = QPushButton("Copy restored result", objectName="Secondary")
        self.download_button = QPushButton("Download restored text", objectName="Gold")
        actions.addWidget(self.restore_button)
        actions.addStretch(1)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.download_button)
        root.addLayout(actions)

        self.restore_button.clicked.connect(self._restore)
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.output_text.toPlainText()))
        self.download_button.clicked.connect(self._download)
        self.load_protected_button.clicked.connect(self._load_protected)

    def refresh(self, select_id: str | None = None) -> None:
        self._documents = tuple(item for item in self.library.list_documents() if item.has_mapping)
        self.document_combo.clear()
        for document in self._documents:
            self.document_combo.addItem(document.title, document.document_id)
        if select_id:
            index = self.document_combo.findData(select_id)
            if index >= 0:
                self.document_combo.setCurrentIndex(index)
        enabled = bool(self._documents)
        self.restore_button.setEnabled(enabled)
        self.load_protected_button.setEnabled(enabled)

    def select_document(self, document_id: str) -> None:
        self.refresh(document_id)

    def _load_protected(self) -> None:
        document_id = self.document_combo.currentData()
        if document_id:
            self.input_text.setPlainText(self.library.get(document_id).protected_text)

    def _restore(self) -> None:
        document_id = self.document_combo.currentData()
        text = self.input_text.toPlainText()
        if not document_id or not text:
            QMessageBox.information(self, "Nothing to restore", "Choose a mapping and paste an AI response.")
            return
        mappings = self.library.get_mappings(document_id)
        missing = [mapping.token for mapping in mappings if mapping.token not in text]
        self.output_text.setPlainText(self.service.restore_text(text, mappings))
        if missing:
            QMessageBox.warning(
                self,
                "Restore completed with warnings",
                f"{len(missing)} mapped placeholder(s) were not present in the supplied result.",
            )

    def _download(self) -> None:
        text = self.output_text.toPlainText()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save restored result", "restored_result.txt", "Text files (*.txt)")
        if path:
            from pathlib import Path

            Path(path if path.lower().endswith(".txt") else path + ".txt").write_text(text, encoding="utf-8")
