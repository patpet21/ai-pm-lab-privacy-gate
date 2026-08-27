from __future__ import annotations

"""Migration bridge: route local Upload/Paste through ProtectSessionService.

The visible Protect page and its proven export/preview controls are intentionally
left unchanged in this phase.  This bridge owns only the local engine boundary
and mirrors session data back into the temporary compatibility dictionaries that
those controls still read.

Drive and Gmail are explicitly excluded until their own migration phases.
"""

from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.application.local_protect_sources import (
    LOCAL_DOCUMENT_KEY,
    build_local_protect_package,
    compatibility_results,
    compatibility_sources,
    should_use_local_adapter,
)
from ai_pm_lab_privacy_gate.application.protect_session_service import ProtectSessionService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


def _current_profile(page):
    base = get_profile(page.profile_combo.currentData())
    return base.__class__(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, page.scope_combo.currentData()),
        threshold=float(page.threshold_input.value()),
    )


def _primary_analysis(analysis):
    return analysis.source(LOCAL_DOCUMENT_KEY) or analysis.sources[0]


def apply_local_protect_session_runtime(main_window) -> None:
    """Move only local Upload/Paste onto the generic N-source session service."""

    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_local_protect_session_runtime", False):
        return
    page._local_protect_session_runtime = True

    session_service = ProtectSessionService(page.service)
    page._protect_session_service = session_service
    page._local_protect_session_managed = False
    page._local_protect_session_analysis = None
    page._local_protect_session_result = None

    previous_start = page._start_analysis
    previous_refresh = page._refresh_preview
    previous_confirm = page._confirm_residual_risk
    previous_clear = page.clear

    def invalidate_local_session(*_args) -> None:
        if getattr(page, "_active_worker", None) is not None:
            return
        page._local_protect_session_managed = False
        page._local_protect_session_analysis = None
        page._local_protect_session_result = None

    page.text_input.textChanged.connect(invalidate_local_session)
    page.pdf_path.textChanged.connect(invalidate_local_session)

    def start_analysis(self) -> None:
        # Connector-specific sources remain on their current proven routes until
        # their dedicated migration. This prevents the first local migration from
        # silently changing Drive provenance or Gmail package behavior.
        metadata = dict(getattr(self, "_external_source_metadata", {}) or {})
        if not should_use_local_adapter(metadata):
            previous_start()
            return

        package = build_local_protect_package(
            document_path=self.pdf_path.text(),
            pasted_text=self.text_input.toPlainText(),
        )
        if package is None:
            previous_start()
            return

        profile = _current_profile(self)

        def task():
            return session_service.analyze(package, profile)

        def ready(analysis) -> None:
            if not analysis.sources:
                return

            self._local_protect_session_managed = True
            self._local_protect_session_analysis = analysis
            self._local_protect_session_result = None

            # Compatibility mirrors keep the current review/preview/export UI
            # stable while its controller is migrated in later phases.
            self._protect_session_sources = compatibility_sources(analysis)
            self._protect_session_results = {}
            self._protect_session_active = analysis.package.source_count > 1
            self._gmail_package_active = False

            primary = _primary_analysis(analysis)
            self._analysis_ready((primary.document, analysis.findings))

            if primary.document.source_kind in {"pdf", "docx", "xlsx", "pptx"}:
                self.preview_tabs.setTabVisible(1, True)
            elif analysis.package.source_count == 1:
                self.preview_tabs.setTabVisible(1, False)

            metric = getattr(self, "_redesign_review_metric", None)
            if metric is not None:
                count = analysis.package.source_count
                metric.setText(
                    "Ready to review"
                    if count == 1
                    else f"Ready to review · {count} sources"
                )

        self._set_busy(True)
        begin = getattr(self, "_redesign_begin_operation", None)
        if callable(begin):
            begin(
                "scan",
                f"Scanning {package.source_count} local source"
                f"{'s' if package.source_count != 1 else ''} with ProtectSession…",
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

    def refresh_preview(self, *_args) -> None:
        analysis = getattr(self, "_local_protect_session_analysis", None)
        if not getattr(self, "_local_protect_session_managed", False) or analysis is None:
            previous_refresh(*_args)
            return

        # The current redesign uses this false branch while review choices are
        # changing. Preserve that UI behavior and only replace the actual engine
        # call when protection is requested.
        if hasattr(self, "_redesign_allow_refresh") and not self._redesign_allow_refresh:
            previous_refresh(*_args)
            return

        selected_ids = {
            self.findings_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.findings_table.rowCount())
            if self.findings_table.item(row, 0).checkState() == Qt.CheckState.Checked
        }
        result = session_service.protect(
            analysis,
            selected_ids,
            replacement_mode=self.mode_combo.currentData(),
        )
        self._local_protect_session_result = result
        self._protect_session_results = compatibility_results(result)

        primary = result.source(LOCAL_DOCUMENT_KEY) or result.sources[0]
        self.current_document = primary.analysis.document
        self.current_result = primary.result
        self.preview.setPlainText(
            result.combined_text
            if result.source_count > 1
            else primary.result.combined_text
        )

        protected_count = result.applied_findings_count
        self.findings_metric.setText(
            f"{len(analysis.findings)} detected  |  {protected_count} protected"
        )

        if self.current_document.source_kind in {"pdf", "docx", "xlsx", "pptx"}:
            self.preview_tabs.setTabVisible(1, True)
            self._pdf_preview_timer.start()
        elif result.source_count == 1:
            self.preview_tabs.setCurrentIndex(0)

        self._set_result_actions(True)

        def sync_metrics() -> None:
            metric = getattr(self, "_redesign_protected_metric", None)
            review = getattr(self, "_redesign_review_metric", None)
            if metric is not None:
                metric.setText(
                    f"{protected_count} protected"
                    + (
                        f" · {result.source_count} sources"
                        if result.source_count > 1
                        else ""
                    )
                )
            if review is not None:
                review.setText(
                    "Protected copy ready"
                    if result.source_count == 1
                    else "Protected copies ready"
                )

        QTimer.singleShot(0, sync_metrics)

    page._refresh_preview = MethodType(refresh_preview, page)

    def confirm_residual(self, action: str) -> bool:
        result = getattr(self, "_local_protect_session_result", None)
        if not getattr(self, "_local_protect_session_managed", False) or result is None:
            return previous_confirm(action)

        residual_by_source = session_service.verify(result, self._current_profile())
        residuals = [
            (source.analysis.source.label, finding)
            for source in result.sources
            for finding in residual_by_source.get(source.analysis.source.key, ())
        ]
        self._last_residual = tuple(finding for _label, finding in residuals)
        source_count = result.source_count

        if not residuals:
            self.verification_metric.setText(
                "Verified: no remaining PII"
                + (f" · {source_count} sources" if source_count > 1 else "")
            )
            self.verification_metric.setProperty("warning", False)
            self.verification_metric.style().unpolish(self.verification_metric)
            self.verification_metric.style().polish(self.verification_metric)
            return True

        self.verification_metric.setText(
            f"Warning: {len(residuals)} possible PII remain"
            + (f" · {source_count} sources" if source_count > 1 else "")
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
            f"before {action}:\n\n{examples}\n\n"
            "Return to Review and protect them whenever possible.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ignore,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Ignore

    page._confirm_residual_risk = MethodType(confirm_residual, page)

    def clear(self) -> None:
        self._local_protect_session_managed = False
        self._local_protect_session_analysis = None
        self._local_protect_session_result = None
        previous_clear()

    page.clear = MethodType(clear, page)
