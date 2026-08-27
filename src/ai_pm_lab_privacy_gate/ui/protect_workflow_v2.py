from __future__ import annotations

from dataclasses import dataclass
from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


_NAVY = "#062B4F"
_INK = "#17384E"
_MUTED = "#61798A"
_TEAL = "#0B7180"
_GREEN = "#23824B"
_AMBER = "#A56A00"
_RED = "#A43D3D"


@dataclass(frozen=True, slots=True)
class SourcePrivacyCheck:
    key: str
    label: str
    detected: int
    protected: int
    residual: int = 0

    @property
    def allowed(self) -> int:
        return max(0, self.detected - self.protected)


@dataclass(frozen=True, slots=True)
class PrivacyCheckSummary:
    sources: tuple[SourcePrivacyCheck, ...]
    detected: int
    protected: int
    allowed: int
    residual: int
    risk: str
    ready: bool
    reason: str


def build_privacy_check_summary(
    sources: tuple[SourcePrivacyCheck, ...],
) -> PrivacyCheckSummary:
    detected = sum(item.detected for item in sources)
    protected = sum(item.protected for item in sources)
    allowed = sum(item.allowed for item in sources)
    residual = sum(item.residual for item in sources)

    if residual:
        risk = "HIGH"
        ready = False
        reason = (
            f"{residual} possible sensitive item(s) were still detected in the protected result."
        )
    elif allowed:
        risk = "MEDIUM"
        ready = False
        reason = (
            f"{allowed} detected item(s) are intentionally still visible in the protected result."
        )
    else:
        risk = "LOW"
        ready = True
        reason = (
            "All selected findings are protected and the local second scan found no residual sensitive data."
            if detected
            else "No sensitive data was detected in the current source set."
        )

    return PrivacyCheckSummary(
        sources=sources,
        detected=detected,
        protected=protected,
        allowed=allowed,
        residual=residual,
        risk=risk,
        ready=ready,
        reason=reason,
    )


