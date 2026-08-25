from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.automatic_temp_cleanup import (
    cleanup_after_completed_save,
    prepare_managed_save,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.source_metadata import resolve_external_source


_INSTALLED = False
_NAVY = "#062B4F"
_INK = "#17384E"
_MUTED = "#61798A"
_TEAL = "#0B7180"
_GREEN = "#23824B"
_AMBER = "#A56A00"


@dataclass(frozen=True, slots=True)
class AIDestination:
    key: str
    label: str
    url: str
    delivery: str
    menu_label: str


_AI_DESTINATIONS = {
    "chatgpt": AIDestination(
        key="chatgpt",
        label="ChatGPT / GPT",
        url="https://chatgpt.com/",
        delivery="clipboard + browser",
        menu_label="ChatGPT / GPT",
    ),
    "claude": AIDestination(
        key="claude",
        label="Claude",
        url="https://claude.ai/",
        delivery="clipboard + browser",
        menu_label="Claude",
    ),
    "other": AIDestination(
        key="other",
        label="Other AI tool",
        url="",
        delivery="clipboard only",
        menu_label="Other AI tool",
    ),
}


def get_ai_destination(key: str) -> AIDestination:
    return _AI_DESTINATIONS.get(
        (key or "").strip().lower(),
        AIDestination(
            key="other",
            label="Other AI tool",
            url="",
            delivery="clipboard only",
            menu_label="Other AI tool",
        ),
    )


@dataclass(frozen=True, slots=True)
class PreflightSnapshot:
    destination: str
    delivery: str
    source: str
    account: str
    item: str
    detected: int
    protected: int
    allowed: int
    residual: int
    profile: str
    scope: str
    mode: str

    @property
    def detected_original_data_leaving(self) -> bool:
        return self.allowed > 0 or self.residual > 0

    @property
    def ready(self) -> bool:
        return not self.detected_original_data_leaving

    @property
    def source_line(self) -> str:
        parts = [part for part in (self.source, self.account, self.item) if part]
        return "  ›  ".join(parts) or "Current protected content"

    @property
    def policy_line(self) -> str:
        parts = [part for part in (self.profile, self.scope, self.mode) if part]
        return "  •  ".join(parts)


def _combo_text(page, attribute: str) -> str:
    combo = getattr(page, attribute, None)
    try:
        return str(combo.currentText() or "").strip() if combo is not None else ""
    except Exception:
        return ""


def _source_details(page: ProtectionPage) -> tuple[str, str, str]:
    external = str(getattr(page, "_external_source_name", "") or "").strip()
    supplied = dict(getattr(page, "_external_source_metadata", {}) or {})
    if external:
        try:
            canonical, metadata = resolve_external_source(page, external, supplied)
            source = str(metadata.get("provider_label", "") or "").strip()
            account = str(metadata.get("account_label", "") or "").strip()
            item = str(metadata.get("item_title", "") or "").strip()
            if not source:
                parts = [part.strip() for part in canonical.split(" • ") if part.strip()]
                source = parts[0] if parts else "Connected source"
            return source, account, item or canonical
        except Exception:
            parts = [part.strip() for part in external.split(" • ") if part.strip()]
            return (
                parts[0] if parts else "Connected source",
                parts[1] if len(parts) >= 3 else "",
                " • ".join(parts[2:] if len(parts) >= 3 else parts[1:]),
            )

    document = getattr(page, "current_document", None)
    source_path = getattr(document, "source_path", None) if document is not None else None
    if source_path is not None:
        return "Local file", "", str(getattr(source_path, "name", source_path))
    return "Pasted text", "", "Pasted text"


def build_preflight_snapshot(
    page: ProtectionPage,
    *,
    destination: str = "AI tool",
    delivery: str = "clipboard only",
    residual_findings=None,
) -> PreflightSnapshot:
    findings = tuple(getattr(page, "current_findings", ()) or ())
    result = getattr(page, "current_result", None)
    applied = tuple(getattr(result, "applied_findings", ()) or ()) if result is not None else ()

    finding_ids = {
        str(getattr(finding, "finding_id", "") or "")
        for finding in findings
        if str(getattr(finding, "finding_id", "") or "")
    }
    applied_ids = {
        str(getattr(finding, "finding_id", "") or "")
        for finding in applied
        if str(getattr(finding, "finding_id", "") or "")
    }
    detected = len(findings)
    protected = len(finding_ids & applied_ids) if finding_ids else len(applied)
    protected = min(protected, detected)
    residual = tuple(
        residual_findings
        if residual_findings is not None
        else (getattr(page, "_last_residual", ()) or ())
    )
    source, account, item = _source_details(page)

    return PreflightSnapshot(
        destination=destination,
        delivery=delivery,
        source=source,
        account=account,
        item=item,
        detected=detected,
        protected=protected,
        allowed=max(0, detected - protected),
        residual=len(residual),
        profile=_combo_text(page, "profile_combo"),
        scope=_combo_text(page, "scope_combo"),
        mode=_combo_text(page, "mode_combo"),
    )


def _run_second_scan(page: ProtectionPage):
    residual = tuple(page.service.verify_protected(page.current_result, page._current_profile()))
    page._last_residual = residual
    if residual:
        page.verification_metric.setText(f"Warning: {len(residual)} possible PII remain")
        page.verification_metric.setProperty("warning", True)
    else:
        page.verification_metric.setText("Verified: no remaining PII")
        page.verification_metric.setProperty("warning", False)
    page.verification_metric.style().unpolish(page.verification_metric)
    page.verification_metric.style().polish(page.verification_metric)
    return residual


def _metric_card(title: str, value: int, note: str, accent: str) -> QFrame:
    card = QFrame(objectName="PreflightMetric")
    card.setStyleSheet(
        "QFrame#PreflightMetric{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:10px;}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(13, 11, 13, 11)
    layout.setSpacing(3)
    number = QLabel(str(value))
    number.setStyleSheet(f"color:{accent};font-size:23px;font-weight:950;")
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{_INK};font-size:10px;font-weight:900;")
    detail = QLabel(note)
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{_MUTED};font-size:8px;")
    layout.addWidget(number)
    layout.addWidget(heading)
    layout.addWidget(detail)
    return card


def _value_row(label: str, value: str, *, strong: bool = False) -> QFrame:
    frame = QFrame(objectName="PreflightValueRow")
    frame.setStyleSheet(
        "QFrame#PreflightValueRow{background:#FFFFFF;border:1px solid #E1E8ED;border-radius:9px;}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(12, 9, 12, 9)
    row.setSpacing(12)
    left = QLabel(label)
    left.setStyleSheet(f"color:{_MUTED};font-size:9px;font-weight:800;")
    right = QLabel(value)
    right.setWordWrap(True)
    right.setStyleSheet(
        f"color:{_NAVY};font-size:10px;font-weight:{'900' if strong else '750'};"
    )
    row.addWidget(left)
    row.addStretch(1)
    row.addWidget(right, 2)
    return frame


class PrivacyPreflightDialog(QDialog):
    def __init__(self, snapshot: PreflightSnapshot, parent=None) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self.setWindowTitle("AI Privacy Preflight")
        self.resize(830, 690)
        self.setMinimumSize(740, 630)
        self.setModal(True)
        self.setStyleSheet("QDialog{background:#F7FAFC;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        shield = QLabel()
        shield.setFixedSize(48, 48)
        shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield.setPixmap(icon("protect", color=_TEAL, size=29).pixmap(29, 29))
        shield.setStyleSheet(
            "background:#EAF6F6;border:1px solid #BFE0E2;border-radius:12px;"
        )
        titles = QVBoxLayout()
        title = QLabel("AI Privacy Preflight")
        title.setStyleSheet(f"color:{_NAVY};font-size:24px;font-weight:950;")
        subtitle = QLabel(
            "Final local privacy check before the protected copy is saved and handed to an AI tool."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(titles, 1)
        local = QLabel("LOCAL-FIRST")
        local.setStyleSheet(
            "background:#EAF6F6;color:#0B7180;border:1px solid #BFE0E2;"
            "border-radius:9px;padding:5px 9px;font-size:8px;font-weight:900;"
        )
        header.addWidget(local, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        safe = snapshot.ready
        status_color = _GREEN if safe else _AMBER
        status = QFrame(objectName="PreflightStatus")
        status.setStyleSheet(
            "QFrame#PreflightStatus{"
            f"background:{'#EAF7EF' if safe else '#FFF5E5'};"
            f"border:1px solid {'#BFE4CD' if safe else '#F0D3A0'};"
            "border-radius:11px;}"
        )
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(14, 11, 14, 11)
        status_icon = QLabel()
        status_icon.setPixmap(
            icon("check" if safe else "protect", color=status_color, size=22).pixmap(22, 22)
        )
        status_text = QVBoxLayout()
        status_title = QLabel("READY FOR AI" if safe else "REVIEW BEFORE AI")
        status_title.setStyleSheet(f"color:{status_color};font-size:12px;font-weight:950;")
        if safe:
            message = (
                "All selected findings are protected and the second scan found no remaining "
                "detected sensitive data."
            )
        elif snapshot.allowed and snapshot.residual:
            message = (
                "Some detected items are left visible, and the second scan still found "
                "possible sensitive data."
            )
        elif snapshot.allowed:
            message = (
                "Some detected items are intentionally left visible in the content that "
                "will be copied."
            )
        else:
            message = (
                "The second scan still found possible sensitive data in the protected result."
            )
        status_message = QLabel(message)
        status_message.setWordWrap(True)
        status_message.setStyleSheet(f"color:{_INK};font-size:9px;")
        status_text.addWidget(status_title)
        status_text.addWidget(status_message)
        status_layout.addWidget(status_icon, alignment=Qt.AlignmentFlag.AlignTop)
        status_layout.addLayout(status_text, 1)
        root.addWidget(status)

        path = QFrame(objectName="PreflightPath")
        path.setStyleSheet(
            "QFrame#PreflightPath{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
        )
        path_layout = QVBoxLayout(path)
        path_layout.setContentsMargins(14, 11, 14, 11)
        path_layout.setSpacing(5)
        path_title = QLabel("PROTECTED DATA PATH")
        path_title.setStyleSheet(f"color:{_TEAL};font-size:8px;font-weight:950;")
        source = QLabel(snapshot.source_line)
        source.setWordWrap(True)
        source.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source.setStyleSheet(f"color:{_NAVY};font-size:11px;font-weight:900;")
        arrow_one = QLabel("↓")
        arrow_one.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_one.setStyleSheet(f"color:{_TEAL};font-size:16px;font-weight:900;")
        local_copy = QLabel("PrivacyGate local Library  •  protected copy")
        local_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_copy.setStyleSheet(
            "background:#F0F7F8;color:#0B7180;border:1px solid #CDE4E6;"
            "border-radius:8px;padding:5px 9px;font-size:9px;font-weight:850;"
        )
        arrow_two = QLabel("↓")
        arrow_two.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_two.setStyleSheet(f"color:{_TEAL};font-size:16px;font-weight:900;")
        destination = QLabel(f"{snapshot.destination}  —  {snapshot.delivery}")
        destination.setAlignment(Qt.AlignmentFlag.AlignCenter)
        destination.setStyleSheet(f"color:{_NAVY};font-size:11px;font-weight:900;")
        path_layout.addWidget(path_title)
        path_layout.addWidget(source)
        path_layout.addWidget(arrow_one)
        path_layout.addWidget(local_copy)
        path_layout.addWidget(arrow_two)
        path_layout.addWidget(destination)
        root.addWidget(path)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(9)
        metrics.addWidget(
            _metric_card(
                "Detected",
                snapshot.detected,
                "Sensitive items found in the source.",
                _NAVY,
            ),
            0,
            0,
        )
        metrics.addWidget(
            _metric_card(
                "Protected",
                snapshot.protected,
                "Items replaced by the selected protection mode.",
                _TEAL,
            ),
            0,
            1,
        )
        metrics.addWidget(
            _metric_card(
                "Allowed by you",
                snapshot.allowed,
                "Detected values intentionally left visible.",
                _AMBER if snapshot.allowed else _GREEN,
            ),
            0,
            2,
        )
        metrics.addWidget(
            _metric_card(
                "Second-scan residual",
                snapshot.residual,
                "Possible sensitive items still detected after protection.",
                _AMBER if snapshot.residual else _GREEN,
            ),
            0,
            3,
        )
        root.addLayout(metrics)

        exposure = (
            "YES — review current choices"
            if snapshot.detected_original_data_leaving
            else "NO detected original values"
        )
        root.addWidget(
            _value_row(
                "Detected sensitive data leaving this PC",
                exposure,
                strong=True,
            )
        )
        root.addWidget(
            _value_row(
                "Protection policy",
                snapshot.policy_line or "Current PrivacyGate settings",
            )
        )
        root.addWidget(
            _value_row(
                "Local Library save",
                "Required — after you continue, PrivacyGate will ask how you want to name the protected copy.",
                strong=True,
            )
        )
        handoff = (
            f"Save the protected copy locally, copy only the protected result, then open "
            f"{snapshot.destination}. Nothing is submitted automatically."
            if "browser" in snapshot.delivery
            else (
                "Save the protected copy locally and copy only the protected result to the "
                "clipboard. You can then paste it into the AI tool you choose."
            )
        )
        root.addWidget(_value_row("AI handoff", handoff))

        actions = QHBoxLayout()
        actions.setSpacing(9)
        review = QPushButton("Back to review")
        review.setMinimumHeight(40)
        review.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C8D7E0;"
            "border-radius:9px;padding:8px 15px;font-weight:850;}"
            "QPushButton:hover{background:#F1F7F9;}"
        )

        if "browser" in snapshot.delivery:
            proceed_text = (
                f"Save & continue to {snapshot.destination}"
                if safe
                else f"Save & continue anyway to {snapshot.destination}"
            )
        else:
            proceed_text = (
                "Save & copy for AI"
                if safe
                else "Save & copy anyway for AI"
            )
        proceed = QPushButton(proceed_text)
        proceed.setMinimumHeight(40)
        proceed.setIcon(icon("external", color="#FFFFFF", size=18))
        proceed.setStyleSheet(
            (
                "QPushButton{background:#0B8390;color:#FFFFFF;border:1px solid #0B8390;"
                "border-radius:9px;padding:8px 16px;font-weight:900;}"
                "QPushButton:hover{background:#096B76;}"
            )
            if safe
            else (
                "QPushButton{background:#B7770A;color:#FFFFFF;border:1px solid #B7770A;"
                "border-radius:9px;padding:8px 16px;font-weight:900;}"
                "QPushButton:hover{background:#9B6508;}"
            )
        )
        actions.addStretch(1)
        actions.addWidget(review)
        actions.addWidget(proceed)
        root.addLayout(actions)

        review.clicked.connect(self.reject)
        proceed.clicked.connect(self.accept)


def _status_message(page: ProtectionPage, destination: AIDestination, title: str) -> None:
    if destination.url:
        message = (
            f'Saved "{title}" to Library — protected text copied; '
            f"{destination.label} opened"
        )
    else:
        message = (
            f'Saved "{title}" to Library — protected text copied for your AI tool'
        )
    try:
        page.window().statusBar().showMessage(message, 9000)
    except Exception:
        pass


def _complete_ai_handoff(page: ProtectionPage, destination: AIDestination) -> None:
    if not page.current_result:
        return

    residual = _run_second_scan(page)
    snapshot = build_preflight_snapshot(
        page,
        destination=destination.label,
        delivery=destination.delivery,
        residual_findings=residual,
    )
    dialog = PrivacyPreflightDialog(snapshot, page)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    # Reuse exactly the same Library save path as Save + Copy / Save + Download.
    # This preserves connector/account provenance and prompts the user for a name.
    prepare_managed_save(page)
    document = page._save_to_library()
    if document is None:
        return

    page._managed_temp_saved_ok = True
    QApplication.clipboard().setText(page.current_result.combined_text)

    if destination.url:
        QDesktopServices.openUrl(QUrl(destination.url))

    # The protected copy is now durable in Library, so a PrivacyGate-managed
    # connector working file can follow the same immediate cleanup policy as
    # Save + Copy / Save + Download.
    cleanup_after_completed_save(page)
    _status_message(page, destination, document.title)


def install_privacy_preflight() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def handoff_to_ai(self: ProtectionPage, destination_key: str) -> None:
        _complete_ai_handoff(self, get_ai_destination(destination_key))

    def copy_and_open_chatgpt(self: ProtectionPage) -> None:
        handoff_to_ai(self, "chatgpt")

    def copy_and_open_claude(self: ProtectionPage) -> None:
        handoff_to_ai(self, "claude")

    def copy_for_other_ai(self: ProtectionPage) -> None:
        handoff_to_ai(self, "other")

    def build_ai_menu(self: ProtectionPage):
        from PySide6.QtWidgets import QMenu

        try:
            self.ai_button.setToolTip(
                "Run Privacy Preflight, save the protected copy to the local Library, "
                "then copy it for ChatGPT, Claude or another AI tool."
            )
        except Exception:
            pass

        menu = QMenu(self)
        menu.addSection("AI destination")

        chatgpt = menu.addAction(icon("external", color=_TEAL, size=17), "ChatGPT / GPT")
        chatgpt.setToolTip("Privacy Preflight → save locally → copy protected text → open ChatGPT")
        chatgpt.triggered.connect(lambda _checked=False: copy_and_open_chatgpt(self))

        claude = menu.addAction(icon("external", color=_TEAL, size=17), "Claude")
        claude.setToolTip("Privacy Preflight → save locally → copy protected text → open Claude")
        claude.triggered.connect(lambda _checked=False: copy_and_open_claude(self))

        other = menu.addAction(icon("copy", color=_TEAL, size=17), "Other AI tool")
        other.setToolTip("Privacy Preflight → save locally → copy protected text")
        other.triggered.connect(lambda _checked=False: copy_for_other_ai(self))

        menu.addSeparator()
        connections = menu.addAction("Configure AI connections…")
        connections.triggered.connect(self.open_connections.emit)
        return menu

    ProtectionPage._privacygate_ai_handoff = handoff_to_ai  # type: ignore[attr-defined]
    ProtectionPage._copy_and_open_chatgpt = copy_and_open_chatgpt  # type: ignore[method-assign]
    ProtectionPage._copy_and_open_claude = copy_and_open_claude  # type: ignore[attr-defined]
    ProtectionPage._copy_for_other_ai = copy_for_other_ai  # type: ignore[attr-defined]
    ProtectionPage._build_ai_menu = build_ai_menu  # type: ignore[method-assign]
