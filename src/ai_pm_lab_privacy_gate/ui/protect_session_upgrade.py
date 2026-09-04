from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QEvent, QObject, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
)

from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.ui.document_pipeline_v2_ui import _load_pptx_internal
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_SUPPORTED_LOCAL = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
_OFFICE_KINDS = {"docx", "xlsx", "pptx"}


def _source_key(finding_id: str) -> str:
    if finding_id.startswith("document::"):
        return "document"
    if finding_id.startswith("text::"):
        return "text"
    return ""


def _tag_findings(findings: tuple[Finding, ...], source: str) -> tuple[Finding, ...]:
    return tuple(
        replace(item, finding_id=f"{source}::{item.finding_id}")
        for item in findings
    )


def _kind_label(kind: str) -> str:
    return {
        "pdf": "PDF",
        "docx": "Word",
        "xlsx": "Excel",
        "pptx": "PowerPoint",
        "txt": "Text",
        "text": "Text",
    }.get(kind, "Document")


def _kind_suffix(kind: str) -> str:
    return {
        "pdf": ".pdf",
        "docx": ".docx",
        "xlsx": ".xlsx",
        "pptx": ".pptx",
        "txt": ".txt",
        "text": ".txt",
    }.get(kind, ".txt")


def _namespace_result(result, namespace: str):
    """Keep reversible tokens unique when two sources share one AI session."""
    if result.replacement_mode != "reversible" or not result.mappings:
        return result

    token_map: dict[str, str] = {}
    mappings = []
    for mapping in result.mappings:
        token = mapping.token
        if token.startswith("[[PG_"):
            replacement = token.replace("[[PG_", f"[[PG_{namespace}_", 1)
        else:
            replacement = token
        token_map[token] = replacement
        mappings.append(replace(mapping, token=replacement))

    pages = []
    for page_content in result.protected_pages:
        text = page_content.text
        for old, new in token_map.items():
            text = text.replace(old, new)
        pages.append(replace(page_content, text=text))

    spans = []
    for span in result.protected_spans:
        spans.append(
            replace(
                span,
                replacement_text=token_map.get(
                    span.replacement_text,
                    span.replacement_text,
                ),
            )
        )

    return replace(
        result,
        protected_pages=tuple(pages),
        mappings=tuple(mappings),
        protected_spans=tuple(spans),
    )


def _combined_session_text(page) -> str:
    results = getattr(page, "_protect_session_results", {})
    sources = getattr(page, "_protect_session_sources", {})
    chunks: list[str] = []
    document_result = results.get("document")
    document_source = sources.get("document")
    if document_result is not None and document_source is not None:
        document = document_source["document"]
        name = (
            document.source_path.name
            if document.source_path is not None
            else _kind_label(document.source_kind)
        )
        chunks.append(f"=== DOCUMENT · {name} ===\n{document_result.combined_text}")
    text_result = results.get("text")
    if text_result is not None:
        chunks.append(f"=== PASTED TEXT ===\n{text_result.combined_text}")
    return "\n\n".join(chunks)


