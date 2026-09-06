from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import (
    GmailAddonMessage,
    GmailAddonTransport,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
PETROL = "#0B7180"
MUTED = "#607789"
GMAIL_URL = "https://mail.google.com/"


def _button_style(primary: bool = False) -> str:
    if primary:
        return (
            "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
            "border-radius:9px;padding:8px 14px;font-weight:850;}"
            "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
            "QPushButton:disabled{background:#D9E2E8;color:#8A99A5;border-color:#D9E2E8;}"
        )
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C4D3DE;"
        "border-radius:9px;padding:8px 13px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;color:#062B4F;border-color:#9BCDD1;}"
    )


def _data_dir(main_window) -> Path:
    apps_page = getattr(main_window, "apps_hub_page", None)
    service = getattr(apps_page, "service", None) if apps_page is not None else None
    data_dir = getattr(service, "data_dir", None) if service is not None else None
    if data_dir:
        return Path(data_dir)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "PrivacyGate"
    return Path.home() / ".privacygate"


def _format_message(message: GmailAddonMessage) -> str:
    lines = []
    if message.sender:
        lines.append(f"From: {message.sender}")
    if message.recipients:
        lines.append(f"To: {message.recipients}")
    if message.sent_at:
        lines.append(f"Date: {message.sent_at}")
    lines.append(f"Subject: {message.subject}")
    lines.append("")
    lines.append(message.body)
    return "\n".join(lines).strip()


