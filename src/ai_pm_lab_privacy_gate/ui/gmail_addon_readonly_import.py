from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

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
    MODE_READONLY,
)
from ai_pm_lab_privacy_gate.ui.gmail_addon_import import (
    GMAIL_URL,
    MUTED,
    NAVY,
    _adopt_addon_component,
    _bring_to_front,
    _button_style,
    _data_dir,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon


def open_gmail_readonly_import(main_window) -> None:
    """Receive a message from the richer current-message readonly Gmail add-on."""
    transport = GmailAddonTransport(_data_dir(main_window), mode=MODE_READONLY)

    dialog = QDialog(main_window)
    dialog.setObjectName("GmailReadonlyImportDialog")
    dialog.setWindowTitle("Gmail → PrivacyGate · Enhanced preview")
    dialog.resize(800, 660)
    dialog.setMinimumSize(700, 570)
    dialog.setStyleSheet("QDialog#GmailReadonlyImportDialog{background:#F8FBFC;}")

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
    title = QLabel("Enhanced Gmail preview")
    title.setStyleSheet(f"color:{NAVY};font-size:21px;font-weight:950;")
    subtitle = QLabel(
        "Open an email in Gmail. The PrivacyGate sidebar can preview that open message before you choose “Open in PrivacyGate”."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:550;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    head.addLayout(titles, 1)

    badge = QLabel("ENHANCED")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        "background:#EDF4FF;color:#355F87;border:1px solid #C9DAEA;"
        "border-radius:8px;padding:5px 9px;font-size:8px;font-weight:950;"
    )
    head.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
    root.addLayout(head)

    scope_note = QLabel(
        "This mode uses Gmail's sensitive current-message readonly permission. It can inspect the message/thread currently open while the add-on is running, but it does not grant mailbox-wide gmail.readonly access."
    )
    scope_note.setWordWrap(True)
    scope_note.setStyleSheet(
        "background:#FFF8E8;color:#6D5320;border:1px solid #F0DCA8;"
        "border-radius:9px;padding:9px;font-size:8px;font-weight:650;"
    )
    root.addWidget(scope_note)

    status_card = QFrame(objectName="GmailReadonlyStatusCard")
    status_card.setStyleSheet(
        "QFrame#GmailReadonlyStatusCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
    )
    status_layout = QVBoxLayout(status_card)
    status_layout.setContentsMargins(14, 11, 14, 11)
    status_layout.setSpacing(6)

    status_title = QLabel("Checking enhanced Gmail add-on…")
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
    advanced = QPushButton("Configure enhanced deployment")
    advanced.setStyleSheet(_button_style(False))
    reset = QPushButton("Pair another device")
    reset.setStyleSheet(_button_style(False))
    action_row.addWidget(open_gmail)
    action_row.addWidget(advanced)
    action_row.addWidget(reset)
    action_row.addStretch(1)
    status_layout.addLayout(action_row)
    root.addWidget(status_card)

    preview = QFrame(objectName="GmailReadonlyPreview")
    preview.setStyleSheet(
        "QFrame#GmailReadonlyPreview{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
    )
    preview_layout = QVBoxLayout(preview)
    preview_layout.setContentsMargins(14, 12, 14, 12)
    preview_layout.setSpacing(7)

    message_title = QLabel("Waiting for Gmail")
    message_title.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
    message_meta = QLabel(
        "In Gmail, preview the open message in the PrivacyGate sidebar and press “Open in PrivacyGate”."
    )
    message_meta.setWordWrap(True)
    message_meta.setStyleSheet(f"color:{MUTED};font-size:9px;")
    preview_layout.addWidget(message_title)
    preview_layout.addWidget(message_meta)

    body_preview = QTextEdit()
    body_preview.setReadOnly(True)
    body_preview.setPlaceholderText("The message you choose in Gmail will appear here.")
    body_preview.setMinimumHeight(235)
    body_preview.setStyleSheet(
        "QTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D7E2EA;"
        "border-radius:8px;padding:12px;font-size:10px;}"
    )
    preview_layout.addWidget(body_preview, 1)

    components = QListWidget()
    components.setMaximumHeight(92)
    components.setStyleSheet(
        "QListWidget{background:#FAFCFD;border:1px solid #E1E8ED;border-radius:8px;padding:4px;}"
        "QListWidget::item{padding:6px;border-radius:6px;}"
        "QListWidget::item:selected{background:#E8F6F6;color:#0B7180;}"
    )
    components.hide()
    preview_layout.addWidget(components)
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
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="privacygate-gmail-readonly")

    def set_setup_state() -> None:
        endpoint_ready = bool(transport.endpoint)
        pairing_value.setVisible(endpoint_ready and not transport.paired)
        copy_pairing.setVisible(endpoint_ready and not transport.paired)
        reset.setVisible(endpoint_ready and transport.paired)
        advanced.setVisible(not endpoint_ready)
        if not endpoint_ready:
            badge.setText("SETUP")
            status_title.setText("Enhanced Gmail add-on is not configured")
            status_text.setText("Configure the separate readonly Apps Script web-app endpoint once for this build.")
            state_label.setText("Setup required")
            state["mode"] = "idle"
        elif transport.paired:
            badge.setText("READY")
            status_title.setText("Enhanced Gmail preview is connected")
            status_text.setText("Open one email in Gmail, review it in the PrivacyGate sidebar, then press “Open in PrivacyGate”.")
            state_label.setText("Waiting for Gmail")
            state["mode"] = "poll"
        else:
            badge.setText("PAIR ONCE")
            status_title.setText("Pair enhanced Gmail preview with this device")
            status_text.setText("Copy this code into the enhanced PrivacyGate Gmail add-on. This pairing is separate from Standard mode.")
            state_label.setText("Waiting for pairing")
            state["mode"] = "status"

    def copy_code() -> None:
        QApplication.clipboard().setText(transport.channel)
        state_label.setText("Pairing code copied")

    def configure_endpoint() -> None:
        value, ok = QInputDialog.getText(
            dialog,
            "Configure enhanced Gmail preview",
            "Readonly Apps Script web-app URL:",
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
        components.hide()
        body_preview.clear()
        state["message"] = None
        use.setEnabled(False)
        set_setup_state()

    def render_message(message: GmailAddonMessage) -> None:
        state["message"] = message
        message_title.setText(message.subject or "(No subject)")
        meta_parts = [part for part in (message.sender, message.sent_at) if part]
        message_meta.setText("  •  ".join(meta_parts) or "Selected Gmail message")
        body_preview.setPlainText(message.body.strip() or "(No plain-text email body)")
        components.clear()

        body_item = QListWidgetItem("Email message")
        body_item.setData(Qt.ItemDataRole.UserRole, ("body", -1))
        components.addItem(body_item)
        for index, attachment in enumerate(message.attachments):
            item = QListWidgetItem(f"Attachment: {attachment.filename}")
            item.setData(Qt.ItemDataRole.UserRole, ("attachment", index))
            components.addItem(item)
        components.setCurrentRow(0)
        components.setVisible(bool(message.attachments))
        use.setEnabled(True)
        badge.setText("RECEIVED")
        status_title.setText("Email received — ready for Protect")
        status_text.setText("Review the message below, then choose “Use in Protect”.")
        state_label.setText("Selected email received")
        _bring_to_front(dialog, main_window)

    def background_operation():
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
            state["future"] = executor.submit(background_operation)

    def use_selected() -> None:
        message = state.get("message")
        current = components.currentItem()
        if not isinstance(message, GmailAddonMessage) or current is None:
            return
        choice = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(choice, tuple) or len(choice) != 2:
            return
        kind, index = choice
        try:
            component_title, _component_kind = _adopt_addon_component(
                main_window,
                message,
                str(kind),
                int(index),
                transport,
            )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Gmail", str(exc))
            return

        protect = main_window.protection_page
        protect._external_source_metadata["access_model"] = "gmail_addons_current_message_readonly"
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported from enhanced Gmail preview: {component_title} — ready for local scan",
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
