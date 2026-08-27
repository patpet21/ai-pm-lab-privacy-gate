from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.domain.company_policy import CompanyPolicy, ProtectionDirective
from ai_pm_lab_privacy_gate.domain.governance import (
    PROFILE_SPEC_VERSION,
    PrivacyRiskLevel,
    UnifiedEnforcementEngine,
    evaluate_privacy_risk,
    profile_fingerprint,
)
from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceContextStore
from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.governance_repository import (
    DocumentGovernanceRepository,
    GovernancePreferencesStore,
    ensure_activity_schema,
    install_activity_hardening,
    prune_activity,
    verify_activity_integrity,
)
from ai_pm_lab_privacy_gate.ui import team_page as team_page_module
from ai_pm_lab_privacy_gate.ui.business_foundation import _engine_for_apps, _engine_for_page
from ai_pm_lab_privacy_gate.ui.feature_suite_2026 import ActivityDialog, AutomationActionService, ProfilesDialog
from ai_pm_lab_privacy_gate.ui.multi_workspace_experience import WorkspaceBindingsDialog
from ai_pm_lab_privacy_gate.ui.privacy_preflight import PrivacyPreflightDialog, get_ai_destination
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.team_page import PolicyEditorDialog, TeamPage


_INSTALLED = False
_LIBRARY_PATCHED = False
_PREFLIGHT_PATCHED = False
_ACTIVITY_DIALOG_PATCHED = False
_PROFILE_DIALOG_PATCHED = False
_POLICY_EDITOR_PATCHED = False
_BINDING_DIALOG_PATCHED = False
_ENFORCEMENT_PATCHED = False

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7180"
MUTED = "#61798A"
GREEN = "#23824B"
AMBER = "#A56A00"
RED = "#B54747"
BORDER = "#D7E2EA"


_EXTRA_POLICY_RULES = {
    "US_ITIN": "Individual Taxpayer ID",
    "US_DRIVER_LICENSE": "Driver license",
    "US_PASSPORT": "Passport",
    "DATE_OF_BIRTH": "Date of birth",
    "POSTAL_CODE": "Postal code",
    "IP_ADDRESS": "IP address",
    "SWIFT_BIC": "SWIFT / BIC",
    "ORGANIZATION": "Organization name",
    "URL": "Web address / URL",
    "INVOICE_NUMBER": "Invoice number",
    "PURCHASE_ORDER_ID": "Purchase order",
    "CONTRACT_ID": "Contract ID",
    "TENANT_ID": "Tenant ID",
    "LEASE_ID": "Lease ID",
    "US_EIN": "Employer identification number",
    "PROPERTY_ACCESS_CODE": "Property access code",
    "LOCKBOX_CODE": "Lockbox code",
    "WIFI_CREDENTIAL": "Wi-Fi credential",
    "PASSWORD_CREDENTIAL": "Password credential",
    "MFA_RECOVERY_CODE": "MFA recovery code",
    "LOAN_NUMBER": "Loan number",
    "PERMIT_ID": "Permit ID",
}

_POLICY_RULE_HELP = {
    "US_SSN": "Government identifier. Required Protect is recommended for managed workspaces.",
    "US_ITIN": "Government tax identifier.",
    "US_DRIVER_LICENSE": "Government-issued identity credential.",
    "US_PASSPORT": "Government-issued identity credential.",
    "DATE_OF_BIRTH": "Personal identifying date.",
    "US_BANK_NUMBER": "Financial account identifier.",
    "US_ROUTING_NUMBER": "Financial routing identifier.",
    "CREDIT_CARD": "Payment-card data.",
    "PROPERTY_ACCESS_CODE": "Physical access credential.",
    "LOCKBOX_CODE": "Physical access credential.",
    "WIFI_CREDENTIAL": "Network access credential.",
    "PASSWORD_CREDENTIAL": "Authentication secret.",
    "MFA_RECOVERY_CODE": "Authentication recovery secret.",
}


def _card() -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:11px;}}"
    )
    return frame


