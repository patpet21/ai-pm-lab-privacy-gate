from __future__ import annotations

from html import escape
from typing import Iterable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.business_foundation import _engine_for_page
from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _open_source_browser
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
RED = "#B54747"
AMBER = "#B7791F"
BORDER = "#DCE5EA"
SOFT = "#F7FAFC"

_PROVIDER_SPECS = (
    ("gmail", "Gmail"),
    ("google_drive", "Google Drive"),
    ("asana", "Asana"),
    ("clickup", "ClickUp"),
    ("trello", "Trello"),
    ("notion", "Notion"),
    ("monday", "monday.com"),
    ("jira", "Jira"),
)
_AI_SPECS = (("chatgpt", "ChatGPT"), ("claude", "Claude"), ("gemini", "Gemini"))
_ENTITY_LABELS = {
    "US_SSN": "SSN",
    "US_BANK_NUMBER": "Bank account",
    "US_ROUTING_NUMBER": "Routing number",
    "CREDIT_CARD": "Credit card",
    "EMAIL_ADDRESS": "Email",
    "PHONE_NUMBER": "Phone number",
    "PERSON": "Person name",
    "STREET_ADDRESS": "Property address",
    "LOCATION": "Location",
    "MONEY_AMOUNT": "Rent amount",
}


def _card(name: str = "MockupCard") -> QFrame:
    frame = QFrame(objectName=name)
    frame.setStyleSheet(
        f"QFrame#{name}{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"
    )
    return frame


def _heading(text: str, size: int = 14) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color:{NAVY};font-size:{size}px;font-weight:900;")
    return label


def _muted(text: str = "", size: int = 9) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{MUTED};font-size:{size}px;")
    return label


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _combined_original(page) -> str:
    document = getattr(page, "current_document", None)
    if document is None:
        return ""
    pages = tuple(getattr(document, "pages", ()) or ())
    if len(pages) == 1:
        return str(getattr(pages[0], "text", "") or "")
    return "\n\n".join(
        f"--- Page {getattr(item, 'page_number', index + 1)} ---\n{getattr(item, 'text', '')}"
        for index, item in enumerate(pages)
    )


