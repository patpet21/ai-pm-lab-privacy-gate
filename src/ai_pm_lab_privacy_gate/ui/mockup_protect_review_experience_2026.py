from __future__ import annotations

"""Complete review experience for the approved 2026 Protect surface.

This layer deliberately reuses the authoritative Protect findings, ProtectSession,
Privacy Check and quick-action controllers. It adds no cloud persistence. Manual
rule values continue to live only in the encrypted LocalManualSensitiveStore.
"""

import base64
import html
from dataclasses import replace
from datetime import datetime, timezone
from types import MethodType

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.application.local_protect_sources import compatibility_sources
from ai_pm_lab_privacy_gate.application.protect_session_service import namespace_findings
from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.business_foundation import _engine_for_page
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
)
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import PrivacyGateProductDialog
from ai_pm_lab_privacy_gate.ui import mockup_protect_manual_sensitive_2026 as manual


AMBER = "#B54708"
AMBER_SOFT = "#FFFAEB"
RED = "#B42318"
RED_SOFT = "#FEF3F2"


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _is_manual_finding(finding) -> bool:
    finding_id = str(getattr(finding, "finding_id", "") or "")
    return finding_id.startswith("manual-") or "::manual-" in finding_id


def _finding_for_row(page, row: int):
    table = page.findings_table
    if row < 0 or row >= table.rowCount():
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    finding_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
    return next(
        (finding for finding in tuple(page.current_findings or ()) if str(finding.finding_id) == finding_id),
        None,
    )


def _selected_finding(page):
    row = getattr(page, "_reviewed_row", None)
    if isinstance(row, int):
        finding = _finding_for_row(page, row)
        if finding is not None:
            return finding
    row = page.findings_table.currentRow()
    return _finding_for_row(page, row)


def _fingerprint(page) -> str:
    document = getattr(page, "current_document", None)
    return manual._document_fingerprint(document) if document is not None else ""


def _rules(page) -> tuple[tuple[str, str], ...]:
    store = getattr(page, "_protect_manual_sensitive_store", None)
    fingerprint = _fingerprint(page)
    if store is None or not fingerprint:
        return ()
    try:
        return tuple(store.list_rules(fingerprint))
    except Exception:
        return ()


def _rule_for_finding(page, finding) -> tuple[str, str] | None:
    if finding is None or not _is_manual_finding(finding):
        return None
    target_text = _normalize_text(getattr(finding, "text", ""))
    target_type = str(getattr(finding, "entity_type", "") or "")
    for exact_text, entity_type in _rules(page):
        if entity_type == target_type and _normalize_text(exact_text) == target_text:
            return exact_text, entity_type
    return None


def _decode_store_row(store, row: dict) -> tuple[str, str] | None:
    try:
        protected = base64.b64decode(str(row.get("protected_value") or ""), validate=True)
        exact_text = store.protector.unprotect(protected)
        entity_type = str(row.get("entity_type") or "CUSTOM")
    except Exception:
        return None
    return exact_text, entity_type


