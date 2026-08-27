from __future__ import annotations

from pathlib import Path

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
from ai_pm_lab_privacy_gate.ui import gmail_browser_route
from ai_pm_lab_privacy_gate.ui.gmail_inbox import (
    _active_account_details,
    _attachment_icon,
    _attachment_label,
    _message_widget,
    _retry,
    _sender_name,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


NAVY = "#202124"
MUTED = "#5F6368"
GMAIL_RED = "#EA4335"
GMAIL_BLUE = "#4285F4"
SUPPORTED_PACKAGE_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}


def _run_busy(parent, title: str, message: str, operation):
    busy = QProgressDialog(message, "", 0, 0, parent)
    busy.setWindowTitle(title)
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setCancelButton(None)
    busy.setMinimumDuration(0)
    busy.setMinimumWidth(410)
    busy.setAutoClose(False)
    busy.setAutoReset(False)
    busy.show()
    QApplication.processEvents()
    try:
        return operation()
    finally:
        busy.close()
        QApplication.processEvents()


def _source_item(text: str, key: str, *, attachment: GmailAttachment | None = None) -> QListWidgetItem:
    if attachment is None:
        item = QListWidgetItem(icon("contact", color=GMAIL_BLUE, size=18), text)
        item.setToolTip(
            "Include the email headers and plain-text body in this Protect session."
        )
    else:
        item = QListWidgetItem(
            _attachment_icon(attachment),
            f"{attachment.filename}\n{_attachment_label(attachment)}",
        )
        item.setToolTip(
            f"Include {attachment.filename} in this Protect session. It is copied "
            "to PrivacyGate's local temporary workspace first."
        )
        item.setSizeHint(QSize(0, 50))
    item.setData(Qt.ItemDataRole.UserRole, key)
    item.setFlags(
        item.flags()
        | Qt.ItemFlag.ItemIsUserCheckable
        | Qt.ItemFlag.ItemIsSelectable
        | Qt.ItemFlag.ItemIsEnabled
    )
    item.setCheckState(Qt.CheckState.Unchecked)
    return item


def _selected_keys(sources: QListWidget) -> list[str]:
    return [
        str(sources.item(index).data(Qt.ItemDataRole.UserRole) or "")
        for index in range(sources.count())
        if sources.item(index).checkState() == Qt.CheckState.Checked
    ]


def _document_as_text(protect, path: Path) -> str:
    document = protect.service.document_from_file(path)
    chunks: list[str] = []
    for page in document.pages:
        location = page.location.strip() if page.location else ""
        if location:
            chunks.append(f"--- {location} ---\n{page.text}")
        elif len(document.pages) > 1:
            chunks.append(f"--- Segment {page.page_number} ---\n{page.text}")
        else:
            chunks.append(page.text)
    return "\n\n".join(chunk for chunk in chunks if chunk.strip())