def _mask_value(entity_type: str, value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    entity = entity_type.upper()
    if entity in {"US_SSN", "US_BANK_NUMBER", "US_ROUTING_NUMBER", "CREDIT_CARD"}:
        tail = "".join(ch for ch in value if ch.isalnum())[-4:]
        return f"•••• •••• {tail}" if tail else "Protected value"
    return value if len(value) <= 58 else value[:55] + "…"


def _directive_text(directive: ProtectionDirective) -> tuple[str, str]:
    if directive is ProtectionDirective.REQUIRED_PROTECT:
        return "Required", "Company required"
    if directive is ProtectionDirective.DEFAULT_PROTECT:
        return "Default protect", "Protected by default"
    if directive is ProtectionDirective.ALLOW:
        return "Allowed", "Per policy"
    return "User choice", "Not required"


def _workspace_context(team_page):
    store = getattr(team_page, "_privacygate_workspace_store", None)
    if store is None:
        return None, None
    context = store.load()
    return context, context.workspaces.get(context.active_key)


def _account_rows(main_window) -> list[tuple[str, str, str, str]]:
    apps_page = getattr(main_window, "apps_hub_page", None)
    service = getattr(apps_page, "service", None)
    rows: list[tuple[str, str, str, str]] = []
    if service is None:
        return rows
    for provider, label in _PROVIDER_SPECS:
        try:
            records = tuple(service.list_connected_accounts(provider))
        except Exception:
            records = ()
        for record in records:
            account_id = str(getattr(record, "account_id", "") or "")
            account_label = str(
                getattr(record, "label", "")
                or getattr(record, "subtitle", "")
                or label
            )
            rows.append((provider, label, account_id, account_label))
    return rows


class ManagedProtectMockup(QWidget):
    """Managed Protect presentation matching the approved Protect & Preflight mockup.

    The original ProtectionPage remains the controller. This view is shown only after
    a managed-workspace scan has produced findings; before that, the existing Protect
    input/scan experience remains visible so no workflow is lost.
    """

    def __init__(self, page, main_window) -> None:
        super().__init__(page)
        self.page = page
        self.main_window = main_window
        self.logo_loader = ProviderLogoLoader(page.library.data_dir, self)
        self.setObjectName("ManagedProtectMockup")
        self._finding_rows: list[QWidget] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(11)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_heading("Protect & Preflight", 27))
        titles.addWidget(_muted("Managed content follows the active workspace policy before AI handoff.", 11))
        header.addLayout(titles, 1)
        self.header_status = QLabel("MANAGED")
        self.header_status.setStyleSheet(
            "background:#E8F7F7;color:#0B7F89;border:1px solid #B8E1E4;"
            "border-radius:10px;padding:6px 10px;font-size:8px;font-weight:900;"
        )
        header.addWidget(self.header_status, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        context = QFrame(objectName="ManagedContextPill")
        context.setStyleSheet(
            "QFrame#ManagedContextPill{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:11px;}"
        )
        context_row = QHBoxLayout(context)
        context_row.setContentsMargins(13, 8, 13, 8)
        building = QLabel()
        building.setPixmap(icon("workflow", color=TEAL, size=18).pixmap(18, 18))
        context_row.addWidget(building)
        self.context_label = QLabel()
        self.context_label.setStyleSheet(f"color:{INK};font-size:10px;font-weight:850;")
        context_row.addWidget(self.context_label)
        context_row.addStretch(1)
        root.addWidget(context)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        self.document_card = _card("ManagedDocumentCard")
        doc = QVBoxLayout(self.document_card)
        doc.setContentsMargins(13, 12, 13, 12)
        doc.setSpacing(7)
        doc.addWidget(_heading("Imported document", 13))
        self.source_label = _muted()
        self.workspace_label = _muted()
        self.policy_label = _muted()
        doc.addWidget(self.source_label)
        doc.addWidget(self.workspace_label)
        doc.addWidget(self.policy_label)
        self.document_preview = QTextBrowser()
        self.document_preview.setOpenExternalLinks(False)
        self.document_preview.setStyleSheet(
            "QTextBrowser{background:#FFFFFF;color:#1D2B36;border:1px solid #D9E1E6;"
            "border-radius:10px;padding:11px;font-size:9px;}"
        )
        doc.addWidget(self.document_preview, 1)
        self.file_label = _muted()
        self.file_label.setStyleSheet(f"color:{INK};font-size:8px;font-weight:700;")
        doc.addWidget(self.file_label)
        columns.addWidget(self.document_card, 3)

        findings_card = _card("ManagedFindingsCard")
        findings = QVBoxLayout(findings_card)
        findings.setContentsMargins(0, 0, 0, 0)
        findings.setSpacing(0)
        findings_header = QHBoxLayout()
        findings_header.setContentsMargins(13, 12, 13, 9)
        findings_header.addWidget(_heading("Detected sensitive items", 13), 1)
        self.finding_count = _muted()
        findings_header.addWidget(self.finding_count)
        findings.addLayout(findings_header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.finding_body = QWidget()
        self.finding_layout = QVBoxLayout(self.finding_body)
        self.finding_layout.setContentsMargins(0, 0, 0, 0)
        self.finding_layout.setSpacing(0)
        self.finding_layout.addStretch(1)
        scroll.setWidget(self.finding_body)
        findings.addWidget(scroll, 1)
        self.finding_footer = _muted()
        self.finding_footer.setStyleSheet(
            f"color:{INK};font-size:8px;font-weight:700;border-top:1px solid #E7EDF1;padding:9px 13px;"
        )
        findings.addWidget(self.finding_footer)
        columns.addWidget(findings_card, 4)

        right = QVBoxLayout()
        right.setSpacing(10)
        preflight_card = _card("ManagedPreflightCard")
        preflight = QVBoxLayout(preflight_card)
        preflight.setContentsMargins(15, 13, 15, 13)
        preflight.setSpacing(9)
        preflight.addWidget(_heading("AI Privacy Preflight", 13))
        self.preflight_steps = QVBoxLayout()
        self.preflight_steps.setSpacing(7)
        preflight.addLayout(self.preflight_steps)
        right.addWidget(preflight_card)

        self.pass_card = QFrame(objectName="ManagedPassCard")
        self.pass_card.setStyleSheet(
            "QFrame#ManagedPassCard{background:#F5FBF7;border:1px solid #9FD0AE;border-radius:12px;}"
        )
        passed = QVBoxLayout(self.pass_card)
        passed.setContentsMargins(15, 13, 15, 13)
        passed.setSpacing(7)
        self.pass_title = QLabel()
        self.pass_title.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
        self.pass_detail = _muted()
        self.pass_detail.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:800;")
        passed.addWidget(self.pass_title)
        passed.addWidget(self.pass_detail)
        right.addWidget(self.pass_card)

        ai_row = QHBoxLayout()
        ai_row.setSpacing(7)
        self.ai_cards: dict[str, tuple[QFrame, QLabel, QLabel, QPushButton]] = {}
        for provider, label in _AI_SPECS:
            tile = _card(f"ManagedAI_{provider}")
            box = QVBoxLayout(tile)
            box.setContentsMargins(8, 8, 8, 8)
            box.setSpacing(4)
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setFixedHeight(30)
            name = QLabel(label)
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;")
            status = QLabel()
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button = QPushButton("Open" if provider != "chatgpt" else "Copy for ChatGPT")
            button.setMinimumHeight(30)
            button.setStyleSheet(
                "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:7px;"
                "padding:6px 7px;font-size:8px;font-weight:850;}"
                "QPushButton:disabled{background:#EEF2F4;color:#9AA8B2;}"
            )
            key = "other" if provider == "gemini" else provider
            button.clicked.connect(lambda _checked=False, destination=key: self.page._privacygate_ai_handoff(destination))
            box.addWidget(logo)
            box.addWidget(name)
            box.addWidget(status)
            box.addStretch(1)
            box.addWidget(button)
            ai_row.addWidget(tile, 1)
            self.ai_cards[provider] = (tile, logo, status, button)
            self.logo_loader.load(
                provider,
                lambda pixmap, target=logo: target.setPixmap(
                    pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                ),
            )
        right.addLayout(ai_row)
        right.addStretch(1)
        columns.addLayout(right, 4)
        root.addLayout(columns, 1)

        warning = QFrame(objectName="ManagedPolicyNotice")
        warning.setStyleSheet(
            "QFrame#ManagedPolicyNotice{background:#FFF9E9;border:1px solid #ECD79B;border-radius:9px;}"
        )
        wrow = QHBoxLayout(warning)
        wrow.setContentsMargins(12, 8, 12, 8)
        wicon = QLabel("⚠")
        wicon.setStyleSheet(f"color:{AMBER};font-size:13px;")
        self.managed_notice = QLabel()
        self.managed_notice.setStyleSheet(f"color:{INK};font-size:9px;font-weight:700;")
        self.managed_notice.setWordWrap(True)
        wrow.addWidget(wicon)
        wrow.addWidget(self.managed_notice, 1)
        root.addWidget(warning)

        footer = QHBoxLayout()
        shield = QLabel()
        shield.setPixmap(icon("protect", color=NAVY, size=18).pixmap(18, 18))
        footer.addWidget(shield)
        footer.addWidget(_muted("Documents, restore mappings, and connector tokens stay local on employee devices.", 8), 1)
        footer.addWidget(_muted("Policy enforcement runs locally before AI handoff.", 8))
        root.addLayout(footer)

    def should_show(self) -> bool:
        engine = _engine_for_page(self.page)
        return bool(
            engine.active
            and engine.policy is not None
            and getattr(self.page, "current_document", None) is not None
            and getattr(self.page, "current_findings", ())
        )

    def _toggle_finding(self, finding_id: str, checked: bool) -> None:
        table = getattr(self.page, "findings_table", None)
        if table is None:
            return
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is None or str(item.data(Qt.ItemDataRole.UserRole) or "") != finding_id:
                continue
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                QTimer.singleShot(0, self.render)
            return

    def _finding_row(self, finding, selected_ids: set[str], engine) -> QWidget:
        entity = str(getattr(finding, "entity_type", "") or "").upper()
        finding_id = str(getattr(finding, "finding_id", "") or "")
        directive = engine.directive_for(entity)
        required = directive is ProtectionDirective.REQUIRED_PROTECT
        title, detail = _directive_text(directive)

        row = QFrame(objectName="ManagedFindingRow")
        row.setStyleSheet(
            "QFrame#ManagedFindingRow{background:#FFFFFF;border:none;border-top:1px solid #EDF1F4;}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(9)
        check = QCheckBox()
        check.setChecked(finding_id in selected_ids)
        check.setEnabled(not required)
        check.stateChanged.connect(
            lambda state, key=finding_id: self._toggle_finding(key, state == Qt.CheckState.Checked.value)
        )
        layout.addWidget(check, alignment=Qt.AlignmentFlag.AlignTop)
        ico = QLabel()
        ico.setPixmap(icon("protect" if required else "contact", color=TEAL, size=17).pixmap(17, 17))
        layout.addWidget(ico, alignment=Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        label = QLabel(_ENTITY_LABELS.get(entity, entity.replace("_", " ").title()))
        label.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;")
        value = QLabel(_mask_value(entity, str(getattr(finding, "text", "") or "")))
        value.setWordWrap(True)
        value.setStyleSheet(f"color:{MUTED};font-size:8px;")
        text.addWidget(label)
        text.addWidget(value)
        layout.addLayout(text, 1)
        policy = QVBoxLayout()
        policy.setSpacing(1)
        policy_title = QLabel(title + ("  🔒" if required else ""))
        policy_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        policy_title.setStyleSheet(
            f"color:{GREEN if directive is not ProtectionDirective.USER_CHOICE else INK};font-size:8px;font-weight:850;"
        )
        policy_detail = QLabel(detail)
        policy_detail.setAlignment(Qt.AlignmentFlag.AlignRight)
        policy_detail.setStyleSheet(f"color:{MUTED};font-size:7px;")
        policy.addWidget(policy_title)
        policy.addWidget(policy_detail)
        layout.addLayout(policy)
        return row

    def _render_steps(self, detected: int, protected: int, required_total: int, required_protected: int) -> None:
        _clear_layout(self.preflight_steps)
        result_ready = getattr(self.page, "current_result", None) is not None
        residual = tuple(getattr(self.page, "_last_residual", ()) or ())
        residual_required = 0
        engine = _engine_for_page(self.page)
        for finding in residual:
            if engine.must_protect(str(getattr(finding, "entity_type", "") or "")):
                residual_required += 1
        steps = (
            ("1", "Detect", f"{detected} sensitive items detected", True),
            ("2", "Protect", f"{protected} items protected per policy", result_ready),
            ("3", "Second scan", "No residual mandatory findings" if residual_required == 0 else f"{residual_required} mandatory residual finding(s)", result_ready and residual_required == 0),
            ("4", "Preflight passed", "Document safe for approved AI handoff", result_ready and required_protected >= required_total and residual_required == 0),
        )
        for number, title, detail, ok in steps:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            bubble = QLabel(number)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setFixedSize(24, 24)
            bubble.setStyleSheet(
                f"background:{TEAL if ok else '#E8EEF2'};color:{'#FFFFFF' if ok else MUTED};"
                "border-radius:12px;font-size:8px;font-weight:900;"
            )
            layout.addWidget(bubble)
            text = QVBoxLayout()
            text.setSpacing(1)
            heading = QLabel(title)
            heading.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;")
            sub = QLabel(detail)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color:{MUTED};font-size:7px;")
            text.addWidget(heading)
            text.addWidget(sub)
            layout.addLayout(text, 1)
            mark = QLabel("✓" if ok else "•")
            mark.setStyleSheet(f"color:{GREEN if ok else MUTED};font-size:12px;font-weight:900;")
            layout.addWidget(mark)
            self.preflight_steps.addWidget(row)

    def render(self) -> None:
        show = self.should_show()
        self.setVisible(show)
        original = getattr(self.page, "_privacygate_original_protect_shell", None)
        if original is not None:
            original.setVisible(not show)
        if not show:
            return

        engine = _engine_for_page(self.page)
        policy = engine.policy
        if policy is None:
            return
        team_page = getattr(self.main_window, "team_page", None)
        role = str(getattr(getattr(team_page, "state", None), "role", "") or "Member").title()
        self.context_label.setText(f"{policy.organization_name}    •    {policy.plan.label}    •    {role}")
        self.header_status.setText(f"POLICY v{policy.version}")

        external = dict(getattr(self.page, "_external_source_metadata", {}) or {})
        provider = str(external.get("provider_label") or "Local document")
        account = str(external.get("account_label") or "")
        item_title = str(external.get("item_title") or "")
        source_bits = [provider] + ([account] if account else [])
        self.source_label.setText("Source:  " + "  •  ".join(source_bits))
        self.workspace_label.setText(f"Workspace context:  {policy.organization_name}")
        self.policy_label.setText(f"Policy origin:  {policy.policy_name} v{policy.version}")

        original_text = _combined_original(self.page)
        preview = escape(original_text[:5200])
        self.document_preview.setHtml(
            "<div style='font-family:Segoe UI,Arial,sans-serif;line-height:1.55;color:#1f2d36'>"
            + preview.replace("\n", "<br>")
            + ("<br><br><b>…</b>" if len(original_text) > 5200 else "")
            + "</div>"
        )
        document = getattr(self.page, "current_document", None)
        source_path = getattr(document, "source_path", None)
        filename = item_title or (source_path.name if source_path else "Imported content")
        self.file_label.setText(f"▣  {filename}    •    processed locally")

        try:
            selected = tuple(self.page._selected_findings())
        except Exception:
            selected = ()
        selected_ids = {str(getattr(item, "finding_id", "") or "") for item in selected}
        findings = tuple(getattr(self.page, "current_findings", ()) or ())
        self.finding_count.setText(f"{len(findings)} findings")
        while self.finding_layout.count() > 1:
            item = self.finding_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for finding in findings:
            self.finding_layout.insertWidget(
                self.finding_layout.count() - 1,
                self._finding_row(finding, selected_ids, engine),
            )

        required_findings = [
            finding
            for finding in findings
            if engine.must_protect(str(getattr(finding, "entity_type", "") or ""))
        ]
        required_protected = sum(
            1 for finding in required_findings if str(getattr(finding, "finding_id", "") or "") in selected_ids
        )
        self.finding_footer.setText(
            "All mandatory items are protected by company policy."
            if required_protected >= len(required_findings)
            else f"{len(required_findings) - required_protected} mandatory item(s) still require protection."
        )
        self._render_steps(len(findings), len(selected_ids), len(required_findings), required_protected)
        self.pass_title.setText(f"✓   {required_protected} / {len(required_findings)}")
        self.pass_detail.setText("mandatory findings protected")
        self.pass_card.setStyleSheet(
            "QFrame#ManagedPassCard{background:#F5FBF7;border:1px solid #9FD0AE;border-radius:12px;}"
            if required_protected >= len(required_findings)
            else "QFrame#ManagedPassCard{background:#FFF8F0;border:1px solid #E8C28E;border-radius:12px;}"
        )

        for provider, (_tile, _logo, status, button) in self.ai_cards.items():
            destination = "other" if provider == "gemini" else provider
            allowed = bool(policy.allowed_ai.get(destination, False))
            status.setText("Allowed" if allowed else "⊘  Blocked")
            status.setStyleSheet(
                f"color:{GREEN if allowed else RED};font-size:8px;font-weight:850;"
            )
            button.setEnabled(allowed)
            if not allowed:
                button.setText("Blocked by policy")
            elif provider == "chatgpt":
                button.setText("Copy for ChatGPT")
            elif provider == "claude":
                button.setText("Open Claude")
            else:
                button.setText("Open Gemini")
        self.managed_notice.setText(
            f"This document remains managed by {policy.organization_name} while this workspace is active. "
            "Mandatory protection and destination rules are enforced locally."
        )


class OrganizationAppsAIView(QWidget):
    """Organization Apps & AI page matching the approved multi-workspace mockup."""

    def __init__(self, main_window, team_page, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.team_page = team_page
        self.logo_loader = ProviderLogoLoader(team_page.state_store.data_dir, self)
        self._rows: list[tuple[str, str, str, str]] = []
        self._binding_widgets: list[QWidget] = []
        self._workspace_radios: dict[str, QRadioButton] = {}
        self._build()
        self.render()
        team_page.state_changed.connect(lambda _state: self.render())

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        top = QHBoxLayout()
        selector_card = _card("WorkspaceSelectorMockup")
        selector_box = QVBoxLayout(selector_card)
        selector_box.setContentsMargins(13, 10, 13, 10)
        selector_box.setSpacing(4)
        selector_box.addWidget(_muted("Active workspace", 8))
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumHeight(38)
        self.workspace_combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;border-radius:9px;"
            "padding:7px 10px;font-size:10px;font-weight:800;}"
        )
        selector_box.addWidget(self.workspace_combo)
        top.addWidget(selector_card, 3)
        top.addStretch(1)
        info = _card("WorkspaceReuseInfo")
        info_box = QVBoxLayout(info)
        info_box.setContentsMargins(14, 10, 14, 10)
        info_box.addWidget(_heading("ⓘ  Connect once. Use across workspaces.", 10))
        info_box.addWidget(_muted("Your connectors stay local and can be reused in any workspace you belong to. Only the selected workspace context determines which policy is applied.", 8))
        top.addWidget(info, 4)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(11)

        left = QVBoxLayout()
        left.setSpacing(9)
        accounts = _card("ConnectedAccountsMockup")
        accounts_box = QVBoxLayout(accounts)
        accounts_box.setContentsMargins(12, 11, 12, 11)
        accounts_box.setSpacing(7)
        accounts_box.addWidget(_heading("Connected accounts", 12))
        accounts_box.addWidget(_muted("The same account can be reused across workspaces.", 8))
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(["Connector", "Account", "Use in workspaces"])
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.accounts_table.setShowGrid(False)
        self.accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.accounts_table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:1px solid #E2E9ED;border-radius:9px;}"
            "QTableWidget::item{padding:6px;border-bottom:1px solid #EEF2F4;}"
            "QHeaderView::section{background:#FFFFFF;color:#425D70;border:none;border-bottom:1px solid #E2E9ED;"
            "padding:7px;font-size:8px;font-weight:850;}"
        )
        accounts_box.addWidget(self.accounts_table, 1)
        self.manage_binding = QPushButton("Manage workspace bindings")
        self.manage_binding.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:8px;"
            "padding:7px 10px;font-size:9px;font-weight:800;}QPushButton:hover{background:#F0FAFA;}"
        )
        self.manage_binding.clicked.connect(self._manage_selected_binding)
        accounts_box.addWidget(self.manage_binding)
        left.addWidget(accounts, 1)

        ai_card = _card("ApprovedAIMockup")
        ai_box = QVBoxLayout(ai_card)
        ai_box.setContentsMargins(12, 10, 12, 10)
        ai_top = QHBoxLayout()
        ai_top.addWidget(_heading("Approved AI for this workspace", 11), 1)
        self.policy_version = _muted()
        ai_top.addWidget(self.policy_version)
        ai_box.addLayout(ai_top)
        self.ai_row = QHBoxLayout()
        self.ai_row.setSpacing(7)
        self.ai_tiles: dict[str, tuple[QLabel, QLabel]] = {}
        for provider, label in _AI_SPECS:
            tile = _card(f"WorkspaceAI_{provider}")
            tile_box = QVBoxLayout(tile)
            tile_box.setContentsMargins(8, 7, 8, 7)
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo.setFixedHeight(28)
            name = QLabel(label)
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setStyleSheet(f"color:{NAVY};font-size:8px;font-weight:850;")
            status = QLabel()
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile_box.addWidget(logo)
            tile_box.addWidget(name)
            tile_box.addWidget(status)
            self.ai_row.addWidget(tile, 1)
            self.ai_tiles[provider] = (logo, status)
            self.logo_loader.load(
                provider,
                lambda pixmap, target=logo: target.setPixmap(
                    pixmap.scaled(27, 27, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                ),
            )
        ai_box.addLayout(self.ai_row)
        left.addWidget(ai_card)
        body.addLayout(left, 4)

        bindings = _card("WorkspaceBindingsMockup")
        bindings_box = QVBoxLayout(bindings)
        bindings_box.setContentsMargins(12, 11, 12, 11)
        bindings_box.setSpacing(7)
        bindings_box.addWidget(_heading("Workspace bindings", 12))
        bindings_box.addWidget(_muted("How each account is bound to workspaces.", 8))
        binding_scroll = QScrollArea()
        binding_scroll.setWidgetResizable(True)
        binding_scroll.setFrameShape(QFrame.Shape.NoFrame)
        binding_body = QWidget()
        self.binding_layout = QVBoxLayout(binding_body)
        self.binding_layout.setContentsMargins(0, 0, 0, 0)
        self.binding_layout.setSpacing(3)
        self.binding_layout.addStretch(1)
        binding_scroll.setWidget(binding_body)
        bindings_box.addWidget(binding_scroll, 1)
        note = _muted("ⓘ  These bindings determine where content can be imported and what policy is applied.", 8)
        note.setStyleSheet(f"background:{SOFT};border:1px solid {BORDER};border-radius:8px;padding:8px;color:{MUTED};font-size:8px;")
        bindings_box.addWidget(note)
        body.addWidget(bindings, 4)

        importer = _card("ImportProtectMockup")
        import_box = QVBoxLayout(importer)
        import_box.setContentsMargins(12, 11, 12, 11)
        import_box.setSpacing(8)
        import_box.addWidget(_heading("Import into Protect", 12))
        import_box.addWidget(_muted("Import content using the selected workspace context.", 8))
        self.import_provider = QComboBox()
        self.import_provider.addItem("Gmail", "gmail")
        self.import_provider.addItem("Google Drive", "google_drive")
        self.import_provider.setMinimumHeight(36)
        import_box.addWidget(self.import_provider)
        self.import_preview = QFrame(objectName="ImportPreview")
        self.import_preview.setStyleSheet("QFrame#ImportPreview{background:#FBFCFD;border:1px solid #DFE7EC;border-radius:9px;}")
        preview_box = QVBoxLayout(self.import_preview)
        preview_box.setContentsMargins(10, 9, 10, 9)
        self.import_source = QLabel()
        self.import_source.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;")
        self.import_detail = _muted()
        preview_box.addWidget(self.import_source)
        preview_box.addWidget(self.import_detail)
        import_box.addWidget(self.import_preview)
        import_box.addWidget(_heading("Import to workspace", 10))
        self.workspace_radio_layout = QVBoxLayout()
        self.workspace_radio_group = QButtonGroup(self)
        self.workspace_radio_group.setExclusive(True)
        import_box.addLayout(self.workspace_radio_layout)
        policy_row = QHBoxLayout()
        policy_row.addWidget(_heading("Policy to apply", 9), 1)
        self.import_policy = _muted()
        policy_row.addWidget(self.import_policy)
        import_box.addLayout(policy_row)
        self.import_button = QPushButton("⇧  Import into Protect")
        self.import_button.setMinimumHeight(38)
        self.import_button.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:8px;padding:8px 10px;"
            "font-size:9px;font-weight:900;}QPushButton:hover{background:#096D76;}"
            "QPushButton:disabled{background:#E9EEF1;color:#9AA8B2;}"
        )
        self.import_button.clicked.connect(self._import_into_protect)
        import_box.addWidget(self.import_button)
        local = _muted("🔒  Import is local. Nothing leaves your device.", 8)
        local.setAlignment(Qt.AlignmentFlag.AlignCenter)
        import_box.addWidget(local)
        import_box.addStretch(1)
        body.addWidget(importer, 3)
        root.addLayout(body, 1)

        footer = _muted("🛡  Connectors and data remain on your device (local-first). Policies are applied locally based on the workspace you select.", 8)
        footer.setStyleSheet(f"background:#FFFFFF;border:1px solid {BORDER};border-radius:9px;padding:8px;color:{INK};font-size:8px;font-weight:700;")
        root.addWidget(footer)

        self.workspace_combo.currentIndexChanged.connect(self._workspace_changed)
        self.import_provider.currentIndexChanged.connect(lambda _index: self.render())

    def _workspace_changed(self, _index: int) -> None:
        key = str(self.workspace_combo.currentData() or "")
        if not key:
            return
        source = getattr(self.team_page, "workspace_selector", None)
        if source is not None:
            index = source.findData(key)
            if index >= 0 and index != source.currentIndex():
                source.setCurrentIndex(index)

    def _manage_selected_binding(self) -> None:
        row = self.accounts_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select an account", "Select a connected account first.")
            return
        item = self.accounts_table.item(row, 0)
        if item is None:
            return
        provider = str(item.data(Qt.ItemDataRole.UserRole) or "")
        account_id = str(item.data(int(Qt.ItemDataRole.UserRole) + 1) or "")
        hidden = getattr(self.team_page, "workspace_accounts_table", None)
        if hidden is None:
            return
        for hidden_row in range(hidden.rowCount()):
            hidden_item = hidden.item(hidden_row, 0)
            if hidden_item is None:
                continue
            if (
                str(hidden_item.data(Qt.ItemDataRole.UserRole) or "") == provider
                and str(hidden_item.data(int(Qt.ItemDataRole.UserRole) + 1) or "") == account_id
            ):
                hidden.setCurrentCell(hidden_row, 0)
                method = getattr(self.team_page, "_privacygate_manage_binding", None)
                if callable(method):
                    method()
                    self.render()
                return

    def _selected_import_workspace(self) -> str:
        for key, radio in self._workspace_radios.items():
            if radio.isChecked():
                return key
        context, _descriptor = _workspace_context(self.team_page)
        return context.active_key if context is not None else ""

    def _import_into_protect(self) -> None:
        provider = str(self.import_provider.currentData() or "")
        label = "Gmail" if provider == "gmail" else "Google Drive"
        if not provider:
            return
        chosen = self._selected_import_workspace()
        source = getattr(self.team_page, "workspace_selector", None)
        if chosen and source is not None:
            index = source.findData(chosen)
            if index >= 0 and index != source.currentIndex():
                source.setCurrentIndex(index)
        _open_source_browser(self.main_window, provider, label)

    def _render_bindings(self, context) -> None:
        while self.binding_layout.count() > 1:
            item = self.binding_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for provider, provider_label, account_id, account_label in self._rows:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(2, 4, 2, 4)
            layout.setSpacing(7)
            logo = QLabel()
            logo.setFixedSize(23, 23)
            self.logo_loader.load(
                provider,
                lambda pixmap, target=logo: target.setPixmap(
                    pixmap.scaled(21, 21, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                ),
            )
            layout.addWidget(logo)
            text = QVBoxLayout()
            text.setSpacing(0)
            name = QLabel(provider_label)
            name.setStyleSheet(f"color:{NAVY};font-size:8px;font-weight:850;")
            account = QLabel(account_label)
            account.setStyleSheet(f"color:{MUTED};font-size:7px;")
            text.addWidget(name)
            text.addWidget(account)
            layout.addLayout(text, 1)
            bindings = context.connector_bindings.get(provider, {}).get(account_id)
            keys: Iterable[str] = context.workspaces.keys() if bindings is None else bindings
            for key in list(keys)[:3]:
                descriptor = context.workspaces.get(key)
                if descriptor is None:
                    continue
                chip = QLabel("Personal" if descriptor.personal else descriptor.name)
                chip.setStyleSheet(
                    "background:#EAF7F7;color:#0B7180;border:1px solid #C9E6E8;border-radius:7px;"
                    "padding:3px 5px;font-size:6px;font-weight:800;"
                )
                layout.addWidget(chip)
            self.binding_layout.insertWidget(self.binding_layout.count() - 1, row)

    def _render_workspace_radios(self, context) -> None:
        while self.workspace_radio_layout.count():
            item = self.workspace_radio_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self.workspace_radio_group.removeButton(widget)
                widget.deleteLater()
        self._workspace_radios.clear()
        for key, descriptor in context.workspaces.items():
            radio = QRadioButton(
                f"{'Personal' if descriptor.personal else descriptor.name} ({descriptor.plan.label})"
            )
            radio.setStyleSheet(f"color:{INK};font-size:8px;")
            radio.setChecked(key == context.active_key)
            self.workspace_radio_group.addButton(radio)
            self.workspace_radio_layout.addWidget(radio)
            self._workspace_radios[key] = radio

    def render(self) -> None:
        context, descriptor = _workspace_context(self.team_page)
        if context is None:
            return
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        for key, item in context.workspaces.items():
            role = item.role.title() if item.role else "You"
            self.workspace_combo.addItem(
                f"{'Personal (Pro)' if item.personal else item.name}   •   {item.plan.label}   •   {role}",
                key,
            )
        self.workspace_combo.setCurrentIndex(max(0, self.workspace_combo.findData(context.active_key)))
        self.workspace_combo.blockSignals(False)

        self._rows = _account_rows(self.main_window)
        self.accounts_table.setRowCount(len(self._rows))
        for row_index, (provider, provider_label, account_id, account_label) in enumerate(self._rows):
            first = QTableWidgetItem(provider_label)
            first.setData(Qt.ItemDataRole.UserRole, provider)
            first.setData(int(Qt.ItemDataRole.UserRole) + 1, account_id)
            self.accounts_table.setItem(row_index, 0, first)
            self.accounts_table.setItem(row_index, 1, QTableWidgetItem(account_label))
            bindings = context.connector_bindings.get(provider, {}).get(account_id)
            keys: Iterable[str] = context.workspaces.keys() if bindings is None else bindings
            names = [
                "Personal" if context.workspaces[key].personal else context.workspaces[key].name
                for key in keys
                if key in context.workspaces
            ]
            self.accounts_table.setItem(row_index, 2, QTableWidgetItem(", ".join(names) if names else "Not assigned"))
        if self._rows and self.accounts_table.currentRow() < 0:
            self.accounts_table.selectRow(0)
        self._render_bindings(context)
        self._render_workspace_radios(context)

        policy = getattr(self.team_page, "state", None).policy if getattr(self.team_page, "state", None) is not None else None
        self.policy_version.setText(f"Policy: {policy.policy_name} v{policy.version}" if policy else "Personal policy")
        for provider, (_logo, status) in self.ai_tiles.items():
            key = "other" if provider == "gemini" else provider
            allowed = True if descriptor is not None and descriptor.personal else bool(policy and policy.allowed_ai.get(key, False))
            status.setText("✓ Allowed" if allowed else "⊘ Blocked")
            status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:7px;font-weight:850;")

        provider = str(self.import_provider.currentData() or "gmail")
        provider_label = "Gmail" if provider == "gmail" else "Google Drive"
        connected = any(row[0] == provider for row in self._rows)
        protect = getattr(self.main_window, "protection_page", None)
        metadata = dict(getattr(protect, "_external_source_metadata", {}) or {}) if protect is not None else {}
        if str(metadata.get("provider") or "") == provider:
            account = str(metadata.get("account_label") or "")
            item = str(metadata.get("item_title") or "Selected source")
            self.import_source.setText(f"{provider_label}   {account}".strip())
            self.import_detail.setText(f"Ready source: {item}\nChoose Import into Protect to browse or replace the source.")
        else:
            self.import_source.setText(provider_label)
            self.import_detail.setText(
                "Connected account ready. Click Import into Protect, choose a source, and PrivacyGate will bring a local working copy into Protect."
                if connected
                else "No connected account for this provider. Connect it from Apps first."
            )
        self.import_button.setEnabled(connected)
        if policy and descriptor is not None and not descriptor.personal:
            self.import_policy.setText(f"{policy.organization_name} v{policy.version}")
        else:
            self.import_policy.setText("Personal")


def _wrap_protect_page(page, mockup: ManagedProtectMockup) -> None:
    if getattr(page, "_privacygate_original_protect_shell", None) is not None:
        return
    root = page.layout()
    if root is None:
        return
    original_shell = QWidget(page)
    original_shell.setObjectName("OriginalProtectShell")
    original_layout = QVBoxLayout(original_shell)
    original_layout.setContentsMargins(0, 0, 0, 0)
    original_layout.setSpacing(root.spacing())
    while root.count():
        item = root.takeAt(0)
        widget = item.widget()
        child = item.layout()
        spacer = item.spacerItem()
        if widget is not None:
            original_layout.addWidget(widget)
        elif child is not None:
            original_layout.addLayout(child)
        elif spacer is not None:
            original_layout.addSpacerItem(spacer)
    root.addWidget(original_shell, 1)
    root.addWidget(mockup, 1)
    page._privacygate_original_protect_shell = original_shell
    page._privacygate_managed_mockup = mockup


def _refresh_after(view: ManagedProtectMockup, callback):
    def wrapped(*args, **kwargs):
        result = callback(*args, **kwargs)
        QTimer.singleShot(0, view.render)
        return result
    return wrapped


def _install_protect_mockup(main_window) -> ManagedProtectMockup | None:
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return None
    existing = getattr(page, "_privacygate_managed_mockup", None)
    if existing is not None:
        return existing
    view = ManagedProtectMockup(page, main_window)
    _wrap_protect_page(page, view)
    for name in (
        "_populate_findings",
        "_refresh_preview",
        "_set_all_findings",
        "_invert_findings",
        "_set_reviewed_finding_protection",
        "clear",
    ):
        current = getattr(page, name, None)
        if callable(current):
            setattr(page, name, _refresh_after(view, current))
    table = getattr(page, "findings_table", None)
    if table is not None:
        table.itemChanged.connect(lambda _item: QTimer.singleShot(0, view.render))
    team_page = getattr(main_window, "team_page", None)
    if team_page is not None:
        team_page.state_changed.connect(lambda _state: QTimer.singleShot(0, view.render))
        team_page.policy_changed.connect(lambda _policy: QTimer.singleShot(0, view.render))
    view.render()
    return view


def _install_organization_apps(main_window) -> OrganizationAppsAIView | None:
    page = getattr(main_window, "team_page", None)
    dashboard = getattr(page, "_privacygate_premium_dashboard", None) if page is not None else None
    if page is None or dashboard is None:
        return None
    existing = getattr(dashboard, "_mockup_apps_ai", None)
    if existing is not None:
        return existing
    stack = getattr(dashboard, "stack", None)
    if stack is None or stack.count() <= 4:
        return None
    old = stack.widget(4)
    apps = OrganizationAppsAIView(main_window, page, dashboard)
    stack.removeWidget(old)
    old.hide()
    stack.insertWidget(4, apps)
    dashboard._mockup_apps_ai = apps
    dashboard._mockup_old_apps_ai = old

    quick_publish = getattr(dashboard, "quick_publish", None)
    if isinstance(quick_publish, QPushButton):
        quick_publish.setText("Publish update\nSync policy to all devices")
    members_preview = getattr(dashboard, "members_preview", None)
    if members_preview:
        table = members_preview[1]
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Name", "Role", "Status", "Joined"])
        for column in range(4):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
    devices_preview = getattr(dashboard, "devices_preview", None)
    if devices_preview:
        devices_preview[1].setHorizontalHeaderLabels(["Device", "User", "Policy Version", "Status"])

    title_label = next((label for label in dashboard.findChildren(QLabel) if label.text() == "Organization"), None)
    subtitle_label = next(
        (
            label
            for label in dashboard.findChildren(QLabel)
            if label.text() == "Company privacy control for managed AI workflows."
        ),
        None,
    )
    original_select = dashboard._select_tab

    def select_tab(index: int) -> None:
        original_select(index)
        if title_label is not None:
            title_label.setText("Apps & AI" if index == 3 else "Organization")
        if subtitle_label is not None:
            subtitle_label.setText(
                "Choose the right workspace context before using connected accounts."
                if index == 3
                else "Company privacy control for managed AI workflows."
            )
        if index == 3:
            apps.render()

    dashboard._select_tab = select_tab
    for visual_index, button in enumerate(getattr(dashboard, "tab_buttons", [])):
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(lambda _checked=False, i=visual_index: dashboard._select_tab(i))

    def polish_overview(_state=None) -> None:
        try:
            dashboard.metric_details["devices"].setText("All up to date")
            dashboard.metric_details["policy"].setText("Updated recently")
        except Exception:
            pass
        table = members_preview[1] if members_preview else None
        if table is not None and table.columnCount() >= 4:
            for row, member in enumerate(page._members[:4]):
                joined = str(member.get("created_at") or member.get("joined_at") or "")
                joined = joined[:10] if joined else "—"
                table.setItem(row, 3, QTableWidgetItem(joined))

    page.state_changed.connect(lambda state: QTimer.singleShot(0, lambda: polish_overview(state)))
    QTimer.singleShot(0, polish_overview)
    return apps


def apply_mockup_fidelity(main_window) -> None:
    """Apply the three approved mockups as the visual source of truth.

    This layer deliberately reuses the existing controller methods for policy,
    workspace switching, account bindings, source import and AI handoff. It changes
    presentation, not the local-first security architecture.
    """

    if getattr(main_window, "_privacygate_mockup_fidelity_applied", False):
        return
    main_window._privacygate_mockup_fidelity_applied = True
    _install_organization_apps(main_window)
    _install_protect_mockup(main_window)
