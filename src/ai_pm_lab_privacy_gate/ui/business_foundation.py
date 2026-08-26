from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.domain.company_policy import (
    CompanyPolicy,
    PolicyEngine,
    PolicyEvaluation,
    ProtectionDirective,
)
from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import (
    PolicyCacheError,
    SecureTeamStateStore,
)
from ai_pm_lab_privacy_gate.ui import apps_hub
from ai_pm_lab_privacy_gate.ui.automatic_temp_cleanup import (
    cleanup_after_completed_save,
    prepare_managed_save,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.privacy_preflight import (
    PrivacyPreflightDialog,
    _run_second_scan,
    _status_message,
    build_preflight_snapshot,
    get_ai_destination,
)
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False
_NAVY = "#062B4F"
_TEAL = "#0B7180"
_GREEN = "#23824B"


def _engine_from_data_dir(data_dir) -> PolicyEngine:
    try:
        state = SecureTeamStateStore(data_dir).load()
    except PolicyCacheError as error:
        return PolicyEngine.unavailable(str(error))
    return PolicyEngine(state.policy)


def _engine_for_page(page: ProtectionPage) -> PolicyEngine:
    engine = getattr(page, "_privacygate_company_policy_engine", None)
    if isinstance(engine, PolicyEngine):
        return engine
    data_dir = getattr(getattr(page, "library", None), "data_dir", None)
    engine = _engine_from_data_dir(data_dir) if data_dir else PolicyEngine()
    page._privacygate_company_policy_engine = engine
    return engine


def _engine_for_apps(page) -> PolicyEngine:
    main_window = getattr(page, "main_window", None)
    data_dir = getattr(getattr(main_window, "library", None), "data_dir", None)
    return _engine_from_data_dir(data_dir) if data_dir else PolicyEngine()


def _finding_for_row(page: ProtectionPage, row: int):
    if row < 0 or row >= page.findings_table.rowCount():
        return None
    checkbox = page.findings_table.item(row, 0)
    if checkbox is None:
        return None
    finding_id = str(checkbox.data(Qt.ItemDataRole.UserRole) or "")
    return next(
        (
            finding
            for finding in page.current_findings
            if str(getattr(finding, "finding_id", "") or "") == finding_id
        ),
        None,
    )


def _apply_company_rules(page: ProtectionPage, *, initialize: bool = False) -> bool:
    engine = _engine_for_page(page)
    changed = False
    page.findings_table.blockSignals(True)
    try:
        for row in range(page.findings_table.rowCount()):
            checkbox = page.findings_table.item(row, 0)
            finding = _finding_for_row(page, row)
            if checkbox is None or finding is None:
                continue
            entity_type = str(getattr(finding, "entity_type", "") or "").upper()
            directive = engine.directive_for(entity_type)

            checkbox.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
            )
            checkbox.setToolTip("")
            if engine.active and directive is ProtectionDirective.REQUIRED_PROTECT:
                if checkbox.checkState() != Qt.CheckState.Checked:
                    checkbox.setCheckState(Qt.CheckState.Checked)
                    changed = True
                checkbox.setFlags(Qt.ItemFlag.ItemIsEnabled)
                checkbox.setToolTip(
                    f"Company required — {engine.organization_name} requires this "
                    "category to be protected."
                )
            elif initialize and engine.active:
                desired = None
                if directive is ProtectionDirective.DEFAULT_PROTECT:
                    desired = Qt.CheckState.Checked
                elif directive is ProtectionDirective.ALLOW:
                    desired = Qt.CheckState.Unchecked
                if desired is not None and checkbox.checkState() != desired:
                    checkbox.setCheckState(desired)
                    changed = True
    finally:
        page.findings_table.blockSignals(False)

    category_list = getattr(page, "category_list", None)
    if category_list is not None:
        page._category_sync = True
        try:
            for index in range(category_list.count()):
                item = category_list.item(index)
                entity_type = str(
                    item.data(Qt.ItemDataRole.UserRole) or ""
                ).upper()
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setToolTip("")
                if engine.active and engine.must_protect(entity_type):
                    item.setCheckState(Qt.CheckState.Checked)
                    item.setFlags(
                        (item.flags() | Qt.ItemFlag.ItemIsEnabled)
                        & ~Qt.ItemFlag.ItemIsUserCheckable
                    )
                    item.setToolTip(
                        f"Company required — {engine.organization_name}."
                    )
        finally:
            page._category_sync = False
        page._sync_category_check_states()
    return changed