def _safe_pdf_bundle(page, document, result, destination: Path) -> tuple[Path, Path] | None:
    try:
        return page.service.save_protected_bundle(
            result,
            destination,
            source_document=document,
        )
    except ValueError as exc:
        if document.source_kind != "pdf":
            raise
        answer = QMessageBox.warning(
            page,
            "Exact layout export unavailable",
            "PrivacyGate could not safely map every selected value back onto "
            "this PDF's original coordinates.\n\n"
            "Export a fully protected safe-reflow PDF instead? A protected TXT "
            "companion will also be created.\n\n"
            f"Technical detail: {exc}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return None
        main = page.service.save_protected_pdf(
            result,
            destination,
            source_document=None,
        )
        companion = page.service.save_protected_text(
            result,
            Path(main).with_suffix(".txt"),
        )
        return Path(main), Path(companion)


class _DriveDialogUsabilityFilter(QObject):
    """Polish Drive navigation after the existing browser dialog is created."""

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QDialog)
            and watched.windowTitle() == "Google Drive — import to Protect"
        ):
            QTimer.singleShot(0, lambda dialog=watched: self._polish(dialog))
        return False

    @staticmethod
    def _polish(dialog: QDialog) -> None:
        for label in dialog.findChildren(QLabel):
            if label.text().startswith("Open folders just like a file picker"):
                label.setText(
                    "Open folders, use ← Back to return one level, or click any "
                    "breadcrumb to jump directly to that folder."
                )
                break

        back_button = None
        for button in dialog.findChildren(QPushButton):
            if button.toolTip() == "Back one folder":
                back_button = button
                break
        if back_button is None:
            return

        back_button.setText("← Back")
        back_button.setFixedSize(82, 32)
        back_button.setShortcut(QKeySequence("Alt+Left"))
        back_button.setToolTip("Back to the previous Drive folder (Alt+Left)")
        back_button.setStyleSheet(
            "QPushButton{border:1px solid #DADCE0;background:#FFFFFF;"
            "border-radius:8px;padding:4px 9px;font-size:11px;font-weight:700;"
            "color:#3C4043;} "
            "QPushButton:hover{background:#F1F3F4;border-color:#BDC1C6;} "
            "QPushButton:disabled{color:#9AA0A6;background:#F8F9FA;}"
        )

        navigation = back_button.parentWidget()
        if navigation is None:
            return
        for crumb in navigation.findChildren(
            QPushButton,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        ):
            if crumb is back_button:
                continue
            if crumb.text() == "My Drive":
                crumb.setText("⌂  My Drive")
            crumb.setToolTip(f"Jump to {crumb.text().replace('⌂', '').strip()}")
            crumb.setStyleSheet(
                "QPushButton{border:0;background:transparent;color:#1A73E8;"
                "padding:5px 7px;font-weight:750;} "
                "QPushButton:hover{background:#E8F0FE;border-radius:7px;}"
            )


def _install_drive_dialog_polish(main_window) -> None:
    app = QApplication.instance()
    if app is None or getattr(app, "_privacygate_drive_usability_filter", None) is not None:
        return
    filter_object = _DriveDialogUsabilityFilter(app)
    app.installEventFilter(filter_object)
    app._privacygate_drive_usability_filter = filter_object
    main_window._privacygate_drive_usability_filter = filter_object


