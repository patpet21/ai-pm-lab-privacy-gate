from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QPushButton

from ai_pm_lab_privacy_gate.application import feature_safety_runtime as _feature_safety_runtime
from ai_pm_lab_privacy_gate.domain.plans import Capability, supports
from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import RulesDialog, WatchedFoldersDialog


_RULES_PATCHED = False
_WATCHED_PATCHED = False


def _patch_rules_dialog() -> None:
    """Make Workspace Rules feed the existing connector/workspace routing stores."""
    global _RULES_PATCHED
    if _RULES_PATCHED:
        return
    _RULES_PATCHED = True
    original_add = RulesDialog._add

    def add_with_live_binding(self: RulesDialog) -> None:
        before = tuple(self.controller.rules.list())
        original_add(self)
        after = tuple(self.controller.rules.list())
        if len(after) <= len(before):
            return
        rule = after[-1]
        team_page = getattr(self.controller.main_window, "team_page", None)
        workspace_store = getattr(team_page, "_privacygate_workspace_store", None)
        if workspace_store is not None and rule.provider and rule.account_id:
            try:
                workspace_store.bind_account(rule.provider, rule.account_id, [rule.workspace_key])
            except Exception:
                # Rule persistence remains valid even if an account identifier does
                # not yet exist in the connector registry on this device.
                pass
        if rule.default_folder:
            try:
                self.controller.routes.set_route(
                    rule.workspace_key,
                    Path(rule.default_folder),
                    custom=True,
                )
            except Exception:
                pass

    RulesDialog._add = add_with_live_binding


def _patch_watched_folder_dialog() -> None:
    """Reject self-feeding watches before they are persisted."""
    global _WATCHED_PATCHED
    if _WATCHED_PATCHED:
        return
    _WATCHED_PATCHED = True
    original_add = WatchedFoldersDialog._add

    def add_safely(self: WatchedFoldersDialog) -> None:
        inbox_raw = self.inbox.text().strip()
        protected_raw = self.protected.text().strip()
        if inbox_raw and protected_raw:
            inbox = Path(inbox_raw).expanduser().resolve()
            protected = Path(protected_raw).expanduser().resolve()
            if inbox == protected:
                QMessageBox.warning(
                    self,
                    "Watched Folders",
                    "Inbox and Protected output must be different folders so protected files are not re-processed.",
                )
                return
            if protected in inbox.parents:
                QMessageBox.warning(
                    self,
                    "Watched Folders",
                    "Protected output cannot be a parent of the Inbox. Choose a separate output folder.",
                )
                return
        original_add(self)

    WatchedFoldersDialog._add = add_safely


def _install_live_preflight(main_window, controller) -> None:
    """Apply the advanced preflight before the existing ChatGPT handoff."""
    protect = getattr(main_window, "protection_page", None)
    if protect is None or bool(getattr(protect, "_privacygate_live_preflight", False)):
        return
    menu_button = getattr(protect, "ai_button", None)
    menu = menu_button.menu() if menu_button is not None else None
    if menu is None:
        return

    manual_action = next(
        (action for action in menu.actions() if action.text().strip() == "Copy & Open ChatGPT"),
        None,
    )
    if manual_action is None:
        return
    try:
        manual_action.triggered.disconnect()
    except (RuntimeError, TypeError):
        pass

    original = protect._copy_and_open_chatgpt

    def guarded_handoff(_checked=False) -> None:
        workspace = controller.active_workspace_key()
        plan = controller.plan_for_workspace(workspace)
        result = getattr(protect, "current_result", None)
        if result is None:
            return
        if supports(plan, Capability.PRIVACY_PREFLIGHT):
            try:
                report = controller.preflight.evaluate(
                    plan,
                    result,
                    protect._current_profile(),
                    target="ChatGPT",
                    workspace_key=workspace,
                )
            except Exception as exc:
                QMessageBox.warning(protect, "Privacy Preflight", str(exc))
                return
            controller.activity.record(
                "privacy_preflight",
                workspace_key=workspace,
                source_kind="protected",
                findings_count=report.residual_findings,
                status="ready" if report.ready else "blocked",
                detail=report.message,
            )
            if not report.ready:
                QMessageBox.warning(
                    protect,
                    "AI handoff blocked by Privacy Preflight",
                    report.message
                    + "\n\nReview the document or workspace rules before opening ChatGPT.",
                )
                return
        original()

    manual_action.triggered.connect(guarded_handoff)
    protect._privacygate_live_preflight = True


def _install_advanced_profile_scan_guard(main_window, controller) -> None:
    """Protect the scan entrypoint in addition to the profile-combo UI gate."""
    protect = getattr(main_window, "protection_page", None)
    if protect is None or bool(getattr(protect, "_privacygate_profile_scan_guard", False)):
        return
    advanced = {"general_business", "construction", "legal", "healthcare_general"}
    scan = getattr(protect, "scan_button", None)
    if not isinstance(scan, QPushButton):
        return
    original = protect._start_analysis
    try:
        scan.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def guarded_scan(_checked=False) -> None:
        key = str(protect.profile_combo.currentData() or "")
        plan = controller.plan_for_workspace(controller.active_workspace_key())
        if key in advanced and not supports(plan, Capability.PRIVACY_PROFILES):
            controller.show_locked(Capability.PRIVACY_PROFILES, "Advanced Privacy Profiles")
            return
        original()

    scan.clicked.connect(guarded_scan)
    protect._privacygate_profile_scan_guard = True


def _bind_connector_entitlement(main_window, controller) -> None:
    """Give the connector service a live plan resolver for service-level gating."""
    apps = getattr(main_window, "apps_hub_page", None)
    service = getattr(apps, "service", None)
    setter = getattr(service, "set_entitlement_plan_resolver", None)
    if not callable(setter):
        return
    setter(lambda: controller.plan_for_workspace(controller.active_workspace_key()))


def apply_feature_suite_runtime(main_window) -> None:
    controller = getattr(main_window, "privacygate_feature_suite", None)
    if controller is None or bool(getattr(main_window, "_privacygate_feature_suite_runtime", False)):
        return
    _patch_rules_dialog()
    _patch_watched_folder_dialog()
    _install_live_preflight(main_window, controller)
    _install_advanced_profile_scan_guard(main_window, controller)
    _bind_connector_entitlement(main_window, controller)
    main_window._privacygate_feature_suite_runtime = True
