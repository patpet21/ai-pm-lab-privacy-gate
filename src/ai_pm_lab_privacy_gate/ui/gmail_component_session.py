from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QFileInfo, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.ui import gmail_browser_route, gmail_package_browser
from ai_pm_lab_privacy_gate.ui.protect_session_upgrade import _namespace_result, _tag_findings
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_EMAIL_MARKER = "=== GMAIL EMAIL BODY ==="
_ATTACHMENT_MARKER = "\n\n=== GMAIL ATTACHMENT · "
_DOCUMENT_KINDS = {"pdf", "docx", "xlsx", "pptx"}


def _source_key(finding_id: str) -> str:
    return finding_id.split("::", 1)[0] if "::" in finding_id else ""


def _body_from_legacy_text(text: str, selected: bool) -> str:
    if not selected:
        return ""
    value = str(text or "")
    if _EMAIL_MARKER in value:
        value = value.split(_EMAIL_MARKER, 1)[1]
    if _ATTACHMENT_MARKER in value:
        value = value.split(_ATTACHMENT_MARKER, 1)[0]
    return value.strip()


def _safe_button_text(label: str, limit: int = 34) -> str:
    clean = " ".join(str(label or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(8, limit - 1)].rstrip() + "…"


def _document_text(document) -> str:
    return "\n\n".join(page.text for page in document.pages if page.text.strip())


def _render_tokens(page, editor: QPlainTextEdit, result) -> None:
    editor.setPlainText(result.combined_text)
    for span in result.combined_spans:
        cursor = QTextCursor(editor.document())
        cursor.setPosition(span.start)
        cursor.setPosition(span.end, QTextCursor.MoveMode.KeepAnchor)
        formatting = QTextCharFormat()
        formatting.setBackground(QColor(page._entity_color(span.entity_type)))
        formatting.setForeground(QColor("#102A43"))
        formatting.setFontWeight(int(QFont.Weight.DemiBold))
        cursor.mergeCharFormat(formatting)


def _ensure_component_ui(page) -> None:
    if getattr(page, "_gmail_component_strip", None) is not None:
        return
    parent = page.preview_tabs.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return

    strip = QFrame(objectName="GmailComponentStrip")
    strip.setStyleSheet(
        "QFrame#GmailComponentStrip{background:#F7FAFC;border:1px solid #D7E3EA;"
        "border-radius:10px;}"
    )
    strip_layout = QHBoxLayout(strip)
    strip_layout.setContentsMargins(10, 7, 10, 7)
    strip_layout.setSpacing(8)
    title = QLabel("EMAIL CONTENTS")
    title.setStyleSheet("color:#61798A;font-size:8px;font-weight:900;")
    strip_layout.addWidget(title)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFixedHeight(42)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:0;}")

    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    row.addStretch(1)
    scroll.setWidget(host)
    strip_layout.addWidget(scroll, 1)

    summary = QLabel("")
    summary.setStyleSheet("color:#61798A;font-size:8px;font-weight:750;")
    strip_layout.addWidget(summary)
    index = layout.indexOf(page.preview_tabs)
    layout.insertWidget(max(0, index), strip)
    strip.hide()

    compare_tab = QWidget()
    compare_layout = QHBoxLayout(compare_tab)
    compare_layout.setContentsMargins(0, 8, 0, 0)
    compare_layout.setSpacing(10)

    def panel(title_text: str, badge_text: str):
        frame = QFrame(objectName="PdfPanel")
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 10, 10, 10)
        heading = QHBoxLayout()
        heading.addWidget(QLabel(title_text, objectName="PdfTitle"))
        heading.addStretch(1)
        heading.addWidget(QLabel(badge_text, objectName="PdfBadge"))
        box.addLayout(heading)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;border:1px solid #D9E3EA;"
            "border-radius:7px;padding:10px;color:#17384E;font-size:11px;}"
        )
        box.addWidget(editor, 1)
        return frame, editor

    original_panel, original_text = panel("Original content", "Local source")
    protected_panel, protected_text = panel("Protected content", "Safe copy preview")
    compare_layout.addWidget(original_panel, 1)
    compare_layout.addWidget(protected_panel, 1)
    text_compare_index = page.preview_tabs.addTab(compare_tab, "Source comparison")

    page._gmail_component_strip = strip
    page._gmail_component_button_row = row
    page._gmail_component_summary = summary
    page._gmail_component_group = QButtonGroup(strip)
    page._gmail_component_group.setExclusive(True)
    page._gmail_component_buttons = {}
    page._gmail_component_text_compare_index = text_compare_index
    page._gmail_component_original_text = original_text
    page._gmail_component_protected_text = protected_text


