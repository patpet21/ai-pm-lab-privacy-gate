from __future__ import annotations

import base64
import html

import httpx
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.service import RemoteItem


PAGE_SIZE = 30


def _decode_b64url(value: str) -> str:
    if not value:
        return ""
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _header(headers: list[dict], name: str) -> str:
    target = name.lower()
    for item in headers:
        if str(item.get("name") or "").lower() == target:
            return str(item.get("value") or "")
    return ""


def _extract_plain_text(part: dict) -> str:
    mime = str(part.get("mimeType") or "")
    body = part.get("body") or {}
    data = str(body.get("data") or "")
    if mime == "text/plain" and data:
        return _decode_b64url(data)
    for child in part.get("parts") or []:
        text = _extract_plain_text(child)
        if text:
            return text
    if mime == "text/html" and data:
        raw = _decode_b64url(data)
        return html.unescape(__import__("re").sub(r"<[^>]+>", " ", raw))
    return ""


def _gmail_page(service, page_token: str = "") -> tuple[list[RemoteItem], str]:
    token = service._token("gmail")
    headers = {"Authorization": f"Bearer {token}"}
    params = {"maxResults": str(PAGE_SIZE)}
    if page_token:
        params["pageToken"] = page_token
    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params=params,
        timeout=service.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows: list[RemoteItem] = []
    for entry in payload.get("messages", []):
        message_id = str(entry.get("id") or "")
        if not message_id:
            continue
        detail = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            timeout=service.timeout,
        )
        detail.raise_for_status()
        message = detail.json()
        msg_headers = message.get("payload", {}).get("headers", [])
        subject = _header(msg_headers, "Subject") or "(No subject)"
        sender = _header(msg_headers, "From")
        date = _header(msg_headers, "Date")
        subtitle = " • ".join(part for part in (sender, date) if part)
        rows.append(RemoteItem("gmail", message_id, subject, subtitle, "email", ""))
    return rows, str(payload.get("nextPageToken") or "")


def _gmail_message_text(service, message_id: str) -> str:
    token = service._token("gmail")
    response = httpx.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "full"},
        timeout=service.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    headers = payload.get("payload", {}).get("headers", [])
    subject = _header(headers, "Subject") or "(No subject)"
    sender = _header(headers, "From")
    to = _header(headers, "To")
    date = _header(headers, "Date")
    body = _extract_plain_text(payload.get("payload") or {}).strip()
    return f"Subject: {subject}\nFrom: {sender}\nTo: {to}\nDate: {date}\n\n{body}".strip()


