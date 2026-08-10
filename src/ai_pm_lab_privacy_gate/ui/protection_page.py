from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPointF, QTimer, QUrl, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QTextCharFormat, QTextCursor
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding, ProtectionResult
from ai_pm_lab_privacy_gate.domain.profiles import get_profile, list_profiles
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


class ProtectionPage(QWidget):
    library_changed = Signal(str)
    open_connections = Signal()
    TOKEN_COLORS = {
        "PERSON": "#DDE7FF",
        "EMAIL_ADDRESS": "#D9F3EE",
        "PHONE_NUMBER": "#FFE8CC",
        "US_SSN": "#FFDDE2",
        "US_ZIP_CODE": "#E8DFFF",
        "IP_ADDRESS": "#D8EEFF",
        "LOCATION": "#FFF1BD",
        "DATE_TIME": "#E3F2D7",
        "CREDIT_CARD": "#F8DDF1",
        "US_BANK_NUMBER": "#F5E0D3",
        "PROPERTY_IDENTIFIER": "#D9F0F3",
        "CUSTOM": "#E7E9ED",
        "REDACTED": "#D8DEE5",
    }

    def __init__(self, service: PrivacyGateService, library: LibraryRepository) -> None:
        super().__init__()
        self.service = service
        self.library = library
        self.thread_pool = QThreadPool.globalInstance()
        self.current_document: AnalysisDocument | None = None
        self.current_findings: tuple[Finding, ...] = ()
        self.current_result: ProtectionResult | None = None
        self._active_worker: FunctionWorker | None = None
        self._category_sync = False
        self._last_residual: tuple[Finding, ...] = ()
        self._preview_directory = Path(tempfile.gettempdir()) / "AI_PM_LAB_Privacy_Gate"
        self._preview_directory.mkdir(parents=True, exist_ok=True)
        for stale_preview in self._preview_directory.glob("protected-preview-*.pdf"):
            try:
                stale_preview.unlink()
            except OSError:
                pass
        self._preview_path = self._preview_directory / f"protected-preview-{os.getpid()}.pdf"
        self._build_ui()
        self._connect_signals()
        self._update_profile_description()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        headings = QVBoxLayout()
        headings.addWidget(QLabel("Protect a document", objectName="PageTitle"))
        headings.addWidget(
            QLabel("Review every detected item before anything leaves this PC.", objectName="Muted")
        )
        title_row.addLayout(headings)
        title_row.addStretch(1)
        self.local_badge = QLabel("LOCAL  |  Protected", objectName="SafeBadge")
        title_row.addWidget(self.local_badge)
        root.addLayout(title_row)

        setup_bar = QHBoxLayout()
        self.setup_toggle = QToolButton()
        self.setup_toggle.setText("Document setup  -")
        self.setup_toggle.setObjectName("SecondaryTool")
        self.setup_toggle.setCheckable(True)
        self.setup_toggle.setChecked(True)
        setup_bar.addWidget(self.setup_toggle)
        setup_bar.addStretch(1)
        setup_bar.addWidget(QLabel("Load text or PDF, choose a profile, then scan.", objectName="Muted"))
        root.addLayout(setup_bar)

        self.setup_card = QFrame(objectName="Card")
        setup = QVBoxLayout(self.setup_card)
        setup.setContentsMargins(18, 16, 18, 16)
        setup.setSpacing(10)
        profile_row = QHBoxLayout()
        profile_col = QVBoxLayout()
        profile_col.addLayout(
            self._info_heading(
                "Industry profile",
                "Selects the Presidio entities and real-estate rules most relevant to the document.",
            )
        )
        self.profile_combo = QComboBox()
        for profile in list_profiles():
            self.profile_combo.addItem(profile.name, profile.key)
        profile_col.addWidget(self.profile_combo)
        self.profile_description = QLabel(objectName="Muted")
        profile_description = self.profile_description
        profile_description.setWordWrap(True)
        profile_col.addWidget(profile_description)
        mode_col = QVBoxLayout()
        mode_col.addLayout(
            self._info_heading(
                "Protection mode",
                "Choose reversible tokens, generic labels, partial masking or permanent redaction.",
            )
        )
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Reversible placeholders", "reversible")
        self.mode_combo.addItem("Generic placeholders", "generic")
        self.mode_combo.addItem("Masked values (keep last 4)", "mask")
        self.mode_combo.addItem("Permanent redaction", "redact")
        mode_col.addWidget(self.mode_combo)
        self.mode_help = QLabel("Reversible mode enables local restore.", objectName="Muted")
        mode_col.addWidget(self.mode_help)
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Detection confidence", objectName="FieldLabel"))
        threshold_row.addWidget(
            self._info_button(
                "Detection confidence",
                "Lower values detect more possible PII but can create false positives. Higher values are stricter.",
            )
        )
        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setRange(0.10, 0.95)
        self.threshold_input.setSingleStep(0.05)
        self.threshold_input.setDecimals(2)
        self.threshold_input.setValue(0.35)
        self.threshold_input.setToolTip("Lower values find more possible PII; higher values reduce false positives.")
        threshold_row.addWidget(self.threshold_input)
        mode_col.addLayout(threshold_row)
        profile_row.addLayout(profile_col, 2)
        profile_row.addSpacing(16)
        profile_row.addLayout(mode_col, 1)
        setup.addLayout(profile_row)

        self.input_tabs = QTabWidget()
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        text_layout.setContentsMargins(0, 10, 0, 0)
        self.text_input = QPlainTextEdit()
        self.text_input.setMinimumHeight(115)
        self.text_input.setMaximumHeight(155)
        self.text_input.setPlaceholderText(
            "Paste an email, lease excerpt, offer, contractor proposal or other business text."
        )
        text_layout.addWidget(self.text_input)
        self.input_tabs.addTab(text_tab, "Paste text")

        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout(pdf_tab)
        pdf_layout.setContentsMargins(0, 14, 0, 6)
        pdf_row = QHBoxLayout()
        self.pdf_path = QLineEdit()
        self.pdf_path.setReadOnly(True)
        self.pdf_path.setPlaceholderText("Choose a PDF with selectable text")
        self.browse_button = QPushButton("Browse PDF", objectName="Secondary")
        pdf_row.addWidget(self.pdf_path, 1)
        pdf_row.addWidget(self.browse_button)
        pdf_layout.addLayout(pdf_row)
        pdf_layout.addWidget(
            QLabel("Image-only PDFs require OCR, which is planned for a later build.", objectName="Muted")
        )
        self.input_tabs.addTab(pdf_tab, "PDF file")
        setup.addWidget(self.input_tabs)

        scan_row = QHBoxLayout()
        self.scan_button = QPushButton("Scan for sensitive data", objectName="Primary")
        self.clear_button = QPushButton("Clear", objectName="Secondary")
        scan_row.addWidget(self.scan_button)
        scan_row.addWidget(self.clear_button)
        scan_row.addStretch(1)
        setup.addLayout(scan_row)
        root.addWidget(self.setup_card)

        metrics = QHBoxLayout()
        self.findings_metric = QLabel("0 findings", objectName="Metric")
        self.types_metric = QLabel("0 categories", objectName="Metric")
        self.pages_metric = QLabel("0 pages", objectName="Metric")
        self.source_metric = QLabel("No document", objectName="SourceMetric")
        self.verification_metric = QPushButton("Second scan before export", objectName="SafetyMetric")
        self.verification_metric.setToolTip(
            "Privacy Gate scans the protected result again before copy, download or AI actions."
        )
        metrics.addWidget(self.findings_metric)
        metrics.addWidget(self.types_metric)
        metrics.addWidget(self.pages_metric)
        metrics.addWidget(self.source_metric)
        metrics.addWidget(self.verification_metric)
        metrics.addStretch(1)
        root.addLayout(metrics)

        self.categories_dialog = QDialog(self)
        self.categories_dialog.setWindowTitle("Protection categories")
        self.categories_dialog.resize(380, 520)
        categories_layout = QVBoxLayout(self.categories_dialog)
        categories_layout.addWidget(QLabel("Protection categories", objectName="SectionTitle"))
        categories_layout.addWidget(
            QLabel("Choose which detected categories will be protected.", objectName="Muted")
        )
        category_actions = QHBoxLayout()
        self.select_all_button = QPushButton("All", objectName="Tiny")
        self.select_none_button = QPushButton("None", objectName="Tiny")
        category_actions.addWidget(self.select_all_button)
        category_actions.addWidget(self.select_none_button)
        category_actions.addStretch(1)
        categories_layout.addLayout(category_actions)
        self.category_list = QListWidget()
        categories_layout.addWidget(self.category_list, 1)
        close_categories = QPushButton("Done", objectName="Primary")
        close_categories.clicked.connect(self.categories_dialog.accept)
        categories_layout.addWidget(close_categories)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        findings_card = QFrame(objectName="Card")
        findings_layout = QVBoxLayout(findings_card)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Detected items", objectName="SectionTitle"))
        filter_row.addStretch(1)
        self.categories_button = QPushButton("Categories", objectName="Secondary")
        self.categories_button.setToolTip("Select or deselect entire groups of detected information.")
        filter_row.addWidget(self.categories_button)
        self.reset_selections_button = QPushButton("Reset", objectName="Tiny")
        self.reset_selections_button.setToolTip("Select every detected item again and clear the filter.")
        filter_row.addWidget(self.reset_selections_button)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter findings")
        self.filter_input.setMaximumWidth(220)
        filter_row.addWidget(self.filter_input)
        findings_layout.addLayout(filter_row)
        self.findings_table = QTableWidget(0, 5)
        self.findings_table.setHorizontalHeaderLabels(
            ["Protect", "Type", "Value", "Page", "Confidence"]
        )
        self.findings_table.setAlternatingRowColors(True)
        self.findings_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.findings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.findings_table.verticalHeader().setVisible(False)
        header = self.findings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        findings_layout.addWidget(self.findings_table, 1)
        findings_actions = QHBoxLayout()
        self.add_sensitive_button = QPushButton("+ Add sensitive item", objectName="Secondary")
        findings_actions.addWidget(self.add_sensitive_button)
        findings_actions.addStretch(1)
        findings_actions.addWidget(QLabel("Click a row to review context", objectName="Muted"))
        findings_layout.addLayout(findings_actions)

        preview_card = QFrame(objectName="Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Protected preview", objectName="SectionTitle"))
        preview_header.addStretch(1)
        preview_header.addWidget(QLabel("Color-coded by protected category", objectName="TokenHint"))
        preview_layout.addLayout(preview_header)

        self.color_legend = QLabel(objectName="ColorLegend")
        self.color_legend.setWordWrap(True)
        self.color_legend.setText("Protected categories will appear here after the scan.")
        preview_layout.addWidget(self.color_legend)

        self.preview_tabs = QTabWidget()
        text_preview_tab = QWidget()
        text_preview_layout = QVBoxLayout(text_preview_tab)
        text_preview_layout.setContentsMargins(0, 8, 0, 0)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Run a scan to generate the protected preview.")
        text_preview_layout.addWidget(self.preview)
        self.preview_tabs.addTab(text_preview_tab, "Protected text")

        pdf_comparison_tab = QWidget()
        pdf_comparison_layout = QVBoxLayout(pdf_comparison_tab)
        pdf_comparison_layout.setContentsMargins(0, 8, 0, 0)
        comparison_note = QLabel(
            "Original source on the left. The secure, layout-preserving protected copy on the right.",
            objectName="Muted",
        )
        comparison_note.setWordWrap(True)
        pdf_comparison_layout.addWidget(comparison_note)
        pdf_controls = QHBoxLayout()
        self.pdf_previous_button = QPushButton("‹", objectName="Tiny")
        self.pdf_previous_button.setToolTip("Previous page in both previews")
        self.pdf_next_button = QPushButton("›", objectName="Tiny")
        self.pdf_next_button.setToolTip("Next page in both previews")
        self.pdf_page_label = QLabel("Page 1 / 1", objectName="PdfPageLabel")
        self.pdf_zoom_out_button = QPushButton("−", objectName="Tiny")
        self.pdf_zoom_out_button.setToolTip("Zoom out both previews")
        self.pdf_fit_button = QPushButton("Fit width", objectName="Tiny")
        self.pdf_fit_button.setToolTip("Fit both PDF previews to their panel width")
        self.pdf_zoom_in_button = QPushButton("+", objectName="Tiny")
        self.pdf_zoom_in_button.setToolTip("Zoom in both previews")
        pdf_controls.addWidget(self.pdf_previous_button)
        pdf_controls.addWidget(self.pdf_next_button)
        pdf_controls.addWidget(self.pdf_page_label)
        pdf_controls.addStretch(1)
        pdf_controls.addWidget(self.pdf_zoom_out_button)
        pdf_controls.addWidget(self.pdf_fit_button)
        pdf_controls.addWidget(self.pdf_zoom_in_button)
        pdf_comparison_layout.addLayout(pdf_controls)
        pdf_splitter = QSplitter(Qt.Orientation.Horizontal)
        original_panel, self.original_pdf_view = self._build_pdf_panel("Original PDF", "Local source")
        protected_panel, self.protected_pdf_view = self._build_pdf_panel(
            "Protected PDF", "Exact download preview"
        )
        self.original_pdf_document = QPdfDocument(self)
        self.protected_pdf_document = QPdfDocument(self)
        self.original_pdf_view.setDocument(self.original_pdf_document)
        self.protected_pdf_view.setDocument(self.protected_pdf_document)
        for view in (self.original_pdf_view, self.protected_pdf_view):
            view.setPageMode(QPdfView.PageMode.MultiPage)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        pdf_splitter.addWidget(original_panel)
        pdf_splitter.addWidget(protected_panel)
        pdf_splitter.setChildrenCollapsible(False)
        pdf_splitter.setSizes([500, 500])
        pdf_comparison_layout.addWidget(pdf_splitter, 1)
        self.preview_tabs.addTab(pdf_comparison_tab, "PDF comparison")
        self.preview_tabs.setTabVisible(1, False)
        preview_layout.addWidget(self.preview_tabs, 1)
        self.labels_input = QLineEdit()
        self.labels_input.setPlaceholderText("Library labels, comma separated (e.g. Lease, Property 014)")
        preview_layout.addWidget(self.labels_input)

        workspace.addWidget(findings_card)
        workspace.addWidget(preview_card)
        workspace.setChildrenCollapsible(False)
        workspace.setSizes([650, 650])
        root.addWidget(workspace, 1)

        action_bar = QFrame(objectName="ActionBar")
        actions = QHBoxLayout(action_bar)
        actions.addWidget(
            self._info_button(
                "Protected result actions",
                "Copy keeps the result in memory. Save stores it locally. Download creates a protected TXT or PDF.",
            )
        )
        self.copy_button = QPushButton("Copy protected text", objectName="Secondary")
        self.copy_button.setToolTip("Copy the protected text after the automatic residual-PII check.")
        self.save_copy_button = QPushButton("Save + Copy", objectName="Primary")
        self.save_copy_button.setToolTip("Save to the encrypted local library and copy the protected text.")
        self.save_download_button = QPushButton("Save + Download", objectName="Gold")
        self.save_download_button.setToolTip("Save locally and export the protected TXT or layout-preserving PDF.")
        self.ai_button = QToolButton()
        self.ai_button.setText("Open with AI")
        self.ai_button.setObjectName("SecondaryTool")
        self.ai_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        ai_menu = self._build_ai_menu()
        self.ai_button.setMenu(ai_menu)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        actions.addWidget(self.save_copy_button)
        actions.addWidget(self.save_download_button)
        actions.addWidget(self.ai_button)
        root.addWidget(action_bar)
        self._set_result_actions(False)

        self._pdf_preview_timer = QTimer(self)
        self._pdf_preview_timer.setSingleShot(True)
        self._pdf_preview_timer.setInterval(220)
        self._pdf_preview_timer.timeout.connect(self._update_pdf_comparison)

    def _info_heading(self, title: str, message: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QLabel(title, objectName="FieldLabel"))
        row.addWidget(self._info_button(title, message))
        row.addStretch(1)
        return row

    def _info_button(self, title: str, message: str) -> QToolButton:
        button = QToolButton()
        button.setText("i")
        button.setObjectName("InfoButton")
        button.setToolTip(message)
        button.clicked.connect(lambda _checked=False: QMessageBox.information(self, title, message))
        return button

    @staticmethod
    def _build_pdf_panel(title: str, subtitle: str) -> tuple[QFrame, QPdfView]:
        panel = QFrame(objectName="PdfPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        heading = QHBoxLayout()
        heading.addWidget(QLabel(title, objectName="PdfTitle"))
        heading.addStretch(1)
        heading.addWidget(QLabel(subtitle, objectName="PdfBadge"))
        layout.addLayout(heading)
        view = QPdfView()
        view.setObjectName("PdfView")
        layout.addWidget(view, 1)
        return panel, view

    def _build_ai_menu(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        manual = menu.addAction("Copy & Open ChatGPT")
        manual.triggered.connect(self._copy_and_open_chatgpt)
        menu.addSeparator()
        connections = menu.addAction("Configure connections…")
        connections.triggered.connect(self.open_connections.emit)
        return menu

    def _connect_signals(self) -> None:
        self.setup_toggle.toggled.connect(self._toggle_setup)
        self.profile_combo.currentIndexChanged.connect(self._update_profile_description)
        self.mode_combo.currentIndexChanged.connect(self._refresh_preview)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_help)
        self.browse_button.clicked.connect(self._browse_pdf)
        self.scan_button.clicked.connect(self._start_analysis)
        self.clear_button.clicked.connect(self.clear)
        self.findings_table.itemChanged.connect(self._refresh_preview)
        self.category_list.itemChanged.connect(self._category_changed)
        self.select_all_button.clicked.connect(lambda: self._set_all_categories(True))
        self.select_none_button.clicked.connect(lambda: self._set_all_categories(False))
        self.categories_button.clicked.connect(self._open_categories)
        self.reset_selections_button.clicked.connect(self._reset_selections)
        self.filter_input.textChanged.connect(self._apply_filter)
        self.findings_table.cellClicked.connect(self._finding_selected)
        self.add_sensitive_button.clicked.connect(self._add_sensitive_item)
        self.copy_button.clicked.connect(self._copy_result)
        self.save_copy_button.clicked.connect(self._save_and_copy)
        self.save_download_button.clicked.connect(self._save_and_download)
        self.verification_metric.clicked.connect(self._show_residual_details)
        self.pdf_previous_button.clicked.connect(lambda: self._change_pdf_page(-1))
        self.pdf_next_button.clicked.connect(lambda: self._change_pdf_page(1))
        self.pdf_zoom_out_button.clicked.connect(lambda: self._zoom_pdf(0.82))
        self.pdf_fit_button.clicked.connect(self._fit_pdf_width)
        self.pdf_zoom_in_button.clicked.connect(lambda: self._zoom_pdf(1.22))
        self.original_pdf_view.pageNavigator().currentPageChanged.connect(self._sync_pdf_page)

    def _toggle_setup(self, visible: bool) -> None:
        self.setup_card.setVisible(visible)
        self.setup_toggle.setText("Document setup  -" if visible else "Document setup  +")

    def _open_categories(self) -> None:
        self.categories_dialog.show()
        self.categories_dialog.raise_()
        self.categories_dialog.activateWindow()

    def _update_profile_description(self) -> None:
        profile = get_profile(self.profile_combo.currentData())
        self.profile_description.setText(profile.description)
        self.threshold_input.setValue(profile.threshold)

    def _update_mode_help(self) -> None:
        messages = {
            "reversible": "Encrypted local mapping enables restore.",
            "generic": "Permanent generic placeholders; original values are not stored.",
            "mask": "Permanent masking keeps only the final four letters or digits.",
            "redact": "Permanent redaction replaces every selected value with [REDACTED].",
        }
        self.mode_help.setText(messages.get(self.mode_combo.currentData(), ""))

    def _browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose PDF", "", "PDF files (*.pdf)")
        if path:
            self.pdf_path.setText(path)
            self.input_tabs.setCurrentIndex(1)

    def _start_analysis(self) -> None:
        profile = replace(
            get_profile(self.profile_combo.currentData()),
            threshold=float(self.threshold_input.value()),
        )
        tab = self.input_tabs.currentIndex()
        text = self.text_input.toPlainText().strip()
        pdf_path = self.pdf_path.text().strip()
        if tab == 0 and not text:
            QMessageBox.information(self, "Nothing to scan", "Paste text before starting the scan.")
            return
        if tab == 1 and not pdf_path:
            QMessageBox.information(self, "No PDF selected", "Choose a PDF before starting the scan.")
            return

        def task():
            document = self.service.document_from_text(text) if tab == 0 else self.service.document_from_pdf(pdf_path)
            return document, self.service.analyze(document, profile)

        self._set_busy(True)
        worker = FunctionWorker(task)
        self._active_worker = worker
        worker.signals.result.connect(self._analysis_ready)
        worker.signals.error.connect(lambda message: QMessageBox.critical(self, "Unable to scan", message))
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self.thread_pool.start(worker)

    def _analysis_ready(self, payload: object) -> None:
        self.current_document, self.current_findings = payload
        self._populate_findings()
        self._refresh_preview()
        self.setup_toggle.setChecked(False)

    def _populate_findings(self) -> None:
        self.findings_table.blockSignals(True)
        self.findings_table.setRowCount(len(self.current_findings))
        for row, finding in enumerate(self.current_findings):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.CheckState.Checked)
            checkbox.setData(Qt.ItemDataRole.UserRole, finding.finding_id)
            self.findings_table.setItem(row, 0, checkbox)
            entity_item = QTableWidgetItem(finding.entity_type)
            entity_item.setBackground(QColor(self._entity_color(finding.entity_type)))
            self.findings_table.setItem(row, 1, entity_item)
            value = QTableWidgetItem(finding.text)
            value.setToolTip(finding.context)
            self.findings_table.setItem(row, 2, value)
            page = str(finding.page_number) if self.current_document and self.current_document.source_kind == "pdf" else "Text"
            self.findings_table.setItem(row, 3, QTableWidgetItem(page))
            confidence = QTableWidgetItem(f"{finding.score:.0%}")
            if finding.score < 0.6:
                confidence.setForeground(QColor("#B7791F"))
            self.findings_table.setItem(row, 4, confidence)
        self.findings_table.blockSignals(False)
        self._populate_categories()
        types = len({item.entity_type for item in self.current_findings})
        pages = len(self.current_document.pages) if self.current_document else 0
        self.findings_metric.setText(f"{len(self.current_findings)} findings")
        self.types_metric.setText(f"{types} categories")
        self.pages_metric.setText(f"{pages} page{'s' if pages != 1 else ''}")
        if self.current_document and self.current_document.source_path:
            self.source_metric.setText(f"PDF  |  {self.current_document.source_path.name}")
            self.source_metric.setToolTip(str(self.current_document.source_path))
        else:
            self.source_metric.setText("Pasted text")
            self.source_metric.setToolTip("")
        self._update_color_legend()

    def _update_color_legend(self) -> None:
        entity_types = sorted({item.entity_type for item in self.current_findings})
        if not entity_types:
            self.color_legend.setText("Protected categories will appear here after the scan.")
            return
        chips = []
        for entity_type in entity_types:
            label = entity_type.replace("_", " ").title()
            chips.append(
                f'<span style="background-color:{self._entity_color(entity_type)}; '
                f'color:#102A43; font-weight:600;">&nbsp;{label}&nbsp;</span>'
            )
        self.color_legend.setText("&nbsp;&nbsp;".join(chips))

    def _populate_categories(self) -> None:
        counts: dict[str, int] = {}
        for finding in self.current_findings:
            counts[finding.entity_type] = counts.get(finding.entity_type, 0) + 1
        self._category_sync = True
        self.category_list.clear()
        for entity_type, count in sorted(counts.items()):
            item = QListWidgetItem(f"{entity_type.replace('_', ' ').title()}   {count}")
            item.setData(Qt.ItemDataRole.UserRole, entity_type)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.category_list.addItem(item)
        self._category_sync = False

    def _category_changed(self, item: QListWidgetItem) -> None:
        if self._category_sync:
            return
        entity_type = item.data(Qt.ItemDataRole.UserRole)
        checked = item.checkState()
        self.findings_table.blockSignals(True)
        for row in range(self.findings_table.rowCount()):
            if self.findings_table.item(row, 1).text() == entity_type:
                self.findings_table.item(row, 0).setCheckState(checked)
        self.findings_table.blockSignals(False)
        self._refresh_preview()

    def _set_all_categories(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.category_list.count()):
            self.category_list.item(index).setCheckState(state)

    def _reset_selections(self) -> None:
        self.filter_input.clear()
        self._set_all_categories(True)

    def _finding_selected(self, row: int, _column: int) -> None:
        if not self.current_document or self.current_document.source_kind != "pdf":
            return
        item = self.findings_table.item(row, 3)
        if item and item.text().isdigit():
            self._set_pdf_page(max(0, int(item.text()) - 1))
            self.preview_tabs.setCurrentIndex(1)

    def _selected_findings(self) -> tuple[Finding, ...]:
        selected_ids = {
            self.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.findings_table.rowCount())
            if self.findings_table.item(row, 0).checkState() == Qt.CheckState.Checked
        }
        return tuple(item for item in self.current_findings if item.finding_id in selected_ids)

    def _refresh_preview(self, *_args) -> None:
        if self.current_document is None:
            return
        self.current_result = self.service.protect(
            self.current_document,
            self._selected_findings(),
            replacement_mode=self.mode_combo.currentData(),
        )
        self._render_preview(self.current_result.combined_text)
        protected_count = len(self.current_result.applied_findings)
        self.findings_metric.setText(
            f"{len(self.current_findings)} detected  |  {protected_count} protected"
        )
        if self.current_document.source_kind == "pdf":
            self.preview_tabs.setTabVisible(1, True)
            self._pdf_preview_timer.start()
        else:
            self.preview_tabs.setTabVisible(1, False)
        self._set_result_actions(True)

    def _entity_color(self, entity_type: str) -> str:
        if entity_type in self.TOKEN_COLORS:
            return self.TOKEN_COLORS[entity_type]
        palette = ("#DCEAF7", "#E4E0F7", "#DFF1E3", "#F7E7D8", "#F3DDE6", "#E8EDD5")
        return palette[sum(ord(character) for character in entity_type) % len(palette)]

    def _render_preview(self, text: str) -> None:
        self.preview.setPlainText(text)
        spans = self.current_result.combined_spans if self.current_result else ()
        for span in spans:
            cursor = QTextCursor(self.preview.document())
            cursor.setPosition(span.start)
            cursor.setPosition(span.end, QTextCursor.MoveMode.KeepAnchor)
            token_format = QTextCharFormat()
            token_format.setBackground(QColor(self._entity_color(span.entity_type)))
            token_format.setForeground(QColor("#102A43"))
            token_format.setFontWeight(int(QFont.Weight.DemiBold))
            cursor.mergeCharFormat(token_format)

    def _update_pdf_comparison(self) -> None:
        if (
            self.current_document is None
            or self.current_result is None
            or self.current_document.source_kind != "pdf"
            or self.current_document.source_path is None
        ):
            return
        protected_path = self._preview_path
        try:
            self.protected_pdf_document.close()
            self.service.save_protected_pdf(
                self.current_result,
                protected_path,
                source_document=self.current_document,
            )
            self.original_pdf_document.close()
            self.original_pdf_document.load(str(self.current_document.source_path))
            self.protected_pdf_document.load(str(protected_path))
        except Exception as exc:
            self.preview_tabs.setTabToolTip(1, f"Preview unavailable: {exc}")
        else:
            self.preview_tabs.setTabToolTip(
                1, "Compare the local source with the secure layout-preserving PDF generated by Privacy Gate."
            )
            self._set_pdf_page(0)

    def _set_pdf_page(self, page: int) -> None:
        page_count = max(
            self.original_pdf_document.pageCount(), self.protected_pdf_document.pageCount()
        )
        if page_count <= 0:
            return
        target = max(0, min(page, page_count - 1))
        for view in (self.original_pdf_view, self.protected_pdf_view):
            view.pageNavigator().jump(target, QPointF(0, 0), view.zoomFactor())
        self.pdf_page_label.setText(f"Page {target + 1} / {page_count}")

    def _change_pdf_page(self, delta: int) -> None:
        self._set_pdf_page(self.original_pdf_view.pageNavigator().currentPage() + delta)

    def _sync_pdf_page(self, page: int) -> None:
        if self.protected_pdf_view.pageNavigator().currentPage() != page:
            self.protected_pdf_view.pageNavigator().jump(
                page, QPointF(0, 0), self.protected_pdf_view.zoomFactor()
            )
        page_count = max(
            self.original_pdf_document.pageCount(), self.protected_pdf_document.pageCount()
        )
        self.pdf_page_label.setText(f"Page {page + 1} / {max(1, page_count)}")

    def _zoom_pdf(self, factor: float) -> None:
        for view in (self.original_pdf_view, self.protected_pdf_view):
            view.setZoomMode(QPdfView.ZoomMode.Custom)
            view.setZoomFactor(max(0.25, min(4.0, view.zoomFactor() * factor)))

    def _fit_pdf_width(self) -> None:
        for view in (self.original_pdf_view, self.protected_pdf_view):
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _apply_filter(self, term: str) -> None:
        value = term.casefold().strip()
        for row in range(self.findings_table.rowCount()):
            haystack = " ".join(
                self.findings_table.item(row, column).text()
                for column in range(1, self.findings_table.columnCount())
            ).casefold()
            self.findings_table.setRowHidden(row, bool(value and value not in haystack))

    def _add_sensitive_item(self) -> None:
        if self.current_document is None:
            return
        value, ok = QInputDialog.getText(self, "Add sensitive item", "Exact text to protect:")
        if not ok or not value:
            return
        entity_type, ok = QInputDialog.getItem(
            self,
            "Sensitive category",
            "Category:",
            ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "US_SSN", "US_BANK_NUMBER", "PROPERTY_IDENTIFIER", "CUSTOM"],
            editable=True,
        )
        if not ok or not entity_type:
            return
        additions: list[Finding] = []
        for page in self.current_document.pages:
            start = 0
            while True:
                index = page.text.find(value, start)
                if index < 0:
                    break
                additions.append(
                    Finding(
                        finding_id=f"manual-{page.page_number}-{index}-{len(additions)}",
                        entity_type=entity_type.strip().upper().replace(" ", "_"),
                        text=value,
                        start=index,
                        end=index + len(value),
                        score=1.0,
                        page_number=page.page_number,
                        context=page.text[max(0, index - 34) : index + len(value) + 34],
                    )
                )
                start = index + len(value)
        if not additions:
            QMessageBox.information(self, "Text not found", "That exact text was not found in the document.")
            return
        self.current_findings = self.current_findings + tuple(additions)
        self._populate_findings()
        self._refresh_preview()

    def _derive_title(self) -> str:
        if self.current_document and self.current_document.source_path:
            return self.current_document.source_path.stem
        for line in self.text_input.toPlainText().splitlines():
            if line.strip():
                return line.strip()[:80]
        return "Protected document"

    def _save_to_library(self):
        if self.current_document is None or self.current_result is None:
            return None
        title, ok = QInputDialog.getText(self, "Save to local library", "Document title:", text=self._derive_title())
        if not ok:
            return None
        source_name = self.current_document.source_path.name if self.current_document.source_path else "Pasted text"
        labels = tuple(part.strip() for part in self.labels_input.text().split(",") if part.strip())
        document = self.library.save(
            title=title,
            source_kind=self.current_document.source_kind,
            source_name=source_name,
            profile_key=self.profile_combo.currentData(),
            result=self.current_result,
            labels=labels,
        )
        self.library_changed.emit(document.document_id)
        return document

    def _current_profile(self):
        return replace(
            get_profile(self.profile_combo.currentData()),
            threshold=float(self.threshold_input.value()),
        )

    def _confirm_residual_risk(self, action: str) -> bool:
        if self.current_result is None:
            return False
        residual = self.service.verify_protected(self.current_result, self._current_profile())
        self._last_residual = residual
        if not residual:
            self.verification_metric.setText("Verified: no remaining PII")
            self.verification_metric.setProperty("warning", False)
            self.verification_metric.style().unpolish(self.verification_metric)
            self.verification_metric.style().polish(self.verification_metric)
            return True
        self.verification_metric.setText(f"Warning: {len(residual)} possible PII remain")
        self.verification_metric.setProperty("warning", True)
        self.verification_metric.style().unpolish(self.verification_metric)
        self.verification_metric.style().polish(self.verification_metric)
        examples = "\n".join(
            f"• {item.entity_type}: {item.text[:45]} (page {item.page_number})"
            for item in residual[:8]
        )
        answer = QMessageBox.warning(
            self,
            "Possible sensitive data remains",
            f"Privacy Gate found {len(residual)} possible sensitive item(s) in the protected copy before {action}:\n\n{examples}\n\nReturn to the findings and protect them whenever possible.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ignore,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ignore

    def _show_residual_details(self) -> None:
        if not self._last_residual:
            QMessageBox.information(
                self,
                "Second privacy scan",
                "The protected result is checked again before it can leave the app. No unresolved items are currently recorded.",
            )
            return
        details = "\n".join(
            f"• Page {item.page_number} — {item.entity_type}: {item.text[:70]}"
            for item in self._last_residual[:20]
        )
        QMessageBox.warning(
            self,
            "Possible sensitive data remains",
            f"Review these possible residual items:\n\n{details}",
        )

    def _copy_result(self) -> None:
        if self.current_result and self._confirm_residual_risk("copying"):
            QApplication.clipboard().setText(self.current_result.combined_text)

    def _save_and_copy(self) -> None:
        if not self._confirm_residual_risk("copying"):
            return
        document = self._save_to_library()
        if document:
            QApplication.clipboard().setText(self.current_result.combined_text)
            QMessageBox.information(self, "Saved locally", "The protected text was saved and copied.")

    def _save_and_download(self) -> None:
        if not self._confirm_residual_risk("downloading"):
            return
        document = self._save_to_library()
        if not document or not self.current_result or not self.current_document:
            return
        if self.current_document.source_kind == "pdf":
            suggested = f"{document.title}_protected.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Save protected PDF", suggested, "PDF files (*.pdf)")
            if path:
                self.service.save_protected_pdf(
                    self.current_result,
                    path if path.lower().endswith(".pdf") else path + ".pdf",
                    source_document=self.current_document,
                )
        else:
            suggested = f"{document.title}_protected.txt"
            path, _ = QFileDialog.getSaveFileName(self, "Save protected text", suggested, "Text files (*.txt)")
            if path:
                self.service.save_protected_text(self.current_result, path if path.lower().endswith(".txt") else path + ".txt")

    def _copy_and_open_chatgpt(self) -> None:
        if not self.current_result or not self._confirm_residual_risk("opening an AI service"):
            return
        QApplication.clipboard().setText(self.current_result.combined_text)
        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))

    def _set_result_actions(self, enabled: bool) -> None:
        for widget in (self.copy_button, self.save_copy_button, self.save_download_button, self.ai_button):
            widget.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.profile_combo.setEnabled(not busy)
        if not busy:
            self._active_worker = None

    def cleanup_pdf_preview(self) -> None:
        """Release Windows PDF file handles before removing the temporary preview."""
        self._pdf_preview_timer.stop()
        self.original_pdf_view.setDocument(None)
        self.protected_pdf_view.setDocument(None)
        self.original_pdf_document.close()
        self.protected_pdf_document.close()
        QApplication.processEvents()
        try:
            self._preview_path.unlink(missing_ok=True)
        except OSError:
            # Qt's renderer can release the handle just after shutdown. Any stale
            # preview is removed automatically at the next application start.
            pass

    def clear(self) -> None:
        self.text_input.clear()
        self.pdf_path.clear()
        self.preview.clear()
        self._pdf_preview_timer.stop()
        self.original_pdf_document.close()
        self.protected_pdf_document.close()
        self.preview_tabs.setTabVisible(1, False)
        self.preview_tabs.setCurrentIndex(0)
        self.findings_table.setRowCount(0)
        self.category_list.clear()
        self.labels_input.clear()
        self.current_document = None
        self.current_findings = ()
        self.current_result = None
        self.findings_metric.setText("0 findings")
        self.types_metric.setText("0 categories")
        self.pages_metric.setText("0 pages")
        self.source_metric.setText("No document")
        self.source_metric.setToolTip("")
        self.color_legend.setText("Protected categories will appear here after the scan.")
        self.verification_metric.setText("Second scan before export")
        self._last_residual = ()
        self._set_result_actions(False)
        self.setup_toggle.setChecked(True)
