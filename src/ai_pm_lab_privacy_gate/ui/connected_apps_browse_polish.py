from __future__ import annotations

import time

import httpx
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QInputDialog,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import materialize_google_drive_item
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_import import (
    list_gmail_attachments,
    materialize_gmail_attachment,
    materialize_gmail_message,
)


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
        for label in parent.findChildren(QLabel):
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
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint deck",
        "text/plain": "Text file",
        "email": "Email",
        "workspace": "Workspace",
        "board": "Board",
    }
    return names.get(kind, kind.replace("application/", ""))


def _active_account_details(service, provider: str) -> tuple[str, str]:
    if service is None or not hasattr(service, "list_connected_accounts"):
        return "", ""
    try:
        accounts = tuple(service.list_connected_accounts(provider))
    except Exception:
        return "", ""
    active = next((account for account in accounts if account.is_active), None)
    if active is None and len(accounts) == 1:
        active = accounts[0]
    if active is None:
        active = next((account for account in accounts if account.is_default), None)
    if active is None:
        return "", ""
    account_id = str(getattr(active, "account_id", "") or "").strip()
    account_label = str(
        getattr(active, "label", "") or getattr(active, "subtitle", "") or ""
    ).strip()
    return account_id, account_label


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


def _run_busy(parent, title: str, message: str, operation):
    busy = QProgressDialog(message, "", 0, 0, parent)
    busy.setWindowTitle(title)
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setCancelButton(None)
    busy.setMinimumDuration(0)
    busy.setMinimumWidth(390)
    busy.setAutoClose(False)
    busy.setAutoReset(False)
    busy.show()
    QApplication.processEvents()
    try:
        return operation()
    finally:
        busy.close()
        QApplication.processEvents()


def _friendly_connection_error(title: str, exc: Exception) -> str:
    if _transient_network_error(exc):
        return (
            f"{title} is temporarily unreachable from this PC. "
            "PrivacyGate kept your connection; check the network and try again in a few seconds."
        )
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 401:
        return (
            f"{title} rejected the saved session. PrivacyGate already tried to refresh it automatically. "
            "If this repeats, use Reconnect once from Apps."
        )
    return str(exc) or f"Unable to reach {title}."


def _drive_call_with_refresh(service, operation):
    try:
        return _retry_network(operation)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 401 or not hasattr(service, "force_google_refresh"):
            raise
        service.force_google_refresh()
        return _retry_network(operation)


