from __future__ import annotations

import re
import time
from pathlib import Path

import httpx
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_import import (
    GmailAttachment,
    list_gmail_attachments,
    materialize_gmail_attachment,
    materialize_gmail_message,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


NAVY = "#202124"
MUTED = "#5F6368"
GMAIL_RED = "#EA4335"
GMAIL_BLUE = "#4285F4"
SURFACE = "#F8FAFD"


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


def _retry(operation, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            time.sleep(0.35 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("Gmail did not return a result.")


def _active_account_details(service) -> tuple[str, str]:
    if service is None or not hasattr(service, "list_connected_accounts"):
        return "", ""
    try:
        accounts = tuple(service.list_connected_accounts("gmail"))
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


def _sender_name(remote) -> str:
    sender = remote.subtitle.split(" • ", 1)[0] if remote.subtitle else ""
    match = re.match(r"\s*([^<]+?)\s*<", sender)
    return (match.group(1).strip() if match else sender.strip()) or "Unknown sender"


def _message_widget(remote) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(10, 7, 10, 7)
    layout.setSpacing(10)

    sender_name = _sender_name(remote)
    initial = next((char.upper() for char in sender_name if char.isalnum()), "M")
    avatar = QLabel(initial)
    avatar.setFixedSize(34, 34)
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    avatar.setStyleSheet(
        "background:#DDE8FA;color:#174EA6;border-radius:17px;font-weight:850;font-size:12px;"
    )
    layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

    copy = QVBoxLayout()
    copy.setSpacing(1)
    top = QHBoxLayout()
    sender_label = QLabel(sender_name)
    sender_label.setStyleSheet(f"color:{NAVY};font-weight:800;font-size:10px;")
    date = remote.subtitle.split(" • ", 1)[1] if " • " in remote.subtitle else ""
    date_label = QLabel(date)
    date_label.setStyleSheet(f"color:{MUTED};font-size:8px;")
    top.addWidget(sender_label, 1)
    top.addWidget(date_label)
    copy.addLayout(top)

    subject = QLabel(remote.title)
    subject.setStyleSheet(f"color:{NAVY};font-weight:750;font-size:10px;")
    subject.setWordWrap(False)
    copy.addWidget(subject)

    snippet = QLabel(remote.url or "")
    snippet.setStyleSheet(f"color:{MUTED};font-size:8px;")
    snippet.setWordWrap(False)
    copy.addWidget(snippet)
    layout.addLayout(copy, 1)
    return box


def _attachment_label(attachment: GmailAttachment) -> str:
    suffix = Path(attachment.filename).suffix.lower()
    return {
        ".pdf": "PDF document",
        ".docx": "Word document",
        ".xlsx": "Excel workbook",
        ".pptx": "PowerPoint presentation",
        ".txt": "Text file",
    }.get(suffix, "Attachment")


def _attachment_icon(attachment: GmailAttachment):
    suffix = Path(attachment.filename).suffix.lower()
    if suffix == ".pdf":
        return icon("document", color="#D93025", size=18)
    if suffix == ".docx":
        return icon("document", color="#4285F4", size=18)
    if suffix == ".xlsx":
        return icon("template", color="#188038", size=18)
    if suffix == ".pptx":
        return icon("report", color="#F9AB00", size=18)
    return icon("document", color="#5F6368", size=18)


def open_gmail_inbox(main_window) -> None:
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None
    if service is None or not hasattr(service, "list_gmail_page"):
        QMessageBox.warning(main_window, "Gmail", "Gmail connector is unavailable in this build.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Gmail — import to Protect")
    dialog.resize(1120, 720)
    dialog.setMinimumSize(900, 580)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(9)

    header = QHBoxLayout()
    gmail_logo = QLabel()
    gmail_logo.setFixedSize(42, 42)
    gmail_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    gmail_logo.setPixmap(icon("contact", color=GMAIL_RED, size=24).pixmap(24, 24))
    gmail_logo.setStyleSheet("background:#FFFFFF;border:1px solid #E0E3E7;border-radius:10px;")
    header.addWidget(gmail_logo)
    titles = QVBoxLayout()
    title = QLabel("Gmail")
    title.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:850;")
    subtitle = QLabel(
        "Read-only mailbox. Select a message, then choose its email body or one supported attachment to import locally into Protect."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)
    privacy = QLabel("READ-ONLY • LOCAL IMPORT")
    privacy.setStyleSheet("background:#FCE8E6;color:#B3261E;border-radius:9px;padding:6px 9px;font-size:9px;font-weight:800;")
    header.addWidget(privacy)
    root.addLayout(header)

    try:
        logo_loader = ProviderLogoLoader(service.data_dir, dialog)
        logo_loader.load(
            "gmail",
            lambda pixmap: gmail_logo.setPixmap(
                pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        dialog._gmail_logo_loader = logo_loader
    except Exception:
        pass

    toolbar = QHBoxLayout()
    search = QLineEdit()
    search.setPlaceholderText("Search mail — sender, subject, keyword, has:attachment…")
    search.setClearButtonEnabled(True)
    search.setMinimumHeight(40)
    search.setStyleSheet(
        "QLineEdit{background:#EAF1FB;color:#202124;border:1px solid #EAF1FB;border-radius:20px;padding:8px 15px;font-size:10px;}"
        "QLineEdit:focus{background:#FFFFFF;border-color:#AECBFA;}"
    )
    search_button = QPushButton("Search")
    search_button.setObjectName("Primary")
    toolbar.addWidget(search, 1)
    toolbar.addWidget(search_button)
    root.addLayout(toolbar)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)

    folders_frame = QFrame()
    folders_layout = QVBoxLayout(folders_frame)
    folders_layout.setContentsMargins(0, 0, 4, 0)
    folders_layout.setSpacing(6)
    compose_hint = QLabel("MAIL")
    compose_hint.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:800;padding-left:8px;")
    folders_layout.addWidget(compose_hint)
    folders = QListWidget()
    folders.setStyleSheet(
        "QListWidget{background:#F8FAFD;border:0;padding:4px;color:#3C4043;}"
        "QListWidget::item{padding:9px 11px;border-radius:0 18px 18px 0;font-weight:650;}"
        "QListWidget::item:hover{background:#F2F6FC;}"
        "QListWidget::item:selected{background:#D3E3FD;color:#001D35;font-weight:800;}"
    )
    for label, value, key in (
        ("Inbox", "INBOX", "contact"),
        ("Starred", "STARRED", "check"),
        ("Sent", "SENT", "external"),
        ("All mail", "", "history"),
    ):
        item = QListWidgetItem(icon(key, color="#5F6368", size=17), label)
        item.setData(Qt.ItemDataRole.UserRole, value)
        folders.addItem(item)
    folders.setCurrentRow(0)
    folders_layout.addWidget(folders, 1)
    splitter.addWidget(folders_frame)

    messages = QListWidget()
    messages.setSpacing(1)
    messages.setStyleSheet(
        "QListWidget{background:#FFFFFF;border:1px solid #DADCE0;border-radius:10px;padding:4px;outline:0;}"
        "QListWidget::item{background:#FFFFFF;border-bottom:1px solid #ECEFF1;margin:0;}"
        "QListWidget::item:hover{background:#F5F8FC;}"
        "QListWidget::item:selected{background:#EAF1FB;color:#202124;}"
    )
    splitter.addWidget(messages)

    detail = QFrame()
    detail.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DADCE0;border-radius:10px;}")
    detail_layout = QVBoxLayout(detail)
    detail_layout.setContentsMargins(14, 13, 14, 13)
    detail_layout.setSpacing(8)
    detail_title = QLabel("Select an email")
    detail_title.setWordWrap(True)
    detail_title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:850;border:0;")
    detail_meta = QLabel("Choose a message to see what can be imported.")
    detail_meta.setWordWrap(True)
    detail_meta.setStyleSheet(f"color:{MUTED};font-size:9px;border:0;")
    detail_layout.addWidget(detail_title)
    detail_layout.addWidget(detail_meta)
    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet("background:#E8EAED;border:0;")
    detail_layout.addWidget(divider)
    content_label = QLabel("CONTENTS")
    content_label.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:850;border:0;")
    detail_layout.addWidget(content_label)
    sources = QListWidget()
    sources.setStyleSheet(
        "QListWidget{background:#FFFFFF;border:0;outline:0;}"
        "QListWidget::item{padding:9px 8px;border:1px solid transparent;border-radius:8px;margin:2px 0;}"
        "QListWidget::item:hover{background:#F8FAFD;}"
        "QListWidget::item:selected{background:#E8F0FE;border-color:#AECBFA;color:#174EA6;}"
    )
    detail_layout.addWidget(sources, 1)
    detail_hint = QLabel("The selected content is copied to PrivacyGate locally; nothing is sent to AI.")
    detail_hint.setWordWrap(True)
    detail_hint.setStyleSheet("background:#F1F8E9;color:#33691E;border:0;border-radius:8px;padding:8px;font-size:9px;")
    detail_layout.addWidget(detail_hint)
    splitter.addWidget(detail)
    splitter.setSizes([155, 610, 315])
    root.addWidget(splitter, 1)

    footer = QHBoxLayout()
    count = QLabel("0 loaded")
    count.setStyleSheet(f"color:{MUTED};font-weight:700;")
    load_more = QPushButton("Load 30 more")
    load_more.setObjectName("Secondary")
    close = QPushButton("Close")
    close.setObjectName("Secondary")
    use = QPushButton("Use in Protect")
    use.setObjectName("Primary")
    use.setEnabled(False)
    footer.addWidget(count)
    footer.addWidget(load_more)
    footer.addStretch(1)
    footer.addWidget(close)
    footer.addWidget(use)
    root.addLayout(footer)

    state = {"next": "", "query": "", "label": "INBOX"}
    lookup = {}
    attachment_cache: dict[str, tuple[GmailAttachment, ...]] = {}
    source_lookup: dict[str, GmailAttachment | None] = {}

    def append_batch(batch) -> None:
        for remote in batch:
            if not remote.item_id or remote.item_id in lookup:
                continue
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, remote.item_id)
            item.setSizeHint(QSize(0, 72))
            messages.addItem(item)
            messages.setItemWidget(item, _message_widget(remote))
            lookup[remote.item_id] = remote
        count.setText(f"{len(lookup)} loaded")

    def fetch(reset: bool) -> None:
        if reset:
            messages.clear()
            lookup.clear()
            state["next"] = ""
            sources.clear()
            source_lookup.clear()
            use.setEnabled(False)
            detail_title.setText("Select an email")
            detail_meta.setText("Choose a message to see its body and supported attachments.")
        try:
            batch, next_token = _run_busy(
                dialog,
                "Loading Gmail",
                "Searching Gmail…" if state["query"] else ("Loading 30 emails from Gmail…" if reset else "Loading 30 more emails…"),
                lambda: _retry(
                    lambda: service.list_gmail_page(
                        state["next"], 30, state["query"], state["label"]
                    )
                ),
            )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to read Gmail", str(exc))
            return
        append_batch(batch)
        state["next"] = next_token
        load_more.setVisible(bool(next_token))

    def apply_search() -> None:
        state["query"] = search.text().strip()
        fetch(True)

    def folder_changed(current, _previous) -> None:
        if current is None:
            return
        state["label"] = str(current.data(Qt.ItemDataRole.UserRole) or "")
        fetch(True)

    def selected_remote():
        current = messages.currentItem()
        if current is None:
            return None
        return lookup.get(current.data(Qt.ItemDataRole.UserRole))

    def selected_source() -> tuple[str, GmailAttachment | None]:
        current = sources.currentItem()
        if current is None:
            return "", None
        key = str(current.data(Qt.ItemDataRole.UserRole) or "")
        return key, source_lookup.get(key)

    def refresh_use_state() -> None:
        key, _attachment = selected_source()
        use.setEnabled(selected_remote() is not None and bool(key))

    def message_changed(current, _previous) -> None:
        sources.clear()
        source_lookup.clear()
        use.setEnabled(False)
        if current is None:
            detail_title.setText("Select an email")
            detail_meta.setText("Choose a message to see its body and supported attachments.")
            return
        remote = selected_remote()
        if remote is None:
            return
        detail_title.setText(remote.title)
        detail_meta.setText(f"{_sender_name(remote)}\nChoose the email body or one attachment.")

        body_item = QListWidgetItem(icon("contact", color=GMAIL_BLUE, size=18), "Email body")
        body_item.setToolTip("Import the message headers and plain-text email body into Protect.")
        body_item.setData(Qt.ItemDataRole.UserRole, "body")
        sources.addItem(body_item)
        source_lookup["body"] = None

        try:
            attachments = attachment_cache.get(remote.item_id)
            if attachments is None:
                attachments = _run_busy(
                    dialog,
                    "Reading email contents",
                    "Checking this email for supported attachments…",
                    lambda: _retry(lambda: list_gmail_attachments(service, remote)),
                )
                attachment_cache[remote.item_id] = attachments
        except Exception as exc:
            detail_meta.setText(f"{_sender_name(remote)}\nAttachments could not be checked: {exc}")
            attachments = ()

        for index, attachment in enumerate(attachments):
            key = f"attachment:{index}"
            item = QListWidgetItem(
                _attachment_icon(attachment),
                f"{attachment.filename}\n{_attachment_label(attachment)}",
            )
            item.setToolTip(f"Import {attachment.filename} into the same local document pipeline as a local upload.")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, 48))
            sources.addItem(item)
            source_lookup[key] = attachment

        sources.setCurrentRow(0)
        if attachments:
            detail_meta.setText(
                f"{_sender_name(remote)}\n1 email body + {len(attachments)} supported attachment(s) available."
            )
        refresh_use_state()

    def import_body(remote) -> None:
        local_path = _run_busy(
            dialog,
            "Importing from Gmail",
            "Preparing the selected email body locally…",
            lambda: _retry(lambda: materialize_gmail_message(service, remote)),
        )
        email_text = local_path.read_text(encoding="utf-8")
        protect = main_window.protection_page
        paste_button = getattr(protect, "_redesign_paste_mode", None)
        if paste_button is not None and not paste_button.isChecked():
            paste_button.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(email_text)
        return protect

    def import_attachment(remote, attachment: GmailAttachment):
        local_path = _run_busy(
            dialog,
            "Importing Gmail attachment",
            f"Preparing {attachment.filename} locally…",
            lambda: _retry(lambda: materialize_gmail_attachment(service, remote, attachment)),
        )
        protect = main_window.protection_page
        document_button = getattr(protect, "_redesign_document_mode", None)
        if document_button is not None and not document_button.isChecked():
            document_button.click()
        protect.input_tabs.setCurrentIndex(1)
        protect.pdf_path.setText(str(local_path))
        return protect

    def use_selected() -> None:
        remote = selected_remote()
        key, attachment = selected_source()
        if remote is None or not key:
            return
        try:
            if key == "body":
                protect = import_body(remote)
                component_title = "Email body"
                component_kind = "email_body"
            elif attachment is not None:
                protect = import_attachment(remote, attachment)
                component_title = attachment.filename
                component_kind = Path(attachment.filename).suffix.lower().lstrip(".") or "attachment"
            else:
                return
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Gmail", str(exc))
            return

        account_id, account_label = _active_account_details(service)
        source_parts = ["Gmail"]
        if account_label:
            source_parts.append(account_label)
        source_parts.extend((remote.title, component_title))
        protect._external_source_name = " • ".join(source_parts)
        protect._external_source_metadata = {
            "provider": "gmail",
            "provider_label": "Gmail",
            "account_id": account_id,
            "account_label": account_label,
            "item_id": str(remote.item_id or ""),
            "item_title": str(remote.title or ""),
            "item_kind": str(remote.kind or "email"),
            "source_component": component_kind,
            "source_component_title": component_title,
        }
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported from Gmail: {component_title} — ready for local scan", 9000
        )

    search.returnPressed.connect(apply_search)
    search_button.clicked.connect(apply_search)
    folders.currentItemChanged.connect(folder_changed)
    load_more.clicked.connect(lambda: fetch(False))
    messages.currentItemChanged.connect(message_changed)
    sources.currentItemChanged.connect(lambda _current, _previous: refresh_use_state())
    sources.itemDoubleClicked.connect(lambda _item: use.click())
    use.clicked.connect(use_selected)
    close.clicked.connect(dialog.reject)

    fetch(True)
    dialog.exec()
