from __future__ import annotations

"""Final single-row command surface for the approved Protect redesign.

This layer only recomposes widgets that already belong to the real Protect runtime.
No connector, workspace, scan, policy, preview or workflow behavior is duplicated.
The previous Policy / Status / Mode / Preflight strip stays hidden; the existing
Workspace, Source, Account and source-action widgets are moved into one compact row.
Workflow status reads only the existing local WatchFolderStore and no path/content is
sent to Supabase.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    MUTED,
    TEXT,
    WHITE,
)


def _active_workspace_key(main_window) -> str:
    page = getattr(main_window, "protection_page", None)
    context_bar = getattr(page, "_managed_workspace_context_bar", None) if page is not None else None
    if context_bar is not None:
        key = str(context_bar.workspace_combo.currentData() or "")
        if key:
            return key
    controller = getattr(main_window, "privacygate_feature_suite", None)
    resolver = getattr(controller, "active_workspace_key", None)
    if callable(resolver):
        try:
            return str(resolver() or "personal")
        except Exception:
            pass
    return "personal"


def _workflow_count(main_window) -> int:
    controller = getattr(main_window, "privacygate_feature_suite", None)
    store = getattr(controller, "watch_store", None) if controller is not None else None
    if store is None:
        return 0
    workspace_key = _active_workspace_key(main_window)
    try:
        configs = tuple(store.list())
    except Exception:
        return 0
    return sum(
        1
        for config in configs
        if bool(getattr(config, "enabled", False))
        and str(getattr(config, "workspace_key", "personal") or "personal") == workspace_key
    )


def _open_workflows(main_window) -> None:
    controller = getattr(main_window, "privacygate_feature_suite", None)
    if controller is None:
        return
    try:
        from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import WatchedFoldersDialog

        WatchedFoldersDialog(controller).exec()
    except Exception:
        for button in tuple(getattr(main_window, "nav_buttons", ()) or ()):
            if " ".join(button.text().split()).lower() == "automation":
                button.click()
                break


def _collapse_legacy_context(context_bar) -> None:
    chips = getattr(context_bar, "_protect_2026_policy_chips", None)
    if chips is not None:
        chips.hide()
        chips.setMaximumSize(0, 0)
    policy = getattr(context_bar, "policy", None)
    if policy is not None:
        policy.hide()
        policy.setMaximumSize(0, 0)


def _field_host(label_text: str, widget: QWidget, *, minimum: int, maximum: int) -> QFrame:
    host = QFrame()
    host.setStyleSheet("QFrame{background:transparent;border:none;}")
    host.setMinimumWidth(minimum)
    host.setMaximumWidth(maximum)
    box = QVBoxLayout(host)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    label = QLabel(label_text)
    label.setStyleSheet(
        f"color:{MUTED};font-size:7px;font-weight:850;background:transparent;border:none;"
    )
    box.addWidget(label)
    box.addWidget(widget)
    return host


def _workflow_button(main_window) -> QPushButton:
    button = QPushButton()
    button.setObjectName("Protect2026WorkflowButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(39)
    button.setMinimumWidth(118)
    button.setMaximumWidth(142)
    button.setIcon(icon("workflow", color=BLUE, size=16))
    button.clicked.connect(lambda _checked=False: _open_workflows(main_window))
    return button


def _refresh_workflow(main_window, button: QPushButton) -> None:
    count = _workflow_count(main_window)
    if count > 0:
        button.setText(f"Workflow · {count} active")
        button.setStyleSheet(
            f"QPushButton{{background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
            "border-radius:9px;padding:8px 9px;font-size:8px;font-weight:850;text-align:left;}"
            "QPushButton:hover{background:#DCFCE7;border-color:#86EFAC;}"
        )
    else:
        button.setText("Workflow · none")
        button.setStyleSheet(
            "QPushButton{background:#F8FAFC;color:#475467;border:1px solid #E4E7EC;"
            "border-radius:9px;padding:8px 9px;font-size:8px;font-weight:850;text-align:left;}"
            f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE};border-color:#C7D7FE;}}"
        )
    button.setToolTip(
        "Local watched-folder workflows for the current workspace. Click to manage them. "
        "Folder paths and source content stay on this device."
    )


def _choose_label(context_bar) -> tuple[str, str]:
    provider = str(context_bar.source_combo.currentData() or "")
    account_id = str(context_bar.account_combo.currentData() or "")
    workspace_key = str(context_bar.workspace_combo.currentData() or "")
    noun = "email" if provider == "gmail" else "file" if provider == "google_drive" else "content"

    needs_approval = False
    try:
        context = context_bar.store.load()
        descriptor = context.workspaces.get(workspace_key)
        needs_approval = bool(
            descriptor is not None
            and not descriptor.personal
            and provider
            and account_id
            and not context_bar.store.is_account_available(provider, account_id, workspace_key)
        )
    except Exception:
        pass

    text = f"Approve & choose {noun}" if needs_approval else f"Choose {noun}"
    tooltip = (
        f"Choose a {noun} from the selected connected account and bring its working copy into this local Protect session."
    )
    return text, tooltip


def _refresh_choose_action(context_bar) -> None:
    text, tooltip = _choose_label(context_bar)
    context_bar.browse.setText(text)
    context_bar.browse.setToolTip(tooltip)


def _prepare_action(button, *, minimum: int, maximum: int) -> None:
    if button is None:
        return
    button.setMinimumHeight(39)
    button.setMinimumWidth(minimum)
    button.setMaximumWidth(maximum)


def _install_single_row(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_protect_2026_unified_row", None) is not None:
        return
    context_bar = getattr(page, "_managed_workspace_context_bar", None)
    quick = getattr(page, "_protect_source_quick_bar", None)
    preview = getattr(page, "preview_card", None)
    preview_layout = preview.layout() if preview is not None else None
    quick_layout = quick.layout() if quick is not None else None
    if context_bar is None or preview_layout is None or not isinstance(quick_layout, QHBoxLayout):
        return

    _collapse_legacy_context(context_bar)

    row_frame = QFrame(objectName="Protect2026UnifiedCommandRow")
    row_frame.setStyleSheet(
        f"QFrame#Protect2026UnifiedCommandRow{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;}}"
    )
    row = QHBoxLayout(row_frame)
    row.setContentsMargins(9, 7, 9, 7)
    row.setSpacing(7)

    workflow = _workflow_button(main_window)
    row.addWidget(workflow)

    upload = getattr(page, "_protect_source_upload", None)
    connected = getattr(page, "_protect_source_connected", None)
    paste = getattr(page, "_protect_source_paste", None)
    scan = getattr(page, "_protect_source_scan", None)
    _prepare_action(upload, minimum=94, maximum=110)
    _prepare_action(connected, minimum=145, maximum=165)
    _prepare_action(paste, minimum=102, maximum=116)
    _prepare_action(scan, minimum=150, maximum=178)

    for button in (upload, connected, paste):
        if button is not None:
            row.addWidget(button)

    context_bar.workspace_combo.setMinimumWidth(155)
    context_bar.workspace_combo.setMaximumWidth(195)
    context_bar.source_combo.setMinimumWidth(58)
    context_bar.source_combo.setMaximumWidth(58)
    context_bar.source_combo.view().setMinimumWidth(190)
    context_bar.account_combo.setMinimumWidth(185)
    context_bar.account_combo.setMaximumWidth(225)
    context_bar.account_combo.view().setMinimumWidth(260)

    row.addWidget(
        _field_host("Workspace", context_bar.workspace_combo, minimum=155, maximum=195)
    )
    row.addWidget(
        _field_host("Source", context_bar.source_combo, minimum=58, maximum=58)
    )
    row.addWidget(
        _field_host("Account", context_bar.account_combo, minimum=185, maximum=225)
    )

    # The language selector is created by the core Protect runtime before this
    # final presentation pass. Move that exact widget into the approved command
    # row so Upload/connected/Paste/Language/Scan describe one coherent session.
    language_panel = getattr(page, "_protect_document_language_panel", None)
    language_combo = getattr(page, "document_language_combo", None)
    language_label = getattr(page, "_protect_document_language_label", None)
    if language_panel is not None and language_combo is not None:
        if language_label is not None:
            language_label.setText("Language")
            language_label.setStyleSheet(
                f"color:{MUTED};font-size:7px;font-weight:850;background:transparent;border:none;"
            )
        language_panel.setStyleSheet("QFrame#ProtectDocumentLanguage{background:transparent;border:none;}")
        language_panel.setMinimumWidth(105)
        language_panel.setMaximumWidth(122)
        language_combo.setMinimumWidth(105)
        language_combo.setMaximumWidth(122)
        language_combo.setMinimumHeight(39)
        row.addWidget(language_panel)

    context_bar.browse.setMinimumHeight(39)
    context_bar.browse.setMinimumWidth(145)
    context_bar.browse.setMaximumWidth(172)
    row.addWidget(context_bar.browse)

    if scan is not None:
        row.addWidget(scan)

    # The old two shells are now empty/redundant. Their real controls have been
    # reparented into the single command row above; all signal connections survive.
    context_bar.hide()
    context_bar.setMaximumHeight(0)
    quick.hide()
    quick.setMaximumHeight(0)

    context_index = preview_layout.indexOf(context_bar)
    quick_index = preview_layout.indexOf(quick)
    indexes = [index for index in (context_index, quick_index) if index >= 0]
    insert_at = min(indexes) if indexes else 1
    preview_layout.insertWidget(insert_at, row_frame)

    page._protect_2026_unified_row = row_frame
    page._protect_2026_workflow_button = workflow

    def refresh(*_args) -> None:
        _refresh_workflow(main_window, workflow)
        _refresh_choose_action(context_bar)

    def schedule(*_args) -> None:
        # Existing connector/workspace controllers update first; this presentation
        # layer then applies the final user-facing action label.
        QTimer.singleShot(10, refresh)

    context_bar.workspace_combo.currentIndexChanged.connect(schedule)
    context_bar.source_combo.currentIndexChanged.connect(schedule)
    context_bar.account_combo.currentIndexChanged.connect(schedule)
    context_bar.team_page.state_changed.connect(schedule)
    context_bar.team_page.policy_changed.connect(schedule)

    controller = getattr(main_window, "privacygate_feature_suite", None)
    timer = getattr(controller, "watch_timer", None) if controller is not None else None
    if timer is not None:
        timer.timeout.connect(schedule)

    refresh()


def apply_mockup_protect_compact_workflow_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_compact_workflow", False)):
        return
    page._protect_2026_compact_workflow = True
    _install_single_row(main_window)