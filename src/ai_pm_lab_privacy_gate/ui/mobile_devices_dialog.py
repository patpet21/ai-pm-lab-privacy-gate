from __future__ import annotations

import io
import json
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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
        self.resize(1080, 790)
        self.setMinimumSize(980, 720)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_pairing_card(), 6)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self._build_pending_card(), 3)
        right.addWidget(self._build_trusted_card(), 2)
        body.addLayout(right, 5)
        root.addLayout(body, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)
        self._refresh()

    @staticmethod
    def _stylesheet() -> str:
        return """
        QDialog {
            background: #f4f7fb;
            color: #142033;
        }
        QFrame#headerCard, QFrame#panelCard {
            background: #ffffff;
            border: 1px solid #dfe6ee;
            border-radius: 16px;
        }
        QFrame#softCard {
            background: #f8fafc;
            border: 1px solid #e4e9ef;
            border-radius: 12px;
        }
        QLabel {
            color: #142033;
            font-size: 13px;
        }
        QLabel#pageTitle {
            font-size: 21px;
            font-weight: 700;
            color: #111827;
        }
        QLabel#pageSubtitle, QLabel#mutedText {
            color: #667085;
            font-size: 12px;
        }
        QLabel#sectionTitle {
            font-size: 16px;
            font-weight: 700;
            color: #152238;
        }
        QLabel#stepNumber {
            min-width: 26px;
            max-width: 26px;
            min-height: 26px;
            max-height: 26px;
            border-radius: 13px;
            background: #e8f7f6;
            color: #087e84;
            font-weight: 700;
        }
        QLabel#selectionTitle {
            font-weight: 700;
            color: #123f46;
        }
        QLabel#selectionValue {
            color: #344054;
        }
        QLabel#emptyState {
            color: #7a8699;
            background: #f8fafc;
            border: 1px dashed #ccd5df;
            border-radius: 10px;
            padding: 18px;
        }
        QPushButton {
            min-height: 38px;
            border-radius: 9px;
            padding: 0 14px;
            font-weight: 600;
            color: #1f2937;
            background: #ffffff;
            border: 1px solid #d7dee7;
        }
        QPushButton:hover {
            background: #f8fafc;
            border-color: #bfc9d5;
        }
        QPushButton:disabled {
            color: #98a2b3;
            background: #edf1f5;
            border-color: #e0e5eb;
        }
        QPushButton#primaryButton {
            color: #ffffff;
            background: #118d95;
            border: 1px solid #118d95;
        }
        QPushButton#primaryButton:hover {
            background: #0c7d84;
        }
        QPushButton#dangerButton {
            color: #b42318;
            background: #fff8f7;
            border: 1px solid #f0c7c3;
        }
        QPushButton#dangerButton:hover {
            background: #fff0ee;
        }
        QPushButton#linkButton {
            color: #2563eb;
            background: transparent;
            border: none;
            text-align: left;
            padding: 0 2px;
            min-height: 28px;
        }
        QListWidget {
            background: #fbfcfe;
            border: 1px solid #dce3eb;
            border-radius: 10px;
            padding: 5px;
            outline: none;
        }
        QListWidget::item {
            color: #1d2939;
            background: transparent;
            border-radius: 8px;
            padding: 9px 10px;
            margin: 2px;
        }
        QListWidget::item:hover {
            background: #eef7f8;
        }
        QListWidget::item:selected {
            color: #073b42;
            background: #d9f2f1;
            border: 1px solid #32a7a9;
        }
        QPlainTextEdit {
            color: #233044;
            background: #f8fafc;
            border: 1px solid #dce3eb;
            border-radius: 10px;
            padding: 8px;
            font-family: Consolas, "Courier New", monospace;
            font-size: 11px;
        }
        """

    @staticmethod
    def _card(object_name: str = "panelCard") -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        return card

    @staticmethod
    def _step(number: str, text: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)
        badge = QLabel(number)
        badge.setObjectName("stepNumber")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(text)
        label.setObjectName("mutedText")
        label.setWordWrap(True)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(label, 1)
        return container

    def _build_header(self) -> QFrame:
        card = self._card("headerCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel("Device Trust")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Pair trusted mobile devices with this Desktop. Pairing never grants automatic access "
            "to your Library or restore mappings."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)

        self.status_badge = QLabel("Offline")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumWidth(118)
        self.status_badge.setMinimumHeight(34)
        layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        return card

    def _build_pairing_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(11)

        title = QLabel("Pair a mobile device")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        steps = QHBoxLayout()
        steps.setSpacing(12)
        steps.addWidget(self._step("1", "Create fresh pairing data"), 1)
        steps.addWidget(self._step("2", "Scan with PrivacyGate Mobile"), 1)
        steps.addWidget(self._step("3", "Approve the request on Desktop"), 1)
        layout.addLayout(steps)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.create_button = QPushButton("Create pairing QR")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._pair)
        actions.addWidget(self.create_button, 2)

        start = QPushButton("Start service")
        start.clicked.connect(self._start)
        actions.addWidget(start, 1)

        stop = QPushButton("Stop service")
        stop.clicked.connect(self._stop)
        actions.addWidget(stop, 1)
        layout.addLayout(actions)

        qr_card = self._card("softCard")
        qr_layout = QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(14, 14, 14, 12)
        qr_layout.setSpacing(6)

        self.qr = QLabel("Create pairing data to generate a temporary QR code.")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setWordWrap(True)
        self.qr.setMinimumHeight(400)
        self.qr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        qr_layout.addWidget(self.qr, 1)

        hint = QLabel("On Mobile: Settings → Desktop Connection → Scan pairing QR")
        hint.setObjectName("mutedText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(hint)
        layout.addWidget(qr_card, 1)

        self.advanced_button = QPushButton("Show advanced pairing data")
        self.advanced_button.setObjectName("linkButton")
        self.advanced_button.setCheckable(True)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_button)

        self.advanced_panel = self._card("softCard")
        advanced = QVBoxLayout(self.advanced_panel)
        advanced.setContentsMargins(10, 10, 10, 10)
        advanced.setSpacing(7)

        advanced_note = QLabel(
            "Fallback only. This JSON contains temporary pairing material and should not be shared."
        )
        advanced_note.setObjectName("mutedText")
        advanced_note.setWordWrap(True)
        advanced.addWidget(advanced_note)

        self.bundle = QPlainTextEdit()
        self.bundle.setReadOnly(True)
        self.bundle.setMaximumHeight(105)
        self.bundle.setPlaceholderText("Pairing JSON will appear here.")
        advanced.addWidget(self.bundle)

        copy = QPushButton("Copy temporary JSON")
        copy.clicked.connect(self._copy)
        advanced.addWidget(copy)
        self.advanced_panel.setVisible(False)
        layout.addWidget(self.advanced_panel)

        return card

    def _build_pending_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Approval requests")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.pending_count = QLabel("0 pending")
        self.pending_count.setObjectName("mutedText")
        title_row.addWidget(self.pending_count)
        layout.addLayout(title_row)

        helper = QLabel(
            "New requests are selected automatically. Confirm the device details before approving."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.pending_empty = QLabel("No devices are waiting for approval.")
        self.pending_empty.setObjectName("emptyState")
        self.pending_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pending_empty)

        self.pending = QListWidget()
        self.pending.setMaximumHeight(125)
        self.pending.currentItemChanged.connect(self._pending_selection_changed)
        layout.addWidget(self.pending)

        self.selection_card = self._card("softCard")
        selected = QGridLayout(self.selection_card)
        selected.setContentsMargins(12, 10, 12, 10)
        selected.setHorizontalSpacing(10)
        selected.setVerticalSpacing(4)

        selection_title = QLabel("Selected device")
        selection_title.setObjectName("selectionTitle")
        selected.addWidget(selection_title, 0, 0, 1, 2)
        selected.addWidget(QLabel("Name"), 1, 0)
        self.selected_name = QLabel("—")
        self.selected_name.setObjectName("selectionValue")
        selected.addWidget(self.selected_name, 1, 1)
        selected.addWidget(QLabel("Device ID"), 2, 0)
        self.selected_id = QLabel("—")
        self.selected_id.setObjectName("selectionValue")
        self.selected_id.setWordWrap(True)
        selected.addWidget(self.selected_id, 2, 1)
        layout.addWidget(self.selection_card)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.approve_button = QPushButton("Approve device")
        self.approve_button.setObjectName("primaryButton")
        self.approve_button.setEnabled(False)
        self.approve_button.clicked.connect(self._approve)
        buttons.addWidget(self.approve_button, 1)

        self.deny_button = QPushButton("Deny request")
        self.deny_button.setObjectName("dangerButton")
        self.deny_button.setEnabled(False)
        self.deny_button.clicked.connect(self._deny)
        buttons.addWidget(self.deny_button, 1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return card

    def _build_trusted_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("Trusted devices")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.device_count = QLabel("0 paired")
        self.device_count.setObjectName("mutedText")
        title_row.addWidget(self.device_count)
        layout.addLayout(title_row)

        helper = QLabel(
            "Revocation blocks future authenticated requests. It does not erase data already saved on a device."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.devices_empty = QLabel("No paired mobile devices yet.")
        self.devices_empty.setObjectName("emptyState")
        self.devices_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.devices_empty)

        self.devices = QListWidget()
        self.devices.setMaximumHeight(110)
        self.devices.currentItemChanged.connect(self._paired_selection_changed)
        layout.addWidget(self.devices)

        self.revoke_button = QPushButton("Revoke selected device")
        self.revoke_button.setEnabled(False)
        self.revoke_button.clicked.connect(self._revoke)
        layout.addWidget(self.revoke_button)
        return card

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_panel.setVisible(checked)
        self.advanced_button.setText(
            "Hide advanced pairing data" if checked else "Show advanced pairing data"
        )

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

            # Keep the dense QR on its original integer pixel grid so phone
            # cameras do not lose module edges through resampling.
            self.qr.setPixmap(pixmap)
            self.qr.setMinimumHeight(max(400, pixmap.height() + 8))
            self.qr.setToolTip(
                "Scan only with PrivacyGate Mobile. Keep the full white border visible."
            )
        except Exception:
            self.qr.clear()
            self.qr.setText(
                "QR generation is unavailable. Open advanced pairing data to use the JSON fallback."
            )

    def _copy(self) -> None:
        if self.bundle.toPlainText() and time.time() < self._expires_at:
            QApplication.clipboard().setText(self.bundle.toPlainText())

    def _pending_selection_changed(self, current, _previous=None) -> None:
        has_selection = current is not None
        self.approve_button.setEnabled(has_selection)
        self.deny_button.setEnabled(has_selection)
        self.selection_card.setVisible(has_selection)
        if current is None:
            self.selected_name.setText("—")
            self.selected_id.setText("—")
            return
        self.selected_name.setText(
            str(current.data(Qt.ItemDataRole.UserRole + 1) or "Mobile device")
        )
        self.selected_id.setText(
            str(current.data(Qt.ItemDataRole.UserRole + 2) or "—")
        )

    def _paired_selection_changed(self, current, _previous=None) -> None:
        self.revoke_button.setEnabled(current is not None)

    def _refresh(self) -> None:
        state = self.manager.status
        if state.state == "online":
            self.status_badge.setText(f"●  Online · {state.port or '—'}")
            self.status_badge.setStyleSheet(
                "color:#067647;background:#ecfdf3;border:1px solid #abefc6;"
                "border-radius:17px;padding:5px 12px;font-weight:700;"
            )
        elif state.state == "error":
            self.status_badge.setText("●  Service error")
            self.status_badge.setStyleSheet(
                "color:#b42318;background:#fff1f0;border:1px solid #f7c7c3;"
                "border-radius:17px;padding:5px 12px;font-weight:700;"
            )
        else:
            self.status_badge.setText("●  Offline")
            self.status_badge.setStyleSheet(
                "color:#667085;background:#f2f4f7;border:1px solid #e4e7ec;"
                "border-radius:17px;padding:5px 12px;font-weight:700;"
            )

        if self._expires_at and time.time() >= self._expires_at:
            self.bundle.clear()
            self.qr.clear()
            self.qr.setText("Pairing data expired. Create a fresh QR to pair a device.")

        selected_pending = self.pending.currentItem()
        selected_request_id = (
            selected_pending.data(Qt.ItemDataRole.UserRole)
            if selected_pending
            else None
        )

        pending_records = self.manager.pairing.list_pending_requests()
        self.pending.blockSignals(True)
        self.pending.clear()
        restored_pending = None
        for record in pending_records:
            name = str(record["client_name"])
            client_id = str(record["client_id"])
            request_id = str(record["request_id"])
            item = QListWidgetItem(f"{name}\n{client_id}")
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
            self.pending.setCurrentRow(0)
        self.pending.blockSignals(False)

        self.pending_count.setText(f"{len(pending_records)} pending")
        self.pending.setVisible(bool(pending_records))
        self.pending_empty.setVisible(not pending_records)
        self._pending_selection_changed(self.pending.currentItem())

        selected_device = self.devices.currentItem()
        selected_id = (
            selected_device.data(Qt.ItemDataRole.UserRole)
            if selected_device
            else None
        )
        device_records = self.manager.pairing.list_clients()
        self.devices.blockSignals(True)
        self.devices.clear()
        restored_device = None
        for record in device_records:
            item = QListWidgetItem(f"{record['client_name']}\n{record['client_id']}")
            item.setData(Qt.ItemDataRole.UserRole, record["client_id"])
            self.devices.addItem(item)
            if record["client_id"] == selected_id:
                restored_device = item
        if restored_device is not None:
            self.devices.setCurrentItem(restored_device)
        self.devices.blockSignals(False)

        self.device_count.setText(f"{len(device_records)} paired")
        self.devices.setVisible(bool(device_records))
        self.devices_empty.setVisible(not device_records)
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
            f"Allow this device to pair with PrivacyGate Desktop?\n\n"
            f"Device: {name}\nDevice ID: {client_id}\n\n"
            "Approval releases a credential for future authenticated requests. "
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
