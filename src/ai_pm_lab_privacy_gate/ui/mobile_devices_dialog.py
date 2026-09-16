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
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager
from ai_pm_lab_privacy_gate.ui.protected_copy_dialog import ProtectedCopyDialog


class AdvancedPairingDataDialog(QDialog):
    def __init__(self, payload: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced pairing data")
        self.resize(700, 470)
        self.setMinimumSize(620, 400)
        self.setStyleSheet(
            """
            QDialog { background: #f4f7fb; }
            QFrame#card { background: white; border: 1px solid #dfe6ee; border-radius: 14px; }
            QLabel#title { color: #111827; font-size: 18px; font-weight: 800; }
            QLabel#muted { color: #667085; }
            QPlainTextEdit {
                color: #233044; background: #f8fafc; border: 1px solid #dce3eb;
                border-radius: 10px; padding: 10px; font-family: Consolas, "Courier New", monospace;
                font-size: 11px;
            }
            QPushButton {
                min-height: 38px; border-radius: 9px; padding: 0 14px; font-weight: 700;
                color: #1f2937; background: #ffffff; border: 1px solid #d7dee7;
            }
            QPushButton#primary { color: white; background: #118d95; border-color: #118d95; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Temporary pairing JSON")
        title.setObjectName("title")
        layout.addWidget(title)
        note = QLabel(
            "Fallback only. This data contains temporary pairing material. "
            "Do not share it publicly; use the QR code whenever possible."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(payload or "Create fresh pairing data first.")
        layout.addWidget(self.text, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        copy = QPushButton("Copy JSON")
        copy.setObjectName("primary")
        copy.setEnabled(bool(payload))
        copy.clicked.connect(self._copy)
        buttons.addWidget(copy)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        root.addWidget(card)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.text.toPlainText())


def open_mobile_devices(main_window) -> None:
    manager = getattr(main_window, "_mobile_link_manager", None)
    if manager is None:
        manager = MobileLinkManager(main_window.service, main_window.library.data_dir)
        main_window._mobile_link_manager = manager
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(manager.stop)
    MobileDevicesDialog(manager, main_window).exec()


class MobileDevicesDialog(QDialog):
    QR_TARGET_PX = 360

    def __init__(self, manager: MobileLinkManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._expires_at = 0.0
        self._pairing_payload = ""

        self.setWindowTitle("Mobile Devices — PrivacyGate Device Trust")
        self.resize(1080, 760)
        self.setMinimumSize(940, 680)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addWidget(self._build_header())

        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.addWidget(self._build_trusted_card(), 3)
        columns.addWidget(self._build_pairing_card(), 2)
        root.addLayout(columns, 1)

        self.pending_card = self._build_pending_card()
        root.addWidget(self.pending_card)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)
        self._refresh()

    @staticmethod
    def _stylesheet() -> str:
        return """
        QDialog { background: #f4f7fb; color: #142033; }
        QFrame#headerCard, QFrame#panelCard {
            background: #ffffff; border: 1px solid #dfe6ee; border-radius: 16px;
        }
        QFrame#softCard {
            background: #f8fafc; border: 1px solid #e4e9ef; border-radius: 12px;
        }
        QFrame#accentCard {
            background: #eefaf9; border: 1px solid #b9e2df; border-radius: 12px;
        }
        QLabel { color: #142033; font-size: 13px; }
        QLabel#pageTitle { font-size: 22px; font-weight: 800; color: #111827; }
        QLabel#pageSubtitle, QLabel#mutedText { color: #667085; font-size: 12px; }
        QLabel#sectionTitle { font-size: 17px; font-weight: 800; color: #152238; }
        QLabel#eyebrow { color: #087e84; font-size: 10px; font-weight: 800; }
        QLabel#selectionTitle { font-weight: 800; color: #123f46; }
        QLabel#selectionValue { color: #344054; }
        QLabel#emptyState {
            color: #7a8699; background: #f8fafc; border: 1px dashed #ccd5df;
            border-radius: 10px; padding: 18px;
        }
        QLabel#stepNumber {
            min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
            border-radius: 12px; background: #d9f2f1; color: #087e84; font-weight: 800;
        }
        QPushButton {
            min-height: 38px; border-radius: 9px; padding: 0 14px; font-weight: 700;
            color: #1f2937; background: #ffffff; border: 1px solid #d7dee7;
        }
        QPushButton:hover { background: #f8fafc; border-color: #bfc9d5; }
        QPushButton:disabled { color: #98a2b3; background: #edf1f5; border-color: #e0e5eb; }
        QPushButton#primaryButton { color: #ffffff; background: #118d95; border-color: #118d95; }
        QPushButton#primaryButton:hover { background: #0c7d84; }
        QPushButton#dangerButton { color: #b42318; background: #fff8f7; border-color: #f0c7c3; }
        QPushButton#secondaryAction { color: #344054; background: #f8fafc; }
        QPushButton#quietButton { color: #667085; background: transparent; border-color: #e4e7ec; }
        QListWidget {
            background: #fbfcfe; border: 1px solid #dce3eb; border-radius: 10px;
            padding: 5px; outline: none;
        }
        QListWidget::item {
            color: #1d2939; padding: 10px 11px; margin: 2px; border-radius: 8px;
        }
        QListWidget::item:hover { background: #eef7f8; }
        QListWidget::item:selected {
            color: #073b42; background: #d9f2f1; border: 1px solid #32a7a9;
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
        row.setSpacing(8)
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
            "Manage trusted mobile devices and explicitly choose which protected Library copies each device may access."
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

    def _build_trusted_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        eyebrow = QLabel("DEVICE TRUST")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Trusted devices")
        title.setObjectName("sectionTitle")
        title_group.addWidget(eyebrow)
        title_group.addWidget(title)
        title_row.addLayout(title_group)
        title_row.addStretch(1)
        self.device_count = QLabel("0 trusted")
        self.device_count.setObjectName("mutedText")
        title_row.addWidget(self.device_count, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(title_row)

        helper = QLabel(
            "Select a trusted device once. Rename it, remove it, or make a protected copy available without selecting the device again."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.devices_empty = QLabel("No trusted mobile devices yet. Pair a device from the panel on the right.")
        self.devices_empty.setObjectName("emptyState")
        self.devices_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.devices_empty.setWordWrap(True)
        layout.addWidget(self.devices_empty, 1)

        self.devices = QListWidget()
        self.devices.setWordWrap(True)
        self.devices.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.devices.currentItemChanged.connect(self._paired_selection_changed)
        layout.addWidget(self.devices, 1)

        action_card = self._card("accentCard")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(12, 11, 12, 11)
        action_layout.setSpacing(8)
        action_label = QLabel("Protected Library access")
        action_label.setObjectName("selectionTitle")
        action_help = QLabel(
            "Grant one protected copy to the selected trusted device. Nothing downloads automatically."
        )
        action_help.setObjectName("mutedText")
        action_help.setWordWrap(True)
        action_layout.addWidget(action_label)
        action_layout.addWidget(action_help)
        self.share_button = QPushButton("Make protected copy available…")
        self.share_button.setObjectName("primaryButton")
        self.share_button.setEnabled(False)
        self.share_button.clicked.connect(self._share_protected_copy)
        action_layout.addWidget(self.share_button)
        layout.addWidget(action_card)

        manage = QHBoxLayout()
        manage.setSpacing(8)
        self.rename_button = QPushButton("Rename device…")
        self.rename_button.setObjectName("secondaryAction")
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self._rename_selected_device)
        manage.addWidget(self.rename_button, 1)
        self.remove_button = QPushButton("Remove device")
        self.remove_button.setObjectName("dangerButton")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._remove_selected_device)
        manage.addWidget(self.remove_button, 1)
        layout.addLayout(manage)
        return card

    def _build_pairing_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        eyebrow = QLabel("ADD DEVICE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Pair a new mobile device")
        title.setObjectName("sectionTitle")
        layout.addWidget(eyebrow)
        layout.addWidget(title)

        intro = QLabel(
            "Pairing creates a trusted device credential only. Library access still requires an explicit grant."
        )
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QVBoxLayout()
        steps.setSpacing(7)
        steps.addWidget(self._step("1", "Create a fresh temporary QR"))
        steps.addWidget(self._step("2", "Scan it in PrivacyGate Mobile"))
        steps.addWidget(self._step("3", "Approve the request on this Desktop"))
        layout.addLayout(steps)

        self.create_button = QPushButton("Create pairing QR")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._pair)
        layout.addWidget(self.create_button)

        service_row = QHBoxLayout()
        service_row.setSpacing(8)
        start = QPushButton("Start service")
        start.setObjectName("quietButton")
        start.clicked.connect(self._start)
        service_row.addWidget(start, 1)
        stop = QPushButton("Stop service")
        stop.setObjectName("quietButton")
        stop.clicked.connect(self._stop)
        service_row.addWidget(stop, 1)
        layout.addLayout(service_row)

        self.qr_panel = self._card("softCard")
        qr_layout = QVBoxLayout(self.qr_panel)
        qr_layout.setContentsMargins(12, 12, 12, 10)
        qr_layout.setSpacing(6)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setFixedHeight(370)
        qr_layout.addWidget(self.qr)
        hint = QLabel("Mobile → Settings → Desktop Connection → Scan pairing QR")
        hint.setObjectName("mutedText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        qr_layout.addWidget(hint)
        self.qr_panel.setVisible(False)
        layout.addWidget(self.qr_panel)

        advanced = QPushButton("Advanced pairing data…")
        advanced.setObjectName("secondaryAction")
        advanced.clicked.connect(self._show_advanced)
        layout.addWidget(advanced)
        layout.addStretch(1)
        return card

    def _build_pending_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("Pairing approval")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.pending_count = QLabel("0 pending")
        self.pending_count.setObjectName("mutedText")
        title_row.addWidget(self.pending_count)
        layout.addLayout(title_row)

        content = QHBoxLayout()
        content.setSpacing(12)
        self.pending = QListWidget()
        self.pending.setMaximumHeight(122)
        self.pending.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pending.currentItemChanged.connect(self._pending_selection_changed)
        content.addWidget(self.pending, 3)

        self.selection_card = self._card("softCard")
        selected = QGridLayout(self.selection_card)
        selected.setContentsMargins(12, 10, 12, 10)
        selected.setHorizontalSpacing(10)
        selected.setVerticalSpacing(4)
        selection_title = QLabel("Request details")
        selection_title.setObjectName("selectionTitle")
        selected.addWidget(selection_title, 0, 0, 1, 2)
        selected.addWidget(QLabel("Name"), 1, 0)
        self.selected_name = QLabel("—")
        self.selected_name.setObjectName("selectionValue")
        selected.addWidget(self.selected_name, 1, 1)
        selected.addWidget(QLabel("Device ID"), 2, 0)
        self.selected_id = QLabel("—")
        self.selected_id.setObjectName("mutedText")
        self.selected_id.setWordWrap(True)
        selected.addWidget(self.selected_id, 2, 1)
        content.addWidget(self.selection_card, 2)
        layout.addLayout(content)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.deny_button = QPushButton("Deny")
        self.deny_button.setObjectName("dangerButton")
        self.deny_button.setEnabled(False)
        self.deny_button.clicked.connect(self._deny)
        buttons.addWidget(self.deny_button)
        self.approve_button = QPushButton("Approve trusted device")
        self.approve_button.setObjectName("primaryButton")
        self.approve_button.setEnabled(False)
        self.approve_button.clicked.connect(self._approve)
        buttons.addWidget(self.approve_button)
        layout.addLayout(buttons)
        return card

    def _show_advanced(self) -> None:
        AdvancedPairingDataDialog(self._pairing_payload, self).exec()

    def _share_protected_copy(self) -> None:
        current = self.devices.currentItem()
        client_id = str(current.data(Qt.ItemDataRole.UserRole)) if current is not None else None
        ProtectedCopyDialog(
            self.manager,
            self,
            preselected_client_id=client_id,
        ).exec()
        self._refresh()

    def _rename_selected_device(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        client_id = str(item.data(Qt.ItemDataRole.UserRole))
        current_name = str(item.data(Qt.ItemDataRole.UserRole + 1) or "Mobile device")
        new_name, accepted = QInputDialog.getText(
            self,
            "Rename trusted device",
            "Device name:",
            text=current_name,
        )
        if not accepted:
            return
        try:
            changed = self.manager.pairing.rename_client(client_id, new_name)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid device name", str(error))
            return
        if not changed:
            QMessageBox.warning(self, "Device unavailable", "This trusted device no longer exists.")
            return
        self._refresh()

    def _remove_selected_device(self) -> None:
        item = self.devices.currentItem()
        if item is None:
            return
        client_id = str(item.data(Qt.ItemDataRole.UserRole))
        client_name = str(item.data(Qt.ItemDataRole.UserRole + 1) or "Mobile device")
        if QMessageBox.question(
            self,
            "Remove trusted device",
            f"Remove {client_name} from this Desktop?\n\n"
            "Its credential and Protected-copy grants will be revoked. Copies already saved on the mobile device are not erased.",
        ) != QMessageBox.StandardButton.Yes:
            return
        if self.manager.pairing.revoke_client(client_id):
            self.manager.library_grants.revoke_client(client_id)
        self._refresh()

    def _start(self) -> None:
        self.manager.start()
        self._refresh()

    def _stop(self) -> None:
        self.manager.stop()
        self._expires_at = 0.0
        self._pairing_payload = ""
        self.qr.clear()
        self.qr_panel.setVisible(False)
        self._refresh()

    def _pair(self) -> None:
        try:
            bundle = self.manager.create_pairing_bundle()
            self._expires_at = bundle.expires_at
            payload = bundle.as_dict()
            self._pairing_payload = json.dumps(payload, indent=2)
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
                box_size=1,
                border=4,
            )
            code.add_data(payload)
            code.make(fit=True)
            total_modules = code.modules_count + (code.border * 2)
            code.box_size = max(2, min(4, self.QR_TARGET_PX // total_modules))
            image = code.make_image(fill_color="black", back_color="white")
            output = io.BytesIO()
            image.save(output, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(output.getvalue(), "PNG"):
                raise RuntimeError("QR image could not be loaded")
            self.qr.setPixmap(pixmap)
            self.qr.setToolTip("")
            self.qr_panel.setVisible(True)
            self.adjustSize()
        except Exception:
            self.qr.clear()
            self.qr_panel.setVisible(False)
            QMessageBox.warning(
                self,
                "QR unavailable",
                "QR generation is unavailable. Use Advanced pairing data for the JSON fallback.",
            )

    def _pending_selection_changed(self, current, _previous=None) -> None:
        has_selection = current is not None
        self.approve_button.setEnabled(has_selection)
        self.deny_button.setEnabled(has_selection)
        self.selection_card.setVisible(has_selection)
        if current is None:
            self.selected_name.setText("—")
            self.selected_id.setText("—")
            return
        self.selected_name.setText(str(current.data(Qt.ItemDataRole.UserRole + 1) or "Mobile device"))
        self.selected_id.setText(str(current.data(Qt.ItemDataRole.UserRole + 2) or "—"))

    def _paired_selection_changed(self, current, _previous=None) -> None:
        enabled = current is not None
        self.rename_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.share_button.setEnabled(enabled)

    def _refresh(self) -> None:
        state = self.manager.status
        if state.state == "online":
            self.status_badge.setText(f"●  Online · {state.port or '—'}")
            self.status_badge.setStyleSheet(
                "color:#067647;background:#ecfdf3;border:1px solid #abefc6;"
                "border-radius:17px;padding:5px 12px;font-weight:800;"
            )
        elif state.state == "error":
            self.status_badge.setText("●  Service error")
            self.status_badge.setStyleSheet(
                "color:#b42318;background:#fff1f0;border:1px solid #f7c7c3;"
                "border-radius:17px;padding:5px 12px;font-weight:800;"
            )
        else:
            self.status_badge.setText("●  Offline")
            self.status_badge.setStyleSheet(
                "color:#667085;background:#f2f4f7;border:1px solid #e4e7ec;"
                "border-radius:17px;padding:5px 12px;font-weight:800;"
            )

        if self._expires_at and time.time() >= self._expires_at:
            self._expires_at = 0.0
            self._pairing_payload = ""
            self.qr.clear()
            self.qr_panel.setVisible(False)

        selected_pending = self.pending.currentItem()
        selected_request_id = selected_pending.data(Qt.ItemDataRole.UserRole) if selected_pending else None
        pending_records = self.manager.pairing.list_pending_requests()
        self.pending.blockSignals(True)
        self.pending.clear()
        restored_pending = None
        for record in pending_records:
            name = str(record["client_name"])
            client_id = str(record["client_id"])
            request_id = str(record["request_id"])
            item = QListWidgetItem(f"{name}\n…{client_id[-12:]}")
            item.setData(Qt.ItemDataRole.UserRole, request_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setData(Qt.ItemDataRole.UserRole + 2, client_id)
            item.setToolTip(client_id)
            self.pending.addItem(item)
            if request_id == selected_request_id:
                restored_pending = item
        if restored_pending is not None:
            self.pending.setCurrentItem(restored_pending)
        elif self.pending.count() > 0:
            self.pending.setCurrentRow(0)
        self.pending.blockSignals(False)
        self.pending_count.setText(f"{len(pending_records)} pending")
        self.pending_card.setVisible(bool(pending_records))
        self._pending_selection_changed(self.pending.currentItem())

        selected_device = self.devices.currentItem()
        selected_id = selected_device.data(Qt.ItemDataRole.UserRole) if selected_device else None
        device_records = self.manager.pairing.list_clients()
        self.devices.blockSignals(True)
        self.devices.clear()
        restored_device = None
        for record in device_records:
            name = str(record["client_name"])
            client_id = str(record["client_id"])
            item = QListWidgetItem(f"{name}\nTrusted device · …{client_id[-12:]}")
            item.setData(Qt.ItemDataRole.UserRole, client_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setToolTip(client_id)
            self.devices.addItem(item)
            if client_id == selected_id:
                restored_device = item
        if restored_device is not None:
            self.devices.setCurrentItem(restored_device)
        elif self.devices.count() > 0:
            self.devices.setCurrentRow(0)
        self.devices.blockSignals(False)
        self.device_count.setText(f"{len(device_records)} trusted")
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
            "Approve trusted device",
            f"Trust this mobile device?\n\nDevice: {name}\nDevice ID: {client_id}\n\n"
            "Approval creates an authenticated device credential. Library access remains explicit and item-by-item.",
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
        if not self.manager.pairing.deny_request(str(item.data(Qt.ItemDataRole.UserRole))):
            QMessageBox.warning(
                self,
                "Request unavailable",
                "This pairing request expired or is no longer pending.",
            )
        self._refresh()