def _mutate_rule(
    page,
    *,
    old_text: str,
    old_type: str,
    new_text: str | None = None,
    new_type: str | None = None,
) -> bool:
    """Update/remove one encrypted local rule without ever exposing it to cloud state."""
    store = getattr(page, "_protect_manual_sensitive_store", None)
    fingerprint = _fingerprint(page)
    if store is None or not fingerprint:
        return False
    try:
        payload = store._read()
        documents = payload.get("documents", {})
        record = documents.get(fingerprint)
        rows = record.get("rules", []) if isinstance(record, dict) else []
        if not isinstance(rows, list):
            return False

        old_key = (_normalize_text(old_text), old_type)
        kept: list[dict] = []
        removed = False
        for row in rows:
            decoded = _decode_store_row(store, row) if isinstance(row, dict) else None
            if decoded is None:
                kept.append(row)
                continue
            plain, entity = decoded
            if not removed and (_normalize_text(plain), entity) == old_key:
                removed = True
                continue
            kept.append(row)
        if not removed:
            return False

        if new_text is not None and new_type is not None:
            new_key = (_normalize_text(new_text), new_type)
            duplicate = False
            for row in kept:
                decoded = _decode_store_row(store, row) if isinstance(row, dict) else None
                if decoded and (_normalize_text(decoded[0]), decoded[1]) == new_key:
                    duplicate = True
                    break
            if not duplicate:
                protected = store.protector.protect(new_text.strip())
                kept.append(
                    {
                        "entity_type": new_type,
                        "protected_value": base64.b64encode(protected).decode("ascii"),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        record["rules"] = kept
        if not kept:
            documents.pop(fingerprint, None)
        store._write(payload)
        return True
    except Exception:
        return False


def _manual_findings(document, rules: tuple[tuple[str, str], ...]):
    rows = []
    seen: set[str] = set()
    for exact_text, entity_type in rules:
        try:
            findings = manual._manual_findings_for_text(document, exact_text, entity_type)
        except Exception:
            findings = ()
        for finding in findings:
            if finding.finding_id in seen:
                continue
            seen.add(finding.finding_id)
            rows.append(finding)
    return tuple(rows)


def _rebuild_manual_state(page) -> None:
    """Rebuild manual findings once while preserving every existing Protect/Keep choice."""
    document = getattr(page, "current_document", None)
    if document is None:
        return
    rules = _rules(page)
    table: QTableWidget = page.findings_table
    previous_states = {
        str(table.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""): table.item(row, 0).checkState()
        for row in range(table.rowCount())
        if table.item(row, 0) is not None
    }

    analysis = getattr(page, "_local_protect_session_analysis", None)
    managed = bool(getattr(page, "_local_protect_session_managed", False))
    target_fingerprint = manual._document_fingerprint(document)

    if managed and analysis is not None:
        updated_sources = []
        for source_analysis in analysis.sources:
            source_document = source_analysis.document
            try:
                same_document = manual._document_fingerprint(source_document) == target_fingerprint
            except Exception:
                same_document = source_document is document
            if not same_document:
                updated_sources.append(source_analysis)
                continue
            automatic = tuple(
                finding for finding in source_analysis.findings if not _is_manual_finding(finding)
            )
            additions = namespace_findings(
                _manual_findings(source_document, rules),
                source_analysis.source.key,
            )
            ids = {finding.finding_id for finding in automatic}
            merged = automatic + tuple(finding for finding in additions if finding.finding_id not in ids)
            updated_sources.append(replace(source_analysis, findings=merged))
        analysis = replace(analysis, sources=tuple(updated_sources))
        page._local_protect_session_analysis = analysis
        try:
            page._protect_session_sources = compatibility_sources(analysis)
        except Exception:
            pass
        page.current_findings = tuple(analysis.findings)
    else:
        automatic = tuple(
            finding for finding in tuple(page.current_findings or ()) if not _is_manual_finding(finding)
        )
        additions = _manual_findings(document, rules)
        ids = {finding.finding_id for finding in automatic}
        page.current_findings = automatic + tuple(
            finding for finding in additions if finding.finding_id not in ids
        )

    page._populate_findings()
    table.blockSignals(True)
    try:
        for row in range(table.rowCount()):
            check = table.item(row, 0)
            if check is None:
                continue
            finding_id = str(check.data(Qt.ItemDataRole.UserRole) or "")
            if finding_id in previous_states:
                check.setCheckState(previous_states[finding_id])
    finally:
        table.blockSignals(False)
    try:
        page._sync_category_check_states()
    except Exception:
        pass
    page._refresh_preview()


class EditLocalRuleDialog(PrivacyGateProductDialog):
    def __init__(self, parent, *, exact_text: str, entity_type: str) -> None:
        super().__init__(
            parent,
            title="Edit local protection rule",
            subtitle="Change a manually added value or its label, then regenerate the same local safe copy.",
            icon_name="protect",
            width=680,
        )
        self.exact = QPlainTextEdit()
        self.exact.setPlainText(exact_text)
        self.exact.setMinimumHeight(82)
        self.exact.setMaximumHeight(120)
        self.exact.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:10px;padding:9px 10px;font-size:10px;}"
            f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
        )
        self.add_field(
            "Exact text to protect",
            self.exact,
            "The replacement must exist in the locally extracted document text.",
        )
        self.category = QComboBox()
        selected_index = 0
        custom = entity_type.startswith("CUSTOM_") or entity_type == "CUSTOM"
        for index, (label, value) in enumerate(manual._CATEGORIES):
            self.category.addItem(label, value)
            if value == entity_type or (custom and value == "CUSTOM"):
                selected_index = index
        self.category.setCurrentIndex(selected_index)
        self.add_field("Category / label", self.category)
        self.custom_label = QLineEdit()
        if entity_type.startswith("CUSTOM_"):
            self.custom_label.setText(entity_type[len("CUSTOM_") :].replace("_", " ").title())
        self.add_field(
            "Custom label",
            self.custom_label,
            "Used only when Custom label is selected; stored locally only.",
        )
        self.category.currentIndexChanged.connect(self._sync)
        self.add_notice(
            "Privacy boundary: the edited exact value stays encrypted in the local PrivacyGate data directory. Nothing here is written to Supabase.",
            privacy=True,
        )
        self.primary, _secondary = self.add_actions(
            primary_text="Save & regenerate",
            primary_callback=self._accept_if_valid,
        )
        self.exact.textChanged.connect(self._sync)
        self.custom_label.textChanged.connect(self._sync)
        self._sync()

    def _sync(self, *_args) -> None:
        custom = str(self.category.currentData() or "") == "CUSTOM"
        self.custom_label.setEnabled(custom)
        valid = bool(self.exact.toPlainText().strip()) and (
            not custom or bool(self.custom_label.text().strip())
        )
        self.primary.setEnabled(valid)

    def _accept_if_valid(self) -> None:
        self._sync()
        if self.primary.isEnabled():
            self.accept()

    @property
    def value(self) -> str:
        return self.exact.toPlainText().strip()

    @property
    def entity_type(self) -> str:
        value = str(self.category.currentData() or "CUSTOM")
        return manual._normalize_custom_label(self.custom_label.text()) if value == "CUSTOM" else value


