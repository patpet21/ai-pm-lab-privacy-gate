from __future__ import annotations

import json
import time

from PySide6.QtCore import QTimer, Qt
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
        self.resize(700, 600)
        layout = QVBoxLayout(self)
        info = QLabel(
            "Pair only devices you own or trust, on your private local network. "
            "Creating pairing data starts the encrypted Desktop analysis service. "
            "Anyone holding the temporary data can pair: deliver it privately. "
            "Library and restore mappings are not shared by this service."
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
        self.bundle = QPlainTextEdit()
        self.bundle.setReadOnly(True)
        self.bundle.setPlaceholderText("Temporary pairing JSON appears here. On Mobile: Settings → Desktop Connection.")
        layout.addWidget(self.bundle)
        copy = QPushButton("Copy temporary pairing data")
        copy.clicked.connect(self._copy)
        layout.addWidget(copy)
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
        self._refresh()

    def _pair(self) -> None:
        try:
            bundle = self.manager.create_pairing_bundle()
            self._expires_at = bundle.expires_at
            self.bundle.setPlainText(json.dumps(bundle.as_dict(), indent=2))
        except Exception:
            QMessageBox.warning(self, "Pairing unavailable", "Could not start pairing. Check the service status and whether port 8767 is already in use.")
        self._refresh()

    def _copy(self) -> None:
        if self.bundle.toPlainText() and time.time() < self._expires_at:
            QApplication.clipboard().setText(self.bundle.toPlainText())

    def _refresh(self) -> None:
        state = self.manager.status
        self.status.setText(f"Service: {state.state} | Port: {state.port or '—'}")
        if state.state == "error":
            self.status.setText("Service error. Check port availability and local security settings.")
        if time.time() >= self._expires_at:
            self.bundle.clear()
        selected = self.devices.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.devices.clear()
        for record in self.manager.pairing.list_clients():
            item = QListWidgetItem(f"{record['client_name']} — {record['client_id']}")
            item.setData(Qt.ItemDataRole.UserRole, record["client_id"])
            self.devices.addItem(item)
            if record["client_id"] == selected_id:
                self.devices.setCurrentItem(item)

    def _revoke(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        if QMessageBox.question(self, "Revoke device", "Block future requests from this device? Previously downloaded data is not deleted.") != QMessageBox.StandardButton.Yes:
            return
        self.manager.pairing.revoke_client(item.data(Qt.ItemDataRole.UserRole))
        self._refresh()