def _chip(text: str, tone: str = "neutral") -> QLabel:
    palette = {
        "green": ("#EAF7EF", GREEN, "#BFE4CD"),
        "amber": ("#FFF5E5", AMBER, "#F0D3A0"),
        "red": ("#FDECEC", RED, "#F1C1C1"),
        "teal": ("#EAF6F6", TEAL, "#BFE0E2"),
        "neutral": ("#F1F5F7", MUTED, BORDER),
    }
    bg, fg, border = palette.get(tone, palette["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:4px 8px;font-size:8px;font-weight:900;"
    )
    return label


def _workspace_snapshot(main_window) -> dict[str, object]:
    result: dict[str, object] = {
        "key": "personal",
        "name": "Personal",
        "personal": True,
        "policy_version": 0,
    }
    page = getattr(main_window, "team_page", None)
    store = getattr(page, "_privacygate_workspace_store", None)
    if store is None:
        return result
    try:
        context = store.load()
        descriptor = context.workspaces.get(context.active_key)
    except Exception:
        return result
    if descriptor is None:
        return result
    result.update({"key": descriptor.key, "name": descriptor.name, "personal": bool(descriptor.personal)})
    state = getattr(page, "state", None)
    policy = getattr(state, "policy", None)
    if policy is not None and not descriptor.personal:
        result["policy_version"] = int(getattr(policy, "version", 0) or 0)
    return result


def _find_layout_containing(layout, widget):
    if layout is None:
        return None
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return layout
        child = item.layout()
        found = _find_layout_containing(child, widget) if child is not None else None
        if found is not None:
            return found
    return None


# Local activity integrity / retention -------------------------------------------------

def _activity_filter_match(event: str, status: str, category: str) -> bool:
    event = event.lower()
    status = status.lower()
    if category == "all":
        return True
    if category == "protect":
        return any(part in event for part in ("scan", "protect", "ocr", "batch"))
    if category == "ai":
        return any(part in event for part in ("preflight", "ai_", "handoff"))
    if category == "blocked":
        return status in {"blocked", "failed", "denied"} or "blocked" in event
    if category == "admin":
        return any(part in event for part in ("policy", "member", "device", "organization"))
    if category == "connector":
        return any(part in event for part in ("connector", "automation", "webhook", "account"))
    if category == "library":
        return any(part in event for part in ("library", "restore", "backup"))
    return True


def _install_activity_dialog() -> None:
    global _ACTIVITY_DIALOG_PATCHED
    if _ACTIVITY_DIALOG_PATCHED:
        return
    _ACTIVITY_DIALOG_PATCHED = True
    original_init = ActivityDialog.__init__
    original_refresh = ActivityDialog.refresh

    def init(self: ActivityDialog, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return
        filters = _card()
        row = QHBoxLayout(filters)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(8)
        title = QLabel("Filters")
        title.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:900;")
        row.addWidget(title)
        self._gov_event_filter = QComboBox()
        for label, key in (
            ("All activity", "all"),
            ("Protect / Scan", "protect"),
            ("AI / Preflight", "ai"),
            ("Blocked / Failed", "blocked"),
            ("Policy / Admin", "admin"),
            ("Connector / Automation", "connector"),
            ("Library / Restore", "library"),
        ):
            self._gov_event_filter.addItem(label, key)
        self._gov_workspace_filter = QComboBox()
        self._gov_workspace_filter.addItem("All workspaces", "")
        self._gov_status_filter = QComboBox()
        self._gov_status_filter.addItem("All statuses", "")
        for value in ("ok", "ready", "blocked", "failed"):
            self._gov_status_filter.addItem(value.title(), value)
        for combo in (self._gov_event_filter, self._gov_workspace_filter, self._gov_status_filter):
            combo.setMinimumHeight(32)
            row.addWidget(combo)
        row.addStretch(1)
        self._gov_integrity = _chip("LOG INTEGRITY · CHECKING", "neutral")
        row.addWidget(self._gov_integrity)
        root.insertWidget(1, filters)

        retention = _card()
        retention_row = QHBoxLayout(retention)
        retention_row.setContentsMargins(12, 8, 12, 8)
        retention_label = QLabel("Local retention")
        retention_label.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:900;")
        retention_note = QLabel(
            "Activity metadata stays on this device. Choose when PrivacyGate should delete older entries."
        )
        retention_note.setStyleSheet(f"color:{MUTED};font-size:8px;")
        self._gov_retention = QComboBox()
        for label, days in (
            ("Keep until I change it", 0),
            ("30 days", 30),
            ("90 days", 90),
            ("180 days", 180),
            ("365 days", 365),
        ):
            self._gov_retention.addItem(label, days)
        prefs = GovernancePreferencesStore(self.controller.activity.path.parent)
        index = self._gov_retention.findData(prefs.retention_days())
        self._gov_retention.setCurrentIndex(max(0, index))
        apply_retention = QPushButton("Apply retention")
        retention_row.addWidget(retention_label)
        retention_row.addWidget(retention_note, 1)
        retention_row.addWidget(self._gov_retention)
        retention_row.addWidget(apply_retention)
        root.insertWidget(2, retention)

        def apply_filters() -> None:
            category = str(self._gov_event_filter.currentData() or "all")
            workspace = str(self._gov_workspace_filter.currentData() or "")
            wanted_status = str(self._gov_status_filter.currentData() or "").lower()
            for table_row in range(self.table.rowCount()):
                event_item = self.table.item(table_row, 1)
                workspace_item = self.table.item(table_row, 2)
                status_item = self.table.item(table_row, 5)
                event = event_item.text() if event_item else ""
                row_workspace = workspace_item.text() if workspace_item else ""
                row_status = status_item.text() if status_item else ""
                visible = _activity_filter_match(event, row_status, category)
                if workspace and row_workspace != workspace:
                    visible = False
                if wanted_status and row_status.lower() != wanted_status:
                    visible = False
                self.table.setRowHidden(table_row, not visible)
        self._governance_apply_activity_filters = apply_filters
        self._gov_event_filter.currentIndexChanged.connect(lambda _i: apply_filters())
        self._gov_workspace_filter.currentIndexChanged.connect(lambda _i: apply_filters())
        self._gov_status_filter.currentIndexChanged.connect(lambda _i: apply_filters())

        def apply_retention_choice() -> None:
            days = int(self._gov_retention.currentData() or 0)
            if days > 0:
                answer = QMessageBox.question(
                    self,
                    "Apply local retention?",
                    f"Delete local activity metadata older than {days} days and keep this rule for future events?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            prefs.set_retention_days(days)
            deleted = prune_activity(self.controller.activity, days) if days > 0 else 0
            original_refresh(self)
            apply_filters()
            QMessageBox.information(
                self,
                "Local retention updated",
                f"Retention is now {days} days. {deleted} old event(s) were removed locally."
                if days > 0
                else "Automatic activity deletion is off. The log remains local until you clear it or choose a retention period.",
            )
        apply_retention.clicked.connect(apply_retention_choice)
        self.refresh()

    def refresh(self: ActivityDialog) -> None:
        original_refresh(self)
        combo = getattr(self, "_gov_workspace_filter", None)
        if combo is not None:
            selected = str(combo.currentData() or "")
            workspaces = sorted(
                {
                    self.table.item(row, 2).text()
                    for row in range(self.table.rowCount())
                    if self.table.item(row, 2) is not None and self.table.item(row, 2).text()
                }
            )
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All workspaces", "")
            for workspace in workspaces:
                combo.addItem(workspace, workspace)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)
        result = verify_activity_integrity(self.controller.activity)
        badge = getattr(self, "_gov_integrity", None)
        if badge is not None:
            if result.ok:
                badge.setText(f"LOG VERIFIED · {result.chained_events}")
                badge.setStyleSheet(
                    "background:#EAF7EF;color:#23824B;border:1px solid #BFE4CD;"
                    "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
                )
            else:
                badge.setText("LOG INTEGRITY WARNING")
                badge.setStyleSheet(
                    "background:#FDECEC;color:#B54747;border:1px solid #F1C1C1;"
                    "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
                )
            badge.setToolTip(result.message)
        apply_filters = getattr(self, "_governance_apply_activity_filters", None)
        if callable(apply_filters):
            apply_filters()

    ActivityDialog.__init__ = init
    ActivityDialog.refresh = refresh


# Centralized Preflight risk -----------------------------------------------------------

def _set_risk_widgets(dialog, risk) -> None:
    title = getattr(dialog, "_gov_risk_title", None)
    reason = getattr(dialog, "_gov_risk_reason", None)
    frame = getattr(dialog, "_gov_risk_frame", None)
    if title is None or reason is None or frame is None:
        return
    bg, fg, border = {
        PrivacyRiskLevel.LOW: ("#EAF7EF", "#23824B", "#BFE4CD"),
        PrivacyRiskLevel.MEDIUM: ("#FFF5E5", "#A56A00", "#F0D3A0"),
        PrivacyRiskLevel.HIGH: ("#FDECEC", "#B54747", "#F1C1C1"),
    }[risk.level]
    frame.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {border};border-radius:10px;}}")
    title.setText(f"PRIVACY RISK · {risk.level.label} · {risk.score}/100")
    title.setStyleSheet(f"color:{fg};font-size:10px;font-weight:950;")
    reason.setText(risk.reason)
    reason.setStyleSheet(f"color:{INK};font-size:9px;")
    dialog._gov_risk_assessment = risk