def _install_source_status(page) -> None:
    toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if toolbar is not None and getattr(page, "_protect_session_source_helper", None) is None:
        helper = QLabel(
            "Add a document, pasted text, or both. A ✓ means that source will be "
            "included in the next local scan."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet(
            "background:#F2FAFA;color:#496A72;border:1px solid #D4E9EA;"
            "border-radius:7px;padding:6px 9px;font-size:9px;font-weight:700;"
        )
        layout = toolbar.layout()
        if layout is not None:
            layout.insertWidget(1, helper)
        page._protect_session_source_helper = helper

    document_mode = getattr(page, "_redesign_document_mode", None)
    paste_mode = getattr(page, "_redesign_paste_mode", None)

    def sync() -> None:
        has_document = bool(page.pdf_path.text().strip())
        has_text = bool(page.text_input.toPlainText().strip())
        if document_mode is not None:
            document_mode.setText("Document  ✓" if has_document else "Document")
            document_mode.setToolTip(
                "Document is included in the next scan."
                if has_document
                else "Open the document source area."
            )
        if paste_mode is not None:
            paste_mode.setText("Paste text  ✓" if has_text else "Paste text")
            paste_mode.setToolTip(
                "Pasted text is included in the next scan."
                if has_text
                else "Open the pasted-text source area."
            )
        helper = getattr(page, "_protect_session_source_helper", None)
        if helper is not None:
            if has_document and has_text:
                helper.setText(
                    "2 sources ready · Document + Pasted text will be scanned together "
                    "and kept separate in Review."
                )
            elif has_document:
                helper.setText(
                    "1 source ready · Document. You can also add pasted text before Scan."
                )
            elif has_text:
                helper.setText(
                    "1 source ready · Pasted text. You can also add a document before Scan."
                )
            else:
                helper.setText(
                    "Add a document, pasted text, or both. A ✓ means that source will be "
                    "included in the next local scan."
                )

    page.text_input.textChanged.connect(sync)
    page.pdf_path.textChanged.connect(sync)
    sync()
    page._protect_session_sync_source_status = sync


def _install_source_review_filter(page) -> None:
    if getattr(page, "_protect_session_filter_bar", None) is not None:
        return
    layout = page.findings_card.layout()
    if layout is None:
        return

    bar = QFrame()
    bar.setObjectName("ProtectSessionSourceFilter")
    row = QHBoxLayout(bar)
    row.setContentsMargins(8, 6, 8, 6)
    row.setSpacing(6)
    label = QLabel("Review source")
    label.setStyleSheet("color:#61798A;font-size:9px;font-weight:800;")
    row.addWidget(label)

    group = QButtonGroup(bar)
    group.setExclusive(True)
    buttons = {}
    for key, text in (
        ("all", "All sources"),
        ("document", "Document"),
        ("text", "Pasted text"),
    ):
        button = QPushButton(text)
        button.setCheckable(True)
        button.setMinimumHeight(30)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#466174;border:1px solid #D7E2EA;"
            "border-radius:7px;padding:4px 9px;font-size:9px;font-weight:750;} "
            "QPushButton:checked{background:#E8F6F6;color:#0B7180;border-color:#A8DADD;}"
        )
        group.addButton(button)
        buttons[key] = button
        row.addWidget(button)
    buttons["all"].setChecked(True)
    row.addStretch(1)

    summary = QLabel("")
    summary.setStyleSheet("color:#61798A;font-size:9px;font-weight:700;")
    row.addWidget(summary)
    bar.hide()

    table_index = layout.indexOf(page.findings_table)
    layout.insertWidget(max(0, table_index), bar)

    def apply_filter() -> None:
        selected_source = "all"
        for key, button in buttons.items():
            if button.isChecked():
                selected_source = key
                break
        term = page.filter_input.text().casefold().strip()
        for row_index in range(page.findings_table.rowCount()):
            checkbox = page.findings_table.item(row_index, 0)
            source = checkbox.data(_SOURCE_ROLE) if checkbox is not None else ""
            haystack = " ".join(
                page.findings_table.item(row_index, column).text()
                for column in range(1, page.findings_table.columnCount())
                if page.findings_table.item(row_index, column) is not None
            ).casefold()
            wrong_source = selected_source != "all" and source != selected_source
            wrong_term = bool(term and term not in haystack)
            page.findings_table.setRowHidden(row_index, wrong_source or wrong_term)

    for button in buttons.values():
        button.clicked.connect(apply_filter)
    page.filter_input.textChanged.connect(lambda _text: apply_filter())

    page._protect_session_filter_bar = bar
    page._protect_session_filter_buttons = buttons
    page._protect_session_filter_summary = summary
    page._protect_session_apply_filter = apply_filter


def _update_source_review_filter(page) -> None:
    bar = getattr(page, "_protect_session_filter_bar", None)
    if bar is None:
        return
    active = bool(getattr(page, "_protect_session_active", False))
    bar.setVisible(active)
    if not active:
        return
    document_count = sum(
        1 for item in page.current_findings if _source_key(item.finding_id) == "document"
    )
    text_count = sum(
        1 for item in page.current_findings if _source_key(item.finding_id) == "text"
    )
    page._protect_session_filter_buttons["all"].setText(
        f"All sources  {document_count + text_count}"
    )
    page._protect_session_filter_buttons["document"].setText(
        f"Document  {document_count}"
    )
    page._protect_session_filter_buttons["text"].setText(
        f"Pasted text  {text_count}"
    )
    page._protect_session_filter_summary.setText("Sources remain separate through export.")
    page._protect_session_apply_filter()


