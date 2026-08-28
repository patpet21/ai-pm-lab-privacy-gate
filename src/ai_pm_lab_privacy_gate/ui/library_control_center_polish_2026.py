from __future__ import annotations

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.domain.company_policy import PolicyEngine
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.ui import library_control_center_2026 as _control
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    resolve_library_workspace,
    scoped_documents,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_PATCHED = False
_BULK_SAFETY_PATCHED = False
_REFRESH_POLISH_PATCHED = False
_COMPLIANCE_PATCHED = False


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


def _install_bulk_safety() -> None:
    """Make mass scope explicit and confirm every AI-access mutation."""
    global _BULK_SAFETY_PATCHED
    if _BULK_SAFETY_PATCHED:
        return
    _BULK_SAFETY_PATCHED = True

    previous_update = _control._update_bulk_bar
    previous_ai_access = _control._bulk_ai_access

    def update_bulk_bar(page) -> None:
        previous_update(page)
        selected = set(getattr(page, "_library_bulk_selected_ids_2026", set()))
        label = getattr(page, "_library_bulk_count_2026", None)
        if label is not None and selected:
            noun = "document" if len(selected) == 1 else "documents"
            label.setText(f"{len(selected)} {noun} selected · Current filtered view")

    def guarded_ai_access(page, allow: bool) -> None:
        documents = _control._selected_bulk_documents(page)
        if not documents:
            return
        if not allow:
            answer = QMessageBox.question(
                page,
                "Block AI / MCP access?",
                f"Block AI / MCP access for {len(documents)} selected protected document(s)?\n\n"
                "This changes only the local protected-copy access preference. Original values and restore mappings remain local.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        previous_ai_access(page, allow)

    _control._update_bulk_bar = update_bulk_bar
    _control._bulk_ai_access = guarded_ai_access


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
            try:
                main_window.statusBar().showMessage(
                    "Organization policy re-check completed locally.", 7000
                )
            except Exception:
                pass

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
            current = page._current()
            context_now = resolve_library_workspace(page)
            button.setEnabled(
                bool(
                    current is not None
                    and context_now.managed
                    and context_now.policy is not None
                )
            )

        worker.signals.result.connect(ready)
        worker.signals.error.connect(failed)
        worker.signals.finished.connect(finished)
        QThreadPool.globalInstance().start(worker)

    button.clicked.connect(lambda _checked=False: run_check())
    _control._update_compliance(page, page._current())


def _install_compact_compliance() -> None:
    """Keep Personal/legacy context to one compact line; retain room for Team policy detail."""
    global _COMPLIANCE_PATCHED
    if _COMPLIANCE_PATCHED:
        return
    _COMPLIANCE_PATCHED = True
    previous = _control._update_compliance

    def update_compliance(page, document) -> None:
        previous(page, document)
        frame = getattr(page, "_library_compliance_frame_2026", None)
        label = getattr(page, "_library_compliance_text_2026", None)
        context = getattr(page, "_library_workspace_context_2026", None)
        if frame is None or label is None:
            return

        if document is not None and context is not None and context.personal:
            metadata = getattr(page, "_library_workspace_metadata_map", {}).get(document.document_id)
            if metadata is None:
                _control._set_compliance_style(
                    page,
                    "amber",
                    "Legacy local · Personal only · not assigned to an Organization · integrity + restore remain local.",
                )
            label.setWordWrap(False)
            frame.setMaximumHeight(46)
        else:
            label.setWordWrap(True)
            frame.setMaximumHeight(68)

    _control._update_compliance = update_compliance


def _install_layout_compaction(page) -> None:
    """Recover vertical room without removing controls or changing their semantics."""
    root = page.layout()
    if root is not None:
        root.setSpacing(8)

    category_buttons = getattr(page, "_library_category_buttons", {})
    for button in category_buttons.values():
        button.setMinimumHeight(28)
        button.setMaximumHeight(30)
    if category_buttons:
        frame = next(iter(category_buttons.values())).parentWidget()
        layout = frame.layout() if frame is not None else None
        if frame is not None:
            frame.setMaximumHeight(43)
        if layout is not None:
            layout.setContentsMargins(5, 4, 5, 4)

    smart = getattr(page, "_library_smart_collections_2026", None)
    smart_layout = smart.layout() if smart is not None else None
    if smart is not None:
        smart.setMaximumHeight(42)
    if smart_layout is not None:
        smart_layout.setContentsMargins(8, 4, 8, 4)
        smart_layout.setSpacing(4)
        for index in range(smart_layout.count()):
            widget = smart_layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                widget.setMinimumHeight(26)
                widget.setMaximumHeight(28)

    source_combo = getattr(page, "_library_source_filter_2026", None)
    filters = source_combo.parentWidget() if source_combo is not None else None
    filters_layout = filters.layout() if filters is not None else None
    if filters is not None:
        filters.setMaximumHeight(48)
    if filters_layout is not None:
        filters_layout.setContentsMargins(8, 5, 8, 5)
        filters_layout.setSpacing(6)
    for combo_name in (
        "_library_source_filter_2026",
        "_library_account_filter_2026",
        "_library_label_filter_2026",
        "_library_type_filter_2026",
    ):
        combo = getattr(page, combo_name, None)
        if combo is not None:
            combo.setMinimumHeight(31)
            combo.setMaximumHeight(32)
    reset = getattr(page, "_library_reset_filters_2026", None)
    if reset is not None:
        reset.setMinimumHeight(31)
        reset.setMaximumHeight(32)

    page.search.setMinimumHeight(36)
    page.search.setMaximumHeight(38)
    for button in (page.backup_button, page.import_backup_button, page.refresh_button):
        button.setMinimumHeight(32)
        button.setMaximumHeight(34)

    bulk = getattr(page, "_library_bulk_bar_2026", None)
    bulk_layout = bulk.layout() if bulk is not None else None
    if bulk is not None:
        bulk.setMaximumHeight(43)
    if bulk_layout is not None:
        bulk_layout.setContentsMargins(8, 4, 8, 4)
        bulk_layout.setSpacing(5)
        for index in range(bulk_layout.count()):
            widget = bulk_layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                widget.setMinimumHeight(26)
                widget.setMaximumHeight(28)

    tabs = getattr(page, "_library_control_tabs_2026", None)
    if tabs is not None:
        tabs.setMaximumHeight(225)


def _install_empty_org_state(page) -> None:
    if getattr(page, "_library_empty_org_state_2026", None) is not None:
        return
    preview_card = page.preview.parentWidget()
    layout = preview_card.layout() if preview_card is not None else None
    if not isinstance(layout, QVBoxLayout):
        return

    frame = QFrame(objectName="LibraryOrganizationEmpty2026")
    frame.setStyleSheet(
        "QFrame#LibraryOrganizationEmpty2026{background:#FBFCFE;border:1px solid #E4E7EC;border-radius:12px;}"
    )
    box = QVBoxLayout(frame)
    box.setContentsMargins(28, 24, 28, 24)
    box.setSpacing(9)
    box.addStretch(1)

    icon_label = QLabel("▣")
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_label.setStyleSheet(
        "color:#2563EB;font-size:25px;font-weight:900;border:none;background:transparent;"
    )
    title = QLabel("No Organization documents yet")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        "color:#101828;font-size:17px;font-weight:950;border:none;background:transparent;"
    )
    subtitle = QLabel()
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        "color:#667085;font-size:9px;border:none;background:transparent;"
    )
    next_step = QLabel()
    next_step.setAlignment(Qt.AlignmentFlag.AlignCenter)
    next_step.setWordWrap(True)
    next_step.setStyleSheet(
        "background:#EEF4FF;color:#2563EB;border:1px solid #D6E4FF;border-radius:9px;"
        "padding:8px 12px;font-size:8.5px;font-weight:850;"
    )

    box.addWidget(icon_label)
    box.addWidget(title)
    box.addWidget(subtitle)
    box.addWidget(next_step, 0, Qt.AlignmentFlag.AlignHCenter)
    box.addStretch(1)

    preview_index = layout.indexOf(page.preview)
    layout.insertWidget(max(1, preview_index), frame, 1)
    frame.hide()

    page._library_empty_org_state_2026 = frame
    page._library_empty_org_title_2026 = title
    page._library_empty_org_subtitle_2026 = subtitle
    page._library_empty_org_next_2026 = next_step


