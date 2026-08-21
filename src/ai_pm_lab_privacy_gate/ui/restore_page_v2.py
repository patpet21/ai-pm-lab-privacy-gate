from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QBoxLayout,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.documents.office_preview import OfficePreviewRenderer
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.restore_service import (
    DocumentRestoreService,
    RestoreReport,
    TOKEN_PATTERN,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui.office_internal_preview import OfficeInternalPreview
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


class BusyIndicator(QWidget):
    """Small animated local-work indicator used for file load and restore."""

    def __init__(self) -> None:
        super().__init__()
        self._frames = ("◐", "◓", "◑", "◒")
        self._index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(110)
        self._timer.timeout.connect(self._tick)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.spinner = QLabel(self._frames[0])
        self.spinner.setStyleSheet("font-size:20px;color:#078c89;font-weight:700;")
        self.message = QLabel()
        self.message.setStyleSheet("color:#37566a;font-weight:600;")
        layout.addWidget(self.spinner)
        layout.addWidget(self.message)
        layout.addStretch(1)
        self.hide()

    def start(self, message: str) -> None:
        self.message.setText(message)
        self._index = 0
        self.spinner.setText(self._frames[0])
        self.show()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._index = (self._index + 1) % len(self._frames)
        self.spinner.setText(self._frames[self._index])


class RestoreDropZone(QFrame):
    file_dropped = Signal(str)
    clicked = Signal()

    SUPPORTED = {".txt", ".pdf", ".docx", ".xlsx"}

    def __init__(self) -> None:
        super().__init__(objectName="RestoreDropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(78)
        self.setStyleSheet(
            "QFrame#RestoreDropZone{background:#f8fcfc;border:1px dashed #58b9b5;"
            "border-radius:10px;}"
            "QFrame#RestoreDropZone:hover{background:#f1fbfa;border-color:#078c89;}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(3)

        self.button = QPushButton("Upload your file", objectName="Primary")
        self.button.setMinimumHeight(40)
        self.button.clicked.connect(self.clicked.emit)

        self.filename = QLabel("or drag and drop it here")
        self.filename.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename.setWordWrap(True)
        self.filename.setStyleSheet("color:#62788a;")

        self.formats = QLabel("TXT, PDF, Word, Excel — processed locally")
        self.formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formats.setStyleSheet("color:#7a8d9d;font-size:11px;")

        layout.addWidget(self.button)
        layout.addWidget(self.filename)
        layout.addWidget(self.formats)

    def set_filename(self, name: str | None) -> None:
        self.filename.setText(name or "or drag and drop it here")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in self.SUPPORTED:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() in self.SUPPORTED:
            self.file_dropped.emit(str(path))
            event.acceptProposedAction()


class RestorePage(QWidget):
    """Restore AI-modified protected content by matching it to a local Library entry."""

    TOKEN_COLORS = PdfDocumentService.ENTITY_COLORS
    FILE_FILTER = (
        "Supported results (*.txt *.pdf *.docx *.xlsx);;"
        "Text files (*.txt);;PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx)"
    )

    def __init__(self, service: PrivacyGateService, library: LibraryRepository) -> None:
        super().__init__()
        self.service = service
        self.library = library
        self.restore_service = DocumentRestoreService()
        self.office_renderer = OfficePreviewRenderer()
        self.thread_pool = QThreadPool.globalInstance()
        self._libreoffice_available = self.office_renderer.find_executable() is not None
        self._documents = ()
        self._source_path: Path | None = None
        self._restored_path: Path | None = None
        self._report: RestoreReport | None = None
        self._active_worker: FunctionWorker | None = None
        self._syncing_text = False
        self._preview_root = Path(tempfile.gettempdir()) / f"AI_PM_LAB_Restore_{os.getpid()}"
        self._preview_root.mkdir(parents=True, exist_ok=True)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        self._outer_layout = outer
        outer.setContentsMargins(24, 18, 24, 14)
        outer.setSpacing(12)

        heading = QHBoxLayout()
        self.heading_layout = heading
        titles = QVBoxLayout()
        self.page_title = QLabel("Restore your AI result", objectName="PageTitle")
        titles.addWidget(self.page_title)
        self.page_subtitle = QLabel(
                "Bring back the original values after AI processing — everything happens locally.",
                objectName="Muted",
        )
        titles.addWidget(self.page_subtitle)
        heading.addLayout(titles)
        heading.addStretch(1)

        self.local_badge = QLabel(
            "100% LOCAL   |   ORIGINAL VALUES STAY ON THIS PC", objectName="SafeBadge"
        )
        heading.addWidget(self.local_badge)
        outer.addLayout(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        # Let the scroll-area viewport dictate the page width.  Controls with
        # long filenames must elide their contents instead of widening the
        # whole page and pushing actions outside the visible window.
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        root = QVBoxLayout(content)
        self._content_layout = root
        root.setContentsMargins(0, 0, 4, 4)
        root.setSpacing(14)

        self.steps_card = QFrame(objectName="Card")
        self.steps_card.setFixedHeight(54)
        steps = QHBoxLayout(self.steps_card)
        steps.setContentsMargins(14, 6, 14, 6)
        steps.setSpacing(7)
        for number, label in (
            ("1", "Add AI result"),
            ("2", "Select original document"),
            ("3", "Restore locally"),
            ("4", "Copy or download"),
        ):
            bubble = QLabel(number)
            bubble.setFixedSize(26, 26)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setStyleSheet(
                "background:#e7f7f5;color:#078c89;border:1px solid #b9e4df;"
                "border-radius:13px;font-weight:800;"
            )
            text = QLabel(label)
            text.setStyleSheet("background:transparent;color:#3d586d;font-weight:600;padding:0;")
            steps.addWidget(bubble)
            steps.addWidget(text)
        steps.addStretch(1)
        root.addWidget(self.steps_card)

        self.input_card = QFrame(objectName="Card")
        self.input_card.setMaximumHeight(250)
        input_layout = QVBoxLayout(self.input_card)
        input_layout.setContentsMargins(14, 10, 14, 10)
        input_layout.setSpacing(6)

        step1_title = QLabel("1. Add the AI result and match its original", objectName="SectionTitle")
        input_layout.addWidget(step1_title)
        step1_help = QLabel(
            "Upload the protected result returned by AI, then choose its original Library document. "
            "Everything is matched and restored locally."
        )
        step1_help.setWordWrap(True)
        step1_help.setStyleSheet("color:#667b8d;")
        input_layout.addWidget(step1_help)

        source_row = QHBoxLayout()
        self.source_row = source_row
        source_row.setSpacing(12)

        upload_panel = QFrame(objectName="PdfPanel")
        upload_col = QVBoxLayout(upload_panel)
        upload_col.setContentsMargins(10, 8, 10, 8)
        upload_col.setSpacing(5)
        upload_title_row = QHBoxLayout()
        upload_title_row.addWidget(QLabel("Add AI result", objectName="SectionTitle"))
        upload_title_row.addStretch(1)
        self.paste_toggle = QPushButton("Paste text", objectName="Secondary")
        self.paste_toggle.setCheckable(True)
        self.paste_toggle.setToolTip("Paste protected text instead of selecting a file")
        upload_title_row.addWidget(self.paste_toggle)
        upload_col.addLayout(upload_title_row)

        self.drop_zone = RestoreDropZone()
        upload_col.addWidget(self.drop_zone)
        self.match_card = QFrame(objectName="PdfPanel")
        match_layout = QVBoxLayout(self.match_card)
        match_layout.setContentsMargins(10, 8, 10, 8)
        match_layout.setSpacing(5)

        match_title_row = QHBoxLayout()
        match_title_row.addWidget(QLabel("Select original from Library", objectName="SectionTitle"))
        match_title_row.addStretch(1)
        match_title_row.addWidget(QLabel("Local Library", objectName="PdfBadge"))
        match_layout.addLayout(match_title_row)

        self.document_combo = QComboBox()
        self.document_combo.setMinimumHeight(40)
        self.document_combo.setMinimumWidth(0)
        self.document_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.document_combo.setMinimumContentsLength(18)
        self.document_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        document_action_row = QHBoxLayout()
        document_action_row.setSpacing(6)
        document_action_row.addWidget(self.document_combo, 1)

        self.clear_button = QPushButton("Clear", objectName="Secondary")
        self.clear_button.setMaximumWidth(72)
        self.restore_button = QPushButton("Restore locally", objectName="Primary")
        self.restore_button.setMaximumWidth(128)
        document_action_row.addWidget(self.clear_button)
        document_action_row.addWidget(self.restore_button)
        match_layout.addLayout(document_action_row)

        self.library_status = QLabel("Choose the matching protected document.")
        self.library_status.setWordWrap(True)
        self.library_status.setMinimumWidth(0)
        self.library_status.setMaximumHeight(36)
        self.library_status.setStyleSheet(
            "background:#f3faf9;border:1px solid #d8eeeb;border-radius:8px;"
            "padding:7px;color:#42675f;font-size:11px;"
        )
        match_layout.addWidget(self.library_status)

        self.busy = BusyIndicator()
        match_layout.addWidget(self.busy)

        source_row.addWidget(upload_panel, 1)
        source_row.addWidget(self.match_card, 1)
        input_layout.addLayout(source_row)

        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText(
            "Paste the AI result here. Example: The revised agreement for [[PG_PERSON_001]] "
            "should be sent to [[PG_EMAIL_ADDRESS_001]]..."
        )
        self.input_text.setMinimumHeight(96)
        self.input_text.setMaximumHeight(118)
        self.input_text.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid #cfdbe5;border-radius:9px;"
            "padding:12px;font-size:13px;}"
        )
        self.input_text.hide()
        input_layout.addWidget(self.input_text)

        self.token_hint = QLabel("No Privacy Gate placeholders detected yet.")
        self.token_hint.setStyleSheet("color:#7a8d9d;font-size:11px;")
        input_layout.addWidget(self.token_hint)
        root.addWidget(self.input_card)

        self.restore_status = QLabel(
            "Add an AI result and select the matching Library document to continue."
        )
        self.restore_status.setWordWrap(True)
        self.restore_status.setMinimumWidth(0)
        self.restore_status.setStyleSheet("color:#6b8091;")
        match_layout.addWidget(self.restore_status)

        self.result_section = QFrame(objectName="Card")
        result_layout = QVBoxLayout(self.result_section)
        result_layout.setContentsMargins(14, 14, 14, 14)
        result_layout.setSpacing(10)

        result_header = QHBoxLayout()
        result_header.addWidget(QLabel("Restored result", objectName="SectionTitle"))
        self.result_metric = QLabel("Restored locally", objectName="SafetyMetric")
        result_header.addStretch(1)
        result_header.addWidget(self.result_metric)
        result_layout.addLayout(result_header)

        self.preview_tabs = QTabWidget()
        self._build_text_tab()
        self._build_document_tab()
        result_layout.addWidget(self.preview_tabs, 1)

        # The preview is the primary workspace.  Source and matching controls
        # are embedded directly below the two document panes rather than
        # repeated in a separate form above them.
        self.input_card.hide()
        self.result_section.show()
        self.preview_tabs.setTabVisible(1, True)
        self.preview_tabs.setCurrentIndex(1)

        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy restored text", objectName="Secondary")
        self.download_text_button = QPushButton("Download restored text", objectName="Secondary")
        self.download_button = QPushButton("Download restored file", objectName="Gold")
        self.copy_button.setMinimumHeight(42)
        self.download_text_button.setMinimumHeight(42)
        self.download_button.setMinimumHeight(42)
        actions.addWidget(self.copy_button, 1)
        actions.addWidget(self.download_text_button, 1)
        actions.addWidget(self.download_button, 1)
        result_layout.addLayout(actions)

        root.addWidget(self.result_section, 1)

        self.safety_note = QLabel(
            "Privacy Gate only uses the encrypted restore key stored on this device. "
            "Your original values are restored locally and are never sent back to the AI."
        )
        self.safety_note.setWordWrap(True)
        self.safety_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.safety_note.setStyleSheet(
            "background:#eefaf8;border:1px solid #d5eeea;border-radius:9px;"
            "padding:10px;color:#28645f;"
        )
        self.safety_note.setMaximumHeight(54)
        root.addWidget(self.safety_note)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self.drop_zone.clicked.connect(self._browse_result)
        self.drop_zone.file_dropped.connect(lambda path: self._begin_load_file(Path(path)))
        self.paste_toggle.toggled.connect(self._toggle_paste_input)
        self.input_text.textChanged.connect(self._on_input_text_changed)
        self.document_combo.currentIndexChanged.connect(self._update_library_status)
        self.restore_button.clicked.connect(self._restore)
        self.clear_button.clicked.connect(self.clear)
        self.copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.output_text.toPlainText())
        )
        self.download_text_button.clicked.connect(self._download_text)
        self.download_button.clicked.connect(self._download)
        self.high_fidelity_button.toggled.connect(self._refresh_document_preview)
        self.full_preview_button.toggled.connect(self._toggle_full_preview)
        self.pdf_previous_button.clicked.connect(lambda: self._move_pdf_page(-1))
        self.pdf_next_button.clicked.connect(lambda: self._move_pdf_page(1))
        self.pdf_fit_button.clicked.connect(self._fit_pdf)
        self.pdf_zoom_out_button.clicked.connect(lambda: self._zoom_pdf(0.85))
        self.pdf_zoom_in_button.clicked.connect(lambda: self._zoom_pdf(1.18))
        self._update_restore_state()

    def _build_text_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        input_card = QFrame(objectName="PdfPanel")
        input_layout = QVBoxLayout(input_card)
        input_layout.addWidget(QLabel("AI result with placeholders", objectName="SectionTitle"))
        self.protected_result_view = QPlainTextEdit()
        self.protected_result_view.setReadOnly(True)
        input_layout.addWidget(self.protected_result_view)

        output_card = QFrame(objectName="PdfPanel")
        output_layout = QVBoxLayout(output_card)
        output_layout.addWidget(QLabel("Restored result", objectName="SectionTitle"))
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)

        layout.addWidget(input_card, 1)
        layout.addWidget(output_card, 1)
        self.preview_tabs.addTab(tab, "Restored text")

    def _build_document_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        options = QHBoxLayout()
        self.preview_note = QLabel(
            "Uploaded AI result on the left; locally restored result on the right.",
            objectName="Muted",
        )
        self.preview_note.setWordWrap(True)
        self.high_fidelity_button = QPushButton("High-fidelity preview", objectName="Secondary")
        self.high_fidelity_button.setCheckable(True)
        self.high_fidelity_button.setVisible(self._libreoffice_available)
        self.full_preview_button = QPushButton("Full screen preview", objectName="Secondary")
        self.full_preview_button.setCheckable(True)
        self.libreoffice_note = QLabel(objectName="Muted")
        self.libreoffice_note.setTextFormat(Qt.TextFormat.RichText)
        self.libreoffice_note.setOpenExternalLinks(True)
        self.install_libreoffice_button = QPushButton(
            "Get LibreOffice (free)", objectName="Secondary"
        )
        self.install_libreoffice_button.setToolTip(
            "Open the official LibreOffice download page. The built-in preview remains available."
        )
        self.install_libreoffice_button.setVisible(False)
        self.install_libreoffice_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.libreoffice.org/download/download-libreoffice/")
            )
        )
        options.addWidget(self.preview_note, 1)
        options.addWidget(self.high_fidelity_button)
        options.addWidget(self.install_libreoffice_button)
        options.addWidget(self.full_preview_button)
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
        self.restore_button.setText("Restore your file")
        self.restore_button.setMaximumWidth(150)
        controls.addWidget(self.restore_button)
        controls.addSpacing(12)
        for widget in (self.pdf_zoom_out_button, self.pdf_fit_button, self.pdf_zoom_in_button):
            controls.addWidget(widget)
        layout.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        (
            input_panel,
            input_panel_layout,
            self.input_pdf_view,
            self.input_office_view,
            self.input_view_stack,
        ) = self._document_panel("AI result", "Placeholders retained")
        (
            output_panel,
            output_panel_layout,
            self.output_pdf_view,
            self.output_office_view,
            self.output_view_stack,
        ) = self._document_panel("Restored result", "Local only")

        # One compact source/mapping strip sits above both large previews.
        # Controls must never consume space inside either document card.
        source_toolbar = QFrame(objectName="EmbeddedSourceToolbar")
        source_toolbar_layout = QVBoxLayout(source_toolbar)
        source_toolbar_layout.setContentsMargins(7, 6, 7, 6)
        source_toolbar_layout.setSpacing(4)
        source_row = QHBoxLayout()
        source_row.setSpacing(8)

        upload_group = QHBoxLayout()
        upload_group.setSpacing(6)
        upload_group.addWidget(QLabel("AI result", objectName="FieldLabel"))
        upload_group.addWidget(self.paste_toggle)
        self.drop_zone.setMinimumHeight(54)
        self.drop_zone.setMaximumHeight(54)
        self.drop_zone.layout().setContentsMargins(6, 2, 6, 2)
        self.drop_zone.layout().setSpacing(1)
        self.drop_zone.button.setMinimumHeight(30)
        self.drop_zone.button.setMaximumHeight(30)
        self.drop_zone.formats.hide()
        upload_group.addWidget(self.drop_zone, 1)
        source_row.addLayout(upload_group, 1)

        mapping_group = QHBoxLayout()
        mapping_group.setSpacing(6)
        mapping_group.addWidget(QLabel("Original", objectName="FieldLabel"))
        mapping_group.addWidget(self.document_combo, 1)
        mapping_group.addWidget(QLabel("Local Library", objectName="PdfBadge"))
        source_row.addLayout(mapping_group, 1)
        source_toolbar_layout.addLayout(source_row)
        source_toolbar_layout.addWidget(self.input_text)

        status_row = QHBoxLayout()
        self.token_hint.setMinimumWidth(0)
        self.library_status.setMinimumWidth(0)
        self.library_status.setMaximumHeight(28)
        status_row.addWidget(self.token_hint, 1)
        status_row.addWidget(self.library_status, 1)
        source_toolbar_layout.addLayout(status_row)
        layout.addWidget(source_toolbar)

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
        splitter.setMinimumHeight(560)
        layout.addWidget(splitter, 1)

        self.preview_tabs.addTab(tab, "Document preview")
        self.preview_tabs.setTabVisible(1, True)

    def _document_panel(self, title: str, subtitle: str):
        panel = QFrame(objectName="PdfPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

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
        return panel, layout, pdf_view, office_view, stack

    def refresh(self, select_id: str | None = None) -> None:
        previous = select_id or self.document_combo.currentData()
        self._documents = tuple(
            item for item in self.library.list_documents()
            if item.has_mapping and item.replacement_mode == "reversible"
        )

        self.document_combo.blockSignals(True)
        self.document_combo.clear()
        self.document_combo.addItem("Choose from Privacy Gate Library...", None)

        for document in self._documents:
            date = document.updated_at.strftime("%b %d, %Y")
            display = f"{document.title}  •  {document.source_name}  •  {date}"
            self.document_combo.addItem(display, document.document_id)

        if previous:
            index = self.document_combo.findData(previous)
            if index >= 0:
                self.document_combo.setCurrentIndex(index)
        self.document_combo.blockSignals(False)
        self._update_library_status()
        self._update_restore_state()

    def select_document(self, document_id: str) -> None:
        self.refresh(document_id)

    def _browse_result(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload your AI result",
            "",
            self.FILE_FILTER,
        )
        if path:
            self._begin_load_file(Path(path))

    def _begin_load_file(self, path: Path) -> None:
        if self._active_worker is not None:
            return

        self._set_busy(True, "Loading your AI result locally…")

        def task():
            return path, self.restore_service.extract_text(path)

        worker = FunctionWorker(task)
        self._active_worker = worker
        worker.signals.result.connect(self._file_loaded)
        worker.signals.error.connect(self._load_failed)
        worker.signals.finished.connect(self._operation_finished)
        self.thread_pool.start(worker)

    def _file_loaded(self, payload: object) -> None:
        path, text = payload
        self._source_path = Path(path)
        self._restored_path = None
        self._report = None

        self._syncing_text = True
        self.input_text.setPlainText(text)
        self._syncing_text = False
        self.paste_toggle.setChecked(False)

        self.drop_zone.set_filename(self._source_path.name)
        self.output_text.clear()
        self.protected_result_view.clear()
        self.result_section.show()
        suffix = self._source_path.suffix.lower()
        if suffix in {".pdf", ".docx", ".xlsx"}:
            self.preview_tabs.setTabVisible(1, True)
            self.preview_tabs.setCurrentIndex(1)
            self._refresh_document_preview()
        else:
            self.preview_tabs.setCurrentIndex(0)
        self._highlight_input_tokens()
        self.restore_status.setText(
            "AI result loaded. Now select the original protected document from your Library."
        )
        self._update_restore_state()
        QTimer.singleShot(0, self._apply_responsive_layout)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        """Stack wide controls when the content pane becomes narrow."""
        # The main window keeps a 1120 px usability floor.  With the navigation
        # collapsed that still leaves roughly 1040 px for this page, so switch
        # before the source controls start clipping rather than waiting for a
        # width the window can never reach.
        compact = self.width() < 1100
        self.source_row.setDirection(
            QBoxLayout.Direction.TopToBottom
            if compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.heading_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if compact
            else QBoxLayout.Direction.LeftToRight
        )
        self.local_badge.setText(
            "100% LOCAL  •  ORIGINAL VALUES STAY ON THIS PC"
            if compact
            else "100% LOCAL   |   ORIGINAL VALUES STAY ON THIS PC"
        )
        if not self.input_text.isVisible():
            self.input_card.setMaximumHeight(430 if compact else 250)

    def _toggle_paste_input(self, visible: bool) -> None:
        """Keep paste support available without permanently consuming preview space."""
        self.input_text.setVisible(visible)
        compact = self.width() < 1100
        self.input_card.setMaximumHeight(
            560 if visible and compact else 390 if visible else 430 if compact else 250
        )
        self.paste_toggle.setText(
            "Use uploaded file" if visible else "Paste text"
        )

    def _load_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Unable to load this result", message)

    def _on_input_text_changed(self) -> None:
        if not self._syncing_text and self.input_text.hasFocus() and self._source_path is not None:
            self._source_path = None
            self._restored_path = None
            self._report = None
            self.drop_zone.set_filename(None)
            self.result_section.show()
        self._update_token_hint()
        self._update_restore_state()

    def _update_token_hint(self) -> None:
        tokens = TOKEN_PATTERN.findall(self.input_text.toPlainText())
        count = len(tokens)
        if count:
            self.token_hint.setText(
                f"{count} Privacy Gate placeholder occurrence{'s' if count != 1 else ''} detected."
            )
            self.token_hint.setStyleSheet("color:#087d7b;font-size:11px;font-weight:700;")
        else:
            self.token_hint.setText("No Privacy Gate placeholders detected yet.")
            self.token_hint.setStyleSheet("color:#a16918;font-size:11px;")

    def _update_library_status(self) -> None:
        document_id = self.document_combo.currentData()
        if not document_id:
            if self._documents:
                self.library_status.setText(
                    "Choose the document you originally protected. Only documents with a local reversible restore key are shown."
                )
            else:
                self.library_status.setText(
                    "No reversible documents are available yet. Protect a document with Reversible placeholders and save it to the Library first."
                )
            self._update_restore_state()
            return

        document = next(
            (item for item in self._documents if item.document_id == document_id),
            None,
        )
        if document is None:
            self._update_restore_state()
            return

        mappings = self.library.get_mappings(document_id)
        self.library_status.setText(
            f"Ready to match: {document.title}  •  {len(mappings)} local restore key"
            f"{'s' if len(mappings) != 1 else ''} available."
        )
        self._update_restore_state()

    def _update_restore_state(self) -> None:
        has_input = bool(self.input_text.toPlainText().strip())
        has_tokens = bool(TOKEN_PATTERN.search(self.input_text.toPlainText()))
        has_document = bool(self.document_combo.currentData())
        busy = self._active_worker is not None
        self.restore_button.setEnabled(has_input and has_tokens and has_document and not busy)

        if busy:
            return
        if not has_input:
            self.restore_status.setText("Add the AI result you want to restore.")
        elif not has_tokens:
            self.restore_status.setText(
                "This result does not contain Privacy Gate placeholders yet."
            )
        elif not has_document:
            self.restore_status.setText(
                "Result ready. Select the original protected document from the Library."
            )
        else:
            self.restore_status.setText(
                "Ready. Privacy Gate will restore the original values locally."
            )

    def _restore(self) -> None:
        document_id = self.document_combo.currentData()
        text = self.input_text.toPlainText()
        if not text:
            QMessageBox.information(
                self, "Add your AI result", "Paste text or upload the AI result first."
            )
            return
        if not TOKEN_PATTERN.search(text):
            QMessageBox.information(
                self,
                "No placeholders found",
                "This result does not contain Privacy Gate placeholders to restore.",
            )
            return
        if not document_id:
            QMessageBox.information(
                self,
                "Select the original protected document",
                "Choose the matching document from Privacy Gate Library first.",
            )
            return
        if self._active_worker is not None:
            return

        mappings = self.library.get_mappings(document_id)
        source_path = self._source_path
        self._set_busy(True, "Restoring original values locally…")

        def task():
            if source_path is None:
                known = {item.token for item in mappings}
                present = set(TOKEN_PATTERN.findall(text))
                unknown = sorted(present.difference(known))
                restored_text = self.service.restore_text(text, mappings)
                restored_count = sum(text.count(item.token) for item in mappings)
                return {
                    "restored_text": restored_text,
                    "restored_count": restored_count,
                    "unknown": unknown,
                    "report": None,
                    "restored_path": None,
                }

            restored_path = self._preview_root / (
                f"restored-result-{os.getpid()}{source_path.suffix.lower()}"
            )
            report = self.restore_service.restore(source_path, mappings, restored_path)
            restored_text = self.restore_service.extract_text(report.output_path)
            return {
                "restored_text": restored_text,
                "restored_count": report.restored_occurrences,
                "unknown": list(report.unknown_tokens),
                "report": report,
                "restored_path": report.output_path,
            }

        worker = FunctionWorker(task)
        self._active_worker = worker
        worker.signals.result.connect(self._restore_ready)
        worker.signals.error.connect(self._restore_failed)
        worker.signals.finished.connect(self._operation_finished)
        self.thread_pool.start(worker)

    def _restore_ready(self, payload: object) -> None:
        restored_count = int(payload["restored_count"])
        if not restored_count:
            self._set_result_actions(False)
            QMessageBox.warning(
                self,
                "No matching placeholders",
                "None of the placeholders in this AI result match the selected Library document. "
                "Choose the document you originally protected and try again.",
            )
            return

        self._report = payload["report"]
        self._restored_path = payload["restored_path"]
        self.protected_result_view.setPlainText(self.input_text.toPlainText())
        self.output_text.setPlainText(payload["restored_text"])
        self._highlight_view_tokens(self.protected_result_view)

        unknown = list(payload["unknown"])
        self.result_metric.setText(
            f"{restored_count} placeholder occurrence"
            f"{'s' if restored_count != 1 else ''} restored locally"
        )
        self.restore_status.setText(
            "Restore complete. Review the result below, then copy or download it."
        )
        self.result_section.show()
        self._set_result_actions(True)

        suffix = self._restored_path.suffix.lower() if self._restored_path is not None else ""
        format_labels = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel"}
        self.download_button.setVisible(suffix in format_labels)
        if suffix in format_labels:
            self.download_button.setText(f"Download restored {format_labels[suffix]} file")

        if self._source_path is not None and self._source_path.suffix.lower() in {
            ".pdf", ".docx", ".xlsx"
        }:
            self.preview_tabs.setTabVisible(1, True)
            self._refresh_document_preview()
        else:
            self.preview_tabs.setTabVisible(1, False)
            self.preview_tabs.setCurrentIndex(0)

        if unknown:
            QMessageBox.warning(
                self,
                "Restore completed with warnings",
                "Some placeholders do not belong to the selected Library document and remain protected:\n\n"
                + "\n".join(unknown[:12]),
            )

    def _restore_failed(self, message: str) -> None:
        self._set_result_actions(False)
        QMessageBox.critical(self, "Restore failed", message)

    def _operation_finished(self) -> None:
        self._active_worker = None
        self.busy.stop()
        self._set_inputs_enabled(True)
        self._update_restore_state()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._set_inputs_enabled(not busy)
        if busy:
            self.busy.start(message)
        else:
            self.busy.stop()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.input_text.setEnabled(enabled)
        self.drop_zone.setEnabled(enabled)
        self.document_combo.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        if not enabled:
            self.restore_button.setEnabled(False)

    def _highlight_input_tokens(self) -> None:
        self._highlight_view_tokens(self.input_text)
        self._update_token_hint()

    def _highlight_view_tokens(self, editor: QPlainTextEdit) -> None:
        text = editor.toPlainText()
        for match in TOKEN_PATTERN.finditer(text):
            entity = match.group(0)[5:].rsplit("_", 1)[0]
            cursor = QTextCursor(editor.document())
            cursor.setPosition(match.start())
            cursor.setPosition(match.end(), QTextCursor.MoveMode.KeepAnchor)
            formatting = QTextCharFormat()
            formatting.setBackground(QColor(self.TOKEN_COLORS.get(entity, "#E7E9ED")))
            formatting.setForeground(QColor("#102A43"))
            formatting.setFontWeight(int(QFont.Weight.DemiBold))
            cursor.mergeCharFormat(formatting)

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
                self.install_libreoffice_button.setVisible(False)
                self.libreoffice_note.clear()
                self.input_view_stack.setCurrentIndex(0)
                self.output_view_stack.setCurrentIndex(0)
                self.input_pdf_document.load(str(self._source_path))
                if self._restored_path:
                    self.output_pdf_document.load(str(self._restored_path))
                self.preview_note.setText(
                    "AI result with placeholders on the left; locally restored PDF on the right."
                )
                self._set_pdf_page(0)
                return

            if suffix not in {".docx", ".xlsx"}:
                self.high_fidelity_button.setVisible(False)
                self.install_libreoffice_button.setVisible(False)
                self.libreoffice_note.clear()
                return

            self.high_fidelity_button.setVisible(self._libreoffice_available)
            self.install_libreoffice_button.setVisible(not self._libreoffice_available)
            if self._libreoffice_available:
                self.libreoffice_note.setText(
                    "LibreOffice detected. Built-in preview remains available."
                )
            else:
                self.high_fidelity_button.setChecked(False)
                self.libreoffice_note.setText(
                    "Built-in preview active. Optional formatting upgrade:"
                )

            if self._libreoffice_available and self.high_fidelity_button.isChecked():
                self._set_pdf_controls(True)
                input_pdf = self.office_renderer.render(
                    self._source_path, self._preview_root / "restore-input-office"
                )
                self.input_view_stack.setCurrentIndex(0)
                self.output_view_stack.setCurrentIndex(0)
                self.input_pdf_document.load(str(input_pdf))
                if self._restored_path:
                    output_pdf = self.office_renderer.render(
                        self._restored_path, self._preview_root / "restore-output-office"
                    )
                    self.output_pdf_document.load(str(output_pdf))
                self.preview_note.setText(
                    "High-fidelity local preview: AI result on the left, restored result on the right."
                )
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
                self.preview_note.setText(
                    f"Built-in {kind} preview: AI result on the left, restored result on the right."
                )
        except Exception as exc:
            self.preview_note.setText(f"Preview unavailable: {exc}")
            self.preview_tabs.setCurrentIndex(0)

    def _set_pdf_controls(self, visible: bool) -> None:
        for widget in (
            self.pdf_previous_button,
            self.pdf_next_button,
            self.pdf_page_label,
            self.pdf_zoom_out_button,
            self.pdf_fit_button,
            self.pdf_zoom_in_button,
        ):
            widget.setVisible(visible)

    def _toggle_full_preview(self, focused: bool) -> None:
        """Expand the restored document comparison without opening a new window."""
        for widget in (
            self.page_title,
            self.page_subtitle,
            self.local_badge,
            self.steps_card,
            self.input_card,
            self.match_card,
            self.safety_note,
        ):
            widget.setVisible(not focused)
        self.full_preview_button.setText(
            "Exit full screen" if focused else "Full screen preview"
        )
        self._outer_layout.setContentsMargins(
            8 if focused else 24,
            8 if focused else 18,
            8 if focused else 24,
            8 if focused else 14,
        )
        self._content_layout.setSpacing(6 if focused else 14)
        if focused:
            self.preview_tabs.setCurrentIndex(1)
            QTimer.singleShot(0, self._fit_pdf)

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
        self.download_text_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)

    def _download_text(self) -> None:
        text = self.output_text.toPlainText()
        if not text:
            return
        stem = self._source_path.stem if self._source_path is not None else "restored_result"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Download restored text",
            f"{stem}_restored.txt",
            "Text files (*.txt)",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        destination.write_text(text, encoding="utf-8")

    def _download(self) -> None:
        if self._source_path is None:
            self._download_text()
            return

        if self._restored_path is None:
            return

        suffix = self._restored_path.suffix.lower()
        suggested = f"{self._source_path.stem}_restored{suffix}"
        labels = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel", ".txt": "Text"}
        label = labels.get(suffix, "Document")
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Download restored {label}",
            suggested,
            f"{label} files (*{suffix})",
        )
        if path:
            destination = Path(path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            shutil.copy2(self._restored_path, destination)

    def clear(self) -> None:
        if self.full_preview_button.isChecked():
            self.full_preview_button.setChecked(False)
        self._source_path = None
        self._restored_path = None
        self._report = None
        self._syncing_text = True
        self.input_text.clear()
        self._syncing_text = False
        self.paste_toggle.setChecked(False)
        self.protected_result_view.clear()
        self.output_text.clear()
        self.drop_zone.set_filename(None)
        self.result_section.show()
        self.preview_tabs.setTabVisible(1, True)
        self.preview_tabs.setCurrentIndex(1)
        self.input_pdf_document.close()
        self.output_pdf_document.close()
        self._set_result_actions(False)
        self._update_token_hint()
        self._update_restore_state()

    def cleanup_previews(self) -> None:
        self.input_pdf_document.close()
        self.output_pdf_document.close()
        shutil.rmtree(self._preview_root, ignore_errors=True)