def _install_fidelity_status(page) -> None:
    if getattr(page, "_protect_fidelity_status", None) is not None:
        return
    comparison_page = page.preview_tabs.widget(1) if page.preview_tabs.count() > 1 else None
    if comparison_page is None or comparison_page.layout() is None:
        return

    status = QLabel("Waiting for a document")
    status.setToolTip("Preview fidelity is selected automatically for the loaded document.")
    status.setWordWrap(True)
    status.setStyleSheet(
        "background:#F8FBFC;color:#496A72;border:1px solid #DFE8ED;"
        "border-radius:7px;padding:6px 9px;font-size:9px;font-weight:800;"
    )
    comparison_page.layout().insertWidget(1, status)
    page._protect_fidelity_status = status

    def sync() -> None:
        document = page.current_document
        path_text = page.pdf_path.text().strip()
        suffix = Path(path_text).suffix.lower() if path_text else ""
        kind = document.source_kind if document is not None else suffix.lstrip(".")
        note = page.comparison_note.text().casefold()

        if not kind:
            status.setText("Waiting for a document")
            status.setToolTip(
                "Preview fidelity is selected automatically for the loaded document."
            )
            return
        if kind == "pdf":
            if "safe reflow" in note:
                status.setText("PDF · Safe reflow")
                status.setToolTip(
                    "Every selected value is protected; safe reflow is used because "
                    "the original layout could not be mapped reliably."
                )
                status.setStyleSheet(
                    "background:#FFF7E6;color:#8A5A16;border:1px solid #F1D39A;"
                    "border-radius:7px;padding:6px 9px;font-size:9px;font-weight:850;"
                )
            else:
                status.setText("PDF · Layout-preserving")
                status.setToolTip(
                    "Layout is preserved when safe. PrivacyGate falls back to safe "
                    "reflow rather than risk leaving data visible."
                )
                status.setStyleSheet(
                    "background:#F2FAFA;color:#496A72;border:1px solid #D4E9EA;"
                    "border-radius:7px;padding:6px 9px;font-size:9px;font-weight:800;"
                )
            return

        if kind in _OFFICE_KINDS:
            if page._libreoffice_available and page.high_fidelity_button.isChecked():
                status.setText(f"{_kind_label(kind)} · High fidelity")
                status.setToolTip("LibreOffice rendering runs locally.")
            elif page._libreoffice_available:
                status.setText(f"{_kind_label(kind)} · Built-in")
                status.setToolTip(
                    "High-fidelity local LibreOffice preview is available."
                )
            else:
                status.setText(f"{_kind_label(kind)} · Built-in")
                status.setToolTip(
                    "Install LibreOffice to enable optional high-fidelity rendering."
                )
            status.setStyleSheet(
                "background:#F2FAFA;color:#496A72;border:1px solid #D4E9EA;"
                "border-radius:7px;padding:6px 9px;font-size:9px;font-weight:800;"
            )
            return

        status.setText("Text · Protected preview")
        status.setToolTip("Protected text preview is generated locally.")

    timer = QTimer(page)
    timer.setInterval(250)
    timer.timeout.connect(sync)
    timer.start()
    page._protect_fidelity_timer = timer
    page._protect_fidelity_sync = sync
    sync()