class RemoveLocalRuleDialog(PrivacyGateProductDialog):
    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            title="Remove local protection rule",
            subtitle="This removes the selected manual rule from this document fingerprint and regenerates the protected copy.",
            icon_name="protect",
            width=610,
        )
        self.add_notice(
            "Only the encrypted local rule is removed. The original document is not modified and no deletion event is sent to Supabase.",
            privacy=True,
        )
        self.add_actions(primary_text="Remove & regenerate", primary_callback=self.accept)


def _edit_selected_rule(page) -> None:
    finding = _selected_finding(page)
    rule = _rule_for_finding(page, finding)
    if rule is None:
        return
    old_text, old_type = rule
    dialog = EditLocalRuleDialog(page, exact_text=old_text, entity_type=old_type)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    new_text, new_type = dialog.value, dialog.entity_type
    try:
        matches = manual._manual_findings_for_text(page.current_document, new_text, new_type)
    except Exception:
        matches = ()
    if not matches:
        manual.ManualValueResultDialog(
            page,
            title="Exact text not found",
            detail="The edited wording is not present in the locally extracted document text. The existing rule was left unchanged.",
            success=False,
        ).exec()
        return
    if not _mutate_rule(
        page,
        old_text=old_text,
        old_type=old_type,
        new_text=new_text,
        new_type=new_type,
    ):
        return
    _rebuild_manual_state(page)


def _remove_selected_rule(page) -> None:
    finding = _selected_finding(page)
    rule = _rule_for_finding(page, finding)
    if rule is None:
        return
    if RemoveLocalRuleDialog(page).exec() != QDialog.DialogCode.Accepted:
        return
    if not _mutate_rule(page, old_text=rule[0], old_type=rule[1]):
        return
    page._reviewed_row = None
    _rebuild_manual_state(page)


