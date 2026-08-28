from __future__ import annotations

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import QMessageBox, QPushButton

from ai_pm_lab_privacy_gate.domain.company_policy import PolicyEngine
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.ui import library_control_center_2026 as _control
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import resolve_library_workspace
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_PATCHED = False


def _install_select_visible(page) -> None:
    if getattr(page, "_library_select_visible_2026", None) is not None:
        return
    frame = getattr(page, "_library_smart_collections_2026", None)
    layout = frame.layout() if frame is not None else None
    if layout is None:
        return

    button = QPushButton("Select visible")
    button.setMinimumHeight(30)
    button.setToolTip("Select every visible, active document in the current workspace and filter view.")
    button.setStyleSheet(_control._button_qss())

    def select_visible() -> None:
        selected = set()
        documents = tuple(getattr(page, "_documents", ()) or ())
        for row, document in enumerate(documents):
            if document.deleted_at is not None or page.table.isRowHidden(row):
                continue
            selected.add(document.document_id)
            widget = getattr(page, "_library_final_rows", {}).get(document.document_id)
            check = getattr(widget, "_library_bulk_checkbox_2026", None) if widget is not None else None
            if check is not None:
                check.blockSignals(True)
                check.setChecked(True)
                check.blockSignals(False)
        page._library_bulk_selected_ids_2026 = selected
        _control._update_bulk_bar(page)

    button.clicked.connect(lambda _checked=False: select_visible())
    layout.insertWidget(max(0, layout.count() - 1), button)
    page._library_select_visible_2026 = button


def _patch_bulk_trash_behavior(page) -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    previous = _control._decorate_bulk_rows

    def decorate(page_object) -> None:
        previous(page_object)
        documents = {
            document.document_id: document
            for document in tuple(getattr(page_object, "_documents", ()) or ())
        }
        selected = set(getattr(page_object, "_library_bulk_selected_ids_2026", set()))
        for document_id, widget in getattr(page_object, "_library_final_rows", {}).items():
            document = documents.get(document_id)
            check = getattr(widget, "_library_bulk_checkbox_2026", None)
            if check is None:
                continue
            trashed = bool(document is not None and document.deleted_at is not None)
            check.setVisible(not trashed)
            check.setEnabled(not trashed)
            if trashed:
                selected.discard(document_id)
                check.blockSignals(True)
                check.setChecked(False)
                check.blockSignals(False)
        page_object._library_bulk_selected_ids_2026 = selected
        _control._update_bulk_bar(page_object)

    _control._decorate_bulk_rows = decorate
    decorate(page)


def _install_live_policy_check(main_window, page) -> None:
    frame = getattr(page, "_library_compliance_frame_2026", None)
    layout = frame.layout() if frame is not None else None
    if layout is None or getattr(page, "_library_policy_recheck_2026", None) is not None:
        return

    button = QPushButton("Re-check current policy")
    button.setMinimumHeight(30)
    button.setToolTip(
        "Run a fresh local residual scan of this protected copy against the current Organization required-protection rules."
    )
    button.setStyleSheet(_control._button_qss())
    layout.addWidget(button)
    page._library_policy_recheck_2026 = button
    page._library_policy_recheck_worker_2026 = None

    previous_compliance = _control._update_compliance

    def update_compliance(page_object, document) -> None:
        previous_compliance(page_object, document)
        context = getattr(page_object, "_library_workspace_context_2026", None)
        control = getattr(page_object, "_library_policy_recheck_2026", None)
        if control is not None:
            control.setVisible(bool(document is not None and context is not None and context.managed))
            control.setEnabled(
                bool(
                    document is not None
                    and context is not None
                    and context.managed
                    and context.policy is not None
                    and getattr(page_object, "_library_policy_recheck_worker_2026", None) is None
                )
            )

    _control._update_compliance = update_compliance

    def run_check() -> None:
        document = page._current()
        context = resolve_library_workspace(page)
        if document is None or not context.managed:
            return
        if context.policy is None:
            QMessageBox.warning(
                page,
                "Organization policy unavailable",
                "PrivacyGate cannot verify the active Organization policy right now. No document content was sent anywhere.",
            )
            return
        if getattr(page, "_library_policy_recheck_worker_2026", None) is not None:
            return

        service = getattr(main_window, "service", None)
        if service is None:
            QMessageBox.warning(page, "Policy check unavailable", "The local privacy engine is unavailable.")
            return

        document_id = document.document_id
        protected_text = document.protected_text
        profile_key = document.profile_key
        policy = context.policy
        active_version = _control._active_policy_version(page)
        loader = getattr(main_window, "_unified_loading", None)
        if loader is not None:
            loader.begin(
                "library.policy-recheck",
                "Checking current policy",
                "Running a fresh local privacy scan of the protected copy…",
            )

        button.setEnabled(False)

        def task():
            profile = get_profile(profile_key)
            local_document = service.document_from_text(protected_text)
            residual = tuple(service.analyze(local_document, profile))
            engine = PolicyEngine(policy)
            required = tuple(
                finding
                for finding in residual
                if engine.must_protect(str(getattr(finding, "entity_type", "") or ""))
            )
            return len(residual), len(required)

        worker = FunctionWorker(task)
        page._library_policy_recheck_worker_2026 = worker

        def ready(payload: object) -> None:
            try:
                residual_count, required_count = int(payload[0]), int(payload[1])
            except Exception:
                residual_count, required_count = 0, 0
            current = page._current()
            if current is None or current.document_id != document_id:
                return

            metadata = _control._governance_metadata(page, document_id)
            captured_version = int(getattr(metadata, "policy_version", 0) or 0) if metadata is not None else 0
            if required_count:
                _control._set_compliance_style(
                    page,
                    "red",
                    f"Current Policy v{active_version} check · {required_count} required sensitive item(s) still detected in the protected copy · AI handoff must remain blocked until re-protected.",
                )
            elif active_version and captured_version != active_version:
                captured = f"v{captured_version}" if captured_version else "no recorded policy version"
                _control._set_compliance_style(
                    page,
                    "amber",
                    f"Fresh required-protection check passed · {residual_count} non-required residual finding(s) detected · captured under {captured}, current Policy v{active_version}. Review policy changes before the next AI handoff.",
                )
            else:
                _control._set_compliance_style(
                    page,
                    "green",
                    f"Current Policy v{active_version} required-protection check passed locally · 0 required residual items · {residual_count} other possible residual finding(s). AI destination rules are still enforced at handoff.",
                )

        def failed(message: str) -> None:
            QMessageBox.warning(
                page,
                "Policy check unavailable",
                "The local policy re-check could not be completed. No document content was sent anywhere.\n\n" + message,
            )

        def finished() -> None:
            page._library_policy_recheck_worker_2026 = None
            if loader is not None:
                loader.end("library.policy-recheck")
            QTimer.singleShot(0, lambda: _control._update_compliance(page, page._current()))

        worker.signals.result.connect(ready)
        worker.signals.error.connect(failed)
        worker.signals.finished.connect(finished)
        QThreadPool.globalInstance().start(worker)

    button.clicked.connect(lambda _checked=False: run_check())
    _control._update_compliance(page, page._current())


def apply_library_control_center_polish_2026(main_window) -> None:
    page = getattr(main_window, "library_page", None)
    if page is None or bool(getattr(page, "_library_control_center_polish_2026", False)):
        return
    page._library_control_center_polish_2026 = True

    _install_select_visible(page)
    _patch_bulk_trash_behavior(page)
    _install_live_policy_check(main_window, page)
    page.refresh()
