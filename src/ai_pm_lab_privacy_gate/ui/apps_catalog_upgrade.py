from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ai_pm_lab_privacy_gate.ui import apps_hub
from ai_pm_lab_privacy_gate.ui.iconography import icon


_INSTALLED = False


def install_apps_catalog_upgrade() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    live = {"google_drive", "gmail", "clickup", "asana", "trello", "notion", "monday", "jira"}
    updated = []
    for app in apps_hub.APPS:
        key, title, description, icon_key, category, supported, path = app
        if key in live:
            supported = True
            if key in {"notion", "monday", "jira"}:
                path = "OAuth / API"
        updated.append((key, title, description, icon_key, category, supported, path))
    apps_hub.APPS = tuple(updated)

    original_connect = apps_hub.AppsHubPage._connect
    original_build = apps_hub.AppsHubPage._build_ui
    original_refresh = apps_hub.AppsHubPage.refresh

    def _connect(self, provider: str, title: str, supported: bool, integration_path: str) -> None:
        connector = {
            "notion": "connect_notion_oauth",
            "monday": "connect_monday_oauth",
            "jira": "connect_jira_oauth",
        }.get(provider)
        if not connector:
            original_connect(self, provider, title, supported, integration_path)
            return
        if not hasattr(self.service, connector):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, f"{title} connection", "This connector is not available in the current build.")
            return
        try:
            getattr(self.service, connector)()
            result = self.service.test_connection(provider)
            from PySide6.QtWidgets import QMessageBox
            if result.ok:
                QMessageBox.information(self, f"{title} connected", f"{result.account_label}\n\n{title} is connected to PrivacyGate in read-only mode.")
            else:
                QMessageBox.warning(self, f"{title} connection", result.detail)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            message = str(exc)
            if "not configured" in message.lower():
                message += "\n\nThe PrivacyGate connector is ready; register the developer OAuth app once and add its client credentials on this device. Customers will only click Connect and Allow."
            QMessageBox.warning(self, f"{title} connection failed", message)
        self.refresh()

    def _build_ui(self) -> None:
        original_build(self)
        panel = QFrame()
        panel.setObjectName("InstalledAppsStrip")
        panel.setStyleSheet("QFrame#InstalledAppsStrip{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:12px;}")
        row = QHBoxLayout(panel)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        installed = QPushButton("Installed ›")
        installed.setObjectName("InstalledAppsButton")
        installed.setCheckable(True)
        installed.setStyleSheet("QPushButton{background:transparent;color:#062B4F;border:0;padding:5px 7px;font-size:11px;font-weight:900;text-align:left;}QPushButton:hover{color:#0B7180;}QPushButton:checked{color:#0B7180;}")
        row.addWidget(installed)
        divider = QLabel("│")
        divider.setStyleSheet("color:#D7E0E7;")
        row.addWidget(divider)
        icons = QHBoxLayout()
        icons.setSpacing(6)
        row.addLayout(icons)
        row.addStretch(1)
        hint = QLabel("Click Installed to show only connected apps")
        hint.setStyleSheet("color:#718696;font-size:9px;")
        row.addWidget(hint)
        self.layout().insertWidget(1, panel)
        self._installed_strip = panel
        self._installed_icons_layout = icons
        self._installed_filter_button = installed
        self._installed_filter_active = False

        def toggle_installed(checked: bool) -> None:
            self._installed_filter_active = checked
            for card, _title, _category, _method in self._cards:
                status = card.findChild(QLabel, "AppStatus")
                provider = status.property("provider") if status is not None else ""
                card.setVisible((not checked) or self._connected(str(provider)))
            installed.setText("Installed only  ×" if checked else "Installed ›")

        installed.toggled.connect(toggle_installed)

    def _rebuild_installed_strip(self) -> None:
        layout = getattr(self, "_installed_icons_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        connected = [app for app in apps_hub.APPS if self._connected(app[0])]
        button = getattr(self, "_installed_filter_button", None)
        if button is not None and not button.isChecked():
            button.setText(f"Installed ({len(connected)}) ›")
        for key, title, _description, icon_key, _category, supported, _path in connected:
            chip = QPushButton()
            chip.setToolTip(title)
            chip.setFixedSize(38, 38)
            chip.setIcon(icon(icon_key, color="#0B7180", size=20))
            chip.setIconSize(QSize(22, 22))
            chip.setStyleSheet("QPushButton{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:10px;}QPushButton:hover{background:#F1F7F8;border-color:#8EC8CD;}")
            chip.clicked.connect(lambda _checked=False, p=key, t=title, s=supported: self._browse(p, t, s))
            layout.addWidget(chip)

            def apply_logo(pixmap, target=chip):
                if not pixmap.isNull():
                    target.setIcon(QIcon(pixmap))
                    target.setIconSize(QSize(23, 23))
            self.logo_loader.load(key, apply_logo)

    def _refresh(self) -> None:
        original_refresh(self)
        _rebuild_installed_strip(self)
        if getattr(self, "_installed_filter_active", False):
            for card, _title, _category, _method in self._cards:
                status = card.findChild(QLabel, "AppStatus")
                provider = status.property("provider") if status is not None else ""
                card.setVisible(self._connected(str(provider)))

    apps_hub.AppsHubPage._connect = _connect
    apps_hub.AppsHubPage._build_ui = _build_ui
    apps_hub.AppsHubPage.refresh = _refresh