def _install_preflight_risk() -> None:
    global _PREFLIGHT_PATCHED
    if _PREFLIGHT_PATCHED:
        return
    _PREFLIGHT_PATCHED = True
    original_init = PrivacyPreflightDialog.__init__

    def init(self: PrivacyPreflightDialog, snapshot, parent=None) -> None:
        original_init(self, snapshot, parent)
        risk = evaluate_privacy_risk(
            detected=snapshot.detected,
            protected=snapshot.protected,
            allowed=snapshot.allowed,
            residual=snapshot.residual,
        )
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 9, 12, 9)
        copy = QVBoxLayout()
        title = QLabel()
        reason = QLabel()
        reason.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(reason)
        layout.addLayout(copy, 1)
        self._gov_risk_frame = frame
        self._gov_risk_title = title
        self._gov_risk_reason = reason
        _set_risk_widgets(self, risk)
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(2, frame)
    PrivacyPreflightDialog.__init__ = init

    try:
        from ai_pm_lab_privacy_gate.ui.business_foundation import CompanyPrivacyPreflightDialog
    except Exception:
        return
    company_original = CompanyPrivacyPreflightDialog.__init__

    def company_init(self, snapshot, policy, evaluation, parent=None) -> None:
        company_original(self, snapshot, policy, evaluation, parent)
        risk = evaluate_privacy_risk(
            detected=snapshot.detected,
            protected=snapshot.protected,
            allowed=snapshot.allowed,
            residual=snapshot.residual,
            destination_allowed=evaluation.destination_allowed,
            policy_required_total=evaluation.required_total,
            policy_required_protected=evaluation.required_protected,
            policy_required_residual=evaluation.required_residual,
        )
        _set_risk_widgets(self, risk)
    CompanyPrivacyPreflightDialog.__init__ = company_init


# Library governance metadata + restore integrity -------------------------------------

def _install_library_repository_patch() -> None:
    global _LIBRARY_PATCHED
    if _LIBRARY_PATCHED:
        return
    _LIBRARY_PATCHED = True
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    original_save = LibraryRepository.save

    def save(self, *args, **kwargs):
        document = original_save(self, *args, **kwargs)
        provider = getattr(self, "_privacygate_governance_context_provider", None)
        context = provider() if callable(provider) else {}
        try:
            DocumentGovernanceRepository(self).capture(
                document.document_id,
                workspace_key=str(context.get("key") or "personal"),
                workspace_name=str(context.get("name") or "Personal"),
                policy_version=int(context.get("policy_version") or 0),
                provenance_scope="local-only",
                integrity_origin="captured",
            )
        except Exception:
            pass
        return document
    LibraryRepository.save = save


def _install_library_context(main_window) -> None:
    _install_library_repository_patch()
    main_window.library._privacygate_governance_context_provider = lambda: _workspace_snapshot(main_window)
    page = getattr(main_window, "library_page", None)
    if page is None or bool(getattr(page, "_privacygate_governance_detail", False)):
        return
    page._privacygate_governance_detail = True
    repository = DocumentGovernanceRepository(main_window.library)
    source_repository = DocumentSourceMetadataRepository(main_window.library.db_path)
    header = getattr(page, "_library_detail_header", None)
    if header is None or header.layout() is None:
        return
    info = QVBoxLayout()
    info.setSpacing(3)
    page._gov_library_source = QLabel("Source · —")
    page._gov_library_protection = QLabel("Protected · —")
    page._gov_library_profile = QLabel("Profile · —")
    page._gov_library_workspace = _chip("WORKSPACE · —", "neutral")
    page._gov_library_integrity = _chip("INTEGRITY · —", "neutral")
    for label in (page._gov_library_source, page._gov_library_protection, page._gov_library_profile):
        label.setStyleSheet(f"color:{MUTED};font-size:8px;")
        info.addWidget(label)
    chips = QHBoxLayout()
    chips.setSpacing(5)
    chips.addWidget(page._gov_library_workspace)
    chips.addWidget(page._gov_library_integrity)
    info.addLayout(chips)
    header.layout().addLayout(info)

    def refresh_detail() -> None:
        document = page._current()
        if document is None:
            page._gov_library_source.setText("Source · —")
            page._gov_library_protection.setText("Protected · —")
            page._gov_library_profile.setText("Profile · —")
            page._gov_library_workspace.setText("WORKSPACE · —")
            page._gov_library_integrity.setText("INTEGRITY · —")
            return
        try:
            source = source_repository.get(document.document_id)
        except Exception:
            source = None
        if source is not None:
            source_text = source.provider_label or source.provider
            if source.account_label:
                source_text += f" · {source.account_label}"
        else:
            source_text = document.source_name or "Local / pasted"
        page._gov_library_source.setText(f"Original source · {source_text} · provenance local only")
        page._gov_library_protection.setText(
            f"Protected · {document.created_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
        )
        page._gov_library_profile.setText(f"Profile · {document.profile_key.replace('_', ' ').title()}")
        try:
            metadata = repository.ensure_baseline(document.document_id)
            check = repository.verify(document.document_id)
        except Exception as error:
            metadata = None
            check = None
            page._gov_library_integrity.setText("INTEGRITY · ERROR")
            page._gov_library_integrity.setToolTip(str(error))
        if metadata is not None:
            policy = f" · Policy v{metadata.policy_version}" if metadata.policy_version else ""
            page._gov_library_workspace.setText(f"WORKSPACE · {metadata.workspace_name}{policy} · LOCAL")
            page._gov_library_workspace.setStyleSheet(
                "background:#EAF6F6;color:#0B7180;border:1px solid #BFE0E2;"
                "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
            )
        if check is not None:
            if check.ok and check.status == "verified":
                page._gov_library_integrity.setText("INTEGRITY · VERIFIED")
                page._gov_library_integrity.setStyleSheet(
                    "background:#EAF7EF;color:#23824B;border:1px solid #BFE4CD;"
                    "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
                )
            elif check.ok:
                page._gov_library_integrity.setText("INTEGRITY · LEGACY BASELINE")
                page._gov_library_integrity.setStyleSheet(
                    "background:#FFF5E5;color:#A56A00;border:1px solid #F0D3A0;"
                    "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
                )
            else:
                page._gov_library_integrity.setText("INTEGRITY · FAILED")
                page._gov_library_integrity.setStyleSheet(
                    "background:#FDECEC;color:#B54747;border:1px solid #F1C1C1;"
                    "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
                )
            page._gov_library_integrity.setToolTip(check.message)
    page.table.itemSelectionChanged.connect(refresh_detail)
    page.refresh_button.clicked.connect(lambda _checked=False: refresh_detail())
    refresh_detail()