def _bring_to_front(dialog: QDialog, main_window) -> None:
    """Best-effort foreground activation after Gmail delivers a message."""
    try:
        main_window.showNormal()
        main_window.raise_()
        main_window.activateWindow()
    except Exception:
        pass

    try:
        dialog.showNormal()
        dialog.raise_()
        dialog.activateWindow()
        QApplication.alert(dialog, 3000)
    except Exception:
        pass

    if os.name == "nt":
        try:
            import ctypes

            hwnd = int(dialog.winId())
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def open_gmail_addon_import(main_window) -> None:
    """Receive one explicitly selected Gmail message through the Gmail Add-on.

    PrivacyGate never receives mailbox-wide OAuth access here. The only email
    available to this flow is the message the user explicitly sends from the
    PrivacyGate Gmail add-on.
    """
    transport = GmailAddonTransport(_data_dir(main_window))
    dialog = QDialog(main_window)
    dialog.setObjectName("GmailAddonImportDialog")
    dialog.setWindowTitle("Gmail → PrivacyGate")
    dialog.resize(780, 650)
    dialog.setMinimumSize(690, 560)
    dialog.setStyleSheet("QDialog#GmailAddonImportDialog{background:#F8FBFC;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 20, 22, 18)
    root.setSpacing(12)

    head = QHBoxLayout()
    mark = QLabel()
    mark.setFixedSize(44, 44)
    mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mark.setPixmap(icon("contact", color="#EA4335", size=25).pixmap(25, 25))
    mark.setStyleSheet("background:#FFFFFF;border:1px solid #DCE6EC;border-radius:11px;")
    head.addWidget(mark)

    titles = QVBoxLayout()
    title = QLabel("Bring a Gmail message into Protect")
    title.setStyleSheet(f"color:{NAVY};font-size:21px;font-weight:950;")
    subtitle = QLabel(
        "1. Open an email in Gmail  •  2. Click “Send to PrivacyGate”  •  "
        "3. PrivacyGate receives it and comes back to the front automatically."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:550;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    head.addLayout(titles, 1)

    badge = QLabel("ADD-ON")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
        "border-radius:8px;padding:5px 9px;font-size:8px;font-weight:950;"
    )
    head.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
    root.addLayout(head)

    privacy = QLabel(
        "Only the email you explicitly choose is transferred. PrivacyGate does not receive "
        "mailbox-wide access and processes the received content locally."
    )
    privacy.setWordWrap(True)
    privacy.setStyleSheet(
        "background:#F1F8E9;color:#33691E;border:1px solid #D9EBCB;"
        "border-radius:9px;padding:9px;font-size:8px;font-weight:650;"
    )
    root.addWidget(privacy)

    status_card = QFrame(objectName="GmailAddonStatusCard")
    status_card.setStyleSheet(
        "QFrame#GmailAddonStatusCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
    )
    status_layout = QVBoxLayout(status_card)
    status_layout.setContentsMargins(14, 12, 14, 12)
    status_layout.setSpacing(7)

    status_title = QLabel("Checking Gmail Add-on…")
    status_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
    status_text = QLabel("")
    status_text.setWordWrap(True)
    status_text.setStyleSheet(f"color:{MUTED};font-size:9px;")
    status_layout.addWidget(status_title)
    status_layout.addWidget(status_text)

    setup_row = QHBoxLayout()
    pairing_value = QLabel(transport.channel)
    pairing_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    pairing_value.setStyleSheet(
        "background:#F6F8FA;color:#17384E;border:1px solid #D7E2EA;"
        "border-radius:8px;padding:8px 10px;font-family:monospace;font-size:9px;"
    )
    copy_pairing = QPushButton("Copy pairing code")
    copy_pairing.setStyleSheet(_button_style(False))
    setup_row.addWidget(pairing_value, 1)
    setup_row.addWidget(copy_pairing)
    status_layout.addLayout(setup_row)

    action_row = QHBoxLayout()
    open_gmail = QPushButton("Open Gmail")
    open_gmail.setIcon(icon("external", color="#FFFFFF", size=16))
    open_gmail.setStyleSheet(_button_style(True))
    advanced = QPushButton("Configure test deployment")
    advanced.setStyleSheet(_button_style(False))
    reset = QPushButton("Pair another device")
    reset.setStyleSheet(_button_style(False))
    action_row.addWidget(open_gmail)
    action_row.addWidget(advanced)
    action_row.addWidget(reset)
    action_row.addStretch(1)
    status_layout.addLayout(action_row)
    root.addWidget(status_card)

    preview = QFrame(objectName="GmailAddonPreview")
    preview.setStyleSheet(
        "QFrame#GmailAddonPreview{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
    )
    preview_layout = QVBoxLayout(preview)
    preview_layout.setContentsMargins(14, 12, 14, 12)
    preview_layout.setSpacing(7)

    message_title = QLabel("Waiting for a selected email")
    message_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
    message_meta = QLabel(
        "Keep this window open, then choose an email in Gmail and click “Send to PrivacyGate”. "
        "When it arrives, PrivacyGate will bring this window back to the front automatically."
    )
    message_meta.setWordWrap(True)
    message_meta.setStyleSheet(f"color:{MUTED};font-size:9px;")
    preview_layout.addWidget(message_title)
    preview_layout.addWidget(message_meta)

    components = QListWidget()
    components.setMinimumHeight(105)
    components.setStyleSheet(
        "QListWidget{background:#FAFCFD;border:1px solid #E1E8ED;border-radius:8px;padding:4px;}"
        "QListWidget::item{padding:7px;border-radius:6px;}"
        "QListWidget::item:selected{background:#E8F6F6;color:#0B7180;}"
    )
    preview_layout.addWidget(components)

    body_preview = QTextEdit()
    body_preview.setReadOnly(True)
    body_preview.setPlaceholderText("The selected email will appear here automatically.")
    body_preview.setStyleSheet(
        "QTextEdit{background:#FAFCFD;color:#17384E;border:1px solid #E1E8ED;"
        "border-radius:8px;padding:8px;font-size:9px;}"
    )
    preview_layout.addWidget(body_preview, 1)
    root.addWidget(preview, 1)

    footer = QHBoxLayout()
    state_label = QLabel("Waiting")
    state_label.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:750;")
    close = QPushButton("Close")
    close.setStyleSheet(_button_style(False))
    use = QPushButton("Use in Protect")
    use.setStyleSheet(_button_style(True))
    use.setEnabled(False)
    footer.addWidget(state_label)
    footer.addStretch(1)
    footer.addWidget(close)
    footer.addWidget(use)
    root.addLayout(footer)

    state: dict[str, object] = {"message": None, "future": None, "mode": "status"}
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="privacygate-gmail-addon")

    def set_setup_state() -> None:
        endpoint_ready = bool(transport.endpoint)
        pairing_value.setVisible(endpoint_ready and not transport.paired)
        copy_pairing.setVisible(endpoint_ready and not transport.paired)
        reset.setVisible(endpoint_ready and transport.paired)
        advanced.setVisible(not endpoint_ready)
        if not endpoint_ready:
            badge.setText("SETUP")
            status_title.setText("Gmail Add-on test deployment is not configured")
            status_text.setText(
                "The public release will ship with this endpoint already configured. "
                "For the current development build, configure the Apps Script web-app deployment once."
            )
            state_label.setText("Setup required")
            state["mode"] = "idle"
        elif transport.paired:
            badge.setText("READY")
            status_title.setText("Gmail is connected")
            status_text.setText(
                "Choose an email in Gmail and click “Send to PrivacyGate”. "
                "This window will return to the front automatically when the email arrives."
            )
            state_label.setText("Waiting for Gmail")
            state["mode"] = "poll"
        else:
            badge.setText("PAIR ONCE")
            status_title.setText("Pair Gmail with this device once")
            status_text.setText(
                "Copy this one-time device code into the PrivacyGate add-on in Gmail. "
                "After pairing, future imports do not require another transfer code."
            )
            state_label.setText("Waiting for pairing")
            state["mode"] = "status"

    def copy_code() -> None:
        QApplication.clipboard().setText(transport.channel)
        state_label.setText("Pairing code copied")

    def configure_endpoint() -> None:
        value, ok = QInputDialog.getText(
            dialog,
            "Configure Gmail Add-on test deployment",
            "Apps Script web-app URL:",
            text=transport.endpoint,
        )
        if not ok:
            return
        try:
            transport.set_endpoint(value)
        except Exception as exc:
            QMessageBox.warning(dialog, "Gmail Add-on", str(exc))
            return
        set_setup_state()

    def reset_pairing() -> None:
        transport.reset_pairing()
        pairing_value.setText(transport.channel)
        components.clear()
        body_preview.clear()
        state["message"] = None
        use.setEnabled(False)
        set_setup_state()

    def render_message(message: GmailAddonMessage) -> None:
        state["message"] = message
        message_title.setText(message.subject or "(No subject)")
        meta = message.sender
        if message.sent_at:
            meta = f"{meta} • {message.sent_at}" if meta else message.sent_at
        message_meta.setText(meta or "Selected Gmail message")
        body_preview.setPlainText(_format_message(message))
        components.clear()

        body_item = QListWidgetItem("Email body")
        body_item.setData(Qt.ItemDataRole.UserRole, ("body", -1))
        components.addItem(body_item)
        for index, attachment in enumerate(message.attachments):
            item = QListWidgetItem(f"{attachment.filename}  •  attachment")
            item.setData(Qt.ItemDataRole.UserRole, ("attachment", index))
            components.addItem(item)
        components.setCurrentRow(0)
        use.setEnabled(True)
        badge.setText("RECEIVED")
        status_title.setText("Email received from Gmail")
        status_text.setText("Review the email below, then choose “Use in Protect”.")
        state_label.setText("Selected email received")
        _bring_to_front(dialog, main_window)

    def do_background_operation():
        mode = str(state.get("mode") or "")
        if mode == "status":
            return ("status", transport.check_pairing())
        if mode == "poll":
            return ("poll", transport.poll())
        return ("idle", None)

    def tick() -> None:
        future = state.get("future")
        if isinstance(future, Future):
            if not future.done():
                return
            state["future"] = None
            try:
                kind, result = future.result()
            except Exception as exc:
                state_label.setText(str(exc))
                return
            if kind == "status" and result:
                transport.mark_paired(True)
                set_setup_state()
            elif kind == "poll" and isinstance(result, GmailAddonMessage):
                render_message(result)
            return

        if state.get("mode") in {"status", "poll"}:
            state["future"] = executor.submit(do_background_operation)

    def use_selected() -> None:
        message = state.get("message")
        current = components.currentItem()
        if not isinstance(message, GmailAddonMessage) or current is None:
            return
        choice = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(choice, tuple) or len(choice) != 2:
            return

        protect = main_window.protection_page
        kind, index = choice
        component_title = "Email body"
        component_kind = "email_body"

        try:
            if kind == "body":
                paste_button = getattr(protect, "_redesign_paste_mode", None)
                if paste_button is not None and not paste_button.isChecked():
                    paste_button.click()
                protect.input_tabs.setCurrentIndex(0)
                protect.text_input.setPlainText(_format_message(message))
            else:
                attachment = message.attachments[int(index)]
                local_path = transport.materialize_attachment(attachment)
                document_button = getattr(protect, "_redesign_document_mode", None)
                if document_button is not None and not document_button.isChecked():
                    document_button.click()
                protect.input_tabs.setCurrentIndex(1)
                protect.pdf_path.setText(str(local_path))
                component_title = attachment.filename
                component_kind = Path(attachment.filename).suffix.lower().lstrip(".") or "attachment"
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Gmail", str(exc))
            return

        protect._external_source_name = " • ".join(
            part for part in ("Gmail Add-on", message.subject, component_title) if part
        )
        protect._external_source_metadata = {
            "provider": "gmail",
            "provider_label": "Gmail Add-on",
            "item_id": message.message_id,
            "thread_id": message.thread_id,
            "item_title": message.subject,
            "item_kind": "email",
            "source_component": component_kind,
            "source_component_title": component_title,
            "access_model": "gmail_addons_current_message_action",
        }
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported from Gmail Add-on: {component_title} — ready for local scan",
            9000,
        )

    copy_pairing.clicked.connect(copy_code)
    advanced.clicked.connect(configure_endpoint)
    reset.clicked.connect(reset_pairing)
    open_gmail.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GMAIL_URL)))
    close.clicked.connect(dialog.reject)
    use.clicked.connect(use_selected)
    components.itemDoubleClicked.connect(lambda _item: use.click())

    timer = QTimer(dialog)
    timer.setInterval(900)
    timer.timeout.connect(tick)
    timer.start()

    set_setup_state()
    tick()
    dialog.exec()

    timer.stop()
    executor.shutdown(wait=False, cancel_futures=True)
