from __future__ import annotations

import io
import json
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager


def open_mobile_devices(main_window) -> None:
    manager = getattr(main_window, "_mobile_link_manager", None)
    if manager is None:
        manager = MobileLinkManager(main_window.service, main_window.library.data_dir)
        main_window._mobile_link_manager = manager
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(manager.stop)
    dialog = MobileDevicesDialog(manager, main_window)
    dialog.exec()


class MobileDevicesDialog(QDialog):
    def __init__(self, manager: MobileLinkManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._expires_at = 0.0
        self.setWindowTitle("Mobile Devices — PrivacyGate Device Trust")
        self.resize(820, 900)
        self.setStyleSheet(
            """
            QLabel#sectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #16243a;
                margin-top: 6px;
            }
            QLabel#helperText {
                color: #667085;
                font-size: 12px;
            }
            QLabel#selectionSummary {
                color: #174c55;
                background: #ecf8f7;
                border: 1px solid #b9e4e0;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QListWidget#pendingList, QListWidget#pairedList {
                background: #ffffff;
                border: 1px solid #d8e1eb;
                border-radius: 10px;
                padding: 4px;
                outline: 0;
            }
            QListWidget#pendingList::item, QListWidget#pairedList::item {
                color: #172033;
                background: #ffffff;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 10px 12px;
                margin: 2px;
            }
            QListWidget#pendingList::item:hover, QListWidget#pairedList::item:hover {
                background: #f3f8fb;
            }
            QListWidget#pendingList::item:selected, QListWidget#pairedList::item:selected {
                color: #0b3340;
                background: #dff5f3;
                border: 1px solid #15999b;
            }
            QPushButton:disabled {
                color: #98a2b3;
                background: #eef2f6;
                border-color: #d7dee7;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Pair only devices you own or trust, on your private local network. "
            "Creating pairing data starts the encrypted Desktop analysis service. "
            "A mobile device can request pairing, but Desktop approval is required "
            "before any credential is released. Library and restore mappings are not shared."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.status = QLabel()
        layout.addWidget(self.status)

        row = QHBoxLayout()
        pair = QPushButton("Create pairing data")
        pair.clicked.connect(self._pair)
        row.addWidget(pair)
        start = QPushButton("Start service")
        start.clicked.connect(self._start)
        row.addWidget(start)
        stop = QPushButton("Stop service")
        stop.clicked.connect(self._stop)
        row.addWidget(stop)
        layout.addLayout(row)

        qr_title = QLabel("Pair a mobile device")
        qr_title.setObjectName("sectionTitle")
        layout.addWidget(qr_title)
        qr_help = QLabel(
            "On PrivacyGate Mobile, open Settings → Desktop Connection and scan this temporary QR code."
        )
        qr_help.setObjectName("helperText")
        qr_help.setWordWrap(True)
        layout.addWidget(qr_help)

        self.qr = QLabel("Create pairing data to show a temporary QR code.")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setMinimumHeight(360)
        self.qr.setWordWrap(True)
        layout.addWidget(self.qr)

        self.bundle = QPlainTextEdit()
        self.bundle.setReadOnly(True)
        self.bundle.setMaximumHeight(92)
        self.bundle.setPlaceholderText(
            "Temporary pairing JSON appears here. On Mobile: Settings → Desktop Connection."
        )
        layout.addWidget(self.bundle)
        copy = QPushButton("Copy temporary pairing data")
        copy.clicked.connect(self._copy)
        layout.addWidget(copy)

        pending_title = QLabel("Pending pairing approvals")
        pending_title.setObjectName("sectionTitle")
        layout.addWidget(pending_title)

        self.pending_help = QLabel(
            "When a device requests access, select it below, then approve or deny the request."
        )
        self.pending_help.setObjectName("helperText")
        self.pending_help.setWordWrap(True)
        layout.addWidget(self.pending_help)

        self.pending = QListWidget()
        self.pending.setObjectName("pendingList")
        self.pending.setMinimumHeight(118)
        self.pending.currentItemChanged.connect(self._pending_selection_changed)
        layout.addWidget(self.pending)

        self.pending_selection = QLabel("No pending device selected.")
        self.pending_selection.setObjectName("selectionSummary")
        self.pending_selection.setWordWrap(True)
        layout.addWidget(self.pending_selection)

        pending_row = QHBoxLayout()
        self.approve_button = QPushButton("Approve device")
        self.approve_button.setEnabled(False)
        self.approve_button.clicked.connect(self._approve)
        pending_row.addWidget(self.approve_button)
        self.deny_button = QPushButton("Deny request")
        self.deny_button.setEnabled(False)
        self.deny_button.clicked.connect(self._deny)
        pending_row.addWidget(self.deny_button)
        layout.addLayout(pending_row)

        paired_title = QLabel("Paired devices")
        paired_title.setObjectName("sectionTitle")
        layout.addWidget(paired_title)
        paired_help = QLabel(
            "These devices have credentials for future authenticated requests. This is not an online-status list."
        )
        paired_help.setObjectName("helperText")
        paired_help.setWordWrap(True)
        layout.addWidget(paired_help)

        self.devices = QListWidget()
        self.devices.setObjectName("pairedList")
        self.devices.setMinimumHeight(95)
        self.devices.currentItemChanged.connect(self._paired_selection_changed)
        layout.addWidget(self.devices)

        self.revoke_button = QPushButton("Revoke selected device")
        self.revoke_button.setEnabled(False)
        self.revoke_button.clicked.connect(self._revoke)
        layout.addWidget(self.revoke_button)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)
        self._refresh()

    def _start(self) -> None:
        self.manager.start()
        self._refresh()

    def _stop(self) -> None:
        self.manager.stop()
        self.bundle.clear()
        self.qr.clear()
        self.qr.setText("Service stopped. Create fresh pairing data before pairing again.")
        self._refresh()

    def _pair(self) -> None:
        try:
            bundle = self.manager.create_pairing_bundle()
            self._expires_at = bundle.expires_at
            payload = bundle.as_dict()
            self.bundle.setPlainText(json.dumps(payload, indent=2))
            self._render_qr(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
        except Exception:
            QMessageBox.warning(
                self,
                "Pairing unavailable",
                "Could not start pairing. Check the service status and whether port 8767 is already in use.",
            )
        self._refresh()

    def _render_qr(self, payload: str) -> None:
        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_L

            # Keep every QR module on an exact integer pixel grid. The pairing
            # bundle contains the pinned TLS certificate and is intentionally
            # dense, so non-integer downscaling can make it hard to scan.
            code = qrcode.QRCode(
                version=None,
                error_correction=ERROR_CORRECT_L,
                box_size=4,
                border=4,
            )
            code.add_data(payload)
            code.make(fit=True)
            image = code.make_image(fill_color="black", back_color="white")
            output = io.BytesIO()
            image.save(output, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(output.getvalue(), "PNG"):
                raise RuntimeError("QR image could not be loaded")
            self.qr.setPixmap(pixmap)
            self.qr.setMinimumHeight(max(360, pixmap.height() + 12))
            self.qr.setToolTip(
                "Scan only with PrivacyGate Mobile. This QR expires automatically. "
                "Keep the whole white border visible in the phone camera."
            )
        except Exception:
            self.qr.clear()
            self.qr.setText(
                "QR generation is unavailable in this environment. "
                "The temporary JSON below remains usable for manual pairing."
            )

    def _copy(self) -> None:
        if self.bundle.toPlainText() and time.time() < self._expires_at:
            QApplication.clipboard().setText(self.bundle.toPlainText())

    def _pending_selection_changed(self, current, _previous=None) -> None:
        has_selection = current is not None
        self.approve_button.setEnabled(has_selection)
        self.deny_button.setEnabled(has_selection)
        if current is None:
            self.pending_selection.setText("No pending device selected.")
            return
        name = str(current.data(Qt.ItemDataRole.UserRole + 1) or "Mobile device")
        client_id = str(current.data(Qt.ItemDataRole.UserRole + 2) or "")
        self.pending_selection.setText(
            f"Selected for approval: {name}\nDevice ID: {client_id}"
        )

    def _paired_selection_changed(self, current, _previous=None) -> None:
        self.revoke_button.setEnabled(current is not None)

    def _refresh(self) -> None:
        state = self.manager.status
        self.status.setText(f"Service: {state.state} | Port: {state.port or '—'}")
        if state.state == "error":
            self.status.setText(
                "Service error. Check port availability and local security settings."
            )
        if self._expires_at and time.time() >= self._expires_at:
            self.bundle.clear()
            self.qr.clear()
            self.qr.setText("Pairing data expired. Create fresh pairing data to try again.")

        selected_pending = self.pending.currentItem()
        selected_request_id = (
            selected_pending.data(Qt.ItemDataRole.UserRole)
            if selected_pending
            else None
        )
        self.pending.blockSignals(True)
        self.pending.clear()
        restored_pending = None
        for record in self.manager.pairing.list_pending_requests():
            name = str(record["client_name"])
            client_id = str(record["client_id"])
            request_id = str(record["request_id"])
            item = QListWidgetItem(
                f"{name}\n{client_id}"
            )
            item.setData(Qt.ItemDataRole.UserRole, request_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setData(Qt.ItemDataRole.UserRole + 2, client_id)
            item.setToolTip(f"Pairing request: {request_id}")
            self.pending.addItem(item)
            if request_id == selected_request_id:
                restored_pending = item

        if restored_pending is not None:
            self.pending.setCurrentItem(restored_pending)
        elif self.pending.count() > 0:
            # A newly arrived request should be actionable immediately without
            # making the user guess that the row must first be selected.
            self.pending.setCurrentRow(0)
        self.pending.blockSignals(False)
        self._pending_selection_changed(self.pending.currentItem())

        selected = self.devices.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.devices.blockSignals(True)
        self.devices.clear()
        restored_device = None
        for record in self.manager.pairing.list_clients():
            item = QListWidgetItem(f"{record['client_name']}\n{record['client_id']}")
            item.setData(Qt.ItemDataRole.UserRole, record["client_id"])
            self.devices.addItem(item)
            if record["client_id"] == selected_id:
                restored_device = item
        if restored_device is not None:
            self.devices.setCurrentItem(restored_device)
        self.devices.blockSignals(False)
        self._paired_selection_changed(self.devices.currentItem())

    def _approve(self) -> None:
        item = self.pending.currentItem()
        if item is None:
            return
        request_id = str(item.data(Qt.ItemDataRole.UserRole))
        name = str(item.data(Qt.ItemDataRole.UserRole + 1))
        client_id = str(item.data(Qt.ItemDataRole.UserRole + 2))
        answer = QMessageBox.question(
            self,
            "Approve device",
            f"Allow this device to pair with PrivacyGate Desktop?\n\n{name}\n{client_id}\n\n"
            "Approval releases a device credential for future authenticated requests. "
            "You can revoke it later.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self.manager.pairing.approve_request(request_id):
            QMessageBox.warning(
                self,
                "Request unavailable",
                "This pairing request expired or is no longer pending.",
            )
        self._refresh()

    def _deny(self) -> None:
        item = self.pending.currentItem()
        if item is None:
            return
        request_id = str(item.data(Qt.ItemDataRole.UserRole))
        if not self.manager.pairing.deny_request(request_id):
            QMessageBox.warning(
                self,
                "Request unavailable",
                "This pairing request expired or is no longer pending.",
            )
        self._refresh()

    def _revoke(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        if QMessageBox.question(
            self,
            "Revoke device",
            "Block future requests from this device? Previously downloaded data is not deleted.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.manager.pairing.revoke_client(item.data(Qt.ItemDataRole.UserRole))
        self._refresh()