def _install_restore_guard(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or bool(getattr(page, "_privacygate_integrity_guard", False)):
        return
    page._privacygate_integrity_guard = True
    repository = DocumentGovernanceRepository(main_window.library)
    badge = _chip("RESTORE INTEGRITY · SELECT A DOCUMENT", "neutral")
    parent = page.library_status.parentWidget()
    if parent is not None and parent.layout() is not None:
        parent.layout().addWidget(badge)
    page._gov_restore_integrity = badge

    def refresh_guard() -> bool:
        document_id = page.document_combo.currentData()
        if not document_id:
            badge.setText("RESTORE INTEGRITY · SELECT A DOCUMENT")
            return True
        try:
            result = repository.verify(str(document_id))
        except Exception as error:
            badge.setText("RESTORE INTEGRITY · ERROR")
            badge.setToolTip(str(error))
            page.restore_button.setEnabled(False)
            return False
        badge.setToolTip(result.message)
        if result.ok and result.status == "verified":
            badge.setText("RESTORE INTEGRITY · VERIFIED")
            badge.setStyleSheet(
                "background:#EAF7EF;color:#23824B;border:1px solid #BFE4CD;"
                "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
            )
            return True
        if result.ok:
            badge.setText("RESTORE INTEGRITY · LEGACY BASELINE")
            badge.setStyleSheet(
                "background:#FFF5E5;color:#A56A00;border:1px solid #F0D3A0;"
                "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
            )
            return True
        badge.setText("RESTORE INTEGRITY · FAILED · RESTORE BLOCKED")
        badge.setStyleSheet(
            "background:#FDECEC;color:#B54747;border:1px solid #F1C1C1;"
            "border-radius:8px;padding:4px 8px;font-size:8px;font-weight:900;"
        )
        page.restore_button.setEnabled(False)
        return False

    original_restore = page._restore
    try:
        page.restore_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    def guarded_restore(_checked=False) -> None:
        if not refresh_guard():
            QMessageBox.critical(
                page,
                "Restore blocked by local integrity check",
                badge.toolTip() or "The protected copy or encrypted restore mapping does not match its recorded local integrity hash.",
            )
            return
        original_restore()
    page.restore_button.clicked.connect(guarded_restore)
    page.document_combo.currentIndexChanged.connect(lambda _i: refresh_guard())
    page.input_text.textChanged.connect(refresh_guard)
    refresh_guard()


# Policy editor, history, compare and non-destructive rollback ------------------------

def _style_policy_combo(combo: QComboBox) -> None:
    value = str(combo.currentData() or "")
    palette = {
        ProtectionDirective.REQUIRED_PROTECT.value: ("#FDECEC", "#9B3535", "#F1C1C1"),
        ProtectionDirective.DEFAULT_PROTECT.value: ("#EAF6F6", "#0B7180", "#BFE0E2"),
        ProtectionDirective.USER_CHOICE.value: ("#F1F5F7", "#526B7C", "#D7E2EA"),
        ProtectionDirective.ALLOW.value: ("#EAF7EF", "#23824B", "#BFE4CD"),
    }
    bg, fg, border = palette.get(value, palette[ProtectionDirective.USER_CHOICE.value])
    combo.setStyleSheet(
        f"QComboBox{{background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
        "padding:6px 9px;font-size:9px;font-weight:850;}QComboBox::drop-down{border:none;width:24px;}"
    )


def _install_policy_editor() -> None:
    global _POLICY_EDITOR_PATCHED
    if _POLICY_EDITOR_PATCHED:
        return
    _POLICY_EDITOR_PATCHED = True
    team_page_module._RULE_LABELS.update(_EXTRA_POLICY_RULES)
    original_init = PolicyEditorDialog.__init__
    def init(self: PolicyEditorDialog, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return
        legend = _card()
        row = QHBoxLayout(legend)
        row.setContentsMargins(10, 8, 10, 8)
        row.addWidget(QLabel("Policy meaning"))
        for text, tone in (
            ("Required · cannot be bypassed", "red"),
            ("Default · employee may change", "teal"),
            ("User choice", "neutral"),
            ("Allowed visible", "green"),
        ):
            row.addWidget(_chip(text, tone))
        row.addStretch(1)
        root.insertWidget(max(0, root.indexOf(self.rules_table)), legend)
        for entity_type, combo in self.rule_combos.items():
            _style_policy_combo(combo)
            combo.currentIndexChanged.connect(lambda _i, target=combo: _style_policy_combo(target))
            for row_index in range(self.rules_table.rowCount()):
                item = self.rules_table.item(row_index, 0)
                if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == entity_type:
                    item.setToolTip(
                        _POLICY_RULE_HELP.get(
                            entity_type,
                            "Choose how the managed workspace should handle this detected category.",
                        )
                    )
                    break
    PolicyEditorDialog.__init__ = init


class PolicyCompareDialog(QDialog):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare policy versions")
        self.resize(780, 600)
        root = QVBoxLayout(self)
        title = QLabel("Policy changes")
        title.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
        note = QLabel("Comparison uses policy metadata only. No document or employee activity data is included.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};")
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D7E2EA;"
            "border-radius:10px;padding:10px;font-family:Consolas,monospace;}"
        )
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        root.addWidget(title)
        root.addWidget(note)
        root.addWidget(view, 1)
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)