class CompanyPrivacyPreflightDialog(PrivacyPreflightDialog):
    def __init__(
        self,
        snapshot,
        policy: CompanyPolicy,
        evaluation: PolicyEvaluation,
        parent=None,
    ) -> None:
        super().__init__(snapshot, parent)
        self.setWindowTitle("AI Privacy Preflight — Company Policy")

        banner = QFrame()
        banner.setStyleSheet(
            "QFrame{background:#EDF8F4;border:1px solid #B9DECD;border-radius:10px;}"
        )
        layout = QVBoxLayout(banner)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        company = QLabel(policy.organization_name)
        company.setStyleSheet(f"color:{_NAVY};font-size:12px;font-weight:950;")
        plan = QLabel(
            f"{policy.plan.label} • Policy v{policy.version} • ACTIVE"
        )
        plan.setStyleSheet("color:#61798A;font-size:9px;font-weight:800;")
        top.addWidget(company)
        top.addStretch(1)
        top.addWidget(plan)
        layout.addLayout(top)

        requirements = QLabel(
            f"Company requirements: {evaluation.required_protected}/"
            f"{evaluation.required_total} mandatory findings protected • "
            f"{evaluation.required_residual} mandatory residual findings"
        )
        requirements.setStyleSheet("color:#17384E;font-size:9px;")
        layout.addWidget(requirements)

        passed = QLabel("✓ COMPANY POLICY PASSED")
        passed.setStyleSheet(f"color:{_GREEN};font-size:10px;font-weight:950;")
        layout.addWidget(passed)

        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(1, banner)


def _company_handoff(page: ProtectionPage, destination_key: str) -> None:
    if not page.current_result:
        return

    destination = get_ai_destination(destination_key)
    engine = _engine_for_page(page)
    if not engine.can_use_ai(destination.key):
        organization = engine.organization_name or "your company"
        detail = (
            engine.unavailable_reason
            if engine.managed_required and not engine.policy
            else f"{destination.label} is disabled by {organization} policy."
        )
        QMessageBox.warning(
            page,
            "Blocked by company policy",
            detail,
        )
        return

    residual = _run_second_scan(page)
    selected_ids = {
        str(getattr(finding, "finding_id", "") or "")
        for finding in page._selected_findings()
    }
    evaluation = engine.evaluate(
        page.current_findings,
        selected_ids,
        destination=destination.key,
        residual_findings=residual,
    )
    if not evaluation.allowed:
        organization = engine.organization_name or "Company"
        QMessageBox.warning(
            page,
            f"Blocked by {organization} policy",
            "\n".join(evaluation.violations),
        )
        return

    snapshot = build_preflight_snapshot(
        page,
        destination=destination.label,
        delivery=destination.delivery,
        residual_findings=residual,
    )
    if engine.active and engine.policy is not None:
        dialog = CompanyPrivacyPreflightDialog(
            snapshot, engine.policy, evaluation, page
        )
    else:
        dialog = PrivacyPreflightDialog(snapshot, page)
    if dialog.exec() != PrivacyPreflightDialog.DialogCode.Accepted:
        return

    prepare_managed_save(page)
    document = page._save_to_library()
    if document is None:
        return
    page._managed_temp_saved_ok = True
    QApplication.clipboard().setText(page.current_result.combined_text)
    if destination.url:
        QDesktopServices.openUrl(QUrl(destination.url))
    cleanup_after_completed_save(page)
    _status_message(page, destination, document.title)


def _business_ai_menu(page: ProtectionPage):
    from PySide6.QtWidgets import QMenu

    engine = _engine_for_page(page)
    menu = QMenu(page)
    menu.addSection("AI destination")

    for key, label, icon_key in (
        ("chatgpt", "ChatGPT / GPT", "external"),
        ("claude", "Claude", "external"),
        ("other", "Other AI tool", "copy"),
    ):
        allowed = engine.can_use_ai(key)
        action_label = label
        if (engine.active or engine.managed_required) and not allowed:
            owner = engine.organization_name or "company"
            action_label = f"{label} — Blocked by {owner} policy"
        action = menu.addAction(
            icon(icon_key, color=_TEAL, size=17),
            action_label,
        )
        action.setEnabled(allowed)
        if allowed:
            action.triggered.connect(
                lambda _checked=False, destination=key: page._privacygate_ai_handoff(
                    destination
                )
            )
        else:
            action.setToolTip(
                engine.unavailable_reason
                or "This AI destination is disabled by the active company policy."
            )

    menu.addSeparator()
    connections = menu.addAction("Configure AI connections…")
    connections.triggered.connect(page.open_connections.emit)
    return menu


