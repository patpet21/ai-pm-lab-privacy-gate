from __future__ import annotations

"""Final compacting pass for the approved Protect header/workspace area.

The large Policy / Status / Mode / Preflight chip strip is removed from the visible
layout because those values are already enforced by the existing controllers and
are available through contextual help.  The recovered space is used for a small,
truthful Workflow control beside the source actions.  Workflow state is read only
from the existing local WatchFolderStore; no folder path or workflow metadata is
sent to Supabase.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    MUTED,
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
        # Navigation remains available even if the dedicated dialog cannot open.
        for button in tuple(getattr(main_window, "nav_buttons", ()) or ()):
            if " ".join(button.text().split()).lower() == "automation":
                button.click()
                break


def _remove_redundant_policy_strip(page) -> None:
    context_bar = getattr(page, "_managed_workspace_context_bar", None)
    if context_bar is None:
        return

    chips = getattr(context_bar, "_protect_2026_policy_chips", None)
    if chips is not None:
        parent_layout = chips.parentWidget().layout() if chips.parentWidget() is not None else None
        if parent_layout is not None:
            parent_layout.removeWidget(chips)
        chips.hide()
        chips.setMaximumWidth(0)
        chips.setMaximumHeight(0)

    # The legacy sentence was already replaced by chips in the previous pass; keep
    # it fully collapsed as well so the context row contains only actionable state.
    policy = getattr(context_bar, "policy", None)
    if policy is not None:
        policy.hide()
        policy.setMaximumWidth(0)
        policy.setMaximumHeight(0)

    root = context_bar.layout()
    if root is not None:
        root.setContentsMargins(10, 5, 10, 6)
        root.setSpacing(3)

    context_bar.setStyleSheet(
        "QFrame#ManagedProtectContextBar{background:#FFFFFF;border:1px solid #E4E7EC;"
        "border-radius:12px;}"
    )


def _install_workflow_control(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    quick = getattr(page, "_protect_source_quick_bar", None) if page is not None else None
    layout = quick.layout() if quick is not None else None
    if page is None or not isinstance(layout, QHBoxLayout):
        return

    existing = getattr(page, "_protect_2026_workflow_button", None)
    if existing is not None:
        return

    workflow = QPushButton()
    workflow.setObjectName("Protect2026WorkflowButton")
    workflow.setCursor(Qt.CursorShape.PointingHandCursor)
    workflow.setMinimumHeight(39)
    workflow.setMinimumWidth(132)
    workflow.setMaximumWidth(170)
    workflow.setIcon(icon("workflow", color=BLUE, size=16))
    workflow.setIconSize(workflow.iconSize())
    workflow.setToolTip(
        "Local watched-folder workflows for the current workspace. Folder paths and source content remain on this device."
    )
    workflow.clicked.connect(lambda _checked=False: _open_workflows(main_window))
    layout.insertWidget(0, workflow)
    page._protect_2026_workflow_button = workflow

    def refresh(*_args) -> None:
        count = _workflow_count(main_window)
        if count > 0:
            workflow.setText(f"Workflow  ·  {count} active")
            workflow.setStyleSheet(
                f"QPushButton{{background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
                "border-radius:9px;padding:8px 10px;font-size:8.5px;font-weight:850;text-align:left;}"
                "QPushButton:hover{background:#DCFCE7;border-color:#86EFAC;}"
            )
        else:
            workflow.setText("Workflow  ·  none")
            workflow.setStyleSheet(
                "QPushButton{background:#F8FAFC;color:#475467;border:1px solid #E4E7EC;"
                "border-radius:9px;padding:8px 10px;font-size:8.5px;font-weight:850;text-align:left;}"
                f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE};border-color:#C7D7FE;}}"
            )
        workflow.setToolTip(
            "Local watched-folder workflows for this workspace. Click to manage them. "
            "PrivacyGate reads only the local workflow configuration here; folder paths are not shown or sent to Supabase."
        )

    context_bar = getattr(page, "_managed_workspace_context_bar", None)
    if context_bar is not None:
        context_bar.workspace_combo.currentIndexChanged.connect(
            lambda *_args: QTimer.singleShot(0, refresh)
        )
    controller = getattr(main_window, "privacygate_feature_suite", None)
    timer = getattr(controller, "watch_timer", None) if controller is not None else None
    if timer is not None:
        timer.timeout.connect(lambda: QTimer.singleShot(0, refresh))
    refresh()


def apply_mockup_protect_compact_workflow_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_compact_workflow", False)):
        return
    page._protect_2026_compact_workflow = True

    _remove_redundant_policy_strip(page)
    _install_workflow_control(main_window)
