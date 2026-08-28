from __future__ import annotations

"""Product-grade manual sensitive-value flow with local encrypted persistence.

No document text, exact custom value, file path or rule is sent to Supabase. Exact
values are protected with the existing LocalProtector and keyed by a SHA-256
fingerprint derived from the already-local extracted document content. Re-scanning
the same content automatically reapplies the user's local manual rules.
"""

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import BLUE, BLUE_SOFT, BORDER, INK, MUTED
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import PrivacyGateProductDialog
from ai_pm_lab_privacy_gate.ui.protection_page import _manual_findings_for_text


_CATEGORIES = (
    ("Person", "PERSON"),
    ("Email", "EMAIL_ADDRESS"),
    ("Phone", "PHONE_NUMBER"),
    ("Location", "LOCATION"),
    ("Street address", "STREET_ADDRESS"),
    ("SSN", "US_SSN"),
    ("Bank account", "US_BANK_NUMBER"),
    ("Money amount", "MONEY_AMOUNT"),
    ("Merchant", "MERCHANT"),
    ("Counterparty", "COUNTERPARTY"),
    ("Transaction ID", "TRANSACTION_ID"),
    ("Property identifier", "PROPERTY_IDENTIFIER"),
    ("Custom label", "CUSTOM"),
)


def _normalize_custom_label(value: str) -> str:
    cleaned = "_".join(part for part in value.strip().upper().replace("-", " ").split() if part)
    safe = "".join(character for character in cleaned if character.isalnum() or character == "_")
    return f"CUSTOM_{safe}" if safe else "CUSTOM"


def _document_fingerprint(document) -> str:
    digest = hashlib.sha256()
    digest.update(str(getattr(document, "source_kind", "") or "").encode("utf-8"))
    for page in tuple(getattr(document, "pages", ()) or ()):
        digest.update(b"\x1e")
        digest.update(str(getattr(page, "page_number", "") or "").encode("ascii", errors="ignore"))
        digest.update(b"\x1f")
        digest.update(str(getattr(page, "text", "") or "").encode("utf-8", errors="replace"))
    return digest.hexdigest()