def _refresh_component_strip(page) -> None:
    _ensure_component_ui(page)
    strip = getattr(page, "_gmail_component_strip", None)
    if strip is None:
        return

    row = page._gmail_component_button_row
    group = page._gmail_component_group
    for button in tuple(page._gmail_component_buttons.values()):
        group.removeButton(button)
        row.removeWidget(button)
        button.deleteLater()
    page._gmail_component_buttons = {}

    manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
    if not manifest:
        strip.hide()
        return

    icon_provider = QFileIconProvider()
    for component in manifest:
        key = str(component["key"])
        label = str(component.get("label") or "Source")
        button = QPushButton(_safe_button_text(label))
        button.setCheckable(True)
        button.setMinimumHeight(30)
        button.setMaximumWidth(260)
        button.setToolTip(label)
        if component.get("component_kind") == "attachment" and component.get("path"):
            button.setIcon(icon_provider.icon(QFileInfo(str(component["path"]))))
            button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#35536A;border:1px solid #D4E0E8;"
            "border-radius:8px;padding:5px 10px;font-size:9px;font-weight:800;text-align:left;}"
            "QPushButton:hover{background:#F1F7FA;border-color:#9FC7CF;}"
            "QPushButton:checked{background:#0B7180;color:#FFFFFF;border-color:#0B7180;}"
        )
        group.addButton(button)
        page._gmail_component_buttons[key] = button
        row.insertWidget(max(0, row.count() - 1), button)
        button.clicked.connect(
            lambda _checked=False, source_key=key: page._gmail_component_select(source_key)
        )

    active = str(getattr(page, "_gmail_component_active_key", "") or "")
    if active not in page._gmail_component_buttons:
        active = str(manifest[0]["key"])
        page._gmail_component_active_key = active
    page._gmail_component_buttons[active].setChecked(True)
    attachments = sum(1 for item in manifest if item.get("component_kind") == "attachment")
    has_body = any(item.get("component_kind") == "body" for item in manifest)
    summary = []
    if has_body:
        summary.append("email body")
    if attachments:
        summary.append(f"{attachments} attachment{'s' if attachments != 1 else ''}")
    page._gmail_component_summary.setText(" + ".join(summary))
    strip.show()


def _show_component(page, key: str) -> None:
    page._gmail_component_active_key = key
    for source_key, button in getattr(page, "_gmail_component_buttons", {}).items():
        button.setChecked(source_key == key)

    payload = getattr(page, "_gmail_component_sources", {}).get(key)
    result = getattr(page, "_gmail_component_results", {}).get(key)
    if payload is None:
        return
    page.current_document = payload["document"]
    if result is None:
        page.current_result = None
        return
    page.current_result = result

    document = payload["document"]
    if document.source_kind in _DOCUMENT_KINDS and document.source_path is not None:
        page.preview_tabs.setTabVisible(1, True)
        page.preview_tabs.setCurrentIndex(1)
        page.preview.setPlainText(result.combined_text)
        page._pdf_preview_timer.start()
    else:
        page.preview_tabs.setTabVisible(1, False)
        page.preview_tabs.setCurrentIndex(page._gmail_component_text_compare_index)
        page._gmail_component_original_text.setPlainText(_document_text(document))
        _render_tokens(page, page._gmail_component_protected_text, result)

    metric = getattr(page, "_redesign_review_metric", None)
    if metric is not None:
        metric.setText(f"Viewing · {payload.get('label', 'Source')}")