def _policy_diff(selected: Mapping[str, object], active: CompanyPolicy) -> str:
    lines: list[str] = []
    active_ai = dict(active.allowed_ai)
    selected_ai = dict(selected.get("allowed_ai") or {})
    for key in sorted(set(active_ai) | set(selected_ai)):
        old, new = bool(selected_ai.get(key, False)), bool(active_ai.get(key, False))
        if old != new:
            lines.append(f"AI · {key}: selected={old} → active={new}")
    active_apps = dict(active.allowed_connectors)
    selected_apps = dict(selected.get("allowed_connectors") or {})
    for key in sorted(set(active_apps) | set(selected_apps)):
        old, new = bool(selected_apps.get(key, False)), bool(active_apps.get(key, False))
        if old != new:
            lines.append(f"APP · {key}: selected={old} → active={new}")
    active_rules = {key: value.value for key, value in active.protection_rules.items()}
    selected_rules = {str(key): str(value) for key, value in dict(selected.get("protection_rules") or {}).items()}
    for key in sorted(set(active_rules) | set(selected_rules)):
        old, new = selected_rules.get(key, "user_choice"), active_rules.get(key, "user_choice")
        if old != new:
            lines.append(f"RULE · {key}: selected={old} → active={new}")
    return "\n".join(lines) or "No policy-control differences between the selected version and the active version."


