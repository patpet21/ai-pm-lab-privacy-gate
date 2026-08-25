from __future__ import annotations

import time

import httpx
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
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
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_import import materialize_gmail_message


NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
MUTED = "#61798A"
BORDER = "#D7E2EA"


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


def _message_widget(remote) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(11, 7, 11, 7)
    layout.setSpacing(2)

    top = QHBoxLayout()
    sender = remote.subtitle.split(" • ", 1)[0] if remote.subtitle else ""
    date = remote.subtitle.split(" • ", 1)[1] if " • " in remote.subtitle else ""
    sender_label = QLabel(sender or "Unknown sender")
    sender_label.setStyleSheet(f"color:{NAVY};font-weight:850;font-size:11px;")
    date_label = QLabel(date)
    date_label.setStyleSheet(f"color:{MUTED};font-size:9px;")
    top.addWidget(sender_label, 1)
    top.addWidget(date_label)
    layout.addLayout(top)

    subject = QLabel(remote.title)
    subject.setStyleSheet(f"color:{NAVY_SOFT};font-weight:800;font-size:11px;")
    subject.setWordWrap(False)
    layout.addWidget(subject)

    snippet = QLabel(remote.url or "")
    snippet.setStyleSheet(f"color:{MUTED};font-size:9px;")
    snippet.setWordWrap(False)
    layout.addWidget(snippet)
    return box


def open_gmail_inbox(main_window) -> None:
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None
    if service is None or not hasattr(service, "list_gmail_page"):
        QMessageBox.warning(main_window, "Gmail", "Gmail connector is unavailable in this build.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Gmail — messages")
    dialog.resize(980, 680)
    dialog.setMinimumSize(820, 560)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 16)
    root.setSpacing(10)

    title = QLabel("Gmail messages")
    title.setStyleSheet(f"color:{NAVY};font-size:25px;font-weight:900;")
    subtitle = QLabel("Browse your mailbox read-only. Only the message you choose is copied locally into PrivacyGate.")
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    root.addWidget(title)
    root.addWidget(subtitle)

    toolbar = QHBoxLayout()
    search = QLineEdit()
    search.setPlaceholderText("Search mail — sender, subject, keywords…")
    search.setClearButtonEnabled(True)
    search.setMinimumHeight(38)
    search.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#10263A;border:1px solid #C8D6E0;border-radius:9px;padding:7px 11px;}"
        "QLineEdit:focus{border-color:#1595A3;}"
    )
    search_button = QPushButton("Search")
    search_button.setObjectName("Primary")
    toolbar.addWidget(search, 1)
    toolbar.addWidget(search_button)
    root.addLayout(toolbar)

    body = QHBoxLayout()
    body.setSpacing(12)

    folders = QListWidget()
    folders.setFixedWidth(165)
    folders.setStyleSheet(
        "QListWidget{background:#F8FBFC;border:1px solid #D7E2EA;border-radius:10px;padding:7px;color:#17384E;}"
        "QListWidget::item{padding:9px 10px;border-radius:7px;font-weight:700;}"
        "QListWidget::item:hover{background:#EAF7F7;}"
        "QListWidget::item:selected{background:#0B7180;color:#FFFFFF;}"
    )
    folder_defs = (("Inbox", "INBOX"), ("Starred", "STARRED"), ("Sent", "SENT"), ("All mail", ""))
    for label, value in folder_defs:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, value)
        folders.addItem(item)
    folders.setCurrentRow(0)
    body.addWidget(folders)

    messages = QListWidget()
    messages.setSpacing(3)
    messages.setStyleSheet(
        "QListWidget{background:#FFFFFF;border:1px solid #C9D7E1;border-radius:10px;padding:6px;outline:0;}"
        "QListWidget::item{background:#FFFFFF;border:1px solid transparent;border-radius:8px;margin:1px 0;}"
        "QListWidget::item:hover{background:#EEF8F8;border-color:#B8E1E4;}"
        "QListWidget::item:selected{background:#DFF2F2;border-color:#8FC7CC;color:#062B4F;}"
    )
    body.addWidget(messages, 1)
    root.addLayout(body, 1)

    footer = QHBoxLayout()
    count = QLabel("0 loaded")
    count.setStyleSheet(f"color:{NAVY_SOFT};font-weight:750;")
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

    def append_batch(batch) -> None:
        for remote in batch:
            if not remote.item_id or remote.item_id in lookup:
                continue
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, remote.item_id)
            item.setSizeHint(QSize(0, 76))
            messages.addItem(item)
            messages.setItemWidget(item, _message_widget(remote))
            lookup[remote.item_id] = remote
        count.setText(f"{len(lookup)} loaded")

    def fetch(reset: bool) -> None:
        if reset:
            messages.clear()
            lookup.clear()
            state["next"] = ""
        try:
            batch, next_token = _run_busy(
                dialog,
                "Loading Gmail",
                "Loading 30 emails from Gmail…" if reset else "Loading 30 more emails…",
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

    def use_selected() -> None:
        current = messages.currentItem()
        if current is None:
            return
        remote = lookup.get(current.data(Qt.ItemDataRole.UserRole))
        if remote is None:
            return
        try:
            local_path = _run_busy(
                dialog,
                "Importing from Gmail",
                "Preparing the selected email locally…",
                lambda: _retry(lambda: materialize_gmail_message(service, remote)),
            )
            email_text = local_path.read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Gmail", str(exc))
            return

        protect = main_window.protection_page
        paste_button = getattr(protect, "_redesign_paste_mode", None)
        if paste_button is not None and not paste_button.isChecked():
            paste_button.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(email_text)
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported from Gmail: {remote.title} — ready for local scan", 9000
        )

    search.returnPressed.connect(apply_search)
    search_button.clicked.connect(apply_search)
    folders.currentItemChanged.connect(folder_changed)
    load_more.clicked.connect(lambda: fetch(False))
    messages.currentItemChanged.connect(lambda current, _prev: use.setEnabled(current is not None))
    messages.itemDoubleClicked.connect(lambda _item: use.click())
    use.clicked.connect(use_selected)
    close.clicked.connect(dialog.reject)

    fetch(True)
    dialog.exec()
