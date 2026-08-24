from __future__ import annotations

import time

import httpx
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import materialize_google_drive_item
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_import import materialize_gmail_message


_PROVIDER_BY_TITLE = {
    "Google Drive": "google_drive",
    "Gmail": "gmail",
    "ClickUp": "clickup",
    "Asana": "asana",
    "Trello": "trello",
}


def _provider_from_button(button: QAbstractButton) -> tuple[str, str] | None:
    parent = button.parentWidget()
    while parent is not None:
        labels = parent.findChildren(QLabel)
        for label in labels:
            title = label.text().strip()
            provider = _PROVIDER_BY_TITLE.get(title)
            if provider:
                return provider, title
        parent = parent.parentWidget()
    return None


def _display_kind(kind: str) -> str:
    names = {
        "application/vnd.google-apps.document": "Google Doc",
        "application/vnd.google-apps.spreadsheet": "Google Sheet",
        "application/vnd.google-apps.presentation": "Google Slides",
        "application/vnd.google-apps.folder": "Folder",
        "application/pdf": "PDF",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel workbook",
        "email": "Email",
        "workspace": "Workspace",
        "board": "Board",
    }
    return names.get(kind, kind.replace("application/", ""))


def _transient_network_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError)):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "winerror 10051",
            "winerror 10060",
            "winerror 10061",
            "network is unreachable",
            "rete non raggiungibile",
            "connection reset",
            "temporarily unavailable",
        )
    )


def _retry_network(operation, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if not _transient_network_error(exc) or attempt == attempts - 1:
                raise
            time.sleep(0.35 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("The connected service did not return a result.")


def _friendly_connection_error(title: str, exc: Exception) -> str:
    if _transient_network_error(exc):
        return (
            f"{title} is temporarily unreachable from this PC. "
            "PrivacyGate kept your connection; check the network and try again in a few seconds."
        )
    return str(exc) or f"Unable to reach {title}."


def _open_source_browser(main_window, provider: str, title: str) -> None:
    page = main_window.cloud_automation_page
    service = getattr(page, "_connected_apps_service", None)
    if service is None:
        QMessageBox.warning(main_window, title, "Connected Apps service is unavailable.")
        return

    try:
        items = _retry_network(lambda: service.list_root_items(provider, limit=60))
    except Exception as exc:
        QMessageBox.warning(main_window, f"Unable to read {title}", _friendly_connection_error(title, exc))
        return

    items = tuple(item for item in items if item.item_id and item.title.strip())

    dialog = QDialog(main_window)
    dialog.setWindowTitle(f"{title} — available sources")
    dialog.resize(820, 600)
    dialog.setMinimumSize(700, 500)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(12)

    heading = QLabel(f"{title} sources", objectName="PageTitle")
    root.addWidget(heading)
    explanation = QLabel(
        "Select a source to bring a local working copy into PrivacyGate. Nothing shown here has been sent to an AI."
    )
    explanation.setWordWrap(True)
    explanation.setStyleSheet("color:#28475D;font-size:11px;")
    root.addWidget(explanation)

    listing = QListWidget()
    listing.setAlternatingRowColors(False)
    listing.setSpacing(4)
    listing.setStyleSheet(
        "QListWidget { background:#FFFFFF; color:#10263A; border:1px solid #C9D7E1; "
        "border-radius:10px; padding:8px; outline:0; font-size:12px; }"
        "QListWidget::item { color:#10263A; background:#FFFFFF; border:1px solid transparent; "
        "border-radius:8px; padding:10px 12px; margin:1px 0; }"
        "QListWidget::item:hover { background:#EAF7F7; color:#062B4F; border:1px solid #B8E1E4; }"
        "QListWidget::item:selected { background:#0B7180; color:#FFFFFF; border:1px solid #0B7180; }"
        "QListWidget::item:selected:active { background:#0B7180; color:#FFFFFF; }"
    )

    item_lookup = {}
    for remote in items:
        kind = _display_kind(remote.kind)
        metadata = kind
        if remote.subtitle:
            metadata += f"   •   {remote.subtitle}"
        row = QListWidgetItem(f"{remote.title}\n{metadata}")
        row.setSizeHint(QSize(0, 58))
        row.setData(Qt.ItemDataRole.UserRole, remote.item_id)
        listing.addItem(row)
        item_lookup[remote.item_id] = remote

    if not items:
        row = QListWidgetItem("No readable sources were returned by this provider.")
        row.setFlags(Qt.ItemFlag.NoItemFlags)
        row.setSizeHint(QSize(0, 48))
        listing.addItem(row)

    root.addWidget(listing, 1)

    footer = QHBoxLayout()
    count = QLabel(f"{len(items)} item(s)")
    count.setStyleSheet("color:#3E5B70;font-weight:700;")
    use_button = QPushButton("Use in Protect", objectName="Primary")
    use_button.setEnabled(False)
    close = QPushButton("Close", objectName="Secondary")
    footer.addWidget(count)
    footer.addStretch(1)
    footer.addWidget(close)
    footer.addWidget(use_button)
    root.addLayout(footer)

    listing.currentItemChanged.connect(
        lambda current, _previous: use_button.setEnabled(bool(current and current.data(Qt.ItemDataRole.UserRole)))
    )
    listing.itemDoubleClicked.connect(lambda _item: use_button.click())
    close.clicked.connect(dialog.reject)

    def use_selected() -> None:
        current = listing.currentItem()
        if current is None:
            return
        remote = item_lookup.get(current.data(Qt.ItemDataRole.UserRole))
        if remote is None:
            return

        protect = main_window.protection_page

        if provider == "google_drive":
            try:
                local_path = _retry_network(lambda: materialize_google_drive_item(service, remote))
            except Exception as exc:
                QMessageBox.warning(dialog, "Unable to import from Google Drive", _friendly_connection_error("Google Drive", exc))
                return
            document_button = getattr(protect, "_redesign_document_mode", None)
            if document_button is not None and not document_button.isChecked():
                document_button.click()
            protect.input_tabs.setCurrentIndex(1)
            protect.pdf_path.setText(str(local_path))
            status = f"Imported from Google Drive: {remote.title} — ready for local scan"

        elif provider == "gmail":
            try:
                local_path = _retry_network(lambda: materialize_gmail_message(service, remote))
                email_text = local_path.read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(dialog, "Unable to import from Gmail", _friendly_connection_error("Gmail", exc))
                return
            paste_button = getattr(protect, "_redesign_paste_mode", None)
            if paste_button is not None and not paste_button.isChecked():
                paste_button.click()
            protect.input_tabs.setCurrentIndex(0)
            protect.text_input.setPlainText(email_text)
            status = f"Imported from Gmail: {remote.title} — ready for local scan"

        else:
            QMessageBox.information(
                dialog,
                f"{title} import",
                "Browsing is connected. Direct import into Protect for this provider is the next connector step.",
            )
            return

        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(status, 9000)

    use_button.clicked.connect(use_selected)
    dialog.exec()


def apply_connected_apps_browse_polish(main_window) -> None:
    page = getattr(main_window, "cloud_automation_page", None)
    if page is None:
        return
    for button in page.findChildren(QAbstractButton):
        if button.text().strip() != "Browse":
            continue
        provider_info = _provider_from_button(button)
        if provider_info is None:
            continue
        provider, title = provider_info
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(lambda _checked=False, p=provider, t=title: _open_source_browser(main_window, p, t))
