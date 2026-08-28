from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    ai_destination_allowed,
    policy_status_text,
    resolve_library_workspace,
)
from ai_pm_lab_privacy_gate.ui.privacy_preflight import (
    PreflightSnapshot,
    get_ai_destination,
)


BLUE = "#2563EB"
INK = "#101828"
TEXT = "#344054"
MUTED = "#667085"
BORDER = "#E4E7EC"
GREEN = "#16A34A"
GREEN_SOFT = "#ECFDF3"
AMBER = "#D97706"
AMBER_SOFT = "#FFF7ED"


def _metric(title: str, value: str, note: str) -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:10px;}}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(3)
    number = QLabel(value)
    number.setStyleSheet(f"color:{INK};font-size:19px;font-weight:900;border:none;")
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{TEXT};font-size:9px;font-weight:850;border:none;")
    detail = QLabel(note)
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
    layout.addWidget(number)
    layout.addWidget(heading)
    layout.addWidget(detail)
    return frame


class LibraryPrivacyPreflightDialog(QDialog):
    """Privacy Preflight for a protected copy that already exists in Library."""

    def __init__(
        self,
        *,
        snapshot: PreflightSnapshot,
        document_title: str,
        policy_line: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self.setWindowTitle("AI Privacy Preflight")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(680, 510)
        self.setStyleSheet("QDialog{background:#F8FAFC;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        tile = QLabel()
        tile.setFixedSize(48, 48)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(icon("protect", color=BLUE, size=27).pixmap(27, 27))
        tile.setStyleSheet(
            "background:#EEF4FF;border:1px solid #D6E4FF;border-radius:12px;"
        )
        titles = QVBoxLayout()
        title = QLabel("AI Privacy Preflight")
        title.setStyleSheet(f"color:{INK};font-size:21px;font-weight:950;border:none;")
        subtitle = QLabel(document_title)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addWidget(tile, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(titles, 1)
        local = QLabel("LOCAL PROTECTED COPY")
        local.setStyleSheet(
            "background:#EEF4FF;color:#2563EB;border:1px solid #D6E4FF;"
            "border-radius:8px;padding:5px 8px;font-size:7.5px;font-weight:900;"
        )
        header.addWidget(local, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        ready = snapshot.ready
        status = QFrame()
        status.setStyleSheet(
            "QFrame{"
            f"background:{GREEN_SOFT if ready else AMBER_SOFT};"
            f"border:1px solid {'#BBF7D0' if ready else '#FED7AA'};"
            "border-radius:11px;}"
        )
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(13, 11, 13, 11)
        status_row.setSpacing(10)
        status_icon = QLabel()
        status_icon.setPixmap(
            icon(
                "check" if ready else "protect",
                color=GREEN if ready else AMBER,
                size=21,
            ).pixmap(21, 21)
        )
        copy = QVBoxLayout()
        status_title = QLabel("READY FOR AI" if ready else "REVIEW BEFORE AI")
        status_title.setStyleSheet(
            f"color:{GREEN if ready else AMBER};font-size:11px;font-weight:950;border:none;"
        )
        message = QLabel(
            "A fresh local residual scan found no remaining detected sensitive data in this saved protected copy."
            if ready
            else f"A fresh local residual scan found {snapshot.residual} possible sensitive item(s). Review before continuing."
        )
        message.setWordWrap(True)
        message.setStyleSheet(f"color:{TEXT};font-size:8.5px;border:none;")
        copy.addWidget(status_title)
        copy.addWidget(message)
        status_row.addWidget(status_icon, 0, Qt.AlignmentFlag.AlignTop)
        status_row.addLayout(copy, 1)
        root.addWidget(status)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(9)
        metrics.addWidget(
            _metric(
                "Originally protected",
                str(snapshot.protected),
                "Findings recorded when this Library copy was created.",
            ),
            0,
            0,
        )
        metrics.addWidget(
            _metric(
                "Residual now",
                str(snapshot.residual),
                "Fresh scan of the protected text before AI handoff.",
            ),
            0,
            1,
        )
        metrics.addWidget(
            _metric("Destination", snapshot.destination, snapshot.delivery),
            0,
            2,
        )
        root.addLayout(metrics)

        path = QFrame()
        path.setStyleSheet(
            f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:11px;}}"
        )
        path_layout = QVBoxLayout(path)
        path_layout.setContentsMargins(13, 11, 13, 11)
        path_layout.setSpacing(6)
        source = QLabel(snapshot.source_line)
        source.setWordWrap(True)
        source.setStyleSheet(f"color:{INK};font-size:9px;font-weight:850;border:none;")
        destination = QLabel(f"→ {snapshot.destination} · {snapshot.delivery}")
        destination.setStyleSheet(f"color:{BLUE};font-size:9px;font-weight:900;border:none;")
        policy = QLabel(policy_line or snapshot.policy_line)
        policy.setWordWrap(True)
        policy.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        path_layout.addWidget(source)
        path_layout.addWidget(destination)
        path_layout.addWidget(policy)
        root.addWidget(path)

        note = QLabel(
            "This item is already stored in the local PrivacyGate Library. Continuing copies only the protected text. "
            "PrivacyGate does not submit content automatically, and restore mappings remain local."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"background:#FFFFFF;color:{MUTED};border:1px solid {BORDER};border-radius:9px;"
            "padding:9px;font-size:8px;"
        )
        root.addWidget(note)

        actions = QHBoxLayout()
        cancel = QPushButton("Back to Library")
        cancel.setMinimumHeight(38)
        cancel.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
            "padding:8px 14px;font-weight:800;}QPushButton:hover{background:#F8FAFC;}"
        )
        proceed = QPushButton(
            f"Continue to {snapshot.destination}"
            if ready
            else f"Continue anyway to {snapshot.destination}"
        )
        proceed.setMinimumHeight(38)
        proceed.setStyleSheet(
            "QPushButton{background:#2563EB;color:#FFFFFF;border:1px solid #2563EB;border-radius:9px;"
            "padding:8px 14px;font-weight:900;}QPushButton:hover{background:#1D4ED8;}"
        )
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(proceed)
        root.addLayout(actions)
        cancel.clicked.connect(self.reject)
        proceed.clicked.connect(self.accept)


def _source_details(page, document) -> tuple[str, str, str]:
    source = "Local file"
    account = ""
    item = document.title

    source_method = getattr(page, "_source_for_document", None)
    if callable(source_method):
        try:
            _key, label = source_method(document)
            source = str(label or source)
        except Exception:
            pass

    account_method = getattr(page, "_account_for_document", None)
    if callable(account_method):
        try:
            _key, label = account_method(document)
            if label and label != "Legacy / unknown account":
                account = str(label)
        except Exception:
            pass

    metadata = getattr(page, "_source_metadata_map", {}).get(document.document_id)
    if metadata is not None:
        value = str(getattr(metadata, "item_title", "") or "").strip()
        if value:
            item = value
    return source, account, item


def _fresh_residual_scan(page, document):
    try:
        service = getattr(page.window(), "service", None)
        if service is None:
            raise RuntimeError("Privacy engine is unavailable.")
        profile = get_profile(document.profile_key)
        protected_document = service.document_from_text(document.protected_text)
        return tuple(service.analyze(protected_document, profile))
    except Exception as error:
        QMessageBox.warning(
            page,
            "Privacy Preflight unavailable",
            "PrivacyGate could not complete the required local residual scan for this saved copy. "
            f"No AI handoff was performed.\n\n{error}",
        )
        return None


def use_library_document_with_ai(page, destination_key: str) -> None:
    document = page._current()
    if document is None or document.deleted_at is not None:
        return

    context = resolve_library_workspace(page)
    destination = get_ai_destination(destination_key)
    allowed = ai_destination_allowed(context, destination.key)
    if allowed is False:
        QMessageBox.information(
            page,
            "Blocked by organization policy",
            f"{destination.label} is not allowed by the active {context.name} policy. "
            "The protected text was not copied or opened.",
        )
        return
    if allowed is None:
        QMessageBox.warning(
            page,
            "Organization policy unavailable",
            "PrivacyGate cannot verify the active organization AI policy right now, so the AI handoff is blocked.",
        )
        return

    residual = _fresh_residual_scan(page, document)
    if residual is None:
        return

    source, account, item = _source_details(page, document)
    snapshot = PreflightSnapshot(
        destination=destination.label,
        delivery=destination.delivery,
        source=source,
        account=account,
        item=item,
        detected=document.findings_count,
        protected=document.findings_count,
        allowed=0,
        residual=len(residual),
        profile=document.profile_key.replace("_", " ").title(),
        scope=("Personal workspace" if context.personal else context.name),
        mode=document.replacement_mode.replace("_", " ").title(),
    )

    policy_line = (
        f"{context.name} · {policy_status_text(context)}"
        if context.managed
        else f"Personal · {context.plan_label}"
    )
    dialog = LibraryPrivacyPreflightDialog(
        snapshot=snapshot,
        document_title=document.title,
        policy_line=policy_line,
        parent=page,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    QApplication.clipboard().setText(document.protected_text)
    if destination.url:
        QDesktopServices.openUrl(QUrl(destination.url))

    try:
        message = f'Protected text from "{document.title}" copied for {destination.label}.'
        page.window().statusBar().showMessage(message, 8000)
    except Exception:
        pass


def show_library_ai_menu(page, button: QPushButton) -> None:
    context = resolve_library_workspace(page)
    menu = QMenu(page)
    menu.setStyleSheet(
        "QMenu{background:#FFFFFF;color:#101828;border:1px solid #D0D5DD;border-radius:10px;padding:6px;}"
        "QMenu::item{padding:8px 12px;border-radius:7px;font-size:9px;}"
        "QMenu::item:selected{background:#EEF4FF;color:#1D4ED8;}"
        "QMenu::item:disabled{color:#98A2B3;}"
    )
    menu.addSection("Privacy Preflight destination")

    for key, label in (
        ("chatgpt", "ChatGPT / GPT"),
        ("claude", "Claude"),
        ("other", "Other AI tool"),
    ):
        allowed = ai_destination_allowed(context, key)
        action = menu.addAction(label)
        action.setEnabled(allowed is True)
        if allowed is False:
            action.setToolTip("Blocked by active organization policy")
        elif allowed is None:
            action.setToolTip("Organization policy status is unavailable")
        action.triggered.connect(
            lambda _checked=False, destination=key: use_library_document_with_ai(page, destination)
        )

    menu.addSeparator()
    policy = menu.addAction(
        f"{context.name}: {policy_status_text(context)}"
        if context.managed
        else f"Personal plan: {context.plan_label}"
    )
    policy.setEnabled(False)
    menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