def _open_source_browser(main_window, provider: str, title: str) -> None:
    page = main_window.cloud_automation_page
    service = getattr(page, "_connected_apps_service", None)
    if service is None:
        QMessageBox.warning(main_window, title, "Connected Apps service is unavailable.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle(f"{title} — available sources")
    dialog.resize(860, 650)
    dialog.setMinimumSize(720, 520)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(11)

    heading = QLabel(f"{title} sources", objectName="PageTitle")
    root.addWidget(heading)
    explanation = QLabel(
        "Search and select a source to bring a local working copy into PrivacyGate. Nothing shown here is sent to AI."
    )
    explanation.setWordWrap(True)
    explanation.setStyleSheet("color:#28475D;font-size:11px;")
    root.addWidget(explanation)

    search_row = QHBoxLayout()
    search = QLineEdit()
    search.setPlaceholderText(f"Search {title} — file, workspace, board or keyword…")
    search.setClearButtonEnabled(True)
    search.setMinimumHeight(38)
    search.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#10263A;border:1px solid #C8D6E0;"
        "border-radius:9px;padding:7px 11px;font-size:11px;}"
        "QLineEdit:focus{border-color:#1595A3;}"
    )
    search_button = QPushButton("Search", objectName="Primary")
    clear_search = QPushButton("All", objectName="Secondary")
    search_row.addWidget(search, 1)
    search_row.addWidget(search_button)
    search_row.addWidget(clear_search)
    root.addLayout(search_row)

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
    )
    root.addWidget(listing, 1)

    footer = QHBoxLayout()
    count = QLabel("0 item(s)")
    count.setStyleSheet("color:#3E5B70;font-weight:700;")
    close = QPushButton("Close", objectName="Secondary")
    use_button = QPushButton("Use in Protect", objectName="Primary")
    use_button.setEnabled(False)
    footer.addWidget(count)
    footer.addStretch(1)
    footer.addWidget(close)
    footer.addWidget(use_button)
    root.addLayout(footer)

    item_lookup = {}

    def populate(rows) -> None:
        listing.clear()
        item_lookup.clear()
        for remote in rows:
            if not remote.item_id or not remote.title.strip():
                continue
            metadata = _display_kind(remote.kind)
            if remote.subtitle:
                metadata += f"   •   {remote.subtitle}"
            row = QListWidgetItem(f"{remote.title}\n{metadata}")
            row.setSizeHint(QSize(0, 58))
            row.setData(Qt.ItemDataRole.UserRole, remote.item_id)
            listing.addItem(row)
            item_lookup[remote.item_id] = remote
        if not item_lookup:
            empty = QListWidgetItem("No matching sources found.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setSizeHint(QSize(0, 48))
            listing.addItem(empty)
        count.setText(f"{len(item_lookup)} item(s)")
        use_button.setEnabled(False)

    def load(query: str = "") -> None:
        label = "Searching" if query else "Loading"
        message = f"Searching {title} for ‘{query}’…" if query else f"Loading data from {title}…"
        try:
            operation = (
                (lambda: service.search_items(provider, query, 60))
                if query and hasattr(service, "search_items")
                else (lambda: service.list_root_items(provider, limit=60))
            )
            if provider == "google_drive":
                rows = _run_busy(
                    dialog,
                    f"{label} Google Drive",
                    message,
                    lambda: _drive_call_with_refresh(service, operation),
                )
            else:
                rows = _run_busy(dialog, f"{label} {title}", message, lambda: _retry_network(operation))
        except Exception as exc:
            QMessageBox.warning(dialog, f"Unable to read {title}", _friendly_connection_error(title, exc))
            return
        populate(rows)

    def run_search() -> None:
        load(search.text().strip())

    def reset_search() -> None:
        search.clear()
        load("")

    def use_selected() -> None:
        current = listing.currentItem()
        if current is None:
            return
        remote = item_lookup.get(current.data(Qt.ItemDataRole.UserRole))
        if remote is None:
            return
        protect = main_window.protection_page
        account_id, account_label = _active_account_details(service, provider)

        if provider == "google_drive":
            try:
                local_path = _run_busy(
                    dialog,
                    "Importing from Google Drive",
                    "Preparing a local working copy for PrivacyGate…",
                    lambda: _drive_call_with_refresh(
                        service, lambda: materialize_google_drive_item(service, remote)
                    ),
                )
            except Exception as exc:
                QMessageBox.warning(dialog, "Unable to import from Google Drive", _friendly_connection_error("Google Drive", exc))
                return
            document_button = getattr(protect, "_redesign_document_mode", None)
            if document_button is not None and not document_button.isChecked():
                document_button.click()
            protect.input_tabs.setCurrentIndex(1)
            protect.pdf_path.setText(str(local_path))
            source_parts = ["Google Drive"]
            if account_label:
                source_parts.append(account_label)
            source_parts.append(remote.title)
            protect._external_source_name = " • ".join(source_parts)
            protect._external_source_metadata = {
                "provider": "google_drive",
                "provider_label": "Google Drive",
                "account_id": account_id,
                "account_label": account_label,
                "item_id": str(remote.item_id or ""),
                "item_title": str(remote.title or ""),
                "item_kind": str(remote.kind or ""),
            }
            status = f"Imported from Google Drive: {remote.title} — ready for local scan"

        elif provider == "gmail":
            try:
                attachments = _run_busy(
                    dialog,
                    "Reading Gmail message",
                    "Checking the selected email and its supported attachments…",
                    lambda: _retry_network(lambda: list_gmail_attachments(service, remote)),
                )
            except Exception as exc:
                QMessageBox.warning(dialog, "Unable to read Gmail attachments", _friendly_connection_error("Gmail", exc))
                return

            chosen_attachment = None
            if attachments:
                choices = ["Email message"] + [f"Attachment: {attachment.filename}" for attachment in attachments]
                choice, ok = QInputDialog.getItem(
                    dialog,
                    "Choose Gmail content",
                    "Protect the email message or one of its supported attachments:",
                    choices,
                    0,
                    False,
                )
                if not ok:
                    return
                if choice != "Email message":
                    chosen_attachment = attachments[choices.index(choice) - 1]

            try:
                if chosen_attachment is not None:
                    local_path = _run_busy(
                        dialog,
                        "Importing Gmail attachment",
                        f"Preparing {chosen_attachment.filename} locally…",
                        lambda: _retry_network(
                            lambda: materialize_gmail_attachment(service, remote, chosen_attachment)
                        ),
                    )
                    document_button = getattr(protect, "_redesign_document_mode", None)
                    if document_button is not None and not document_button.isChecked():
                        document_button.click()
                    protect.input_tabs.setCurrentIndex(1)
                    protect.pdf_path.setText(str(local_path))
                    item_title = f"{remote.title} • {chosen_attachment.filename}"
                    status = f"Imported Gmail attachment: {chosen_attachment.filename} — ready for local scan"
                else:
                    local_path = _run_busy(
                        dialog,
                        "Importing from Gmail",
                        "Preparing the selected email locally…",
                        lambda: _retry_network(lambda: materialize_gmail_message(service, remote)),
                    )
                    email_text = local_path.read_text(encoding="utf-8")
                    paste_button = getattr(protect, "_redesign_paste_mode", None)
                    if paste_button is not None and not paste_button.isChecked():
                        paste_button.click()
                    protect.input_tabs.setCurrentIndex(0)
                    protect.text_input.setPlainText(email_text)
                    item_title = remote.title
                    status = f"Imported from Gmail: {remote.title} — ready for local scan"
            except Exception as exc:
                QMessageBox.warning(dialog, "Unable to import from Gmail", _friendly_connection_error("Gmail", exc))
                return

            source_parts = ["Gmail"]
            if account_label:
                source_parts.append(account_label)
            source_parts.append(item_title)
            protect._external_source_name = " • ".join(source_parts)
            protect._external_source_metadata = {
                "provider": "gmail",
                "provider_label": "Gmail",
                "account_id": account_id,
                "account_label": account_label,
                "item_id": str(remote.item_id or ""),
                "item_title": str(item_title or ""),
                "item_kind": "attachment" if chosen_attachment is not None else str(remote.kind or "email"),
            }

        else:
            QMessageBox.information(
                dialog,
                f"{title} import",
                "Browsing and search are connected. Direct import into Protect for this provider is the next connector step.",
            )
            return

        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(status, 9000)

    listing.currentItemChanged.connect(
        lambda current, _previous: use_button.setEnabled(
            bool(current and current.data(Qt.ItemDataRole.UserRole))
        )
    )
    listing.itemDoubleClicked.connect(lambda _item: use_button.click())
    search.returnPressed.connect(run_search)
    search_button.clicked.connect(run_search)
    clear_search.clicked.connect(reset_search)
    close.clicked.connect(dialog.reject)
    use_button.clicked.connect(use_selected)

    load("")
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