def _install_pptx_input_support(page) -> None:
    zone = getattr(page, "_redesign_upload_zone", None)
    if zone is not None:
        type(zone)._supported = staticmethod(
            lambda path: Path(path).suffix.lower() in _SUPPORTED_LOCAL
        )
        zone.setToolTip(
            "Drop PDF, Word, Excel, PowerPoint or TXT. Files are processed locally."
        )
    page.browse_button.setToolTip(
        "Upload PDF, DOCX, XLSX, PPTX or TXT. The source stays on this device."
    )
    quick_upload = getattr(page, "_protect_source_upload", None)
    if quick_upload is not None:
        quick_upload.setToolTip(
            "Choose a local PDF, Word, Excel, PowerPoint or TXT file."
        )

    def refresh_initial_preview(path_text: str) -> None:
        if not path_text:
            page.office_preview_options_widget.setVisible(False)
            return
        source = Path(path_text)
        suffix = source.suffix.lower()
        if suffix not in _SUPPORTED_LOCAL:
            return

        if suffix in {".docx", ".xlsx", ".pptx"}:
            page.office_preview_options_widget.setVisible(True)
            page.high_fidelity_button.setVisible(page._libreoffice_available)
            page.install_libreoffice_button.setVisible(not page._libreoffice_available)
            if page._libreoffice_available:
                page.libreoffice_note.setText(
                    "Built-in preview active. High-fidelity LibreOffice rendering is available locally."
                )
            else:
                page.libreoffice_note.setText(
                    "Built-in preview active. Optional high-fidelity preview requires LibreOffice."
                )

        if suffix != ".pptx":
            return
        try:
            page.original_pdf_document.close()
            page.protected_pdf_document.close()
            page.original_office_view.clear()
            page.protected_office_view.clear()
            _load_pptx_internal(page.original_office_view, source, False)
            page.original_view_stack.setCurrentIndex(1)
            page.protected_view_stack.setCurrentIndex(1)
            page.preview_tabs.setTabVisible(1, True)
            page.preview_tabs.setCurrentIndex(1)
            page.comparison_note.setText(
                "PowerPoint loaded locally. Scan to review sensitive data, then Protect "
                "to create an editable protected deck."
            )
        except Exception as exc:
            page.comparison_note.setText(f"PowerPoint preview unavailable: {exc}")

    page.pdf_path.textChanged.connect(refresh_initial_preview)
    if page.pdf_path.text().strip():
        refresh_initial_preview(page.pdf_path.text().strip())