def _set_policy_engine(page: ProtectionPage, engine: PolicyEngine) -> None:
    page._privacygate_company_policy_engine = engine
    changed = _apply_company_rules(page)
    try:
        page.ai_button.setMenu(page._build_ai_menu())
    except Exception:
        pass
    if changed and page.current_document is not None:
        page._refresh_preview()


def install_business_foundation() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_populate = ProtectionPage._populate_findings
    original_category_changed = ProtectionPage._category_changed
    original_set_all = ProtectionPage._set_all_findings
    original_invert = ProtectionPage._invert_findings
    original_review_decision = ProtectionPage._set_reviewed_finding_protection
    original_selected = ProtectionPage._selected_findings
    original_update_context = ProtectionPage._update_review_context

    def populate(self: ProtectionPage) -> None:
        original_populate(self)
        _apply_company_rules(self, initialize=True)

    def category_changed(self: ProtectionPage, item) -> None:
        if getattr(self, "_privacygate_category_change_active", False):
            return
        self._privacygate_category_change_active = True
        try:
            _category_changed(self, item)
        finally:
            self._privacygate_category_change_active = False

    def _category_changed(self: ProtectionPage, item) -> None:
        entity_type = str(item.data(Qt.ItemDataRole.UserRole) or "")
        engine = _engine_for_page(self)
        if engine.active and engine.must_protect(entity_type):
            self._category_sync = True
            try:
                item.setCheckState(Qt.CheckState.Checked)
            finally:
                self._category_sync = False
            return
        original_category_changed(self, item)
        # A personal workspace has no policy to re-apply. Touching every item
        # here emits another itemChanged signal on some Qt versions and used to
        # cause an unbounded Protect preview refresh loop.
        if engine.active and _apply_company_rules(self):
            self._refresh_preview()

    def set_all(self: ProtectionPage, protected: bool) -> None:
        original_set_all(self, protected)
        if _apply_company_rules(self):
            self._refresh_preview()

    def invert(self: ProtectionPage) -> None:
        original_invert(self)
        if _apply_company_rules(self):
            self._refresh_preview()

    def review_decision(self: ProtectionPage, protected: bool) -> None:
        if not protected and self._reviewed_row is not None:
            finding = _finding_for_row(self, self._reviewed_row)
            if finding is not None and _engine_for_page(self).must_protect(
                str(getattr(finding, "entity_type", "") or "")
            ):
                QMessageBox.information(
                    self,
                    "Company required",
                    f"{getattr(finding, 'entity_type', 'This category')} must be "
                    "protected by the active company policy.",
                )
                return
        original_review_decision(self, protected)
        if _apply_company_rules(self):
            self._refresh_preview()

    def selected(self: ProtectionPage):
        chosen = tuple(original_selected(self))
        engine = _engine_for_page(self)
        if not engine.active:
            return chosen
        chosen_ids = {
            str(getattr(finding, "finding_id", "") or "")
            for finding in chosen
        }
        enforced_ids = engine.enforce_selected_ids(
            self.current_findings, chosen_ids
        )
        return tuple(
            finding
            for finding in self.current_findings
            if str(getattr(finding, "finding_id", "") or "") in enforced_ids
        )

    def update_context(self: ProtectionPage, row: int) -> None:
        original_update_context(self, row)
        finding = _finding_for_row(self, row)
        if finding is None:
            return
        engine = _engine_for_page(self)
        required = engine.active and engine.must_protect(
            str(getattr(finding, "entity_type", "") or "")
        )
        if required:
            self.keep_this_button.setEnabled(False)
            self.keep_this_button.setToolTip(
                f"Locked by {engine.organization_name} company policy."
            )
        else:
            self.keep_this_button.setToolTip("")

    ProtectionPage._populate_findings = populate
    ProtectionPage._category_changed = category_changed
    ProtectionPage._set_all_findings = set_all
    ProtectionPage._invert_findings = invert
    ProtectionPage._set_reviewed_finding_protection = review_decision
    ProtectionPage._selected_findings = selected
    ProtectionPage._update_review_context = update_context
    ProtectionPage._build_ai_menu = _business_ai_menu
    ProtectionPage._privacygate_ai_handoff = _company_handoff
    ProtectionPage._privacygate_set_policy_engine = _set_policy_engine

    original_app_connect = apps_hub.AppsHubPage._connect
    original_app_browse = apps_hub.AppsHubPage._browse
    original_app_refresh = apps_hub.AppsHubPage.refresh

    def connector_allowed(self, provider: str) -> bool:
        engine = _engine_for_apps(self)
        if engine.can_use_connector(provider):
            return True
        QMessageBox.information(
            self,
            "Disabled by company policy",
            engine.unavailable_reason
            or f"{provider.replace('_', ' ').title()} is disabled by "
            f"{engine.organization_name or 'your company'} policy.",
        )
        return False

    def app_connect(self, provider, title, supported, integration_path) -> None:
        if not connector_allowed(self, provider):
            return
        original_app_connect(self, provider, title, supported, integration_path)

    def app_browse(self, provider, title, supported) -> None:
        if not connector_allowed(self, provider):
            return
        original_app_browse(self, provider, title, supported)

    def app_refresh(self) -> None:
        original_app_refresh(self)
        engine = _engine_for_apps(self)
        if not (engine.active or engine.managed_required):
            return

        for status in self.findChildren(QLabel, "AppStatus"):
            provider = str(status.property("provider") or "")
            if provider and not engine.can_use_connector(provider):
                status.setText("Policy locked")
                status.setStyleSheet(
                    "background:#FDECEC;color:#9B3535;border:1px solid #F1C1C1;"
                    "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )
        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = str(button.property("provider") or "")
            if provider and not engine.can_use_connector(provider):
                button.setEnabled(False)
                button.setText("Disabled by company")
                button.setToolTip(
                    engine.unavailable_reason
                    or f"Disabled by {engine.organization_name} policy."
                )
        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = str(button.property("provider") or "")
            if provider and not engine.can_use_connector(provider):
                button.setEnabled(False)
                button.setToolTip(
                    engine.unavailable_reason
                    or f"Disabled by {engine.organization_name} policy."
                )

    apps_hub.AppsHubPage._connect = app_connect
    apps_hub.AppsHubPage._browse = app_browse
    apps_hub.AppsHubPage.refresh = app_refresh


def apply_business_main_window(main_window) -> None:
    if hasattr(main_window, "team_page"):
        return

    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QPushButton

    from ai_pm_lab_privacy_gate.ui.team_page import TeamPage

    team_page = TeamPage(
        main_window.library.data_dir,
        main_window.connection_identity,
        main_window,
    )
    team_index = main_window.pages.addWidget(team_page)
    main_window.team_page = team_page
    main_window.team_page_index = team_index

    team_button = QPushButton("Team & Plans", objectName="NavButton")
    team_button.setCheckable(True)
    team_button.setToolTip("Plans, company policy, members and devices")
    team_button.setIcon(icon("protect", color="#FFFFFF", size=20))
    team_button.setIconSize(QSize(20, 20))
    team_button.clicked.connect(
        lambda _checked=False: main_window._show_page(team_index)
    )
    main_window.nav_group.addButton(team_button)

    settings_button = next(
        (
            button
            for button in main_window.nav_buttons
            if button.text() == "Settings"
        ),
        None,
    )
    if settings_button is not None:
        layout_index = main_window.side_layout.indexOf(settings_button)
        main_window.side_layout.insertWidget(max(0, layout_index), team_button)
        list_index = main_window.nav_buttons.index(settings_button)
        main_window.nav_buttons.insert(list_index, team_button)
        main_window.nav_labels.insert(list_index, "Team & Plans")
    else:
        main_window.side_layout.addWidget(team_button)
        main_window.nav_buttons.append(team_button)
        main_window.nav_labels.append("Team & Plans")

    previous_show_page = main_window._show_page

    def show_page(index: int) -> None:
        if index == team_index:
            main_window.pages.setCurrentIndex(team_index)
            for button in main_window.nav_buttons:
                button.setChecked(False)
            team_button.setChecked(True)
            team_page.refresh_silent()
            return
        previous_show_page(index)

    main_window._show_page = show_page

    initial_engine = _engine_from_data_dir(main_window.library.data_dir)
    main_window.protection_page._privacygate_set_policy_engine(initial_engine)

    def policy_changed(policy) -> None:
        engine = PolicyEngine(policy) if isinstance(policy, CompanyPolicy) else PolicyEngine()
        main_window.protection_page._privacygate_set_policy_engine(engine)
        apps_page = getattr(main_window, "apps_hub_page", None)
        if apps_page is not None:
            apps_page.refresh()

    team_page.policy_changed.connect(policy_changed)
    team_page.open_account.connect(
        lambda: main_window._show_page(main_window.pages.indexOf(main_window.settings_page))
    )