def _adopt_imported_package(page) -> None:
    metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
    if (
        metadata.get("provider") != "gmail"
        or metadata.get("package_mode") != "gmail_message_package"
    ):
        return

    selected = [str(value) for value in metadata.get("selected_components") or ()]
    body_selected = bool(metadata.get("email_body_selected"))
    attachment_count = int(metadata.get("attachment_count") or 0)
    attachment_names = [value for value in selected if value != "Email body"]
    body_text = _body_from_legacy_text(page.text_input.toPlainText(), body_selected)

    materialized: list[Path] = []
    if attachment_count:
        primary = Path(page.pdf_path.text().strip())
        if primary.is_file():
            materialized.append(primary)
    for raw in tuple(getattr(page, "_gmail_component_extra_paths", ()) or ()):
        path = Path(raw)
        if path.is_file() and path not in materialized:
            materialized.append(path)

    manifest: list[dict[str, str]] = []
    if body_selected:
        manifest.append(
            {
                "key": "gmail_body",
                "label": "Email body",
                "component_kind": "body",
                "text": body_text,
                "path": "",
            }
        )
    for index, path in enumerate(materialized):
        manifest.append(
            {
                "key": f"gmail_attachment_{index + 1}",
                "label": attachment_names[index] if index < len(attachment_names) else path.name,
                "component_kind": "attachment",
                "text": "",
                "path": str(path),
            }
        )
    if not manifest:
        return

    # Stop using Paste text as a hidden container for attachment 2+.
    if body_selected:
        page.text_input.setPlainText(body_text)
    else:
        page.text_input.clear()

    page._gmail_component_manifest = tuple(manifest)
    page._gmail_component_sources = {}
    page._gmail_component_results = {}
    page._gmail_component_active_key = str(manifest[0]["key"])
    page._gmail_package_active = False
    page._protect_session_active = False
    page._protect_session_sources = {}
    page._protect_session_results = {}
    page.current_document = None
    page.current_findings = ()
    page.current_result = None
    page.findings_table.setRowCount(0)
    page.category_list.clear()
    page.preview.clear()
    page._set_result_actions(False)

    old_filter = getattr(page, "_protect_session_filter_bar", None)
    if old_filter is not None:
        old_filter.hide()
    _refresh_component_strip(page)
    helper = getattr(page, "_protect_session_source_helper", None)
    if helper is not None:
        helper.setText(
            f"Gmail package ready · {len(manifest)} independent source(s). "
            "Use the Email body / attachment buttons to switch the preview after Scan."
        )


def _install_capture_and_route(page) -> None:
    if not getattr(gmail_package_browser, "_gmail_component_capture_installed", False):
        original = gmail_package_browser._document_as_text

        def capture(protect, path: Path) -> str:
            text = original(protect, path)
            if getattr(protect, "_gmail_component_capture_enabled", False):
                protect._gmail_component_extra_paths.append(Path(path))
            return text

        gmail_package_browser._document_as_text = capture
        gmail_package_browser._gmail_component_capture_installed = True

    base_route = gmail_browser_route.open_gmail_inbox

    def routed(window) -> None:
        page._gmail_component_capture_enabled = True
        page._gmail_component_extra_paths = []
        try:
            base_route(window)
        finally:
            page._gmail_component_capture_enabled = False
        _adopt_imported_package(page)

    gmail_browser_route.open_gmail_inbox = routed