def open_gmail_browser(main_window) -> None:
    cloud = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud, "_connected_apps_service", None) if cloud else None
    if service is None:
        QMessageBox.warning(main_window, "Gmail", "Connected Apps service is unavailable.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Gmail — available messages")
    dialog.resize(860, 650)
    dialog.setMinimumSize(720, 520)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(12)

    title = QLabel("Gmail messages")
    title.setStyleSheet("color:#062B4F;font-size:25px;font-weight:900;")
    root.addWidget(title)
    note = QLabel("30 messages are loaded at a time. Load more pages as needed; only the message you choose is brought into Protect locally.")
    note.setWordWrap(True)
    note.setStyleSheet("color:#516F82;font-size:11px;")
    root.addWidget(note)

    listing = QListWidget()
    listing.setSpacing(3)
    listing.setStyleSheet(
        "QListWidget{background:#FFFFFF;color:#10263A;border:1px solid #C9D7E1;border-radius:10px;padding:8px;outline:0;font-size:12px;}"
        "QListWidget::item{color:#10263A;background:#FFFFFF;border:1px solid transparent;border-radius:8px;padding:10px 12px;margin:1px 0;}"
        "QListWidget::item:hover{background:#EAF7F7;color:#062B4F;border:1px solid #B8E1E4;}"
        "QListWidget::item:selected{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;}"
    )
    root.addWidget(listing, 1)

    footer = QHBoxLayout()
    count = QLabel("0 loaded")
    count.setStyleSheet("color:#3E5B70;font-weight:700;")
    load_more = QPushButton("Load 30 more")
    use = QPushButton("Use in Protect")
    close = QPushButton("Close")
    use.setEnabled(False)
    load_more.setStyleSheet("QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #B9CBD5;border-radius:8px;padding:8px 14px;font-weight:750;} QPushButton:hover{background:#F1FAFA;border-color:#8FB8BF;}")
    use.setStyleSheet("QPushButton{background:#0B7180;color:white;border:1px solid #0B7180;border-radius:8px;padding:8px 14px;font-weight:800;} QPushButton:disabled{background:#D7E0E7;color:#8796A4;border-color:#D7E0E7;}")
    close.setStyleSheet("QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #B9CBD5;border-radius:8px;padding:8px 14px;font-weight:750;}")
    footer.addWidget(count)
    footer.addWidget(load_more)
    footer.addStretch(1)
    footer.addWidget(close)
    footer.addWidget(use)
    root.addLayout(footer)

    items: dict[str, RemoteItem] = {}
    state = {"next": "", "loaded": 0, "initial": True}

    def append_page() -> None:
        load_more.setEnabled(False)
        load_more.setText("Loading…")
        try:
            rows, next_token = _gmail_page(service, "" if state["initial"] else state["next"])
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to read Gmail", str(exc))
            load_more.setEnabled(True)
            load_more.setText("Load 30 more")
            return
        state["initial"] = False
        state["next"] = next_token
        for remote in rows:
            if remote.item_id in items:
                continue
            items[remote.item_id] = remote
            row = QListWidgetItem(f"{remote.title}\n{remote.subtitle}")
            row.setData(Qt.ItemDataRole.UserRole, remote.item_id)
            row.setSizeHint(QSize(0, 58))
            listing.addItem(row)
        state["loaded"] = len(items)
        count.setText(f"{state['loaded']} loaded")
        load_more.setVisible(bool(state["next"]))
        load_more.setEnabled(bool(state["next"]))
        load_more.setText("Load 30 more")

    def use_selected() -> None:
        current = listing.currentItem()
        if current is None:
            return
        message_id = current.data(Qt.ItemDataRole.UserRole)
        remote = items.get(message_id)
        if remote is None:
            return
        try:
            text = _gmail_message_text(service, message_id)
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import Gmail message", str(exc))
            return
        protect = main_window.protection_page
        paste_mode = getattr(protect, "_redesign_paste_mode", None)
        if paste_mode is not None and not paste_mode.isChecked():
            paste_mode.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(text)
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(f"Imported from Gmail: {remote.title} — ready for local scan", 9000)

    listing.currentItemChanged.connect(lambda current, _prev: use.setEnabled(bool(current)))
    listing.itemDoubleClicked.connect(lambda _item: use.click())
    load_more.clicked.connect(append_page)
    use.clicked.connect(use_selected)
    close.clicked.connect(dialog.reject)

    append_page()
    dialog.exec()


def apply_runtime_fixes(main_window) -> None:
    """Small post-construction fixes that preserve existing business logic."""
    protect = getattr(main_window, "protection_page", None)
    if protect is not None:
        # These legacy controls are still used internally for state/verification,
        # but after the redesign they must not render as orphan widgets over the sidebar.
        for name in ("verification_metric", "findings_metric", "types_metric", "pages_metric", "source_metric"):
            widget = getattr(protect, name, None)
            if widget is not None:
                widget.hide()
                widget.setMaximumHeight(0)

    # Patch the Apps page Browse behavior for Gmail. Card signals call self._browse
    # dynamically, so replacing the instance method here is sufficient.
    apps = getattr(main_window, "apps_hub_page", None)
    if apps is not None and not hasattr(apps, "_privacygate_original_browse"):
        original = apps._browse
        apps._privacygate_original_browse = original

        def browse(provider: str, title: str, supported: bool) -> None:
            if provider == "gmail" and supported and apps._connected(provider):
                open_gmail_browser(main_window)
                return
            original(provider, title, supported)

        apps._browse = browse

    # The Protect quick picker imports the browser function at module scope;
    # route Gmail to the same paginated browser while preserving every other provider.
    try:
        from ai_pm_lab_privacy_gate.ui import protect_source_picker as picker
        old_open = picker._open_source_browser
        if not getattr(picker, "_gmail_pagination_installed", False):
            def routed_open(window, provider: str, title: str):
                if provider == "gmail":
                    open_gmail_browser(window)
                    return
                old_open(window, provider, title)
            picker._open_source_browser = routed_open
            picker._gmail_pagination_installed = True
    except Exception:
        pass