class LocalManualSensitiveStore:
    """Tiny encrypted sidecar for user-defined sensitive-value rules."""

    def __init__(self, data_dir: Path) -> None:
        self.directory = Path(data_dir) / "LocalOverrides"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "manual_sensitive_rules.json"
        self.protector = LocalProtector()

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "documents": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"version": 1, "documents": {}}
        if not isinstance(payload, dict):
            return {"version": 1, "documents": {}}
        documents = payload.get("documents")
        if not isinstance(documents, dict):
            payload["documents"] = {}
        payload["version"] = 1
        return payload

    def _write(self, payload: dict) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def list_rules(self, fingerprint: str) -> tuple[tuple[str, str], ...]:
        payload = self._read()
        record = payload.get("documents", {}).get(fingerprint, {})
        rows = record.get("rules", ()) if isinstance(record, dict) else ()
        values: list[tuple[str, str]] = []
        for row in rows if isinstance(rows, list) else ():
            try:
                protected = base64.b64decode(str(row.get("protected_value") or ""), validate=True)
                exact_text = self.protector.unprotect(protected)
                entity_type = str(row.get("entity_type") or "CUSTOM")
            except Exception:
                continue
            if exact_text and entity_type:
                values.append((exact_text, entity_type))
        return tuple(values)

    def add_rule(self, fingerprint: str, *, source_kind: str, exact_text: str, entity_type: str) -> bool:
        existing = self.list_rules(fingerprint)
        normalized = exact_text.strip()
        if any(text == normalized and category == entity_type for text, category in existing):
            return False

        payload = self._read()
        documents = payload.setdefault("documents", {})
        record = documents.setdefault(
            fingerprint,
            {"source_kind": source_kind, "rules": []},
        )
        rules = record.setdefault("rules", [])
        protected = self.protector.protect(normalized)
        rules.append(
            {
                "entity_type": entity_type,
                "protected_value": base64.b64encode(protected).decode("ascii"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        # Deliberately do not persist path, filename, document title, extracted text,
        # account, workspace, organization or any cloud identifier.
        record["source_kind"] = source_kind
        self._write(payload)
        return True


class AddSensitiveValueDialog(PrivacyGateProductDialog):
    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            title="Add missed sensitive value",
            subtitle="Manually protect exact text the automatic detector did not catch. The safe copy will be regenerated immediately.",
            icon_name="protect",
            width=690,
        )

        guide = QFrame(objectName="ManualSensitiveGuide")
        guide.setStyleSheet(
            "QFrame#ManualSensitiveGuide{background:#F8FAFC;border:1px solid #EAECF0;border-radius:11px;}"
        )
        guide_box = QVBoxLayout(guide)
        guide_box.setContentsMargins(12, 10, 12, 10)
        guide_box.setSpacing(5)
        heading = QLabel("For PDF, Word, Excel or PowerPoint")
        heading.setStyleSheet(f"color:{INK};font-size:9px;font-weight:900;border:none;")
        guide_box.addWidget(heading)
        for number, text in (
            ("1", "Open Protected text or use the visible document to identify the value you want to hide."),
            ("2", "Copy the exact word or phrase as it appears in the document and paste it below."),
            ("3", "Choose what the value represents. PrivacyGate finds every exact occurrence and regenerates the protected copy."),
        ):
            row = QHBoxLayout()
            badge = QLabel(number)
            badge.setFixedSize(21, 21)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #C7D7FE;border-radius:10px;"
                "font-size:7px;font-weight:950;"
            )
            copy = QLabel(text)
            copy.setWordWrap(True)
            copy.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(copy, 1)
            guide_box.addLayout(row)
        self.body.addWidget(guide)

        self.exact_text = QPlainTextEdit()
        self.exact_text.setPlaceholderText("Paste the exact text to protect…")
        self.exact_text.setMinimumHeight(92)
        self.exact_text.setMaximumHeight(130)
        self.exact_text.setStyleSheet(
            "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:10px;padding:9px 10px;font-size:10px;}"
            f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
        )
        self.add_field(
            "Exact text to protect",
            self.exact_text,
            "Match is case-insensitive and tolerates normal whitespace differences, but the wording must exist in the extracted local document text.",
        )

        self.category = QComboBox()
        for label, value in _CATEGORIES:
            self.category.addItem(label, value)
        self.add_field(
            "Category / label",
            self.category,
            "The selected category controls the placeholder label and uses the same category color in Review and the protected preview.",
        )

        self.custom_label = QLineEdit()
        self.custom_label.setPlaceholderText("e.g. Client name, Building code, Internal project")
        self.custom_label.setEnabled(False)
        self.add_field(
            "Custom label (only when Custom label is selected)",
            self.custom_label,
            "A custom label is normalized locally and is never uploaded.",
        )
        self.category.currentIndexChanged.connect(self._sync_custom)

        self.add_notice(
            "Saved locally on this device: the exact value is encrypted with PrivacyGate's existing local protector and associated only with a content fingerprint. No filename, path, document text, workspace ID or custom value is sent to Supabase.",
            privacy=True,
        )
        self.add_notice(
            "After you add the value, it appears as a Manual tag in Detected items and the existing protection engine regenerates the protected document from the updated finding set."
        )
        self.primary_button, _secondary = self.add_actions(
            primary_text="Add & regenerate",
            primary_callback=self._validate_and_accept,
        )
        self.exact_text.textChanged.connect(self._sync_action)
        self.custom_label.textChanged.connect(self._sync_action)
        self._sync_action()

    def _sync_custom(self, *_args) -> None:
        custom = str(self.category.currentData() or "") == "CUSTOM"
        self.custom_label.setEnabled(custom)
        self._sync_action()

    def _sync_action(self) -> None:
        exact = bool(self.exact_text.toPlainText().strip())
        custom_ok = (
            str(self.category.currentData() or "") != "CUSTOM"
            or bool(self.custom_label.text().strip())
        )
        self.primary_button.setEnabled(exact and custom_ok)

    def _validate_and_accept(self) -> None:
        if not self.exact_text.toPlainText().strip():
            return
        if str(self.category.currentData() or "") == "CUSTOM" and not self.custom_label.text().strip():
            self.custom_label.setFocus()
            return
        self.accept()

    @property
    def value(self) -> str:
        return self.exact_text.toPlainText().strip()

    @property
    def entity_type(self) -> str:
        value = str(self.category.currentData() or "CUSTOM")
        return _normalize_custom_label(self.custom_label.text()) if value == "CUSTOM" else value


class ManualValueResultDialog(PrivacyGateProductDialog):
    def __init__(self, parent, *, title: str, detail: str, success: bool) -> None:
        super().__init__(
            parent,
            title=title,
            subtitle=detail,
            icon_name="check" if success else "protect",
            width=590,
        )
        self.add_notice(
            "The local manual-rule store never writes document content or exact custom values to Supabase.",
            privacy=True,
        )
        self.add_actions(primary_text="Done", primary_callback=self.accept, secondary_text="Close")


def _merge_manual_findings(page, rules: tuple[tuple[str, str], ...]) -> int:
    if page.current_document is None:
        return 0
    existing_ids = {finding.finding_id for finding in tuple(page.current_findings or ())}
    additions = []
    for exact_text, entity_type in rules:
        for finding in _manual_findings_for_text(page.current_document, exact_text, entity_type):
            if finding.finding_id not in existing_ids:
                additions.append(finding)
                existing_ids.add(finding.finding_id)
    if additions:
        page.current_findings = tuple(page.current_findings) + tuple(additions)
    return len(additions)


def _reapply_saved_rules(page) -> int:
    if page.current_document is None:
        return 0
    store = getattr(page, "_protect_manual_sensitive_store", None)
    if store is None:
        return 0
    fingerprint = _document_fingerprint(page.current_document)
    rules = store.list_rules(fingerprint)
    added = _merge_manual_findings(page, rules)
    if added:
        page._populate_findings()
        page._refresh_preview()
    return added


def _add_manual_sensitive(page) -> None:
    if page.current_document is None:
        QMessageBox.information(
            page,
            "Scan a source first",
            "Add a document or pasted text and run Scan & Protect before adding a missed sensitive value.",
        )
        return

    dialog = AddSensitiveValueDialog(page)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    exact_text = dialog.value
    entity_type = dialog.entity_type
    additions = _manual_findings_for_text(page.current_document, exact_text, entity_type)
    if not additions:
        ManualValueResultDialog(
            page,
            title="Exact text not found",
            detail="PrivacyGate could not find that wording in the locally extracted document text. Copy the exact word or phrase from Protected text or the source and try again.",
            success=False,
        ).exec()
        return

    store = page._protect_manual_sensitive_store
    fingerprint = _document_fingerprint(page.current_document)
    stored_new = store.add_rule(
        fingerprint,
        source_kind=str(getattr(page.current_document, "source_kind", "") or ""),
        exact_text=exact_text,
        entity_type=entity_type,
    )

    existing_ids = {finding.finding_id for finding in tuple(page.current_findings or ())}
    new_findings = tuple(finding for finding in additions if finding.finding_id not in existing_ids)
    if new_findings:
        page.current_findings = tuple(page.current_findings) + new_findings

    # Same existing regeneration path used by checkbox changes: no parallel
    # protection engine and no duplicate preview document are introduced.
    page._populate_findings()
    page._refresh_preview()
    if getattr(page, "_redesign_review_metric", None) is not None:
        page._redesign_review_metric.setText(
            f"Manual value protected · {len(additions)} occurrence(s)"
        )

    ManualValueResultDialog(
        page,
        title="Sensitive value added",
        detail=(
            f"{len(additions)} occurrence(s) were added to Review and the protected copy was regenerated. "
            + ("The encrypted local rule will be reapplied when this same document content is scanned again." if stored_new else "This encrypted local rule was already saved for the document.")
        ),
        success=True,
    ).exec()


def apply_mockup_protect_manual_sensitive_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_manual_sensitive", False)):
        return
    page._protect_2026_manual_sensitive = True

    data_dir = Path(page.library.data_dir)
    page._protect_manual_sensitive_store = LocalManualSensitiveStore(data_dir)

    legacy_add = page._add_sensitive_item

    def add_sensitive(self) -> None:
        _add_manual_sensitive(self)

    page._add_sensitive_item = MethodType(add_sensitive, page)
    try:
        page.add_sensitive_button.clicked.disconnect(legacy_add)
    except (RuntimeError, TypeError):
        try:
            page.add_sensitive_button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
    page.add_sensitive_button.clicked.connect(page._add_sensitive_item)

    previous_analysis_ready = page._analysis_ready

    def analysis_ready_with_local_rules(self, payload: object) -> None:
        previous_analysis_ready(payload)
        added = _reapply_saved_rules(self)
        if added and getattr(self, "_redesign_review_metric", None) is not None:
            self._redesign_review_metric.setText(
                f"Protected copy ready · {added} saved manual finding(s) reapplied"
            )

    page._analysis_ready = MethodType(analysis_ready_with_local_rules, page)
