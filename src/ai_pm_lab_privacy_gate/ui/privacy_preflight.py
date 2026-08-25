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
class PreflightSnapshot:
    destination: str
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
    destination: str = "ChatGPT",
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
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(3)
    number = QLabel(str(value))
    number.setStyleSheet(f"color:{accent};font-size:22px;font-weight:950;")
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{_INK};font-size:10px;font-weight:850;")
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
        "QFrame#PreflightValueRow{background:#FFFFFF;border:1px solid #E1E8ED;border-radius:8px;}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(10, 8, 10, 8)
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
        self.setWindowTitle("Privacy Preflight")
        self.resize(790, 650)
        self.setMinimumSize(700, 590)
        self.setModal(True)
        self.setStyleSheet("QDialog{background:#F7FAFC;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        shield = QLabel()
        shield.setFixedSize(46, 46)
        shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield.setPixmap(icon("protect", color=_TEAL, size=28).pixmap(28, 28))
        shield.setStyleSheet("background:#EAF6F6;border:1px solid #BFE0E2;border-radius:11px;")
        titles = QVBoxLayout()
        title = QLabel("Privacy Preflight")
        title.setStyleSheet(f"color:{_NAVY};font-size:23px;font-weight:950;")
        subtitle = QLabel("Final local check before protected content leaves this PC.")
        subtitle.setStyleSheet(f"color:{_MUTED};font-size:10px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(titles, 1)
        local = QLabel("LOCAL CHECK")
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
            f"border:1px solid {'#BFE4CD' if safe else '#F0D3A0'};border-radius:11px;}}"
        )
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(13, 11, 13, 11)
        status_icon = QLabel()
        status_icon.setPixmap(
            icon("check" if safe else "protect", color=status_color, size=22).pixmap(22, 22)
        )
        status_text = QVBoxLayout()
        status_title = QLabel("READY TO OPEN SAFELY" if safe else "REVIEW BEFORE OPENING")
        status_title.setStyleSheet(f"color:{status_color};font-size:12px;font-weight:950;")
        if safe:
            message = "All selected findings are protected and the second scan found no remaining detected sensitive data."
        elif snapshot.allowed and snapshot.residual:
            message = "Some detected items are left visible, and the second scan still found possible sensitive data."
        elif snapshot.allowed:
            message = "Some detected items are intentionally left visible in the content that will be copied."
        else:
            message = "The second scan still found possible sensitive data in the protected result."
        status_message = QLabel(message)
        status_message.setWordWrap(True)
        status_message.setStyleSheet(f"color:{_INK};font-size:9px;")
        status_text.addWidget(status_title)
        status_text.addWidget(status_message)
        status_layout.addWidget(status_icon, alignment=Qt.AlignmentFlag.AlignTop)
        status_layout.addLayout(status_text, 1)
        root.addWidget(status)

        path = QFrame(objectName="PreflightPath")
        path.setStyleSheet("QFrame#PreflightPath{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}")
        path_layout = QVBoxLayout(path)
        path_layout.setContentsMargins(13, 11, 13, 11)
        path_layout.setSpacing(6)
        path_title = QLabel("DATA PATH")
        path_title.setStyleSheet(f"color:{_TEAL};font-size:8px;font-weight:950;")
        source = QLabel(snapshot.source_line)
        source.setWordWrap(True)
        source.setStyleSheet(f"color:{_NAVY};font-size:11px;font-weight:900;")
        arrow = QLabel("↓")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setStyleSheet(f"color:{_TEAL};font-size:18px;font-weight:900;")
        destination = QLabel(f"{snapshot.destination}  —  clipboard + browser")
        destination.setAlignment(Qt.AlignmentFlag.AlignCenter)
        destination.setStyleSheet(f"color:{_NAVY};font-size:11px;font-weight:900;")
        path_layout.addWidget(path_title)
        path_layout.addWidget(source)
        path_layout.addWidget(arrow)
        path_layout.addWidget(destination)
        root.addWidget(path)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(9)
        metrics.addWidget(_metric_card("Detected", snapshot.detected, "Sensitive items found in the source.", _NAVY), 0, 0)
        metrics.addWidget(_metric_card("Protected", snapshot.protected, "Items replaced by the selected mode.", _TEAL), 0, 1)
        metrics.addWidget(_metric_card("Allowed by you", snapshot.allowed, "Detected values intentionally left visible.", _AMBER if snapshot.allowed else _GREEN), 0, 2)
        metrics.addWidget(_metric_card("Second-scan residual", snapshot.residual, "Possible sensitive items still detected after protection.", _AMBER if snapshot.residual else _GREEN), 0, 3)
        root.addLayout(metrics)

        exposure = "YES — review current choices" if snapshot.detected_original_data_leaving else "NO detected original values"
        root.addWidget(_value_row("Detected sensitive data leaving this PC", exposure, strong=True))
        root.addWidget(_value_row("Protection policy", snapshot.policy_line or "Current PrivacyGate settings"))
        root.addWidget(
            _value_row(
                "What PrivacyGate will do",
                "Copy only the protected result to the clipboard and open ChatGPT. It will not submit anything automatically.",
            )
        )

        actions = QHBoxLayout()
        review = QPushButton("Back to review")
        review.setMinimumHeight(38)
        review.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C8D7E0;border-radius:9px;"
            "padding:7px 14px;font-weight:850;}QPushButton:hover{background:#F1F7F9;}"
        )
        proceed = QPushButton("Copy protected text & open ChatGPT" if safe else "Continue with current choices")
        proceed.setMinimumHeight(38)
        proceed.setIcon(icon("external", color="#FFFFFF", size=18))
        proceed.setStyleSheet(
            (
                "QPushButton{background:#0B8390;color:#FFFFFF;border:1px solid #0B8390;border-radius:9px;"
                "padding:7px 15px;font-weight:900;}QPushButton:hover{background:#096B76;}"
            )
            if safe
            else (
                "QPushButton{background:#B7770A;color:#FFFFFF;border:1px solid #B7770A;border-radius:9px;"
                "padding:7px 15px;font-weight:900;}QPushButton:hover{background:#9B6508;}"
            )
        )
        actions.addStretch(1)
        actions.addWidget(review)
        actions.addWidget(proceed)
        root.addLayout(actions)
        review.clicked.connect(self.reject)
        proceed.clicked.connect(self.accept)


def install_privacy_preflight() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def copy_and_open_chatgpt(self: ProtectionPage) -> None:
        if not self.current_result:
            return

        # The same local second-scan engine used by copy/download is run here,
        # but its result is presented inside one consolidated Preflight dialog.
        residual = _run_second_scan(self)
        snapshot = build_preflight_snapshot(
            self,
            destination="ChatGPT",
            residual_findings=residual,
        )
        dialog = PrivacyPreflightDialog(snapshot, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Preserve the existing manual handoff exactly: clipboard + browser;
        # PrivacyGate never auto-submits the content to ChatGPT.
        QApplication.clipboard().setText(self.current_result.combined_text)
        QDesktopServices.openUrl(QUrl("https://chatgpt.com/"))
        try:
            self.window().statusBar().showMessage(
                "Privacy Preflight complete — protected text copied; ChatGPT opened",
                8000,
            )
        except Exception:
            pass

    ProtectionPage._copy_and_open_chatgpt = copy_and_open_chatgpt  # type: ignore[method-assign]