def _filter_match(page, row: int, mode: str) -> bool:
    check = page.findings_table.item(row, 0)
    finding = _finding_for_row(page, row)
    if check is None or finding is None:
        return False
    if mode == "protected":
        return check.checkState() == Qt.CheckState.Checked
    if mode == "kept":
        return check.checkState() != Qt.CheckState.Checked
    if mode == "manual":
        return _is_manual_finding(finding)
    return True


def _apply_combined_filter(page) -> None:
    mode = str(getattr(page, "_protect_review_filter", "all") or "all")
    term = page.filter_input.text().casefold().strip()
    for row in range(page.findings_table.rowCount()):
        haystack = " ".join(
            page.findings_table.item(row, column).text()
            for column in range(1, page.findings_table.columnCount())
            if page.findings_table.item(row, column) is not None
        ).casefold()
        visible = _filter_match(page, row, mode) and (not term or term in haystack)
        page.findings_table.setRowHidden(row, not visible)


def _set_review_filter(page, mode: str) -> None:
    page._protect_review_filter = mode
    for key, button in getattr(page, "_protect_review_summary_buttons", {}).items():
        button.setChecked(key == mode)
    _apply_combined_filter(page)


def _risk_state(page) -> tuple[str, str, str, str]:
    summary = getattr(page, "_privacy_check_summary", None)
    if summary is None:
        if getattr(page, "current_result", None) is not None:
            return "CHECKING", BLUE, BLUE_SOFT, "#C7D7FE"
        return "NOT CHECKED", MUTED, "#F2F4F7", BORDER
    risk = str(getattr(summary, "risk", "") or "").upper()
    if risk == "LOW":
        return "LOW RISK", GREEN, GREEN_SOFT, "#BBF7D0"
    if risk == "MEDIUM":
        return "REVIEW", AMBER, AMBER_SOFT, "#FEDF89"
    return "HIGH RISK", RED, RED_SOFT, "#FECDCA"


def _update_review_summary(page) -> None:
    buttons = getattr(page, "_protect_review_summary_buttons", None)
    if not buttons:
        return
    total = page.findings_table.rowCount()
    protected = 0
    manual_count = 0
    for row in range(total):
        check = page.findings_table.item(row, 0)
        if check is not None and check.checkState() == Qt.CheckState.Checked:
            protected += 1
        finding = _finding_for_row(page, row)
        manual_count += int(finding is not None and _is_manual_finding(finding))
    kept = total - protected
    buttons["all"].setText(f"{total} detected")
    buttons["protected"].setText(f"{protected} protected")
    buttons["kept"].setText(f"{kept} kept")
    buttons["manual"].setText(f"Local rules · {len(_rules(page))}")

    text, color, background, border = _risk_state(page)
    badge = page._protect_review_risk
    badge.setText(text)
    badge.setToolTip(
        "This status comes from PrivacyGate's real local Privacy Check of the protected result."
    )
    badge.setStyleSheet(
        f"background:{background};color:{color};border:1px solid {border};"
        "border-radius:8px;padding:5px 8px;font-size:7.5px;font-weight:950;"
    )