def _metric_card(title: str, value: str, note: str) -> QFrame:
    card = QFrame(objectName="ProtectPrivacyMetric")
    card.setStyleSheet(
        "QFrame#ProtectPrivacyMetric{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:10px;}"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(12, 10, 12, 10)
    box.setSpacing(3)
    number = QLabel(value)
    number.setStyleSheet(f"color:{_NAVY};font-size:21px;font-weight:950;")
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{_INK};font-size:9px;font-weight:900;")
    detail = QLabel(note)
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{_MUTED};font-size:8px;")
    box.addWidget(number)
    box.addWidget(heading)
    box.addWidget(detail)
    return card


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _source_label(page, key: str, payload: dict) -> str:
    label = str(payload.get("label") or "").strip()
    if label:
        return label
    document = payload.get("document")
    source_path = getattr(document, "source_path", None) if document is not None else None
    if source_path is not None:
        return str(getattr(source_path, "name", source_path))
    if key == "text":
        return "Pasted text"
    if key == "gmail_body":
        return "Email body"
    return key.replace("_", " ").strip().title() or "Source"


def _protection_sources(page) -> tuple[dict, ...]:
    gmail_results = dict(getattr(page, "_gmail_component_results", {}) or {})
    gmail_sources = dict(getattr(page, "_gmail_component_sources", {}) or {})
    if gmail_results:
        order = [
            str(item.get("key") or "")
            for item in tuple(getattr(page, "_gmail_component_manifest", ()) or ())
            if str(item.get("key") or "") in gmail_results
        ]
        for key in gmail_results:
            if key not in order:
                order.append(key)
        return tuple(
            {
                "key": key,
                "label": _source_label(page, key, gmail_sources.get(key, {})),
                "findings": tuple(gmail_sources.get(key, {}).get("findings") or ()),
                "result": gmail_results[key],
            }
            for key in order
        )

    session_results = dict(getattr(page, "_protect_session_results", {}) or {})
    session_sources = dict(getattr(page, "_protect_session_sources", {}) or {})
    if session_results:
        order = [key for key in ("document", "text") if key in session_results]
        order.extend(key for key in session_results if key not in order)
        return tuple(
            {
                "key": key,
                "label": _source_label(page, key, session_sources.get(key, {})),
                "findings": tuple(session_sources.get(key, {}).get("findings") or ()),
                "result": session_results[key],
            }
            for key in order
        )

    result = getattr(page, "current_result", None)
    if result is None:
        return ()
    document = getattr(page, "current_document", None)
    source_path = getattr(document, "source_path", None) if document is not None else None
    metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
    label = str(metadata.get("item_title") or "").strip()
    if not label and source_path is not None:
        label = str(getattr(source_path, "name", source_path))
    if not label:
        label = "Pasted text" if getattr(document, "source_kind", "") == "text" else "Current source"
    return (
        {
            "key": "source",
            "label": label,
            "findings": tuple(getattr(page, "current_findings", ()) or ()),
            "result": result,
        },
    )


def _ensure_privacy_check_ui(page) -> None:
    if getattr(page, "_privacy_check_tab", None) is not None:
        return

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea{background:#F8FBFC;border:0;}")
    host = QWidget()
    root = QVBoxLayout(host)
    root.setContentsMargins(16, 15, 16, 15)
    root.setSpacing(12)
    scroll.setWidget(host)

    header = QHBoxLayout()
    shield = QLabel()
    shield.setFixedSize(42, 42)
    shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
    shield.setPixmap(icon("protect", color=_TEAL, size=24).pixmap(24, 24))
    shield.setStyleSheet(
        "background:#EAF6F6;border:1px solid #BFE0E2;border-radius:11px;"
    )
    titles = QVBoxLayout()
    title = QLabel("Privacy Check")
    title.setStyleSheet(f"color:{_NAVY};font-size:20px;font-weight:950;")
    subtitle = QLabel(
        "Local second scan of the protected result for this document/session. Nothing is sent anywhere."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{_MUTED};font-size:9px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
    header.addLayout(titles, 1)
    local = QLabel("LOCAL CHECK")
    local.setStyleSheet(
        "background:#EAF6F6;color:#0B7180;border:1px solid #BFE0E2;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
    )
    header.addWidget(local, alignment=Qt.AlignmentFlag.AlignTop)
    root.addLayout(header)

    status = QFrame(objectName="ProtectPrivacyStatus")
    status_layout = QHBoxLayout(status)
    status_layout.setContentsMargins(13, 11, 13, 11)
    status_layout.setSpacing(10)
    status_icon = QLabel()
    status_icon.setFixedWidth(26)
    status_title = QLabel("WAITING FOR PROTECTED RESULT")
    status_title.setStyleSheet(f"color:{_MUTED};font-size:11px;font-weight:950;")
    status_reason = QLabel("Run Scan & Protect to create a document-specific privacy check.")
    status_reason.setWordWrap(True)
    status_reason.setStyleSheet(f"color:{_INK};font-size:9px;")
    status_text = QVBoxLayout()
    status_text.addWidget(status_title)
    status_text.addWidget(status_reason)
    risk_badge = QLabel("—")
    risk_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    risk_badge.setMinimumWidth(78)
    status_layout.addWidget(status_icon)
    status_layout.addLayout(status_text, 1)
    status_layout.addWidget(risk_badge)
    root.addWidget(status)

    metrics = QGridLayout()
    metrics.setHorizontalSpacing(8)
    detected_card = _metric_card("Detected", "0", "Sensitive items found in all current sources.")
    protected_card = _metric_card("Protected", "0", "Detected items replaced by the selected mode.")
    allowed_card = _metric_card("Still visible", "0", "Detected items intentionally left unchanged.")
    residual_card = _metric_card("Residual", "0", "Possible sensitive data found by the local second scan.")
    for index, card in enumerate((detected_card, protected_card, allowed_card, residual_card)):
        metrics.addWidget(card, 0, index)
    root.addLayout(metrics)

    policy = QLabel("")
    policy.setWordWrap(True)
    policy.setStyleSheet(
        "background:#FFFFFF;color:#496173;border:1px solid #D7E2EA;border-radius:9px;"
        "padding:9px 11px;font-size:9px;font-weight:750;"
    )
    root.addWidget(policy)

    sources_title = QLabel("SOURCE CHECKS")
    sources_title.setStyleSheet(f"color:{_TEAL};font-size:8px;font-weight:950;")
    root.addWidget(sources_title)
    sources_host = QWidget()
    sources_layout = QVBoxLayout(sources_host)
    sources_layout.setContentsMargins(0, 0, 0, 0)
    sources_layout.setSpacing(7)
    root.addWidget(sources_host)
    root.addStretch(1)

    index = page.preview_tabs.addTab(scroll, "Privacy Check")
    page.preview_tabs.setTabVisible(index, False)

    page._privacy_check_tab = scroll
    page._privacy_check_tab_index = index
    page._privacy_check_status = status
    page._privacy_check_status_icon = status_icon
    page._privacy_check_status_title = status_title
    page._privacy_check_status_reason = status_reason
    page._privacy_check_risk_badge = risk_badge
    page._privacy_check_metric_values = tuple(
        card.layout().itemAt(0).widget()
        for card in (detected_card, protected_card, allowed_card, residual_card)
    )
    page._privacy_check_policy = policy
    page._privacy_check_sources_layout = sources_layout
    page._privacy_check_generation = 0
    page._privacy_check_open_on_ready = False
    page._privacy_check_worker = None


def _show_loading(page) -> None:
    page.preview_tabs.setTabVisible(page._privacy_check_tab_index, True)
    page._privacy_check_status.setStyleSheet(
        "QFrame#ProtectPrivacyStatus{background:#F2FAFA;border:1px solid #CDE5E6;border-radius:10px;}"
    )
    page._privacy_check_status_icon.setPixmap(
        icon("protect", color=_TEAL, size=20).pixmap(20, 20)
    )
    page._privacy_check_status_title.setText("CHECKING PROTECTED RESULT…")
    page._privacy_check_status_title.setStyleSheet(
        f"color:{_TEAL};font-size:11px;font-weight:950;"
    )
    page._privacy_check_status_reason.setText(
        "Running the local second scan across every protected source in this session."
    )
    page._privacy_check_risk_badge.setText("LOCAL")
    page._privacy_check_risk_badge.setStyleSheet(
        "background:#EAF6F6;color:#0B7180;border:1px solid #BFE0E2;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:950;"
    )


def _render_summary(page, summary: PrivacyCheckSummary) -> None:
    if summary.risk == "LOW":
        color, background, border = _GREEN, "#EAF7EF", "#BFE4CD"
        title = "READY — LOW PRIVACY RISK"
        status_icon_name = "check"
    elif summary.risk == "MEDIUM":
        color, background, border = _AMBER, "#FFF5E5", "#F0D3A0"
        title = "REVIEW — MEDIUM PRIVACY RISK"
        status_icon_name = "protect"
    else:
        color, background, border = _RED, "#FDEEEE", "#E7BABA"
        title = "REVIEW — HIGH PRIVACY RISK"
        status_icon_name = "protect"

    page._privacy_check_status.setStyleSheet(
        "QFrame#ProtectPrivacyStatus{"
        f"background:{background};border:1px solid {border};border-radius:10px;}}"
    )
    page._privacy_check_status_icon.setPixmap(
        icon(status_icon_name, color=color, size=20).pixmap(20, 20)
    )
    page._privacy_check_status_title.setText(title)
    page._privacy_check_status_title.setStyleSheet(
        f"color:{color};font-size:11px;font-weight:950;"
    )
    page._privacy_check_status_reason.setText(summary.reason)
    page._privacy_check_risk_badge.setText(summary.risk)
    page._privacy_check_risk_badge.setStyleSheet(
        f"background:{background};color:{color};border:1px solid {border};"
        "border-radius:8px;padding:5px 9px;font-size:9px;font-weight:950;"
    )

    for label, value in zip(
        page._privacy_check_metric_values,
        (summary.detected, summary.protected, summary.allowed, summary.residual),
    ):
        label.setText(str(value))

    profile = page.profile_combo.currentText() if hasattr(page, "profile_combo") else ""
    scope = page.scope_combo.currentText() if hasattr(page, "scope_combo") else ""
    mode = page.mode_combo.currentText() if hasattr(page, "mode_combo") else ""
    page._privacy_check_policy.setText(
        f"Protection policy  •  {profile}  •  {scope}  •  {mode}  •  "
        f"{len(summary.sources)} source{'s' if len(summary.sources) != 1 else ''}"
    )

    layout = page._privacy_check_sources_layout
    _clear_layout(layout)
    for source in summary.sources:
        row = QFrame(objectName="ProtectPrivacySource")
        row.setStyleSheet(
            "QFrame#ProtectPrivacySource{background:#FFFFFF;border:1px solid #DEE7ED;border-radius:9px;}"
        )
        box = QHBoxLayout(row)
        box.setContentsMargins(11, 8, 11, 8)
        name = QLabel(source.label)
        name.setStyleSheet(f"color:{_NAVY};font-size:9px;font-weight:900;")
        detail = QLabel(
            f"{source.detected} detected  •  {source.protected} protected  •  "
            f"{source.allowed} visible  •  {source.residual} residual"
        )
        detail.setStyleSheet(f"color:{_MUTED};font-size:8px;font-weight:700;")
        source_risk = "HIGH" if source.residual else ("MEDIUM" if source.allowed else "LOW")
        badge = QLabel(source_risk)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:#F2F6F8;color:#496173;border:1px solid #D7E2EA;"
            "border-radius:7px;padding:4px 7px;font-size:8px;font-weight:900;"
        )
        box.addWidget(name, 2)
        box.addWidget(detail, 3)
        box.addWidget(badge)
        layout.addWidget(row)

    page.verification_metric.setText(
        f"Privacy Check: {summary.risk} · "
        + ("ready" if summary.ready else "review recommended")
    )
    page.verification_metric.setProperty("warning", not summary.ready)
    page.verification_metric.style().unpolish(page.verification_metric)
    page.verification_metric.style().polish(page.verification_metric)


def _start_privacy_check(page) -> None:
    items = _protection_sources(page)
    if not items:
        return

    _ensure_privacy_check_ui(page)
    page._privacy_check_generation += 1
    generation = page._privacy_check_generation
    _show_loading(page)

    profile = page._current_profile()

    def task():
        residuals = {}
        for item in items:
            residuals[item["key"]] = tuple(
                page.service.verify_protected(item["result"], profile)
            )
        return residuals

    def ready(payload: object) -> None:
        if generation != page._privacy_check_generation:
            return
        residuals = dict(payload)
        checks = tuple(
            SourcePrivacyCheck(
                key=str(item["key"]),
                label=str(item["label"]),
                detected=len(tuple(item["findings"])),
                protected=len(tuple(item["result"].applied_findings)),
                residual=len(tuple(residuals.get(item["key"], ()))),
            )
            for item in items
        )
        summary = build_privacy_check_summary(checks)
        page._privacy_check_summary = summary
        page._last_residual = tuple(
            finding
            for item in items
            for finding in tuple(residuals.get(item["key"], ()))
        )
        _render_summary(page, summary)
        if page._privacy_check_open_on_ready:
            page.preview_tabs.setCurrentIndex(page._privacy_check_tab_index)
            page._privacy_check_open_on_ready = False

    def failed(message: str) -> None:
        if generation != page._privacy_check_generation:
            return
        page._privacy_check_status_title.setText("PRIVACY CHECK UNAVAILABLE")
        page._privacy_check_status_title.setStyleSheet(
            f"color:{_AMBER};font-size:11px;font-weight:950;"
        )
        page._privacy_check_status_reason.setText(
            "The protected copy is still available. The local second scan could not complete: "
            + message
        )

    worker = FunctionWorker(task)
    page._privacy_check_worker = worker
    worker.signals.result.connect(ready)
    worker.signals.error.connect(failed)
    page.thread_pool.start(worker)


def _update_steps(page) -> None:
    steps = page.findChild(QFrame, "RedesignSteps")
    if steps is None:
        return
    replacements = {
        "Add document": "Add sources",
        "Scan locally": "Scan & protect",
        "Review choices": "Privacy Check",
        "Save or use with AI": "Save or use with AI",
    }
    for label in steps.findChildren(QLabel):
        text = label.text().strip()
        if text in replacements:
            label.setText(replacements[text])


def apply_protect_workflow_v2(main_window) -> None:
    """Unify Scan + Protect and add a fresh document/session Privacy Check tab.

    This intentionally does not reuse the legacy AI Preflight dialog. The new
    Privacy Check is tied directly to the protected source set currently open in
    Protect and works for local files, Paste text, Document+Text, and Gmail
    multi-source packages.
    """
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_protect_workflow_v2", False):
        return
    page._protect_workflow_v2 = True

    _ensure_privacy_check_ui(page)
    _update_steps(page)

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.hide()
        protect_button.setToolTip(
            "Protection now updates automatically after Scan & Protect and whenever review choices change."
        )

    page.scan_button.setText("Scan & Protect")
    page.scan_button.setToolTip(
        "Scan every selected source locally, create the protected copy, then run Privacy Check."
    )

    previous_set_busy = page._set_busy

    def set_busy(self, busy: bool) -> None:
        previous_set_busy(busy)
        self.scan_button.setText(
            "Scanning & protecting…" if busy else "Scan & Protect"
        )

    page._set_busy = MethodType(set_busy, page)

    # The existing review table already has a debounced protection updater.
    # Make initial protection explicit as part of the single Scan & Protect
    # command by invoking the hidden compatibility action once rows exist.
    def trigger_initial_protection(*_args) -> None:
        button = getattr(page, "_redesign_protect_button", None)
        if button is None:
            return
        QTimer.singleShot(0, lambda: button.click() if button.isEnabled() else None)

    try:
        page.findings_table.model().rowsInserted.connect(trigger_initial_protection)
    except Exception:
        pass

    page.scan_button.clicked.connect(
        lambda _checked=False: setattr(page, "_privacy_check_open_on_ready", True)
    )

    previous_refresh = page._refresh_preview

    def refresh_preview(self, *_args) -> None:
        previous_refresh(*_args)
        if _protection_sources(self):
            QTimer.singleShot(0, lambda: _start_privacy_check(self))

    page._refresh_preview = MethodType(refresh_preview, page)
    page._refresh_privacy_check = MethodType(
        lambda self: _start_privacy_check(self),
        page,
    )

    previous_clear = page.clear

    def clear(self) -> None:
        self._privacy_check_generation += 1
        self._privacy_check_open_on_ready = False
        previous_clear()
        self.preview_tabs.setTabVisible(self._privacy_check_tab_index, False)
        self._privacy_check_summary = None
        self._privacy_check_status_title.setText("WAITING FOR PROTECTED RESULT")
        self._privacy_check_status_reason.setText(
            "Run Scan & Protect to create a document-specific privacy check."
        )
        for label in self._privacy_check_metric_values:
            label.setText("0")
        _clear_layout(self._privacy_check_sources_layout)

    try:
        page.clear_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page.clear = MethodType(clear, page)
    page.clear_button.clicked.connect(page.clear)
