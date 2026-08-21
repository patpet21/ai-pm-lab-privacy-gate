from __future__ import annotations

import os
import re
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
    QStackedWidget,
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
from ai_pm_lab_privacy_gate.domain.profiles import (
    entities_for_scope,
    get_profile,
    get_scope,
    list_profiles,
    list_scopes,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.documents.office_preview import OfficePreviewRenderer
from ai_pm_lab_privacy_gate.ui.office_internal_preview import OfficeInternalPreview
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


def _manual_findings_for_text(
    document: AnalysisDocument,
    value: str,
    entity_type: str,
) -> tuple[Finding, ...]:
    """Locate a user-supplied value reliably in extracted document text.

    PDF/Word extraction can change capitalization and collapse or expand spaces.
    Matching the words case-insensitively while accepting any whitespace keeps the
    finding offsets anchored to the *actual* extracted text.  Those exact offsets
    are then used by protection, visual preview, export, restore, and Library save.
    """
    requested = " ".join(value.split())
    if not requested:
        return ()
    normalized_entity = entity_type.strip().upper().replace(" ", "_")
    pattern = re.compile(
        r"\s+".join(re.escape(part) for part in requested.split(" ")),
        flags=re.IGNORECASE,
    )
    additions: list[Finding] = []
    for page in document.pages:
        for match in pattern.finditer(page.text):
            matched_text = page.text[match.start() : match.end()]
            additions.append(
                Finding(
                    finding_id=(
                        f"manual-{page.page_number}-{match.start()}-"
                        f"{match.end()}-{normalized_entity}"
                    ),
                    entity_type=normalized_entity,
                    text=matched_text,
                    start=match.start(),
                    end=match.end(),
                    score=1.0,
                    page_number=page.page_number,
                    context=page.text[
                        max(0, match.start() - 34) : min(len(page.text), match.end() + 34)
                    ],
                )
            )
    return tuple(additions)


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
        "US_ROUTING_NUMBER": "#E5EED2",
        "SWIFT_BIC": "#DDEBD7",
        "CARD_LAST_FOUR": "#F8DDF1",
        "CARD_TRANSACTION_ID": "#F3E3D5",
        "TRANSFER_TRANSACTION_ID": "#E2E6F5",
        "STATEMENT_REFERENCE": "#DEE7EE",
        "POSTAL_CODE": "#E8DFFF",
        "STREET_ADDRESS": "#FFF1BD",
        "MONEY_AMOUNT": "#DDEFD9",
        "MERCHANT": "#E5E0F5",
        "COUNTERPARTY": "#DCE8F8",
        "TRANSACTION_REFERENCE": "#F4E7D5",
        "BUSINESS_REGISTRATION_NUMBER": "#DEE7EE",
        "INVOICE_NUMBER": "#E2E6F5",
        "PURCHASE_ORDER_ID": "#E5E0F5",
        "CONTRACT_ID": "#D9F0F3",
        "CUSTOMER_ID": "#DCE8F8",
        "EMPLOYEE_ID": "#DDE7FF",
        "CASE_REFERENCE": "#F4E7D5",
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
        self._reviewed_row: int | None = None
        self._last_residual: tuple[Finding, ...] = ()
        self._preview_directory = Path(tempfile.gettempdir()) / "AI_PM_LAB_Privacy_Gate"
        self._preview_directory.mkdir(parents=True, exist_ok=True)
        for stale_preview in self._preview_directory.glob("protected-preview-*.pdf"):
            try:
                stale_preview.unlink()
            except OSError:
                pass
        self._preview_generation = 0
        self._preview_path: Path | None = None
        self._office_original_directory = self._preview_directory / f"office-original-{os.getpid()}"
        self._office_protected_directory = self._preview_directory / f"office-protected-{os.getpid()}"
        self._office_preview_renderer = OfficePreviewRenderer()
        self._libreoffice_available = self._office_preview_renderer.find_executable() is not None
        self._build_ui()
        self._connect_signals()
        self._update_profile_description()
        self._update_scope_description()

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
        setup_bar.addWidget(
            QLabel("Load text, PDF, Word or Excel, choose a profile, then scan.", objectName="Muted")
        )
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
        profile_description.setVisible(False)
        scope_col = QVBoxLayout()
        scope_col.addLayout(
            self._info_heading(
                "Protection scope",
                "Controls whether Privacy Gate scans essential PII only or also financial and business-sensitive data.",
            )
        )
        self.scope_combo = QComboBox()
        for scope in list_scopes():
            self.scope_combo.addItem(scope.name, scope.key)
        self.scope_combo.setCurrentIndex(self.scope_combo.findData("financial"))
        scope_col.addWidget(self.scope_combo)
        self.scope_description = QLabel(objectName="Muted")
        self.scope_description.setWordWrap(True)
        self.scope_description.setVisible(False)
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
        self.mode_help.setVisible(False)
        confidence_col = QVBoxLayout()
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Confidence", objectName="FieldLabel"))
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
        confidence_col.addLayout(threshold_row)
        document_col = QVBoxLayout()
        document_col.addLayout(
            self._info_heading(
                "Document file",
                "Choose a local PDF, Word or Excel file. Its original contents stay on this computer.",
            )
        )
        document_row = QHBoxLayout()
        document_row.setSpacing(6)
        self.pdf_path = QLineEdit()
        self.pdf_path.setReadOnly(True)
        self.pdf_path.setPlaceholderText("PDF, Word or Excel")
        self.browse_button = QPushButton("Browse", objectName="Secondary")
        document_row.addWidget(self.pdf_path, 1)
        document_row.addWidget(self.browse_button)
        document_col.addLayout(document_row)
        profile_row.addLayout(profile_col, 2)
        profile_row.addSpacing(10)
        profile_row.addLayout(scope_col, 2)
        profile_row.addSpacing(10)
        profile_row.addLayout(mode_col, 2)
        profile_row.addSpacing(10)
        profile_row.addLayout(confidence_col, 1)
        profile_row.addSpacing(10)
        profile_row.addLayout(document_col, 3)
        setup.addLayout(profile_row)

        self.input_tabs = QTabWidget()
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        text_layout.setContentsMargins(0, 10, 0, 0)
        self.text_input = QPlainTextEdit()
        self.text_input.setMinimumHeight(72)
        self.text_input.setMaximumHeight(92)
        self.text_input.setPlaceholderText(
            "Paste an email, lease excerpt, offer, contractor proposal or other business text."
        )
        text_layout.addWidget(self.text_input)
        self.input_tabs.addTab(text_tab, "Paste text")

        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout(pdf_tab)
        pdf_layout.setContentsMargins(0, 7, 0, 2)
        pdf_layout.addWidget(
            QLabel(
                "Use the Document file selector above. PDF, Word and Excel content is processed locally.",
                objectName="Muted",
            )
        )
        self.input_tabs.addTab(pdf_tab, "Document file")
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

        selection_row = QHBoxLayout()
        selection_row.addWidget(
            QLabel("Checked = protect  |  Unchecked = keep", objectName="ReviewGuide")
        )
        selection_row.addStretch(1)
        self.protect_all_button = QPushButton("Protect all", objectName="Tiny")
        self.keep_all_button = QPushButton("Keep all", objectName="Tiny")
        self.invert_selection_button = QPushButton("Invert", objectName="Tiny")
        self.protect_all_button.setToolTip("Protect every detected item in the document.")
        self.keep_all_button.setToolTip("Keep every detected value visible in the protected copy.")
        self.invert_selection_button.setToolTip("Reverse all protected and unprotected items.")
        selection_row.addWidget(self.protect_all_button)
        selection_row.addWidget(self.keep_all_button)
        selection_row.addWidget(self.invert_selection_button)
        findings_layout.addLayout(selection_row)
        self.findings_table = QTableWidget(0, 5)
        self.findings_table.setHorizontalHeaderLabels(
            ["Protect", "Type", "Value", "Location", "Confidence"]
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
        findings_actions.addWidget(QLabel("Select a row to inspect it", objectName="Muted"))
        findings_layout.addLayout(findings_actions)

        self.finding_context = QLabel(
            "Select a detected item to see its location and surrounding text.",
            objectName="ReviewContext",
        )
        self.finding_context.setWordWrap(True)
        self.finding_context.setMinimumHeight(48)
        findings_layout.addWidget(self.finding_context)
        finding_decision_row = QHBoxLayout()
        self.protect_this_button = QPushButton("Protect this", objectName="Primary")
        self.keep_this_button = QPushButton("Keep original", objectName="Secondary")
        self.protect_this_button.setEnabled(False)
        self.keep_this_button.setEnabled(False)
        finding_decision_row.addWidget(self.protect_this_button)
        finding_decision_row.addWidget(self.keep_this_button)
        finding_decision_row.addStretch(1)
        findings_layout.addLayout(finding_decision_row)

        preview_card = QFrame(objectName="Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Protected preview", objectName="SectionTitle"))
        preview_header.addStretch(1)
        self.focus_preview_button = QPushButton("Full document view", objectName="Secondary")
        self.focus_preview_button.setCheckable(True)
        self.focus_preview_button.setToolTip(
            "Use the full window for the original/protected comparison. The review panel remains one click away."
        )
        preview_header.addWidget(self.focus_preview_button)
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
        self.comparison_note = QLabel(
            "Original source on the left. The secure, layout-preserving protected copy on the right.",
            objectName="Muted",
        )
        self.comparison_note.setWordWrap(True)
        pdf_comparison_layout.addWidget(self.comparison_note)
        office_preview_options = QHBoxLayout()
        self.high_fidelity_button = QPushButton("High-fidelity preview", objectName="Secondary")
        self.high_fidelity_button.setCheckable(True)
        self.high_fidelity_button.setToolTip(
            "Use LibreOffice locally for a page-accurate Word or Excel preview."
        )
        self.libreoffice_note = QLabel(objectName="Muted")
        self.libreoffice_note.setOpenExternalLinks(True)
        self.libreoffice_note.setTextFormat(Qt.TextFormat.RichText)
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
        office_preview_options.addWidget(self.high_fidelity_button)
        office_preview_options.addWidget(self.libreoffice_note, 1)
        office_preview_options.addWidget(self.install_libreoffice_button)
        self.office_preview_options_widget = QWidget()
        self.office_preview_options_widget.setLayout(office_preview_options)
        self.office_preview_options_widget.setVisible(False)
        pdf_comparison_layout.addWidget(self.office_preview_options_widget)
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
        self.document_preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        (
            original_panel,
            self.original_pdf_view,
            self.original_office_view,
            self.original_view_stack,
        ) = self._build_document_panel("Original document", "Local source")
        (
            protected_panel,
            self.protected_pdf_view,
            self.protected_office_view,
            self.protected_view_stack,
        ) = self._build_document_panel(
            "Protected document", "Safe copy preview"
        )
        self.original_pdf_document = QPdfDocument(self)
        self.protected_pdf_document = QPdfDocument(self)
        self.original_pdf_view.setDocument(self.original_pdf_document)
        self.protected_pdf_view.setDocument(self.protected_pdf_document)
        for view in (self.original_pdf_view, self.protected_pdf_view):
            view.setPageMode(QPdfView.PageMode.MultiPage)
            view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.document_preview_splitter.addWidget(original_panel)
        self.document_preview_splitter.addWidget(protected_panel)
        # Exposed for the optional streamlined UI.  Keeping references to the
        # two shells lets that UI place source/result actions inside the same
        # cards as the document previews instead of duplicating the previews.
        self.original_document_panel = original_panel
        self.protected_document_panel = protected_panel
        self.document_preview_splitter.setChildrenCollapsible(False)
        self.document_preview_splitter.setSizes([600, 600])
        pdf_comparison_layout.addWidget(self.document_preview_splitter, 1)
        self.preview_tabs.addTab(pdf_comparison_tab, "Document comparison")
        self.preview_tabs.setTabVisible(1, False)
        preview_layout.addWidget(self.preview_tabs, 1)
        self.labels_input = QLineEdit()
        self.labels_input.setPlaceholderText("Library labels, comma separated (e.g. Lease, Property 014)")
        preview_layout.addWidget(self.labels_input)

        self.workspace = workspace
        self.findings_card = findings_card
        self.preview_card = preview_card
        self.workspace.addWidget(findings_card)
        self.workspace.addWidget(preview_card)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setStretchFactor(0, 2)
        self.workspace.setStretchFactor(1, 5)
        self.workspace.setSizes([430, 1050])
        root.addWidget(self.workspace, 1)

        action_bar = QFrame(objectName="ActionBar")
        actions = QHBoxLayout(action_bar)
        actions.addWidget(
            self._info_button(
                "Protected result actions",
                "Copy keeps the result in memory. Save stores it locally. Download creates a protected TXT, PDF, DOCX or XLSX.",
            )
        )
        self.copy_button = QPushButton("Copy protected text", objectName="Secondary")
        self.copy_button.setToolTip("Copy the protected text after the automatic residual-PII check.")
        self.save_copy_button = QPushButton("Save + Copy", objectName="Primary")
        self.save_copy_button.setToolTip("Save to the encrypted local library and copy the protected text.")
        self.save_download_button = QPushButton("Save + Download", objectName="Gold")
        self.save_download_button.setToolTip(
            "Save locally and export the protected TXT, PDF, Word or Excel copy."
        )
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
        self._pdf_preview_timer.timeout.connect(self._update_document_comparison)

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

    def _build_document_panel(
        self, title: str, subtitle: str
    ) -> tuple[QFrame, QPdfView, OfficeInternalPreview, QStackedWidget]:
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
        office_view = OfficeInternalPreview(self.TOKEN_COLORS)
        stack = QStackedWidget()
        stack.addWidget(view)
        stack.addWidget(office_view)
        layout.addWidget(stack, 1)
        return panel, view, office_view, stack

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
        self.scope_combo.currentIndexChanged.connect(self._update_scope_description)
        self.mode_combo.currentIndexChanged.connect(self._refresh_preview)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_help)
        self.browse_button.clicked.connect(self._browse_document)
        self.scan_button.clicked.connect(self._start_analysis)
        self.clear_button.clicked.connect(self.clear)
        self.findings_table.itemChanged.connect(self._refresh_preview)
        self.category_list.itemChanged.connect(self._category_changed)
        self.select_all_button.clicked.connect(lambda: self._set_all_categories(True))
        self.select_none_button.clicked.connect(lambda: self._set_all_categories(False))
        self.categories_button.clicked.connect(self._open_categories)
        self.reset_selections_button.clicked.connect(self._reset_selections)
        self.protect_all_button.clicked.connect(lambda: self._set_all_findings(True))
        self.keep_all_button.clicked.connect(lambda: self._set_all_findings(False))
        self.invert_selection_button.clicked.connect(self._invert_findings)
        self.protect_this_button.clicked.connect(
            lambda: self._set_reviewed_finding_protection(True)
        )
        self.keep_this_button.clicked.connect(
            lambda: self._set_reviewed_finding_protection(False)
        )
        self.filter_input.textChanged.connect(self._apply_filter)
        self.focus_preview_button.toggled.connect(self._toggle_preview_focus)
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
        self.high_fidelity_button.toggled.connect(lambda _checked: self._pdf_preview_timer.start())
        self.original_office_view.tabs.currentChanged.connect(
            lambda index: self._sync_office_tab(self.protected_office_view, index)
        )
        self.protected_office_view.tabs.currentChanged.connect(
            lambda index: self._sync_office_tab(self.original_office_view, index)
        )

    @staticmethod
    def _sync_office_tab(target: OfficeInternalPreview, index: int) -> None:
        if index >= 0 and target.tabs.currentIndex() != index and index < target.tabs.count():
            target.tabs.setCurrentIndex(index)

    def _toggle_setup(self, visible: bool) -> None:
        self.setup_card.setVisible(visible)
        self.setup_toggle.setText("Document setup  -" if visible else "Document setup  +")

    def _toggle_preview_focus(self, focused: bool) -> None:
        """Switch between maximum document space and item-by-item review controls."""
        self.findings_card.setVisible(not focused)
        self.setup_card.setVisible(not focused and self.setup_toggle.isChecked())
        self.setup_toggle.setVisible(not focused)
        self.focus_preview_button.setText(
            "Show review panel" if focused else "Full document view"
        )
        if focused:
            self.workspace.setSizes([0, max(1200, self.width())])
        else:
            self.workspace.setSizes([430, 1050])

    def _open_categories(self) -> None:
        self.categories_dialog.show()
        self.categories_dialog.raise_()
        self.categories_dialog.activateWindow()

    def _update_profile_description(self) -> None:
        profile = get_profile(self.profile_combo.currentData())
        self.profile_description.setText(profile.description)
        self.threshold_input.setValue(profile.threshold)

    def _update_scope_description(self) -> None:
        scope = get_scope(self.scope_combo.currentData())
        self.scope_description.setText(scope.description)

    def _update_mode_help(self) -> None:
        messages = {
            "reversible": "Encrypted local mapping enables restore.",
            "generic": "Permanent generic placeholders; original values are not stored.",
            "mask": "Permanent masking keeps only the final four letters or digits.",
            "redact": "Permanent redaction replaces every selected value with [REDACTED].",
        }
        self.mode_help.setText(messages.get(self.mode_combo.currentData(), ""))

    def _browse_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a document",
            "",
            "Supported documents (*.pdf *.docx *.xlsx);;PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx)",
        )
        if path:
            self.pdf_path.setText(path)
            self.input_tabs.setCurrentIndex(1)

    def _start_analysis(self) -> None:
        base_profile = get_profile(self.profile_combo.currentData())
        profile = replace(
            base_profile,
            entities=entities_for_scope(base_profile, self.scope_combo.currentData()),
            threshold=float(self.threshold_input.value()),
        )
        tab = self.input_tabs.currentIndex()
        text = self.text_input.toPlainText().strip()
        document_path = self.pdf_path.text().strip()
        if tab == 0 and not text:
            QMessageBox.information(self, "Nothing to scan", "Paste text before starting the scan.")
            return
        if tab == 1 and not document_path:
            QMessageBox.information(
                self,
                "No document selected",
                "Choose a PDF, Word or Excel document before scanning.",
            )
            return

        def task():
            document = (
                self.service.document_from_text(text)
                if tab == 0
                else self.service.document_from_file(document_path)
            )
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
        if self.current_document.source_kind in {"pdf", "docx", "xlsx"}:
            self.focus_preview_button.setChecked(True)

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
            if self.current_document and self.current_document.source_kind == "pdf":
                location = f"Page {finding.page_number}"
            elif self.current_document and self.current_document.source_kind in {"docx", "xlsx"}:
                source_page = next(
                    page
                    for page in self.current_document.pages
                    if page.page_number == finding.page_number
                )
                location = source_page.location
            else:
                location = "Text"
            self.findings_table.setItem(row, 3, QTableWidgetItem(location))
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
        unit = (
            "page"
            if self.current_document and self.current_document.source_kind == "pdf"
            else "segment"
        )
        self.pages_metric.setText(f"{pages} {unit}{'s' if pages != 1 else ''}")
        if self.current_document and self.current_document.source_path:
            self.source_metric.setText(
                f"{self.current_document.source_kind.upper()}  |  {self.current_document.source_path.name}"
            )
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

    def _set_all_findings(self, protected: bool) -> None:
        state = Qt.CheckState.Checked if protected else Qt.CheckState.Unchecked
        self.findings_table.blockSignals(True)
        for row in range(self.findings_table.rowCount()):
            self.findings_table.item(row, 0).setCheckState(state)
        self.findings_table.blockSignals(False)
        self._sync_category_check_states()
        self._refresh_preview()

    def _invert_findings(self) -> None:
        self.findings_table.blockSignals(True)
        for row in range(self.findings_table.rowCount()):
            item = self.findings_table.item(row, 0)
            state = (
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            item.setCheckState(state)
        self.findings_table.blockSignals(False)
        self._sync_category_check_states()
        self._refresh_preview()

    def _sync_category_check_states(self) -> None:
        self._category_sync = True
        try:
            for index in range(self.category_list.count()):
                category = self.category_list.item(index)
                entity_type = category.data(Qt.ItemDataRole.UserRole)
                states = [
                    self.findings_table.item(row, 0).checkState()
                    for row in range(self.findings_table.rowCount())
                    if self.findings_table.item(row, 1).text() == entity_type
                ]
                if states and all(state == Qt.CheckState.Checked for state in states):
                    category.setCheckState(Qt.CheckState.Checked)
                elif states and all(state == Qt.CheckState.Unchecked for state in states):
                    category.setCheckState(Qt.CheckState.Unchecked)
                else:
                    category.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            self._category_sync = False

    def _set_reviewed_finding_protection(self, protected: bool) -> None:
        if self._reviewed_row is None or self._reviewed_row >= self.findings_table.rowCount():
            return
        state = Qt.CheckState.Checked if protected else Qt.CheckState.Unchecked
        self.findings_table.item(self._reviewed_row, 0).setCheckState(state)
        self._sync_category_check_states()
        self._update_review_context(self._reviewed_row)

    def _finding_selected(self, row: int, _column: int) -> None:
        if not self.current_document:
            return
        self._reviewed_row = row
        self._update_review_context(row)
        finding_id = self.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        finding = next(
            (item for item in self.current_findings if item.finding_id == finding_id),
            None,
        )
        if finding is not None and self.current_document.source_kind == "pdf":
            self._set_pdf_page(max(0, finding.page_number - 1))
            self.preview_tabs.setCurrentIndex(1)
        elif finding is not None and self.current_document.source_kind == "xlsx":
            location = self.findings_table.item(row, 3).text()
            self.original_office_view.focus_location(location)
            self.protected_office_view.focus_location(location)
            self.preview_tabs.setCurrentIndex(1)

    def _update_review_context(self, row: int) -> None:
        finding_id = self.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        finding = next(
            (item for item in self.current_findings if item.finding_id == finding_id),
            None,
        )
        if finding is None:
            return
        location = self.findings_table.item(row, 3).text()
        decision = (
            "PROTECTED"
            if self.findings_table.item(row, 0).checkState() == Qt.CheckState.Checked
            else "KEPT ORIGINAL"
        )
        context = " ".join(finding.context.split())
        self.finding_context.setText(
            f"{decision} · {finding.entity_type.replace('_', ' ').title()} · {location}\n{context}"
        )
        self.protect_this_button.setEnabled(True)
        self.keep_this_button.setEnabled(True)

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
        if self.current_document.source_kind in {"pdf", "docx", "xlsx"}:
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

    def _update_document_comparison(self) -> None:
        if (
            self.current_document is None
            or self.current_result is None
            or self.current_document.source_path is None
        ):
            return
        try:
            self.protected_pdf_document.close()
            self.original_pdf_document.close()
            if self.current_document.source_kind == "pdf":
                self.office_preview_options_widget.setVisible(False)
                self.original_view_stack.setCurrentIndex(0)
                self.protected_view_stack.setCurrentIndex(0)
                self._set_pdf_controls_enabled(True)
                original_path = self.current_document.source_path
                previous_preview = self._preview_path
                self._preview_generation += 1
                protected_path = self._preview_directory / (
                    f"protected-preview-{os.getpid()}-{self._preview_generation}.pdf"
                )
                self.service.save_protected_pdf(
                    self.current_result,
                    protected_path,
                    source_document=self.current_document,
                )
                self.comparison_note.setText(
                    "Original PDF on the left. The secure, layout-preserving protected PDF on the right."
                )
                self.original_pdf_document.load(str(original_path))
                self.protected_pdf_document.load(str(protected_path))
                self._preview_path = protected_path
                self._set_pdf_page(0)
                QApplication.processEvents()
                if previous_preview is not None and previous_preview != protected_path:
                    try:
                        previous_preview.unlink(missing_ok=True)
                    except OSError:
                        # The old renderer handle can be released one event-loop
                        # cycle later. Startup cleanup removes any stale preview.
                        pass
            elif self.current_document.source_kind in {"docx", "xlsx"}:
                suffix = self.current_document.source_path.suffix
                protected_office_path = self._preview_directory / f"protected-office-{os.getpid()}{suffix}"
                self.service.save_protected_office(
                    self.current_result,
                    protected_office_path,
                    source_document=self.current_document,
                )
                self.office_preview_options_widget.setVisible(True)
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
                    original_path = self._office_preview_renderer.render(
                        self.current_document.source_path, self._office_original_directory
                    )
                    protected_path = self._office_preview_renderer.render(
                        protected_office_path, self._office_protected_directory
                    )
                    self.original_view_stack.setCurrentIndex(0)
                    self.protected_view_stack.setCurrentIndex(0)
                    self._set_pdf_controls_enabled(True)
                    self.original_pdf_document.load(str(original_path))
                    self.protected_pdf_document.load(str(protected_path))
                    self.comparison_note.setText(
                        "High-fidelity local rendering: original on the left and protected copy on the right."
                    )
                    self._set_pdf_page(0)
                else:
                    self.original_office_view.load(self.current_document.source_path, protected=False)
                    self.protected_office_view.load(protected_office_path, protected=True)
                    self.original_office_view.synchronize_with(self.protected_office_view)
                    self.original_view_stack.setCurrentIndex(1)
                    self.protected_view_stack.setCurrentIndex(1)
                    self._set_pdf_controls_enabled(False)
                    kind = "worksheet" if self.current_document.source_kind == "xlsx" else "document"
                    self.comparison_note.setText(
                        f"Built-in {kind} preview: original on the left and editable protected copy on the right. "
                        "No additional software is required."
                    )
            else:
                return
        except Exception as exc:
            self.preview_tabs.setTabToolTip(1, f"Preview unavailable: {exc}")
            self.comparison_note.setText(str(exc))
            self.preview_tabs.setCurrentIndex(0)
        else:
            self.preview_tabs.setTabToolTip(
                1, "Compare the local source with the secure layout-preserving copy generated by Privacy Gate."
            )
            self.preview_tabs.setCurrentIndex(1)

    def _set_pdf_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.pdf_previous_button,
            self.pdf_next_button,
            self.pdf_page_label,
            self.pdf_zoom_out_button,
            self.pdf_fit_button,
            self.pdf_zoom_in_button,
        ):
            widget.setVisible(enabled)

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
            [
                "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "STREET_ADDRESS",
                "US_SSN", "US_BANK_NUMBER", "MONEY_AMOUNT", "MERCHANT", "COUNTERPARTY",
                "TRANSACTION_ID", "PROPERTY_IDENTIFIER", "CUSTOM",
            ],
            editable=True,
        )
        if not ok or not entity_type:
            return
        additions = _manual_findings_for_text(self.current_document, value, entity_type)
        if not additions:
            QMessageBox.information(
                self,
                "Text not found",
                "That text was not found in the document. Check the wording and try again.",
            )
            return
        existing_ids = {finding.finding_id for finding in self.current_findings}
        self.current_findings = self.current_findings + tuple(
            finding for finding in additions if finding.finding_id not in existing_ids
        )
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
        base_profile = get_profile(self.profile_combo.currentData())
        return replace(
            base_profile,
            entities=entities_for_scope(base_profile, self.scope_combo.currentData()),
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
        elif self.current_document.source_kind in {"docx", "xlsx"}:
            suffix = f".{self.current_document.source_kind}"
            label = "Word" if suffix == ".docx" else "Excel"
            suggested = f"{document.title}_protected{suffix}"
            path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save protected {label} document",
                suggested,
                f"{label} files (*{suffix})",
            )
            if path:
                self.service.save_protected_office(
                    self.current_result,
                    path if path.lower().endswith(suffix) else path + suffix,
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
        self.scope_combo.setEnabled(not busy)
        if not busy:
            self._active_worker = None

    def cleanup_pdf_preview(self) -> None:
        """Release document handles before removing local temporary previews."""
        self._pdf_preview_timer.stop()
        self.original_pdf_view.setDocument(None)
        self.protected_pdf_view.setDocument(None)
        self.original_pdf_document.close()
        self.protected_pdf_document.close()
        QApplication.processEvents()
        try:
            if self._preview_path is not None:
                self._preview_path.unlink(missing_ok=True)
            for directory in (self._office_original_directory, self._office_protected_directory):
                for preview in (directory.glob("*") if directory.exists() else ()):
                    preview.unlink(missing_ok=True)
                directory.rmdir() if directory.exists() else None
            for office_copy in self._preview_directory.glob(f"protected-office-{os.getpid()}.*"):
                office_copy.unlink(missing_ok=True)
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
        self._reviewed_row = None
        self.finding_context.setText(
            "Select a detected item to see its location and surrounding text."
        )
        self.protect_this_button.setEnabled(False)
        self.keep_this_button.setEnabled(False)
        self.findings_metric.setText("0 findings")
        self.types_metric.setText("0 categories")
        self.pages_metric.setText("0 pages")
        self.source_metric.setText("No document")
        self.source_metric.setToolTip("")
        self.color_legend.setText("Protected categories will appear here after the scan.")
        self.verification_metric.setText("Second scan before export")
        self._last_residual = ()
        self._set_result_actions(False)
        self.focus_preview_button.setChecked(False)
        self.setup_toggle.setChecked(True)