def _install_package_runtime(page) -> None:
    previous_start = page._start_analysis
    previous_refresh = page._refresh_preview
    previous_populate = page._populate_findings
    previous_confirm = page._confirm_residual_risk
    previous_save = page._save_to_library
    previous_copy = page._copy_result
    previous_ai = page._copy_and_open_chatgpt
    previous_clear = page.clear

    def start_analysis(self) -> None:
        manifest = tuple(getattr(self, "_gmail_component_manifest", ()) or ())
        if not manifest:
            previous_start()
            return

        base_profile = get_profile(self.profile_combo.currentData())
        profile = replace(
            base_profile,
            entities=entities_for_scope(base_profile, self.scope_combo.currentData()),
            threshold=float(self.threshold_input.value()),
        )

        def task():
            sources = {}
            for component in manifest:
                key = str(component["key"])
                if component.get("component_kind") == "body":
                    document = self.service.document_from_text(str(component.get("text") or ""))
                else:
                    document = self.service.document_from_file(str(component.get("path") or ""))
                sources[key] = {
                    "document": document,
                    "findings": _tag_findings(self.service.analyze(document, profile), key),
                    "label": str(component.get("label") or "Source"),
                    "component_kind": str(component.get("component_kind") or "attachment"),
                }
            return sources

        def ready(payload: object) -> None:
            sources = dict(payload)
            if not sources:
                return
            self._gmail_package_active = True
            self._gmail_component_sources = sources
            self._gmail_component_results = {}
            self._protect_session_active = False
            combined = tuple(
                finding
                for component in manifest
                for finding in sources[str(component["key"])]["findings"]
            )
            first_key = (
                self._gmail_component_active_key
                if self._gmail_component_active_key in sources
                else str(manifest[0]["key"])
            )
            self._gmail_component_active_key = first_key
            self._analysis_ready((sources[first_key]["document"], combined))
            _refresh_component_strip(self)
            self._gmail_component_select(first_key)
            metric = getattr(self, "_redesign_review_metric", None)
            if metric is not None:
                metric.setText(f"Ready to review · {len(manifest)} Gmail sources")

        self._set_busy(True)
        begin = getattr(self, "_redesign_begin_operation", None)
        if callable(begin):
            begin("scan", f"Scanning {len(manifest)} Gmail source(s) locally…")
        worker = FunctionWorker(task)
        self._active_worker = worker
        worker.signals.result.connect(ready)
        worker.signals.error.connect(
            lambda message: QMessageBox.critical(self, "Unable to scan Gmail package", message)
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
        if not getattr(self, "_gmail_package_active", False):
            previous_populate()
            return
        active_document = self.current_document
        try:
            self.current_document = self.service.document_from_text("")
            ProtectionPage._populate_findings(self)
        finally:
            self.current_document = active_document

        by_id = {finding.finding_id: finding for finding in self.current_findings}
        for row_index in range(self.findings_table.rowCount()):
            checkbox = self.findings_table.item(row_index, 0)
            if checkbox is None:
                continue
            finding_id = str(checkbox.data(Qt.ItemDataRole.UserRole) or "")
            key = _source_key(finding_id)
            checkbox.setData(_SOURCE_ROLE, key)
            payload = self._gmail_component_sources.get(key, {})
            finding = by_id.get(finding_id)
            document = payload.get("document")
            location_item = self.findings_table.item(row_index, 3)
            if not payload or finding is None or document is None or location_item is None:
                continue
            label = str(payload.get("label") or "Source")
            if payload.get("component_kind") == "body":
                location_item.setText("Email body")
            elif document.source_kind == "pdf":
                location_item.setText(f"{label} · Page {finding.page_number}")
            else:
                source_page = next(
                    (item for item in document.pages if item.page_number == finding.page_number),
                    None,
                )
                detail = source_page.location if source_page is not None and source_page.location else f"Segment {finding.page_number}"
                location_item.setText(f"{label} · {detail}")

        self.findings_metric.setText(
            f"{len(self.current_findings)} findings · {len(self._gmail_component_sources)} sources"
        )
        old_filter = getattr(self, "_protect_session_filter_bar", None)
        if old_filter is not None:
            old_filter.hide()

    page._populate_findings = MethodType(populate_findings, page)

    def refresh_preview(self, *_args) -> None:
        if not getattr(self, "_gmail_package_active", False):
            previous_refresh(*_args)
            return
        if hasattr(self, "_redesign_allow_refresh") and not self._redesign_allow_refresh:
            selected = len(self._selected_findings())
            self.current_result = None
            self._gmail_component_results = {}
            self._redesign_protected_metric.setText(f"{selected} selected")
            self._redesign_review_metric.setText("Review selection, then protect")
            self._redesign_protect_button.setEnabled(bool(self.current_findings))
            self._redesign_final_actions.hide()
            self._redesign_set_final_actions(False)
            return

        selected_ids = {
            self.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.findings_table.rowCount())
            if self.findings_table.item(row, 0).checkState() == Qt.CheckState.Checked
        }
        results = {}
        for index, component in enumerate(self._gmail_component_manifest, start=1):
            key = str(component["key"])
            payload = self._gmail_component_sources[key]
            selected = tuple(
                finding for finding in payload["findings"] if finding.finding_id in selected_ids
            )
            result = self.service.protect(
                payload["document"],
                selected,
                replacement_mode=self.mode_combo.currentData(),
            )
            results[key] = _namespace_result(result, f"GMAIL{index}")

        self._gmail_component_results = results
        self._gmail_component_select(self._gmail_component_active_key)
        protected_count = sum(len(result.applied_findings) for result in results.values())
        self.findings_metric.setText(
            f"{len(self.current_findings)} detected  |  {protected_count} protected"
        )
        self._set_result_actions(True)

        def sync_metrics() -> None:
            if getattr(self, "_gmail_package_active", False):
                self._redesign_protected_metric.setText(
                    f"{protected_count} protected · {len(results)} sources"
                )
                self._redesign_review_metric.setText(
                    f"Protected package ready · {len(results)} sources"
                )

        QTimer.singleShot(0, sync_metrics)

    page._refresh_preview = MethodType(refresh_preview, page)

    def select_component(self, key: str) -> None:
        _show_component(self, key)

    page._gmail_component_select = MethodType(select_component, page)

    try:
        page.findings_table.cellClicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def select_source_first(row_index: int, _column: int) -> None:
        if not getattr(page, "_gmail_package_active", False):
            return
        checkbox = page.findings_table.item(row_index, 0)
        if checkbox is None:
            return
        key = _source_key(str(checkbox.data(Qt.ItemDataRole.UserRole) or ""))
        if key:
            page._gmail_component_select(key)

    page.findings_table.cellClicked.connect(select_source_first)
    page.findings_table.cellClicked.connect(page._finding_selected)

    def confirm_residual(self, action: str) -> bool:
        if not getattr(self, "_gmail_package_active", False):
            return previous_confirm(action)
        if not self._gmail_component_results:
            return False
        profile = self._current_profile()
        residuals = []
        for key, result in self._gmail_component_results.items():
            label = str(self._gmail_component_sources[key].get("label") or "Source")
            for finding in self.service.verify_protected(result, profile):
                residuals.append((label, finding))
        self._last_residual = tuple(finding for _label, finding in residuals)
        if not residuals:
            self.verification_metric.setText(
                f"Verified: no remaining PII · {len(self._gmail_component_results)} sources"
            )
            self.verification_metric.setProperty("warning", False)
            self.verification_metric.style().unpolish(self.verification_metric)
            self.verification_metric.style().polish(self.verification_metric)
            return True

        self.verification_metric.setText(
            f"Warning: {len(residuals)} possible PII remain"
        )
        self.verification_metric.setProperty("warning", True)
        self.verification_metric.style().unpolish(self.verification_metric)
        self.verification_metric.style().polish(self.verification_metric)
        examples = "\n".join(
            f"• {label} · {finding.entity_type}: {finding.text[:45]}"
            for label, finding in residuals[:8]
        )
        answer = QMessageBox.warning(
            self,
            "Possible sensitive data remains",
            f"PrivacyGate found {len(residuals)} possible sensitive item(s) "
            f"across this Gmail package before {action}:\n\n{examples}\n\n"
            "Return to Review and protect them whenever possible.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ignore,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ignore

    page._confirm_residual_risk = MethodType(confirm_residual, page)

    def combined_package_text(self) -> str:
        chunks = []
        for component in self._gmail_component_manifest:
            key = str(component["key"])
            result = self._gmail_component_results.get(key)
            if result is None:
                continue
            label = str(component.get("label") or "Source")
            heading = (
                "=== GMAIL EMAIL BODY ==="
                if component.get("component_kind") == "body"
                else f"=== GMAIL ATTACHMENT · {label} ==="
            )
            chunks.append(f"{heading}\n{result.combined_text}")
        return "\n\n".join(chunks)

    page._gmail_component_combined_text = MethodType(combined_package_text, page)

    def copy_result(self) -> None:
        if not getattr(self, "_gmail_package_active", False):
            previous_copy()
            return
        if self._confirm_residual_risk("copying"):
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._gmail_component_combined_text())

    page._copy_result = MethodType(copy_result, page)

    def copy_and_open_ai(self) -> None:
        if not getattr(self, "_gmail_package_active", False):
            previous_ai()
            return
        if not self._confirm_residual_risk("opening an AI service"):
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._gmail_component_combined_text())
        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))

    page._copy_and_open_chatgpt = MethodType(copy_and_open_ai, page)

    def save_to_library(self):
        if not getattr(self, "_gmail_package_active", False):
            return previous_save()
        if not self._gmail_component_results:
            return None
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(
            self,
            "Save Gmail protection package",
            "Package title:",
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
        for component in self._gmail_component_manifest:
            key = str(component["key"])
            payload = self._gmail_component_sources[key]
            result = self._gmail_component_results[key]
            document = payload["document"]
            source_label = str(payload.get("label") or "Source")
            library_item = self.library.save(
                title=f"{title} — {source_label}",
                source_kind=document.source_kind,
                source_name=source_label,
                profile_key=self.profile_combo.currentData(),
                result=result,
                labels=labels,
            )
            saved.append(library_item)
            self.library_changed.emit(library_item.document_id)
        return saved[0] if saved else None

    page._save_to_library = MethodType(save_to_library, page)

    def clear(self) -> None:
        self._gmail_component_manifest = ()
        self._gmail_component_sources = {}
        self._gmail_component_results = {}
        self._gmail_component_active_key = ""
        self._gmail_package_active = False
        previous_clear()
        _refresh_component_strip(self)

    try:
        page.clear_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page.clear = MethodType(clear, page)
    page.clear_button.clicked.connect(page.clear)


def apply_gmail_component_session(main_window) -> None:
    """Keep Gmail body and every selected attachment as separate Protect sources."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_gmail_component_session_runtime", False):
        return
    page._gmail_component_session_runtime = True
    page._gmail_component_manifest = ()
    page._gmail_component_sources = {}
    page._gmail_component_results = {}
    page._gmail_component_active_key = ""
    page._gmail_package_active = False
    page._gmail_component_capture_enabled = False
    page._gmail_component_extra_paths = []

    _ensure_component_ui(page)
    _install_package_runtime(page)
    _install_capture_and_route(page)