def _has_any_org_document(page) -> bool:
    try:
        all_documents = tuple(page.library.list_documents(include_deleted=True))
        context, _metadata, documents = scoped_documents(page, all_documents)
        return bool(context.managed and documents)
    except Exception:
        return True


def _action_widgets(page):
    widgets = [
        page.copy_button,
        page.export_button,
        page.edit_button,
        page.favorite_button,
        page.mcp_button,
        page.restore_button,
        page.restore_trash_button,
        page.delete_button,
    ]
    use_ai = getattr(page, "_library_use_ai_button_2026", None)
    if use_ai is not None:
        widgets.append(use_ai)
    return tuple(widgets)


def _update_empty_org_state(page) -> None:
    frame = getattr(page, "_library_empty_org_state_2026", None)
    if frame is None:
        return
    context = getattr(page, "_library_workspace_context_2026", None)
    truly_empty = bool(context is not None and context.managed and not _has_any_org_document(page))

    header = getattr(page, "_library_detail_header", None)
    context_label = getattr(page, "_library_detail_context_2026", None)
    context_bar = context_label.parentWidget() if context_label is not None else None
    protected_bar = getattr(page, "_protected_content_bar", None)
    tabs = getattr(page, "_library_control_tabs_2026", None)
    policy_recheck = getattr(page, "_library_policy_recheck_2026", None)

    frame.setVisible(truly_empty)
    for widget in (header, context_bar, protected_bar, tabs, page.preview):
        if widget is not None:
            widget.setVisible(not truly_empty)

    if truly_empty:
        name = str(getattr(context, "name", "") or "Organization")
        page._library_empty_org_title_2026.setText(f"No protected documents in {name}")
        page._library_empty_org_subtitle_2026.setText(
            "This Library only shows protected copies explicitly saved while this Organization workspace is active. "
            "Personal and Legacy local documents stay separate."
        )
        page._library_empty_org_next_2026.setText(
            f"Next step · Open Protect with {name} selected, then save the protected result to the local Library."
        )
        for widget in _action_widgets(page):
            widget.hide()
        if policy_recheck is not None:
            policy_recheck.hide()
        return

    current = page._current()
    for widget in _action_widgets(page):
        widget.show()
    if current is not None:
        trashed = current.deleted_at is not None
        page.restore_button.setVisible(not trashed)
        page.restore_trash_button.setVisible(trashed)
    else:
        page.restore_trash_button.hide()
    if policy_recheck is not None:
        policy_recheck.setVisible(bool(current is not None and context is not None and context.managed))


def _install_refresh_polish_hook() -> None:
    global _REFRESH_POLISH_PATCHED
    if _REFRESH_POLISH_PATCHED:
        return
    _REFRESH_POLISH_PATCHED = True
    previous = _control._after_refresh

    def after_refresh(page) -> None:
        previous(page)
        _update_empty_org_state(page)

    _control._after_refresh = after_refresh


def apply_library_control_center_polish_2026(main_window) -> None:
    page = getattr(main_window, "library_page", None)
    if page is None or bool(getattr(page, "_library_control_center_polish_2026", False)):
        return
    page._library_control_center_polish_2026 = True

    _install_select_visible(page)
    _patch_bulk_trash_behavior(page)
    _install_bulk_safety()
    _install_live_policy_check(main_window, page)
    _install_compact_compliance()
    _install_layout_compaction(page)
    _install_empty_org_state(page)
    _install_refresh_polish_hook()
    page.refresh()