class PolicyHistoryDialog(QDialog):
    def __init__(self, page: TeamPage, rows: list[dict[str, object]]) -> None:
        super().__init__(page)
        self.page = page
        self.rows = rows
        self.setWindowTitle("Company policy history")
        self.resize(920, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)
        title = QLabel("Company policy history")
        title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:950;")
        note = QLabel(
            "Versions are immutable. Restoring an older policy publishes its controls as a new version, preserving history."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};")
        root.addWidget(title)
        root.addWidget(note)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Version", "Created", "Policy hash", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        active_version = int(getattr(page.state.policy, "version", 0) or 0) if page.state.policy else 0
        self.table.setRowCount(len(rows))
        for index, item in enumerate(rows):
            version = int(item.get("version") or 0)
            created = str(item.get("created_at") or "").replace("T", " ")[:19]
            digest = str(item.get("policy_sha256") or "")
            values = (
                f"v{version}", created or "—",
                digest[:24] + ("…" if len(digest) > 24 else ""),
                "ACTIVE" if version == active_version else "Historical",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, index)
                self.table.setItem(index, column, cell)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        compare = QPushButton("Compare with active")
        restore = QPushButton("Restore as new version")
        close = QPushButton("Close")
        actions.addWidget(compare)
        actions.addWidget(restore)
        actions.addStretch(1)
        actions.addWidget(close)
        root.addLayout(actions)
        compare.clicked.connect(self._compare)
        restore.clicked.connect(self._restore)
        close.clicked.connect(self.reject)
        if rows:
            self.table.selectRow(0)

    def _selected(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        index = int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else row
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def _compare(self) -> None:
        selected, active = self._selected(), self.page.state.policy
        if selected is None or active is None or not isinstance(selected.get("policy_json"), Mapping):
            return
        PolicyCompareDialog(_policy_diff(selected["policy_json"], active), self).exec()

    def _restore(self) -> None:
        selected, active = self._selected(), self.page.state.policy
        if selected is None or active is None:
            return
        version = int(selected.get("version") or 0)
        if version == active.version:
            QMessageBox.information(self, "Policy history", "That version is already active.")
            return
        policy_json = selected.get("policy_json")
        if not isinstance(policy_json, Mapping):
            return
        answer = QMessageBox.question(
            self,
            "Restore historical controls?",
            f"Publish the controls from v{version} as a new immutable policy version? The existing history will be preserved.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        payload = dict(policy_json)
        payload.update(
            {
                "organization_id": active.organization_id,
                "organization_name": active.organization_name,
                "version": active.version,
                "plan": active.plan.value,
                "policy_name": active.policy_name,
                "issued_at": active.issued_at,
            }
        )
        restored = CompanyPolicy.from_dict(payload)
        self.accept()
        self.page._run_team_action(
            lambda session: self.page.team_client.publish_policy(session, restored),
            success_message=f"Policy controls from v{version} were published as a new version.",
            refresh_after=True,
        )


def _install_policy_history(main_window) -> None:
    from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import SupabaseTeamClient
    if not hasattr(SupabaseTeamClient, "list_policy_versions"):
        def list_policy_versions(self, session, organization_id: str):
            payload = self._request(
                "GET", "/rest/v1/privacy_gate_policy_versions", session,
                params={
                    "organization_id": f"eq.{organization_id}",
                    "select": "version,policy_json,policy_sha256,created_at,created_by",
                    "order": "version.desc", "limit": "100",
                },
            )
            return [dict(row) for row in payload] if isinstance(payload, list) else []
        SupabaseTeamClient.list_policy_versions = list_policy_versions  # type: ignore[attr-defined]
    page = getattr(main_window, "team_page", None)
    if page is None or bool(getattr(page, "_privacygate_policy_history", False)):
        return
    page._privacygate_policy_history = True
    button = QPushButton("Policy history")
    button.setToolTip("Compare policy versions or republish an older version as a new immutable version.")
    layout = _find_layout_containing(page.layout(), page.edit_policy_button)
    if layout is not None:
        layout.insertWidget(layout.indexOf(page.edit_policy_button) + 1, button)
    def open_history() -> None:
        if not page.state.organization_id or page.state.role not in {"owner", "admin"}:
            return
        page._run_team_action(
            lambda session: page.team_client.list_policy_versions(session, page.state.organization_id),
            result_handler=lambda rows: PolicyHistoryDialog(page, list(rows or [])).exec(),
            refresh_after=False,
        )
    button.clicked.connect(open_history)
    def visibility(_state=None) -> None:
        button.setVisible(bool(page.state.organization_id and page.state.role in {"owner", "admin"}))
    page.state_changed.connect(visibility)
    visibility()


# Organization compliance + local admin audit -----------------------------------------

def _install_organization_compliance(main_window, controller) -> None:
    page = getattr(main_window, "team_page", None)
    sections = getattr(page, "sections", None) if page is not None else None
    if page is None or sections is None or bool(getattr(page, "_privacygate_compliance_strip", False)):
        return
    overview = sections.widget(0) if sections.count() else None
    layout = overview.layout() if overview is not None else None
    if not isinstance(layout, QVBoxLayout):
        return
    page._privacygate_compliance_strip = True
    frame = _card()
    root = QVBoxLayout(frame)
    root.setContentsMargins(13, 10, 13, 10)
    top = QHBoxLayout()
    heading = QLabel("Compliance status")
    heading.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:950;")
    top.addWidget(heading)
    top.addStretch(1)
    top.addWidget(_chip("METADATA ONLY · LOCAL ADMIN AUDIT", "teal"))
    root.addLayout(top)
    metrics = QGridLayout()
    page._gov_policy_status = QLabel("—")
    page._gov_device_status = QLabel("—")
    page._gov_member_status = QLabel("—")
    page._gov_alert_status = QLabel("—")
    for column, (label, value) in enumerate(
        (
            ("Policy compliance", page._gov_policy_status),
            ("Devices compliant", page._gov_device_status),
            ("Members", page._gov_member_status),
            ("Alerts", page._gov_alert_status),
        )
    ):
        box = QFrame()
        box.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E1E8ED;border-radius:9px;}")
        col = QVBoxLayout(box)
        col.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(label.upper())
        caption.setStyleSheet(f"color:{MUTED};font-size:7px;font-weight:900;")
        value.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:950;")
        col.addWidget(caption)
        col.addWidget(value)
        metrics.addWidget(box, 0, column)
    root.addLayout(metrics)
    page._gov_alert_detail = QLabel()
    page._gov_alert_detail.setWordWrap(True)
    page._gov_alert_detail.setStyleSheet(f"color:{MUTED};font-size:8px;")
    root.addWidget(page._gov_alert_detail)
    layout.insertWidget(1, frame)

    def update(_state=None) -> None:
        state, policy = page.state, page.state.policy
        active_members = [row for row in page._members if str(row.get("status") or "") == "active"]
        active_devices = [row for row in page._devices if str(row.get("status") or "") == "active"]
        synced = [
            row for row in active_devices
            if policy is not None and int(row.get("last_policy_version") or 0) == int(policy.version)
        ]
        out_of_sync = max(0, len(active_devices) - len(synced))
        restricted = [row for row in page._devices if str(row.get("status") or "") in {"disabled", "revoked"}]
        alerts = out_of_sync + len(restricted) + (0 if policy else 1)
        page._gov_policy_status.setText(f"v{policy.version} active" if policy else "Needs attention")
        if state.role in {"owner", "admin", "manager"}:
            page._gov_device_status.setText(f"{len(synced)} / {len(active_devices)}")
            page._gov_member_status.setText(f"{len(active_members)} / {len(page._members)}")
        else:
            page._gov_device_status.setText("This device")
            page._gov_member_status.setText("Private")
        page._gov_alert_status.setText(str(alerts))
        details: list[str] = []
        if not policy:
            details.append("company policy unavailable")
        if out_of_sync:
            details.append(f"{out_of_sync} active device(s) need the current policy")
        if restricted:
            details.append(f"{len(restricted)} disabled/revoked endpoint(s)")
        page._gov_alert_detail.setText(
            "No compliance alerts in the currently synced metadata." if not details else " · ".join(details)
        )
    page.state_changed.connect(update)
    update()

    def snapshot() -> dict[str, object]:
        policy = page.state.policy
        members = {
            str(row.get("user_id") or ""): (str(row.get("role") or "member"), str(row.get("status") or "active"))
            for row in page._members if str(row.get("user_id") or "")
        }
        devices = {
            str(row.get("installation_hash") or ""): (str(row.get("status") or "active"), int(row.get("last_policy_version") or 0))
            for row in page._devices if str(row.get("installation_hash") or "")
        }
        return {"policy": int(policy.version) if policy else 0, "members": members, "devices": devices}
    page._privacygate_admin_audit_snapshot = snapshot()

    def audit(_state=None) -> None:
        before = dict(getattr(page, "_privacygate_admin_audit_snapshot", {}) or {})
        after = snapshot()
        workspace = _workspace_snapshot(main_window)
        policy_version, before_policy = int(after.get("policy") or 0), int(before.get("policy") or 0)
        if before_policy and policy_version and before_policy != policy_version:
            controller.activity.record(
                "organization_policy_changed",
                workspace_key=str(workspace.get("key") or "personal"),
                source_kind="policy", status="ok",
                detail=f"Company policy version changed v{before_policy} → v{policy_version}",
                policy_version=policy_version,
                provenance_scope="admin-metadata-local-only",
            )
        before_members, after_members = dict(before.get("members") or {}), dict(after.get("members") or {})
        for key, current in after_members.items():
            previous = before_members.get(key)
            if previous and previous != current:
                change = "role" if previous[0] != current[0] else "status"
                position = 0 if change == "role" else 1
                controller.activity.record(
                    f"organization_member_{change}_changed",
                    workspace_key=str(workspace.get("key") or "personal"), source_kind="member", status="ok",
                    detail=f"Member {change} changed {previous[position]} → {current[position]}",
                    policy_version=policy_version, provenance_scope="admin-metadata-local-only",
                )
        before_devices, after_devices = dict(before.get("devices") or {}), dict(after.get("devices") or {})
        for key, current in after_devices.items():
            previous = before_devices.get(key)
            if previous and previous != current:
                if previous[0] != current[0]:
                    detail, event = f"Managed device status changed {previous[0]} → {current[0]}", "organization_device_status_changed"
                else:
                    detail, event = f"Managed device policy sync changed v{previous[1]} → v{current[1]}", "organization_device_policy_changed"
                controller.activity.record(
                    event, workspace_key=str(workspace.get("key") or "personal"), source_kind="device", status="ok",
                    detail=detail, policy_version=policy_version, provenance_scope="admin-metadata-local-only",
                )
        page._privacygate_admin_audit_snapshot = after
    page.state_changed.connect(audit)


# Workspace consent, isolation cue and connected-account UX ---------------------------

def _install_binding_dialog() -> None:
    global _BINDING_DIALOG_PATCHED
    if _BINDING_DIALOG_PATCHED:
        return
    _BINDING_DIALOG_PATCHED = True
    original_available = WorkspaceContextStore.is_account_available
    def explicit_available(self, provider: str, account_id: str, workspace_key: str) -> bool:
        context = self.load()
        explicit = context.connector_bindings.get(provider, {}).get(account_id)
        if explicit is None:
            descriptor = context.workspaces.get(workspace_key)
            return bool(descriptor is not None and descriptor.personal)
        return workspace_key in explicit
    WorkspaceContextStore.is_account_available = explicit_available
    WorkspaceContextStore._privacygate_previous_is_account_available = original_available  # type: ignore[attr-defined]

    original_init = WorkspaceBindingsDialog.__init__
    def init(self: WorkspaceBindingsDialog, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        context = self.context_store.load()
        explicit = context.connector_bindings.get(self.provider, {}).get(self.account_id)
        if explicit is None:
            for key, check in self.checks.items():
                descriptor = context.workspaces.get(key)
                check.setChecked(bool(descriptor is not None and descriptor.personal))
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return
        consent = _card()
        box = QVBoxLayout(consent)
        box.setContentsMargins(11, 9, 11, 9)
        heading = QLabel("Explicit workspace consent")
        heading.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;")
        note = QLabel(
            "Checking a company workspace allows this local account to be used there. Source provenance, document titles/content and OAuth credentials remain on this device and are not sent to Organization."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED};font-size:8px;")
        revoke = QPushButton("Revoke from all company workspaces now")
        revoke.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#B54747;border:1px solid #F1C1C1;"
            "border-radius:8px;padding:6px 10px;font-weight:850;}"
        )
        box.addWidget(heading)
        box.addWidget(note)
        box.addWidget(revoke, 0, Qt.AlignmentFlag.AlignLeft)
        root.insertWidget(max(0, root.count() - 2), consent)
        def revoke_company() -> None:
            personal = [key for key, descriptor in context.workspaces.items() if descriptor.personal]
            self.context_store.bind_account(self.provider, self.account_id, personal)
            for key, check in self.checks.items():
                descriptor = context.workspaces.get(key)
                check.setChecked(bool(descriptor is not None and descriptor.personal))
            QMessageBox.information(
                self, "Workspace access revoked",
                "This account is now available only in Personal. No OAuth credential or source content was copied or deleted.",
            )
        revoke.clicked.connect(revoke_company)
    WorkspaceBindingsDialog.__init__ = init


def _install_workspace_cues(main_window) -> None:
    page = getattr(main_window, "team_page", None)
    if page is None or bool(getattr(page, "_privacygate_governance_workspace_cue", False)):
        return
    page._privacygate_governance_workspace_cue = True
    def update_cue(*_args) -> None:
        store = getattr(page, "_privacygate_workspace_store", None)
        selector = getattr(page, "workspace_selector", None)
        note = getattr(page, "workspace_context_note", None)
        if store is None or selector is None:
            return
        try:
            context = store.load()
            descriptor = context.workspaces.get(context.active_key)
        except Exception:
            return
        if descriptor is None:
            return
        if descriptor.personal:
            selector.setStyleSheet(
                "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #AFCFD3;"
                "border-radius:9px;padding:7px 10px;font-weight:850;}"
            )
            if note is not None:
                note.setText("PERSONAL · local policy and account context")
                note.setStyleSheet(f"color:{TEAL};font-size:9px;font-weight:900;")
        else:
            selector.setStyleSheet(
                "QComboBox{background:#EAF2F7;color:#062B4F;border:2px solid #2F6F91;"
                "border-radius:9px;padding:6px 9px;font-weight:950;}"
            )
            if note is not None:
                policy = page.state.policy
                version = f" · POLICY v{policy.version}" if policy else " · POLICY UNAVAILABLE"
                note.setText(f"COMPANY WORKSPACE · {descriptor.name.upper()}{version}")
                note.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:950;")
        table = getattr(page, "workspace_accounts_table", None)
        if table is not None:
            for row in range(table.rowCount()):
                provider_item = table.item(row, 0)
                if provider_item is None:
                    continue
                provider = str(provider_item.data(Qt.ItemDataRole.UserRole) or "")
                account_id = str(provider_item.data(int(Qt.ItemDataRole.UserRole) + 1) or "")
                bindings = context.connector_bindings.get(provider, {}).get(account_id)
                if bindings is None:
                    table.setItem(row, 2, QTableWidgetItem("Personal only · company consent required"))
                available = store.is_account_available(provider, account_id, context.active_key)
                table.setItem(row, 3, QTableWidgetItem("Available" if available else "Consent required"))
    selector = getattr(page, "workspace_selector", None)
    if selector is not None:
        selector.currentIndexChanged.connect(update_cue)
    page.state_changed.connect(update_cue)
    update_cue()


# Privacy Profiles --------------------------------------------------------------------

def _install_profile_dialog() -> None:
    global _PROFILE_DIALOG_PATCHED
    if _PROFILE_DIALOG_PATCHED:
        return
    _PROFILE_DIALOG_PATCHED = True
    original_init = ProfilesDialog.__init__
    def init(self: ProfilesDialog, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return
        panel = _card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        self._gov_profile_version = QLabel("Profile specification")
        self._gov_profile_version.setStyleSheet(f"color:{TEAL};font-size:9px;font-weight:950;")
        self._gov_profile_protects = QLabel()
        self._gov_profile_protects.setWordWrap(True)
        self._gov_profile_limits = QLabel()
        self._gov_profile_limits.setWordWrap(True)
        self._gov_profile_protects.setStyleSheet(f"color:{INK};font-size:9px;")
        self._gov_profile_limits.setStyleSheet(f"color:{MUTED};font-size:8px;")
        layout.addWidget(self._gov_profile_version)
        layout.addWidget(self._gov_profile_protects)
        layout.addWidget(self._gov_profile_limits)
        root.insertWidget(max(1, root.count() - 1), panel)
        def update() -> None:
            row = self.table.currentRow()
            if row < 0:
                return
            item = self.table.item(row, 0)
            if item is None:
                return
            key = str(item.data(Qt.ItemDataRole.UserRole) or "")
            try:
                from ai_pm_lab_privacy_gate.application.feature_suite import AdvancedProfileCatalog
                selected = AdvancedProfileCatalog.get(key)
            except Exception:
                return
            self._gov_profile_version.setText(
                f"PROFILE SPEC · {PROFILE_SPEC_VERSION} · FINGERPRINT {profile_fingerprint(selected)}"
            )
            self._gov_profile_protects.setText(
                f"Protects · {len(set(selected.entities))} configured detector categories for {selected.name}."
            )
            self._gov_profile_limits.setText(
                "Does not guarantee every sensitive value. Healthcare — General Privacy is not a specialized clinical/HIPAA recognizer pack."
                if key == "healthcare_general"
                else "Does not guarantee every sensitive value. Custom/company rules and the second local scan remain part of the protection workflow."
            )
        self.table.itemSelectionChanged.connect(update)
        if self.table.rowCount() and self.table.currentRow() < 0:
            self.table.selectRow(0)
        update()
    ProfilesDialog.__init__ = init


# Unified enforcement -----------------------------------------------------------------

def _install_unified_enforcement(main_window, controller) -> None:
    global _ENFORCEMENT_PATCHED
    if _ENFORCEMENT_PATCHED:
        return
    _ENFORCEMENT_PATCHED = True
    original_handoff = ProtectionPage._privacygate_ai_handoff
    def handoff(self: ProtectionPage, destination_key: str) -> None:
        destination = get_ai_destination(destination_key)
        workspace = controller.active_workspace_key()
        engine = _engine_for_page(self)
        decision = UnifiedEnforcementEngine.ai(
            destination=destination.key,
            workspace_key=workspace,
            policy_allows=engine.can_use_ai,
            rule_allows=controller.rules.allows,
            managed_required=engine.managed_required,
            policy_available=engine.policy is not None or not engine.managed_required,
            organization_name=engine.organization_name,
            unavailable_reason=engine.unavailable_reason,
        )
        if not decision.allowed:
            context = _workspace_snapshot(main_window)
            result = getattr(self, "current_result", None)
            controller.activity.record(
                "ai_handoff_blocked", workspace_key=workspace, source_kind="protected", status="blocked",
                detail=decision.reason, ai_destination=destination.label,
                policy_version=int(context.get("policy_version") or 0), risk_level="high",
                protection_mode=str(getattr(result, "replacement_mode", "") or ""), provenance_scope="local-only",
            )
            QMessageBox.warning(self, "AI handoff blocked", decision.reason)
            return
        original_handoff(self, destination_key)
    ProtectionPage._privacygate_ai_handoff = handoff

    from ai_pm_lab_privacy_gate.ui import apps_hub
    current_connect, current_browse = apps_hub.AppsHubPage._connect, apps_hub.AppsHubPage._browse
    def connector_decision(page, provider: str):
        engine = _engine_for_apps(page)
        return UnifiedEnforcementEngine.connector(
            provider=provider, workspace_key=controller.active_workspace_key(),
            policy_allows=engine.can_use_connector,
            organization_name=engine.organization_name, unavailable_reason=engine.unavailable_reason,
        )
    def app_connect(self, provider, title, supported, integration_path) -> None:
        decision = connector_decision(self, provider)
        if not decision.allowed:
            QMessageBox.information(self, "Connector blocked", decision.reason)
            return
        current_connect(self, provider, title, supported, integration_path)
    def app_browse(self, provider, title, supported) -> None:
        decision = connector_decision(self, provider)
        if not decision.allowed:
            QMessageBox.information(self, "Connector blocked", decision.reason)
            return
        current_browse(self, provider, title, supported)
    apps_hub.AppsHubPage._connect = app_connect
    apps_hub.AppsHubPage._browse = app_browse

    original_automation = AutomationActionService.trigger_n8n
    def trigger_n8n(self, plan, url, payload=None, *, workspace_key="personal"):
        rules = getattr(self, "_privacygate_governance_rules", None)
        decision = UnifiedEnforcementEngine.automation(
            target="n8n", workspace_key=workspace_key,
            rule_allows=rules.allows if rules is not None else None,
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return original_automation(self, plan, url, payload, workspace_key=workspace_key)
    AutomationActionService.trigger_n8n = trigger_n8n
    controller.automation._privacygate_governance_rules = controller.rules


# Public installer --------------------------------------------------------------------

def apply_governance_hardening_2026(main_window) -> None:
    """Add privacy/governance hardening without replacing existing product flows."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    install_activity_hardening()
    controller = getattr(main_window, "privacygate_feature_suite", None)
    if controller is not None:
        ensure_activity_schema(controller.activity)
    _install_preflight_risk()
    _install_activity_dialog()
    _install_policy_editor()
    _install_binding_dialog()
    _install_profile_dialog()
    _install_library_context(main_window)
    _install_restore_guard(main_window)
    _install_policy_history(main_window)
    _install_workspace_cues(main_window)
    if controller is not None:
        _install_organization_compliance(main_window, controller)
        _install_unified_enforcement(main_window, controller)
