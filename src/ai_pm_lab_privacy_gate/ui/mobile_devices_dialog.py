from __future__ import annotations

import io
import json
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
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
        self.resize(760, 860)
        layout = QVBoxLayout(self)
        info = QLabel(
            "Pair only devices you own or trust, on your private local network. "
            "Creating pairing data starts the encrypted Desktop analysis service. "
            "The temporary data lets a device request pairing, but Desktop approval is now required "
            "before any bearer credential is released. Library and restore mappings are not shared "
            "by this service."
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

        self.qr = QLabel("Create pairing data to show a temporary QR code.")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setMinimumHeight(230)
        self.qr.setWordWrap(True)
        layout.addWidget(self.qr)

        self.bundle = QPlainTextEdit()
        self.bundle.setReadOnly(True)
        self.bundle.setMaximumHeight(180)
        self.bundle.setPlaceholderText(
            "Temporary pairing JSON appears here. On Mobile: Settings → Desktop Connection."
        )
        layout.addWidget(self.bundle)
        copy = QPushButton("Copy temporary pairing data")
        copy.clicked.connect(self._copy)
        layout.addWidget(copy)

        layout.addWidget(QLabel("Pending pairing approvals"))
        self.pending = QListWidget()
        self.pending.setMinimumHeight(110)
        layout.addWidget(self.pending)
        pending_row = QHBoxLayout()
        approve = QPushButton("Approve selected request")
        approve.clicked.connect(self._approve)
        pending_row.addWidget(approve)
        deny = QPushButton("Deny selected request")
        deny.clicked.connect(self._deny)
        pending_row.addWidget(deny)
        layout.addLayout(pending_row)

        layout.addWidget(QLabel("Paired devices (not an online-status list)"))
        self.devices = QListWidget()
        layout.addWidget(self.devices)
        revoke = QPushButton("Revoke selected device")
        revoke.clicked.connect(self._revoke)
        layout.addWidget(revoke)

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

            code = qrcode.QRCode(
                version=None,
                error_correction=ERROR_CORRECT_L,
                box_size=6,
                border=3,
            )
            code.add_data(payload)
            code.make(fit=True)
            image = code.make_image(fill_color="black", back_color="white")
            output = io.BytesIO()
            image.save(output, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(output.getvalue(), "PNG"):
                raise RuntimeError("QR image could not be loaded")
            self.qr.setPixmap(
                pixmap.scaled(
                    290,
                    290,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            )
            self.qr.setToolTip("Scan only with PrivacyGate Mobile. This QR expires automatically.")
        except Exception:
            self.qr.clear()
            self.qr.setText(
                "QR generation is unavailable in this environment. "
                "The temporary JSON below remains usable for manual pairing."
            )

    def _copy(self) -> None:
        if self.bundle.toPlainText() and time.time() < self._expires_at:
            QApplication.clipboard().setText(self.bundle.toPlainText())

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
        self.pending.clear()
        for record in self.manager.pairing.list_pending_requests():
            name = str(record["client_name"])
            client_id = str(record["client_id"])
            request_id = str(record["request_id"])
            item = QListWidgetItem(
                f"{name} — {client_id} — request {request_id[:10]}…"
            )
            item.setData(Qt.ItemDataRole.UserRole, request_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setData(Qt.ItemDataRole.UserRole + 2, client_id)
            self.pending.addItem(item)
            if request_id == selected_request_id:
                self.pending.setCurrentItem(item)

        selected = self.devices.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.devices.clear()
        for record in self.manager.pairing.list_clients():
            item = QListWidgetItem(f"{record['client_name']} — {record['client_id']}")
            item.setData(Qt.ItemDataRole.UserRole, record["client_id"])
            self.devices.addItem(item)
            if record["client_id"] == selected_id:
                self.devices.setCurrentItem(item)

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