def _ensure_review_summary(page) -> None:
    if getattr(page, "_protect_review_summary", None) is not None:
        return
    layout = page.findings_card.layout()
    table = page.findings_table
    target = getattr(page, "_protect_2026_findings_legend", None)
    index = layout.indexOf(target) if target is not None else layout.indexOf(table)
    if index < 0:
        return

    frame = QFrame(objectName="ProtectReviewSummary")
    frame.setStyleSheet(
        "QFrame#ProtectReviewSummary{background:#F8FAFC;border:1px solid #EAECF0;border-radius:10px;}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(9, 6, 9, 6)
    row.setSpacing(5)
    buttons = {}
    for key in ("all", "protected", "kept", "manual"):
        button = QPushButton()
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton{{background:#FFFFFF;color:#475467;border:1px solid {BORDER};border-radius:8px;"
            "padding:5px 8px;font-size:7.5px;font-weight:850;}"
            f"QPushButton:checked{{background:{BLUE_SOFT};color:{BLUE};border-color:#C7D7FE;}}"
        )
        button.clicked.connect(lambda _checked=False, value=key: _set_review_filter(page, value))
        row.addWidget(button)
        buttons[key] = button
    row.addStretch(1)
    risk = QLabel("NOT CHECKED")
    row.addWidget(risk)
    layout.insertWidget(index, frame)
    page._protect_review_summary = frame
    page._protect_review_summary_buttons = buttons
    page._protect_review_risk = risk
    page._protect_review_filter = "all"
    buttons["all"].setChecked(True)
    _update_review_summary(page)


def _policy_reason(page, finding) -> str:
    try:
        engine = _engine_for_page(page)
        if not bool(getattr(engine, "active", False)) or getattr(engine, "policy", None) is None:
            return "Local detection profile"
        directive = engine.directive_for(str(finding.entity_type))
    except Exception:
        return "Local detection profile"
    if directive is ProtectionDirective.REQUIRED_PROTECT:
        return "Required by organization policy"
    if directive is ProtectionDirective.DEFAULT_PROTECT:
        return "Default protect under organization policy"
    if directive is ProtectionDirective.USER_CHOICE:
        return "Organization policy leaves this item to user review"
    return "Organization policy allows this category"


def _render_why_detected(page, row: int) -> None:
    finding = _finding_for_row(page, row)
    if finding is None:
        return
    check = page.findings_table.item(row, 0)
    protected = check is not None and check.checkState() == Qt.CheckState.Checked
    manual_source = _is_manual_finding(finding)
    location_item = page.findings_table.item(row, 3)
    location = location_item.text() if location_item is not None else f"Page {finding.page_number}"
    origin = "Manual · local rule" if manual_source else "Automatic · local detector"
    confidence = "User supplied" if manual_source else f"{finding.score:.0%}"
    reason = (
        "Added manually on this device because the automatic detector did not classify the value."
        if manual_source
        else _policy_reason(page, finding)
    )
    if manual_source:
        policy = _policy_reason(page, finding)
        if policy != "Local detection profile":
            reason += f" Policy: {policy}."
    context = html.escape(" ".join(str(finding.context or "").split()))
    state = "PROTECT" if protected else "KEEP ORIGINAL"
    state_color = GREEN if protected else AMBER
    page.finding_context.setTextFormat(Qt.TextFormat.RichText)
    page.finding_context.setText(
        f'<div style="color:#344054;font-size:9px;">'
        f'<b style="color:{state_color};">{state}</b> &nbsp;·&nbsp; '
        f'<b>{html.escape(str(finding.entity_type).replace("_", " ").title())}</b> &nbsp;·&nbsp; '
        f'{html.escape(location)}<br>'
        f'<span style="color:#667085;">Origin:</span> {html.escape(origin)} &nbsp;·&nbsp; '
        f'<span style="color:#667085;">Confidence:</span> {html.escape(confidence)}<br>'
        f'<span style="color:#667085;">Why:</span> {html.escape(reason)}<br>'
        f'<span style="color:#667085;">Context:</span> {context}</div>'
    )
    page.protect_this_button.setEnabled(True)
    page.keep_this_button.setEnabled(True)
    manual_selected = manual_source and _rule_for_finding(page, finding) is not None
    page._protect_edit_manual.setEnabled(manual_selected)
    page._protect_remove_manual.setEnabled(manual_selected)


def _install_manual_management(page) -> None:
    if getattr(page, "_protect_edit_manual", None) is not None:
        return
    add = page.add_sensitive_button
    parent_layout = None
    parent = add.parentWidget()
    while parent is not None and parent_layout is None:
        layout = parent.layout()
        if isinstance(layout, (QHBoxLayout, QVBoxLayout)) and layout.indexOf(add) >= 0:
            parent_layout = layout
            break
        parent = parent.parentWidget()
    if parent_layout is None:
        return
    edit = QPushButton("Edit local rule")
    remove = QPushButton("Remove local rule")
    for button in (edit, remove):
        button.setMinimumHeight(34)
        button.setEnabled(False)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:8px;padding:6px 9px;font-size:7.5px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;}"
            "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
        )
    remove.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#B42318;border:1px solid #FECDCA;"
        "border-radius:8px;padding:6px 9px;font-size:7.5px;font-weight:850;}"
        "QPushButton:hover{background:#FEF3F2;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )
    index = parent_layout.indexOf(add)
    parent_layout.insertWidget(index + 1, edit)
    parent_layout.insertWidget(index + 2, remove)
    edit.clicked.connect(lambda _checked=False: _edit_selected_rule(page))
    remove.clicked.connect(lambda _checked=False: _remove_selected_rule(page))
    page._protect_edit_manual = edit
    page._protect_remove_manual = remove


