from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import DeviceSummary
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

NAVY = "#062B4F"
TEAL = "#0B7F89"
MUTED = "#61798A"
BORDER = "#DCE6EB"


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.deleteLater()


def _pretty_seen(value: str) -> str:
    if not value:
        return "Not available"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%b %d, %Y · %H:%M")
    except ValueError:
        return value[:16].replace("T", " ")


class PrivacyGateDevicesController:
    """Minimal multi-device account foundation.

    This only exposes device identity metadata already stored by PrivacyGate.
    It does not synchronize Library content, mappings, PII or documents and it
    does not create any remote-control path between devices.
    """

    def __init__(self, main_window, account_controller) -> None:
        self.main_window = main_window
        self.account_controller = account_controller
        self.account_client = account_controller.account_client
        self.thread_pool = QThreadPool.globalInstance()
        self.worker = None
        self.controls = None
        self.panel = None
        self.rows = None
        self.count = None
        self.refresh_button = None
        self._ux_patched = False
        QTimer.singleShot(120, self._install_when_ready)

    def _install_when_ready(self) -> None:
        settings = getattr(self.main_window, "settings_page", None)
        controls = (
            settings.findChild(QFrame, "SettingsAccountControls")
            if settings is not None
            else None
        )
        if controls is None:
            QTimer.singleShot(120, self._install_when_ready)
            return

        self.controls = controls
        self._rename_settings()
        self._ensure_panel()
        self._patch_account_refresh()
        self.refresh()

    def _rename_settings(self) -> None:
        settings = getattr(self.main_window, "settings_page", None)
        if settings is None:
            return
        for label in settings.findChildren(QLabel):
            text = label.text().strip()
            if text == "Account":
                label.setText("Account & Devices")
            elif text == (
                "Identity, display name, plan and entitlement controls for this "
                "PrivacyGate account."
            ):
                label.setText(
                    "Account identity, plan and minimal authorized-device metadata. "
                    "Documents and restore mappings remain local."
                )

    def _ensure_panel(self) -> None:
        if self.controls is None:
            return
        existing = self.controls.findChild(QFrame, "PrivacyGateDevicesPanel")
        if existing is not None:
            self.panel = existing
            return

        panel = QFrame(self.controls)
        panel.setObjectName("PrivacyGateDevicesPanel")
        panel.setStyleSheet(
            "QFrame#PrivacyGateDevicesPanel{background:#FFFFFF;"
            + f"border:1px solid {BORDER};"
            + "border-radius:14px;}"
        )
        root = QVBoxLayout(panel)
        root.setContentsMargins(14, 13, 14, 13)
        root.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Your devices")
        title.setStyleSheet(
            f"color:{NAVY};font-size:14px;font-weight:900;border:none;"
        )
        subtitle = QLabel(
            "One PrivacyGate Account can identify multiple installations. "
            "No Library, document or restore-mapping sync is enabled."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        count = QLabel("LOCAL")
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count.setStyleSheet(
            "background:#EEF8F7;color:#0B7F89;border:1px solid #CFE7E4;"
            "border-radius:9px;padding:4px 8px;font-size:8px;font-weight:900;"
        )
        header.addWidget(count)

        refresh_button = QPushButton("Refresh devices")
        refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#062B4F;border:1px solid #C9D7E0;"
            "border-radius:9px;padding:7px 10px;font-weight:800;}"
            "QPushButton:hover{background:#F5FAFB;}"
        )
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)

        root.addLayout(header)

        rows_widget = QWidget(panel)
        rows = QVBoxLayout(rows_widget)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(7)
        root.addWidget(rows_widget)

        note = QLabel(
            "Stored online for devices: account association, hashed installation identity, "
            "device name, platform, app version, status and last connection time."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#F7FAFC;color:#61798A;border:1px solid #E4EBEF;"
            "border-radius:9px;padding:8px;font-size:8px;"
        )
        root.addWidget(note)

        layout = self.controls.layout()
        if isinstance(layout, QVBoxLayout):
            layout.addWidget(panel)

        self.panel = panel
        self.rows = rows
        self.count = count
        self.refresh_button = refresh_button

    def _patch_account_refresh(self) -> None:
        ux = getattr(self.main_window, "_privacygate_account_ux_controller", None)
        if ux is None or self._ux_patched:
            return

        original_refresh = ux.refresh_surfaces
        controller = self

        def refresh_surfaces() -> None:
            original_refresh()
            controller._rename_settings()
            controller.refresh()

        ux.refresh_surfaces = refresh_surfaces
        self._ux_patched = True

    def refresh(self) -> None:
        if self.rows is None or self.count is None or self.refresh_button is None:
            return
        if not self.account_client.current_user_id:
            self._render_signed_out()
            return
        if self.worker is not None:
            return

        self.refresh_button.setEnabled(False)
        self.count.setText("SYNCING")
        self._render_message("Refreshing authorized device metadata…")

        def load_devices() -> list[DeviceSummary]:
            session = self.account_client.restore_session()
            if session is None:
                return []
            return self.account_client.list_devices(session)

        worker = FunctionWorker(load_devices)
        self.worker = worker
        worker.signals.result.connect(self._render_devices)
        worker.signals.error.connect(self._render_error)
        worker.signals.finished.connect(self._refresh_finished)
        self.thread_pool.start(worker)

    def _render_signed_out(self) -> None:
        self.count.setText("LOCAL")
        self.refresh_button.hide()
        self._render_message(
            "Sign in to see the devices linked to your PrivacyGate Account. "
            "This installation remains fully usable locally."
        )

    def _render_message(self, text: str) -> None:
        if self.rows is None:
            return
        _clear_layout(self.rows)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            "background:#F8FAFC;color:#61798A;border:1px solid #E5ECEF;"
            "border-radius:10px;padding:10px;font-size:9px;"
        )
        self.rows.addWidget(label)

    def _render_error(self, _message: str) -> None:
        self.count.setText("UNAVAILABLE")
        self._render_message(
            "Device metadata could not be refreshed right now. "
            "Local PrivacyGate features and your existing MCP connection are unaffected."
        )

    def _refresh_finished(self) -> None:
        self.worker = None
        if self.refresh_button is not None:
            self.refresh_button.setEnabled(True)
            if self.account_client.current_user_id:
                self.refresh_button.show()

    def _render_devices(self, devices: list[DeviceSummary]) -> None:
        if self.rows is None:
            return
        _clear_layout(self.rows)
        self.refresh_button.show()

        if not devices:
            self.count.setText("0 DEVICES")
            self._render_message(
                "No device record is currently visible for this account."
            )
            return

        self.count.setText(f"{len(devices)} DEVICE" + ("" if len(devices) == 1 else "S"))

        for device in devices:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#F8FBFC;border:1px solid #E1E9ED;border-radius:11px;}"
            )
            layout = QHBoxLayout(row)
            layout.setContentsMargins(11, 9, 11, 9)
            layout.setSpacing(10)

            copy = QVBoxLayout()
            copy.setSpacing(2)
            name = QLabel(device.display_name or "This device")
            name.setStyleSheet(
                f"color:{NAVY};font-size:10px;font-weight:900;border:none;"
            )
            meta = QLabel(
                f"{device.platform.title()}  ·  PrivacyGate {device.app_version or 'unknown'}  "
                f"·  Last connected {_pretty_seen(device.updated_at)}"
            )
            meta.setWordWrap(True)
            meta.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
            copy.addWidget(name)
            copy.addWidget(meta)
            layout.addLayout(copy, 1)

            if device.is_current:
                current = QLabel("THIS DEVICE")
                current.setAlignment(Qt.AlignmentFlag.AlignCenter)
                current.setStyleSheet(
                    "background:#EAF8F6;color:#0B7F89;border:1px solid #CBE7E3;"
                    "border-radius:8px;padding:4px 7px;font-size:7px;font-weight:900;"
                )
                layout.addWidget(current)

            status = QLabel(device.status.upper())
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if device.status.lower() == "active":
                status.setStyleSheet(
                    "background:#EEF9F1;color:#267A45;border:1px solid #D1EAD9;"
                    "border-radius:8px;padding:4px 7px;font-size:7px;font-weight:900;"
                )
            else:
                status.setStyleSheet(
                    "background:#FFF4F1;color:#9A4538;border:1px solid #F0D5CF;"
                    "border-radius:8px;padding:4px 7px;font-size:7px;font-weight:900;"
                )
            layout.addWidget(status)
            self.rows.addWidget(row)


def install_account_devices_foundation_2026(main_window, account_controller):
    existing = getattr(main_window, "_privacygate_devices_controller_2026", None)
    if isinstance(existing, PrivacyGateDevicesController):
        return existing
    controller = PrivacyGateDevicesController(main_window, account_controller)
    main_window._privacygate_devices_controller_2026 = controller
    return controller