def _apply_multisource_runtime(page) -> None:
    if getattr(page, "_protect_multisource_runtime", False):
        return
    page._protect_multisource_runtime = True
    page._protect_session_active = False
    page._protect_session_sources = {}
    page._protect_session_results = {}

    _install_source_status(page)
    _install_source_review_filter(page)
    _install_fidelity_status(page)
    _install_pptx_input_support(page)

    original_start_analysis = page._start_analysis
    original_populate_findings = page._populate_findings
    original_refresh_preview = page._refresh_preview
    original_confirm_residual = page._confirm_residual_risk
    original_save_library = page._save_to_library
    original_copy_result = page._copy_result
    original_copy_ai = page._copy_and_open_chatgpt
    original_clear = page.clear
    original_analysis_ready = page._analysis_ready

    def invalidate_multisource() -> None:
        if page._active_worker is not None:
            return
        page._protect_session_active = False
        page._protect_session_sources = {}
        page._protect_session_results = {}
        _update_source_review_filter(page)

    page.text_input.textChanged.connect(invalidate_multisource)
    page.pdf_path.textChanged.connect(lambda _text: invalidate_multisource())

    def start_analysis(self) -> None:
        text = self.text_input.toPlainText().strip()
        document_path = self.pdf_path.text().strip()
        if not (text and document_path):
            self._protect_session_active = False
            self._protect_session_sources = {}
            self._protect_session_results = {}
            _update_source_review_filter(self)
            if document_path:
                self.input_tabs.setCurrentIndex(1)
            elif text:
                self.input_tabs.setCurrentIndex(0)
            original_start_analysis()
            return

        base_profile = get_profile(self.profile_combo.currentData())
        profile = replace(
            base_profile,
            entities=entities_for_scope(
                base_profile,
                self.scope_combo.currentData(),
            ),
            threshold=float(self.threshold_input.value()),
        )

        def task():
            document = self.service.document_from_file(document_path)
            document_findings = _tag_findings(
                self.service.analyze(document, profile),
                "document",
            )
            text_document = self.service.document_from_text(text)
            text_findings = _tag_findings(
                self.service.analyze(text_document, profile),
                "text",
            )
            return {
                "document": {
                    "document": document,
                    "findings": document_findings,
                },
                "text": {
                    "document": text_document,
                    "findings": text_findings,
                },
            }

        def ready(payload: object) -> None:
            sources = dict(payload)
            self._protect_session_active = True
            self._protect_session_sources = sources
            self._protect_session_results = {}
            document_source = sources["document"]
            text_source = sources["text"]
            combined_findings = (
                tuple(document_source["findings"])
                + tuple(text_source["findings"])
            )
            original_analysis_ready(
                (document_source["document"], combined_findings)
            )
            self.preview_tabs.setTabVisible(
                1,
                document_source["document"].source_kind
                in {"pdf", "docx", "xlsx", "pptx"},
            )
            self._redesign_review_metric.setText("Ready to review · 2 sources")
            _update_source_review_filter(self)

        self._set_busy(True)
        if hasattr(self, "_redesign_begin_operation"):
            self._redesign_begin_operation(
                "scan",
                "Loading and scanning document + pasted text locally…",
            )
        worker = FunctionWorker(task)
        self._active_worker = worker
        worker.signals.result.connect(ready)
        worker.signals.error.connect(
            lambda message: QMessageBox.critical(
                self,
                "Unable to scan",
                message,
            )
        )
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self.thread_pool.start(worker)

    try:
        page.scan_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page._start_analysis = MethodType(start_analysis, page)
    page.scan_button.clicked.connect(page._start_analysis)

    def populate_findings(self) -> None:
        original_populate_findings()
        if not self._protect_session_active:
            _update_source_review_filter(self)
            return

        document_source = self._protect_session_sources.get("document", {})
        document = document_source.get("document")
        for row_index in range(self.findings_table.rowCount()):
            checkbox = self.findings_table.item(row_index, 0)
            if checkbox is None:
                continue
            finding_id = str(
                checkbox.data(Qt.ItemDataRole.UserRole) or ""
            )
            source = _source_key(finding_id)
            checkbox.setData(_SOURCE_ROLE, source)
            location_item = self.findings_table.item(row_index, 3)
            if location_item is None:
                continue
            if source == "text":
                location_item.setText("Pasted text")
                continue
            finding = next(
                (
                    item
                    for item in self.current_findings
                    if item.finding_id == finding_id
                ),
                None,
            )
            if finding is None or document is None:
                continue
            if document.source_kind == "pdf":
                location = f"Page {finding.page_number}"
            else:
                source_page = next(
                    (
                        source_page
                        for source_page in document.pages
                        if source_page.page_number == finding.page_number
                    ),
                    None,
                )
                location = (
                    source_page.location
                    if source_page is not None and source_page.location
                    else f"Segment {finding.page_number}"
                )
            filename = (
                document.source_path.name
                if document.source_path is not None
                else _kind_label(document.source_kind)
            )
            location_item.setText(f"Document · {filename} · {location}")
        _update_source_review_filter(self)

    page._populate_findings = MethodType(populate_findings, page)

    def refresh_preview(self, *_args) -> None:
        if not self._protect_session_active:
            original_refresh_preview(*_args)
            return

        if hasattr(self, "_redesign_allow_refresh") and not self._redesign_allow_refresh:
            selected = len(self._selected_findings())
            self.current_result = None
            self._redesign_protected_metric.setText(f"{selected} selected")
            self._redesign_review_metric.setText(
                "Review selection, then protect"
            )
            self._redesign_protect_button.setEnabled(
                bool(self.current_findings)
            )
            self._redesign_protect_button.setText(
                "Update protection"
                if self._redesign_final_actions.isVisible()
                else "Protect document"
            )
            self._redesign_final_actions.hide()
            self._redesign_set_final_actions(False)
            return

        selected_ids = {
            self.findings_table.item(row_index, 0).data(
                Qt.ItemDataRole.UserRole
            )
            for row_index in range(self.findings_table.rowCount())
            if self.findings_table.item(row_index, 0).checkState()
            == Qt.CheckState.Checked
        }
        results = {}
        for source, payload in self._protect_session_sources.items():
            selected = tuple(
                finding
                for finding in payload["findings"]
                if finding.finding_id in selected_ids
            )
            result = self.service.protect(
                payload["document"],
                selected,
                replacement_mode=self.mode_combo.currentData(),
            )
            namespace = "DOC" if source == "document" else "TEXT"
            results[source] = _namespace_result(result, namespace)

        self._protect_session_results = results
        document_payload = self._protect_session_sources["document"]
        self.current_document = document_payload["document"]
        self.current_result = results["document"]
        self.preview.setPlainText(_combined_session_text(self))

        protected_count = sum(
            len(result.applied_findings)
            for result in results.values()
        )
        self.findings_metric.setText(
            f"{len(self.current_findings)} detected  |  "
            f"{protected_count} protected"
        )
        if self.current_document.source_kind in {
            "pdf",
            "docx",
            "xlsx",
            "pptx",
        }:
            self.preview_tabs.setTabVisible(1, True)
            self._pdf_preview_timer.start()
        else:
            self.preview_tabs.setTabVisible(1, False)
        self._set_result_actions(True)

        def sync_metrics() -> None:
            if self._protect_session_active:
                self._redesign_protected_metric.setText(
                    f"{protected_count} protected · 2 sources"
                )
                self._redesign_review_metric.setText(
                    "Protected copies ready"
                )

        QTimer.singleShot(0, sync_metrics)

    page._refresh_preview = MethodType(refresh_preview, page)

    def select_source_after_click(row_index: int, _column: int) -> None:
        if not self._protect_session_active:
            return
        checkbox = self.findings_table.item(row_index, 0)
        if checkbox is None:
            return
        source = checkbox.data(_SOURCE_ROLE)
        if source == "text":
            self.preview_tabs.setCurrentIndex(0)
        elif source == "document":
            document = self._protect_session_sources["document"]["document"]
            if document.source_kind in {"pdf", "docx", "xlsx", "pptx"}:
                self.preview_tabs.setCurrentIndex(1)

    page.findings_table.cellClicked.connect(select_source_after_click)

    def confirm_residual(self, action: str) -> bool:
        if not self._protect_session_active:
            return original_confirm_residual(action)
        if not self._protect_session_results:
            return False

        profile = self._current_profile()
        residuals: list[tuple[str, Finding]] = []
        for source, result in self._protect_session_results.items():
            for item in self.service.verify_protected(result, profile):
                residuals.append((source, item))
        self._last_residual = tuple(item for _source, item in residuals)
        if not residuals:
            self.verification_metric.setText(
                "Verified: no remaining PII · 2 sources"
            )
            self.verification_metric.setProperty("warning", False)
            self.verification_metric.style().unpolish(
                self.verification_metric
            )
            self.verification_metric.style().polish(
                self.verification_metric
            )
            return True

        self.verification_metric.setText(
            f"Warning: {len(residuals)} possible PII remain · 2 sources"
        )
        self.verification_metric.setProperty("warning", True)
        self.verification_metric.style().unpolish(
            self.verification_metric
        )
        self.verification_metric.style().polish(
            self.verification_metric
        )
        examples = "\n".join(
            f"• {'Document' if source == 'document' else 'Pasted text'} · "
            f"{item.entity_type}: {item.text[:45]}"
            for source, item in residuals[:8]
        )
        answer = QMessageBox.warning(
            self,
            "Possible sensitive data remains",
            f"PrivacyGate found {len(residuals)} possible sensitive item(s) "
            f"across the protected sources before {action}:\n\n{examples}\n\n"
            "Return to Review and protect them whenever possible.",
            QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Ignore,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ignore

    page._confirm_residual_risk = MethodType(confirm_residual, page)

    def save_to_library(self):
        if not self._protect_session_active:
            return original_save_library()
        if not self._protect_session_results:
            return None

        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(
            self,
            "Save protection session",
            "Session title:",
            text=self._derive_title(),
        )
        if not ok:
            return None
        labels = tuple(
            part.strip()
            for part in self.labels_input.text().split(",")
            if part.strip()
        )
        saved = []
        for source in ("document", "text"):
            payload = self._protect_session_sources[source]
            result = self._protect_session_results[source]
            document = payload["document"]
            source_name = (
                document.source_path.name
                if document.source_path is not None
                else "Pasted text"
            )
            suffix = "Document" if source == "document" else "Pasted text"
            saved_document = self.library.save(
                title=f"{title} — {suffix}",
                source_kind=document.source_kind,
                source_name=source_name,
                profile_key=self.profile_combo.currentData(),
                result=result,
                labels=labels,
            )
            saved.append(saved_document)
            self.library_changed.emit(saved_document.document_id)
        return saved[0] if saved else None

    page._save_to_library = MethodType(save_to_library, page)

    def copy_result(self) -> None:
        if not self._protect_session_active:
            original_copy_result()
            return
        if self._confirm_residual_risk("copying"):
            QApplication.clipboard().setText(_combined_session_text(self))

    page._copy_result = MethodType(copy_result, page)

    def copy_and_open_ai(self) -> None:
        if not self._protect_session_active:
            original_copy_ai()
            return
        if not self._confirm_residual_risk("opening an AI service"):
            return
        QApplication.clipboard().setText(_combined_session_text(self))
        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))

    page._copy_and_open_chatgpt = MethodType(copy_and_open_ai, page)

    def download_current() -> None:
        if self.current_result is None or self.current_document is None:
            return
        begin = getattr(self, "_redesign_begin_operation", None)
        end = getattr(self, "_redesign_end_operation", None)
        if callable(begin):
            begin(
                "verify",
                "Running final privacy check before download…",
            )
        try:
            if not self._confirm_residual_risk("downloading"):
                return

            if self._protect_session_active:
                document_payload = self._protect_session_sources["document"]
                document = document_payload["document"]
                result = self._protect_session_results["document"]
            else:
                document = self.current_document
                result = self.current_result

            label = _kind_label(document.source_kind)
            suffix = _kind_suffix(document.source_kind)
            suggested = f"{self._derive_title()}_protected{suffix}"
            path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save protected {label}",
                suggested,
                f"{label} files (*{suffix})",
            )
            if not path:
                return
            destination = Path(path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)

            if callable(begin):
                begin(
                    "export",
                    f"Generating protected {label} + TXT locally…",
                )
            try:
                outputs = _safe_pdf_bundle(
                    self,
                    document,
                    result,
                    destination,
                )
                if outputs is None:
                    return
                main_output, companion = outputs
                extra_text = None
                if self._protect_session_active:
                    text_result = self._protect_session_results["text"]
                    extra_text = self.service.save_protected_text(
                        text_result,
                        Path(main_output).with_name(
                            f"{Path(main_output).stem}_pasted_text.txt"
                        ),
                    )
            finally:
                if callable(end):
                    end("export")

            paths = [str(main_output)]
            if companion != main_output:
                paths.append(str(companion))
            if self._protect_session_active and extra_text is not None:
                paths.append(str(extra_text))
            QMessageBox.information(
                self,
                "Protected files exported",
                "Saved locally:\n\n" + "\n".join(paths),
            )
        finally:
            if callable(end):
                end("verify")

    actions = getattr(page, "_redesign_action_buttons", ())
    if len(actions) >= 2:
        download_action = actions[1]
        try:
            download_action.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        download_action.clicked.connect(download_current)

    def clear(self) -> None:
        self._protect_session_active = False
        self._protect_session_sources = {}
        self._protect_session_results = {}
        original_clear()
        _update_source_review_filter(self)
        sync = getattr(self, "_protect_session_sync_source_status", None)
        if callable(sync):
            sync()

    try:
        page.clear_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page.clear = MethodType(clear, page)
    page.clear_button.clicked.connect(page.clear)


def apply_protect_session_upgrade(main_window) -> None:
    """Polish Drive navigation and make Protect a real multi-source session."""
    _install_drive_dialog_polish(main_window)
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return
    _apply_multisource_runtime(page)