def open_gmail_package_browser(main_window) -> None:
    """Browse Gmail and import body + one or more supported attachments together."""
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None
    if service is None or not hasattr(service, "list_gmail_page"):
        QMessageBox.warning(main_window, "Gmail", "Gmail connector is unavailable in this build.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Gmail — import to Protect")
    dialog.resize(1140, 735)
    dialog.setMinimumSize(920, 590)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(9)

    header = QHBoxLayout()
    gmail_logo = QLabel()
    gmail_logo.setFixedSize(42, 42)
    gmail_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    gmail_logo.setPixmap(icon("contact", color=GMAIL_RED, size=24).pixmap(24, 24))
    gmail_logo.setStyleSheet(
        "background:#FFFFFF;border:1px solid #E0E3E7;border-radius:10px;"
    )
    header.addWidget(gmail_logo)
    titles = QVBoxLayout()
    title = QLabel("Gmail")
    title.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:850;")
    subtitle = QLabel(
        "Select an email, then check the email body, one attachment, or several "
        "attachments. Selected content is prepared locally and scanned together in Protect."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)
    privacy = QLabel("READ-ONLY • LOCAL IMPORT")
    privacy.setStyleSheet(
        "background:#FCE8E6;color:#B3261E;border-radius:9px;padding:6px 9px;"
        "font-size:9px;font-weight:800;"
    )
    header.addWidget(privacy)
    root.addLayout(header)

    try:
        logo_loader = ProviderLogoLoader(service.data_dir, dialog)
        logo_loader.load(
            "gmail",
            lambda pixmap: gmail_logo.setPixmap(
                pixmap.scaled(
                    26,
                    26,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
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
        "QLineEdit{background:#EAF1FB;color:#202124;border:1px solid #EAF1FB;"
        "border-radius:20px;padding:8px 15px;font-size:10px;}"
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
    folders_label = QLabel("MAIL")
    folders_label.setStyleSheet(
        f"color:{MUTED};font-size:9px;font-weight:800;padding-left:8px;"
    )
    folders_layout.addWidget(folders_label)
    folders = QListWidget()
    folders.setStyleSheet(
        "QListWidget{background:#F8FAFD;border:0;padding:4px;color:#3C4043;}"
        "QListWidget::item{padding:9px 11px;font-weight:650;}"
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
        "QListWidget{background:#FFFFFF;border:1px solid #DADCE0;border-radius:10px;"
        "padding:4px;outline:0;}"
        "QListWidget::item{background:#FFFFFF;border-bottom:1px solid #ECEFF1;margin:0;}"
        "QListWidget::item:hover{background:#F5F8FC;}"
        "QListWidget::item:selected{background:#EAF1FB;color:#202124;}"
    )
    splitter.addWidget(messages)

    detail = QFrame()
    detail.setStyleSheet(
        "QFrame{background:#FFFFFF;border:1px solid #DADCE0;border-radius:10px;}"
    )
    detail_layout = QVBoxLayout(detail)
    detail_layout.setContentsMargins(14, 13, 14, 13)
    detail_layout.setSpacing(8)
    detail_title = QLabel("Select an email")
    detail_title.setWordWrap(True)
    detail_title.setStyleSheet(
        f"color:{NAVY};font-size:13px;font-weight:850;border:0;"
    )
    detail_meta = QLabel("Choose a message to see its body and supported attachments.")
    detail_meta.setWordWrap(True)
    detail_meta.setStyleSheet(f"color:{MUTED};font-size:9px;border:0;")
    detail_layout.addWidget(detail_title)
    detail_layout.addWidget(detail_meta)

    source_actions = QHBoxLayout()
    contents_label = QLabel("CONTENTS TO PROTECT")
    contents_label.setStyleSheet(
        f"color:{MUTED};font-size:9px;font-weight:850;border:0;"
    )
    select_all = QPushButton("Select all")
    select_all.setObjectName("Tiny")
    clear_all = QPushButton("Clear")
    clear_all.setObjectName("Tiny")
    source_actions.addWidget(contents_label)
    source_actions.addStretch(1)
    source_actions.addWidget(select_all)
    source_actions.addWidget(clear_all)
    detail_layout.addLayout(source_actions)

    sources = QListWidget()
    sources.setSelectionMode(QListWidget.SelectionMode.NoSelection)
    sources.setStyleSheet(
        "QListWidget{background:#FFFFFF;border:0;outline:0;}"
        "QListWidget::item{padding:8px 7px;border:1px solid transparent;"
        "border-radius:8px;margin:2px 0;}"
        "QListWidget::item:hover{background:#F8FAFD;}"
    )
    detail_layout.addWidget(sources, 1)
    detail_hint = QLabel(
        "Check any combination. PDF, Word (.docx), Excel/Sheets exports (.xlsx), "
        "PowerPoint/Slides exports (.pptx) and TXT are processed locally."
    )
    detail_hint.setWordWrap(True)
    detail_hint.setStyleSheet(
        "background:#F1F8E9;color:#33691E;border:0;border-radius:8px;"
        "padding:8px;font-size:9px;"
    )
    detail_layout.addWidget(detail_hint)
    splitter.addWidget(detail)
    splitter.setSizes([155, 600, 330])
    root.addWidget(splitter, 1)

    footer = QHBoxLayout()
    count = QLabel("0 loaded")
    count.setStyleSheet(f"color:{MUTED};font-weight:700;")
    load_more = QPushButton("Load 30 more")
    load_more.setObjectName("Secondary")
    close = QPushButton("Close")
    close.setObjectName("Secondary")
    use = QPushButton("Use selected in Protect")
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

    def selected_remote():
        current = messages.currentItem()
        if current is None:
            return None
        return lookup.get(current.data(Qt.ItemDataRole.UserRole))

    def refresh_use_state() -> None:
        selected = _selected_keys(sources)
        use.setEnabled(selected_remote() is not None and bool(selected))
        if selected:
            use.setText(f"Use selected in Protect  ({len(selected)})")
        else:
            use.setText("Use selected in Protect")

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
            refresh_use_state()
            detail_title.setText("Select an email")
            detail_meta.setText("Choose a message to see its body and supported attachments.")
        try:
            batch, next_token = _run_busy(
                dialog,
                "Loading Gmail",
                "Searching Gmail…"
                if state["query"]
                else ("Loading 30 emails from Gmail…" if reset else "Loading 30 more emails…"),
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

    def message_changed(current, _previous) -> None:
        sources.clear()
        source_lookup.clear()
        refresh_use_state()
        if current is None:
            return
        remote = selected_remote()
        if remote is None:
            return
        detail_title.setText(remote.title)
        detail_meta.setText(
            f"{_sender_name(remote)}\nCheck the email body, attachments, or both."
        )

        body_item = _source_item("Email body", "body")
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
            detail_meta.setText(
                f"{_sender_name(remote)}\nAttachments could not be checked: {exc}"
            )
            attachments = ()

        for index, attachment in enumerate(attachments):
            key = f"attachment:{index}"
            sources.addItem(_source_item(attachment.filename, key, attachment=attachment))
            source_lookup[key] = attachment

        if attachments:
            detail_meta.setText(
                f"{_sender_name(remote)}\nEmail body + {len(attachments)} supported "
                "attachment(s). Check any combination."
            )
        refresh_use_state()

    def set_checks(checked: bool) -> None:
        state_value = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(sources.count()):
            sources.item(index).setCheckState(state_value)
        refresh_use_state()

    def use_selected() -> None:
        remote = selected_remote()
        keys = _selected_keys(sources)
        if remote is None or not keys:
            return

        want_body = "body" in keys
        attachments = [
            source_lookup[key]
            for key in keys
            if key.startswith("attachment:") and source_lookup.get(key) is not None
        ]
        try:
            body_text = ""
            if want_body:
                body_path = _run_busy(
                    dialog,
                    "Importing from Gmail",
                    "Preparing the selected email body locally…",
                    lambda: _retry(lambda: materialize_gmail_message(service, remote)),
                )
                body_text = body_path.read_text(encoding="utf-8")

            local_attachments: list[tuple[GmailAttachment, Path]] = []
            for attachment in attachments:
                local_path = _run_busy(
                    dialog,
                    "Importing Gmail attachment",
                    f"Preparing {attachment.filename} locally…",
                    lambda a=attachment: _retry(
                        lambda: materialize_gmail_attachment(service, remote, a)
                    ),
                )
                local_attachments.append((attachment, local_path))
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Gmail", str(exc))
            return

        protect = main_window.protection_page
        text_sections: list[str] = []
        if body_text.strip():
            text_sections.append(f"=== GMAIL EMAIL BODY ===\n{body_text.strip()}")

        primary_attachment: tuple[GmailAttachment, Path] | None = None
        if local_attachments:
            primary_attachment = local_attachments[0]
            protect.pdf_path.setText(str(primary_attachment[1]))
            protect.input_tabs.setCurrentIndex(1)

        # Protect currently provides one native document comparison lane. Any
        # additional selected attachment is still fully read by the same local
        # document pipeline and added to the joint text lane with a clear source
        # boundary. This preserves multi-attachment scanning without hiding data.
        for attachment, path in local_attachments[1:]:
            try:
                extracted = _document_as_text(protect, path)
            except Exception as exc:
                QMessageBox.warning(
                    dialog,
                    "Attachment could not be read",
                    f"{attachment.filename} could not be extracted locally:\n{exc}",
                )
                return
            text_sections.append(
                f"=== GMAIL ATTACHMENT · {attachment.filename} ===\n{extracted}"
            )

        if text_sections:
            protect.text_input.setPlainText("\n\n".join(text_sections))
        elif not want_body:
            protect.text_input.clear()

        if primary_attachment is None and want_body:
            protect.input_tabs.setCurrentIndex(0)

        account_id, account_label = _active_account_details(service)
        component_titles = (["Email body"] if want_body else []) + [
            attachment.filename for attachment, _path in local_attachments
        ]
        protect._external_source_name = " • ".join(
            [part for part in ("Gmail", account_label, remote.title) if part]
        )
        protect._external_source_metadata = {
            "provider": "gmail",
            "provider_label": "Gmail",
            "account_id": account_id,
            "account_label": account_label,
            "item_id": str(remote.item_id or ""),
            "item_title": str(remote.title or ""),
            "item_kind": str(remote.kind or "email"),
            "package_mode": "gmail_message_package",
            "selected_components": component_titles,
            "selected_component_count": len(component_titles),
            "email_body_selected": want_body,
            "attachment_count": len(local_attachments),
            "primary_attachment": primary_attachment[0].filename if primary_attachment else "",
        }
        protect._gmail_package_components = tuple(component_titles)

        sync_source_status = getattr(protect, "_protect_session_sync_source_status", None)
        if callable(sync_source_status):
            sync_source_status()
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported {len(component_titles)} Gmail component(s) locally into Protect.",
            7000,
        )

    def apply_search() -> None:
        state["query"] = search.text().strip()
        fetch(True)

    def folder_changed(current, _previous) -> None:
        if current is None:
            return
        state["label"] = str(current.data(Qt.ItemDataRole.UserRole) or "")
        fetch(True)

    sources.itemChanged.connect(lambda _item: refresh_use_state())
    select_all.clicked.connect(lambda: set_checks(True))
    clear_all.clicked.connect(lambda: set_checks(False))
    messages.currentItemChanged.connect(message_changed)
    search.returnPressed.connect(apply_search)
    search_button.clicked.connect(apply_search)
    folders.currentItemChanged.connect(folder_changed)
    load_more.clicked.connect(lambda: fetch(False))
    close.clicked.connect(dialog.reject)
    use.clicked.connect(use_selected)

    fetch(True)
    dialog.exec()


def apply_gmail_package_browser(main_window) -> None:
    """Route Gmail to the multi-component package picker."""
    gmail_browser_route.open_gmail_inbox = open_gmail_package_browser
