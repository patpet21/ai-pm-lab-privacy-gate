from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QStackedWidget, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.documents.office_preview import OfficePreviewRenderer
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.restore_service import (
    DocumentRestoreService, RestoreReport, TOKEN_PATTERN,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui.office_internal_preview import OfficeInternalPreview


class RestorePage(QWidget):
    """Restore AI-modified protected results without sending mappings off-device."""

    TOKEN_COLORS = PdfDocumentService.ENTITY_COLORS
    FILE_FILTER = (
        "Supported protected results (*.txt *.pdf *.docx *.xlsx);;"
        "Text files (*.txt);;PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx)"
    )

    def __init__(self, service: PrivacyGateService, library: LibraryRepository) -> None:
        super().__init__()
        self.service = service
        self.library = library
        self.restore_service = DocumentRestoreService()
        self.office_renderer = OfficePreviewRenderer()
        self._libreoffice_available = self.office_renderer.find_executable() is not None
        self._documents = ()
        self._source_path: Path | None = None
        self._restored_path: Path | None = None
        self._report: RestoreReport | None = None
        self._preview_root = Path(tempfile.gettempdir()) / f"AI_PM_LAB_Restore_{os.getpid()}"
        self._preview_root.mkdir(parents=True, exist_ok=True)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(10)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(QLabel("Restore an AI result", objectName="PageTitle"))
        titles.addWidget(QLabel(
            "Load a protected TXT, PDF, Word or Excel result, then restore its real values locally.",
            objectName="Muted",
        ))
        heading.addLayout(titles)
        heading.addStretch(1)
        heading.addWidget(QLabel("LOCAL  |  Restore mapping never leaves this PC", objectName="StatusBadge"))
        root.addLayout(heading)

        setup = QFrame(objectName="Card")
        setup_layout = QHBoxLayout(setup)
        setup_layout.setContentsMargins(12, 10, 12, 10)
        upload_column = QVBoxLayout()
        upload_heading = QHBoxLayout()
        upload_heading.addWidget(QLabel("1. AI result with placeholders", objectName="FieldLabel"))
        upload_heading.addWidget(self._info_button(
            "AI result file",
            "Choose the protected TXT, PDF, DOCX or XLSX returned by an AI. It must retain the Privacy Gate placeholders exactly.",
        ))
        upload_heading.addStretch(1)
        upload_column.addLayout(upload_heading)
        upload_row = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.source_path.setPlaceholderText("Choose A protected + Analysis.txt/.pdf/.docx/.xlsx")
        self.browse_button = QPushButton("Browse result", objectName="Secondary")
        upload_row.addWidget(self.source_path, 1)
        upload_row.addWidget(self.browse_button)
        upload_column.addLayout(upload_row)
        setup_layout.addLayout(upload_column, 1)

        mapping_column = QVBoxLayout()
        mapping_heading = QHBoxLayout()
        mapping_heading.addWidget(QLabel("2. Original protection mapping", objectName="FieldLabel"))
        mapping_heading.addWidget(self._info_button(
            "Local source mapping",
            "Choose the Library entry that originally created these placeholders. Only its encrypted local mapping is used; the original document is not uploaded.",
        ))
        mapping_heading.addStretch(1)
        mapping_column.addLayout(mapping_heading)
        mapping_row = QHBoxLayout()
        self.document_combo = QComboBox()
        self.load_protected_button = QPushButton("Load Library text", objectName="Secondary")
        mapping_row.addWidget(self.document_combo, 1)
        mapping_row.addWidget(self.load_protected_button)
        mapping_column.addLayout(mapping_row)
        setup_layout.addLayout(mapping_column, 1)
        root.addWidget(setup)

        status_bar = QFrame(objectName="Card")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 7, 12, 7)
        self.format_label = QLabel("No result loaded", objectName="Metric")
        self.mapping_label = QLabel("Choose a source mapping", objectName="Metric")
        self.restore_status = QLabel("Ready", objectName="Muted")
        self.restore_button = QPushButton("Restore locally", objectName="Primary")
        status_layout.addWidget(self.format_label)
        status_layout.addWidget(self.mapping_label)
        status_layout.addWidget(self.restore_status, 1)
        status_layout.addWidget(self.restore_button)
        root.addWidget(status_bar)

        self.preview_tabs = QTabWidget()
        self._build_text_tab()
        self._build_document_tab()
        root.addWidget(self.preview_tabs, 1)

        actions = QFrame(objectName="ActionBar")
        actions_layout = QHBoxLayout(actions)
        actions_layout.addWidget(self._info_button(
            "Restored result",
            "Copy is available for text. Download keeps the same format as the AI result: TXT, PDF, DOCX or XLSX.",
        ))
        self.copy_button = QPushButton("Copy restored text", objectName="Secondary")
        self.download_button = QPushButton("Download restored file", objectName="Gold")
        actions_layout.addWidget(self.copy_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.download_button)
        root.addWidget(actions)

        self.browse_button.clicked.connect(self._browse_result)
        self.load_protected_button.clicked.connect(self._load_protected)
        self.restore_button.clicked.connect(self._restore)
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.output_text.toPlainText()))
        self.download_button.clicked.connect(self._download)
        self.high_fidelity_button.toggled.connect(self._refresh_document_preview)
        self.document_combo.currentIndexChanged.connect(self._update_mapping_status)
        self.pdf_previous_button.clicked.connect(lambda: self._move_pdf_page(-1))
        self.pdf_next_button.clicked.connect(lambda: self._move_pdf_page(1))
        self.pdf_fit_button.clicked.connect(self._fit_pdf)
        self.pdf_zoom_out_button.clicked.connect(lambda: self._zoom_pdf(0.85))
        self.pdf_zoom_in_button.clicked.connect(lambda: self._zoom_pdf(1.18))
        self._set_result_actions(False)

    def _build_text_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        input_card = QFrame(objectName="Card")
        input_layout = QVBoxLayout(input_card)
        input_layout.addWidget(QLabel("Protected AI result", objectName="SectionTitle"))
        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText("Paste a protected AI response here, or load a protected result file above.")
        input_layout.addWidget(self.input_text)
        output_card = QFrame(objectName="Card")
        output_layout = QVBoxLayout(output_card)
        output_layout.addWidget(QLabel("Locally restored result", objectName="SectionTitle"))
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        layout.addWidget(input_card, 1)
        layout.addWidget(output_card, 1)
        self.preview_tabs.addTab(tab, "Text & placeholders")

    def _build_document_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        options = QHBoxLayout()
        self.preview_note = QLabel(
            "Load a PDF, Word or Excel result to compare protected and locally restored files.",
            objectName="Muted",
        )
        self.preview_note.setWordWrap(True)
        self.high_fidelity_button = QPushButton("High-fidelity preview", objectName="Secondary")
        self.high_fidelity_button.setCheckable(True)
        self.high_fidelity_button.setToolTip("Use LibreOffice locally for a page-accurate Word or Excel preview.")
        self.libreoffice_note = QLabel(objectName="Muted")
        self.libreoffice_note.setTextFormat(Qt.TextFormat.RichText)
        self.libreoffice_note.setOpenExternalLinks(True)
        options.addWidget(self.preview_note, 1)
        options.addWidget(self.high_fidelity_button)
        options.addWidget(self.libreoffice_note)
        layout.addLayout(options)
        controls = QHBoxLayout()
        self.pdf_previous_button = QPushButton("‹", objectName="Tiny")
        self.pdf_next_button = QPushButton("›", objectName="Tiny")
        self.pdf_page_label = QLabel("Page 1 / 1", objectName="PdfPageLabel")
        self.pdf_zoom_out_button = QPushButton("−", objectName="Tiny")
        self.pdf_fit_button = QPushButton("Fit width", objectName="Tiny")
        self.pdf_zoom_in_button = QPushButton("+", objectName="Tiny")
        for widget in (self.pdf_previous_button, self.pdf_next_button, self.pdf_page_label):
            controls.addWidget(widget)
        controls.addStretch(1)
        for widget in (self.pdf_zoom_out_button, self.pdf_fit_button, self.pdf_zoom_in_button):
            controls.addWidget(widget)
        layout.addLayout(controls)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        input_panel, self.input_pdf_view, self.input_office_view, self.input_view_stack = self._document_panel(
            "Protected AI result", "No real PII"
        )
        output_panel, self.output_pdf_view, self.output_office_view, self.output_view_stack = self._document_panel(
            "Locally restored file", "Local preview"
        )
        self.input_pdf_document = QPdfDocument(self)
        self.output_pdf_document = QPdfDocument(self)
        self.input_pdf_view.setDocument(self.input_pdf_document)
        self.output_pdf_view.setDocument(self.output_pdf_document)
        for view in (self.input_pdf_view, self.output_pdf_view):
            view.setPageMode(QPdfView.PageMode.MultiPage)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        splitter.addWidget(input_panel)
        splitter.addWidget(output_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([700, 700])
        layout.addWidget(splitter, 1)
        self.preview_tabs.addTab(tab, "Document comparison")
        self.preview_tabs.setTabVisible(1, False)

    def _document_panel(self, title: str, subtitle: str):
        panel = QFrame(objectName="Card")
        layout = QVBoxLayout(panel)
        header = QHBoxLayout()
        header.addWidget(QLabel(title, objectName="SectionTitle"))
        header.addStretch(1)
        header.addWidget(QLabel(subtitle, objectName="PdfBadge"))
        layout.addLayout(header)
        pdf_view = QPdfView()
        pdf_view.setObjectName("PdfView")
        office_view = OfficeInternalPreview(self.TOKEN_COLORS)
        stack = QStackedWidget()
        stack.addWidget(pdf_view)
        stack.addWidget(office_view)
        layout.addWidget(stack, 1)
        return panel, pdf_view, office_view, stack

    @staticmethod
    def _info_button(title: str, message: str) -> QToolButton:
        button = QToolButton()
        button.setText("i")
        button.setObjectName("InfoButton")
        button.setToolTip(message)
        button.clicked.connect(lambda _checked=False: QMessageBox.information(button, title, message))
        return button

    def refresh(self, select_id: str | None = None) -> None:
        self._documents = tuple(item for item in self.library.list_documents() if item.has_mapping)
        previous = select_id or self.document_combo.currentData()
        self.document_combo.clear()
        for document in self._documents:
            self.document_combo.addItem(f"{document.title}  •  {document.source_kind.upper()}", document.document_id)
        if previous:
            index = self.document_combo.findData(previous)
            if index >= 0:
                self.document_combo.setCurrentIndex(index)
        enabled = bool(self._documents)
        self.restore_button.setEnabled(enabled)
        self.load_protected_button.setEnabled(enabled)
        self._update_mapping_status()

    def select_document(self, document_id: str) -> None:
        self.refresh(document_id)

    def _update_mapping_status(self) -> None:
        index = self.document_combo.currentIndex()
        self.mapping_label.setText(
            f"Mapping: {self._documents[index].title}" if 0 <= index < len(self._documents)
            else "Choose a source mapping"
        )

    def _browse_result(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open protected AI result", "", self.FILE_FILTER)
        if path:
            self._load_file(Path(path))

    def _load_file(self, path: Path) -> None:
        try:
            text = self.restore_service.extract_text(path)
        except Exception as exc:
            QMessageBox.critical(self, "Unable to open result", str(exc))
            return
        self._source_path = path
        self._restored_path = None
        self._report = None
        self.source_path.setText(str(path))
        self.format_label.setText(path.suffix[1:].upper())
        self.input_text.setPlainText(text)
        self.output_text.clear()
        self._highlight_input_tokens()
        self._set_result_actions(False)
        if path.suffix.lower() in {".pdf", ".docx", ".xlsx"}:
            self.preview_tabs.setTabVisible(1, True)
            self.preview_tabs.setCurrentIndex(1)
            self._refresh_document_preview()
        else:
            self.preview_tabs.setTabVisible(1, False)
            self.preview_tabs.setCurrentIndex(0)
        self.restore_status.setText("Loaded — choose the matching Library mapping and restore locally")

    def _load_protected(self) -> None:
        document_id = self.document_combo.currentData()
        if not document_id:
            return
        document = self.library.get(document_id)
        self._source_path = None
        self._restored_path = None
        self.source_path.clear()
        self.input_text.setPlainText(document.protected_text)
        self.output_text.clear()
        self.format_label.setText("TEXT")
        self.preview_tabs.setTabVisible(1, False)
        self.preview_tabs.setCurrentIndex(0)
        self._highlight_input_tokens()
        self._set_result_actions(False)

    def _highlight_input_tokens(self) -> None:
        text = self.input_text.toPlainText()
        for match in TOKEN_PATTERN.finditer(text):
            entity = match.group(0)[5:].rsplit("_", 1)[0]
            cursor = QTextCursor(self.input_text.document())
            cursor.setPosition(match.start())
            cursor.setPosition(match.end(), QTextCursor.MoveMode.KeepAnchor)
            formatting = QTextCharFormat()
            formatting.setBackground(QColor(self.TOKEN_COLORS.get(entity, "#E7E9ED")))
            formatting.setForeground(QColor("#102A43"))
            formatting.setFontWeight(int(QFont.Weight.DemiBold))
            cursor.mergeCharFormat(formatting)

    def _restore(self) -> None:
        document_id = self.document_combo.currentData()
        if not document_id:
            QMessageBox.information(self, "Nothing to restore", "Choose the original protection mapping.")
            return
        mappings = self.library.get_mappings(document_id)
        try:
            if self._source_path is None:
                text = self.input_text.toPlainText()
                if not text:
                    raise ValueError("Paste or load a protected AI result first.")
                known = {item.token for item in mappings}
                unknown = sorted(set(TOKEN_PATTERN.findall(text)).difference(known))
                self.output_text.setPlainText(self.service.restore_text(text, mappings))
                self._report = None
                self._restored_path = None
                restored_count = sum(text.count(item.token) for item in mappings)
            else:
                restored_path = self._preview_root / f"restored-result{self._source_path.suffix.lower()}"
                self._report = self.restore_service.restore(self._source_path, mappings, restored_path)
                self._restored_path = self._report.output_path
                self.output_text.setPlainText(self.restore_service.extract_text(self._restored_path))
                unknown = list(self._report.unknown_tokens)
                restored_count = self._report.restored_occurrences
                self._refresh_document_preview()
            if not restored_count:
                raise ValueError(
                    "No matching Privacy Gate placeholders were found. Choose the Library mapping that originally protected this result."
                )
        except Exception as exc:
            self._set_result_actions(False)
            QMessageBox.critical(self, "Restore failed", str(exc))
            return
        self.restore_status.setText(f"Restored {restored_count} placeholder occurrence(s) locally")
        self._set_result_actions(True)
        if unknown:
            QMessageBox.warning(
                self, "Restore completed with warnings",
                "Some placeholders do not belong to the selected mapping and were left protected:\n\n"
                + "\n".join(unknown[:12]),
            )

    def _refresh_document_preview(self) -> None:
        if self._source_path is None:
            return
        suffix = self._source_path.suffix.lower()
        try:
            self.input_pdf_document.close()
            self.output_pdf_document.close()
            if suffix == ".pdf":
                self._set_pdf_controls(True)
                self.high_fidelity_button.setVisible(False)
                self.libreoffice_note.clear()
                self.input_view_stack.setCurrentIndex(0)
                self.output_view_stack.setCurrentIndex(0)
                self.input_pdf_document.load(str(self._source_path))
                if self._restored_path:
                    self.output_pdf_document.load(str(self._restored_path))
                self.preview_note.setText("Protected PDF on the left; locally restored PDF on the right.")
                self._set_pdf_page(0)
                return
            if suffix not in {".docx", ".xlsx"}:
                return
            self.high_fidelity_button.setVisible(self._libreoffice_available)
            if self._libreoffice_available:
                self.libreoffice_note.setText("LibreOffice detected — optional page-accurate rendering available.")
            else:
                self.high_fidelity_button.setChecked(False)
                self.libreoffice_note.setText(
                    "Built-in preview active. For optional page-accurate rendering, install "
                    "<a href='https://www.libreoffice.org/download/download-libreoffice/'>LibreOffice (free)</a>."
                )
            if self._libreoffice_available and self.high_fidelity_button.isChecked():
                self._set_pdf_controls(True)
                input_pdf = self.office_renderer.render(self._source_path, self._preview_root / "input-office")
                self.input_view_stack.setCurrentIndex(0)
                self.output_view_stack.setCurrentIndex(0)
                self.input_pdf_document.load(str(input_pdf))
                if self._restored_path:
                    output_pdf = self.office_renderer.render(self._restored_path, self._preview_root / "output-office")
                    self.output_pdf_document.load(str(output_pdf))
                self.preview_note.setText("High-fidelity local rendering through LibreOffice; no document is uploaded.")
                self._set_pdf_page(0)
            else:
                self._set_pdf_controls(False)
                self.input_office_view.load(self._source_path, protected=True)
                self.input_view_stack.setCurrentIndex(1)
                self.output_office_view.clear()
                if self._restored_path:
                    self.output_office_view.load(self._restored_path, protected=False)
                    self.input_office_view.synchronize_with(self.output_office_view)
                self.output_view_stack.setCurrentIndex(1)
                kind = "worksheet" if suffix == ".xlsx" else "document"
                self.preview_note.setText(f"Built-in {kind} preview is always available without additional software.")
        except Exception as exc:
            self.preview_note.setText(f"Preview unavailable: {exc}")

    def _set_pdf_controls(self, visible: bool) -> None:
        for widget in (
            self.pdf_previous_button, self.pdf_next_button, self.pdf_page_label,
            self.pdf_zoom_out_button, self.pdf_fit_button, self.pdf_zoom_in_button,
        ):
            widget.setVisible(visible)

    def _set_pdf_page(self, page: int) -> None:
        count = max(self.input_pdf_document.pageCount(), self.output_pdf_document.pageCount())
        if count <= 0:
            self.pdf_page_label.setText("Page 0 / 0")
            return
        page = max(0, min(page, count - 1))
        for view in (self.input_pdf_view, self.output_pdf_view):
            navigator = view.pageNavigator()
            if navigator:
                navigator.jump(page, navigator.currentLocation(), view.zoomFactor())
        self.pdf_page_label.setText(f"Page {page + 1} / {count}")

    def _move_pdf_page(self, delta: int) -> None:
        navigator = self.input_pdf_view.pageNavigator()
        self._set_pdf_page((navigator.currentPage() if navigator else 0) + delta)

    def _fit_pdf(self) -> None:
        for view in (self.input_pdf_view, self.output_pdf_view):
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _zoom_pdf(self, factor: float) -> None:
        for view in (self.input_pdf_view, self.output_pdf_view):
            view.setZoomMode(QPdfView.ZoomMode.Custom)
            view.setZoomFactor(max(0.2, min(5.0, view.zoomFactor() * factor)))

    def _set_result_actions(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)

    def _download(self) -> None:
        if self._source_path is None:
            text = self.output_text.toPlainText()
            if not text:
                return
            path, _ = QFileDialog.getSaveFileName(self, "Save restored result", "restored_result.txt", "Text files (*.txt)")
            if path:
                Path(path if path.lower().endswith(".txt") else path + ".txt").write_text(text, encoding="utf-8")
            return
        if self._restored_path is None:
            return
        suffix = self._restored_path.suffix.lower()
        suggested = f"{self._source_path.stem}_restored{suffix}"
        labels = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel", ".txt": "Text"}
        label = labels.get(suffix, "Document")
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save restored {label} result", suggested, f"{label} files (*{suffix})"
        )
        if path:
            destination = Path(path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            shutil.copy2(self._restored_path, destination)

    def cleanup_previews(self) -> None:
        self.input_pdf_document.close()
        self.output_pdf_document.close()
        shutil.rmtree(self._preview_root, ignore_errors=True)