def _copy_protected_text(page) -> None:
    if getattr(page, "current_result", None) is None:
        return
    if not page._confirm_residual_risk("copying protected text"):
        return
    QApplication.clipboard().setText(page.current_result.combined_text)
    metric = getattr(page, "_redesign_review_metric", None)
    if metric is not None:
        metric.setText("Protected text copied")


def _configure_final_actions(page) -> None:
    bar = getattr(page, "_protect_quick_actions", None)
    if bar is None:
        return
    save = getattr(page, "_protect_save_only", None)
    copy = getattr(page, "_protect_save_copy", None)
    download = getattr(page, "_protect_save_download", None)
    ai = getattr(page, "_protect_open_ai", None)
    if save is not None:
        save.setText("Save to Library")
        save.setToolTip("Save the protected result and restore mapping to the local PrivacyGate Library.")
    if copy is not None:
        copy.setText("Copy protected text")
        copy.setToolTip("Run the local Privacy Check, then copy only the protected text.")
        try:
            copy.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        copy.clicked.connect(lambda _checked=False: _copy_protected_text(page))
    if download is not None:
        download.setText("Download safe copy")
        download.setToolTip(
            "Run the final local check, keep the restore mapping in the local Library, then export the protected file."
        )
    if ai is not None:
        ai.setText("Use with AI")
        ai.setToolTip(
            "Choose an approved AI destination. PrivacyGate runs the existing Privacy Preflight before the handoff."
        )
    for label in bar.findChildren(QLabel):
        if "Protected copy ready" in label.text() or "choose" in label.text().lower():
            label.setText("Safe copy ready — save locally, download, copy, or use with approved AI")
    page._protect_final_action_bar = bar


def _refresh_product_state(page) -> None:
    _update_review_summary(page)
    _apply_combined_filter(page)
    bar = getattr(page, "_protect_final_action_bar", None)
    if bar is not None:
        bar.setVisible(getattr(page, "current_result", None) is not None)


def apply_mockup_protect_review_experience_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_review_experience", False)):
        return
    page._protect_2026_review_experience = True

    _ensure_review_summary(page)
    _install_manual_management(page)
    _configure_final_actions(page)

    previous_populate = page._populate_findings

    def populate_with_product_state(self) -> None:
        previous_populate()
        _ensure_review_summary(self)
        _update_review_summary(self)
        _apply_combined_filter(self)

    page._populate_findings = MethodType(populate_with_product_state, page)

    previous_context = page._update_review_context

    def review_context(self, row: int) -> None:
        try:
            _render_why_detected(self, row)
        except Exception:
            previous_context(row)

    page._update_review_context = MethodType(review_context, page)

    page.findings_table.itemChanged.connect(lambda *_args: QTimer.singleShot(0, lambda: _refresh_product_state(page)))
    page.filter_input.textChanged.connect(lambda *_args: QTimer.singleShot(0, lambda: _apply_combined_filter(page)))
    page.findings_table.cellClicked.connect(lambda row, _column: QTimer.singleShot(0, lambda: _render_why_detected(page, row)))
    page.add_sensitive_button.clicked.connect(lambda *_args: QTimer.singleShot(0, lambda: _refresh_product_state(page)))
    page.clear_button.clicked.connect(lambda *_args: QTimer.singleShot(0, lambda: _refresh_product_state(page)))

    timer = QTimer(page)
    timer.setInterval(500)
    timer.timeout.connect(lambda: _refresh_product_state(page))
    timer.start()
    page._protect_review_product_timer = timer
    _refresh_product_state(page)
