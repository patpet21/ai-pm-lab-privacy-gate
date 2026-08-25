from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage, _secondary_style


_INSTALLED = False


def install_apps_disconnect_layout() -> None:
    """Add a real Disconnect action and keep filtered app cards packed in the grid."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_build_ui = AppsHubPage._build_ui
    original_refresh = AppsHubPage.refresh
    original_filter = AppsHubPage._filter_cards

    def reflow(self: AppsHubPage) -> None:
        if not self._cards:
            return
        parent = self._cards[0][0].parentWidget()
        grid = parent.layout() if parent is not None else None
        if not isinstance(grid, QGridLayout):
            return
        for card, *_meta in self._cards:
            grid.removeWidget(card)
        visible = [card for card, *_meta in self._cards if not card.isHidden()]
        for index, card in enumerate(visible):
            grid.addWidget(card, index // 3, index % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)

    def disconnect_provider(self: AppsHubPage, provider: str, title: str) -> None:
        if not self._connected(provider):
            return
        answer = QMessageBox.question(
            self,
            f"Disconnect {title}",
            f"Disconnect {title} from PrivacyGate on this device?\n\n"
            "The saved local connection credentials for this provider will be removed. "
            "Your data in the provider will not be changed or deleted.",
            QMessageBox.StandardButton.Disconnect if hasattr(QMessageBox.StandardButton, "Disconnect") else QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        accepted = answer == QMessageBox.StandardButton.Yes
        if hasattr(QMessageBox.StandardButton, "Disconnect"):
            accepted = accepted or answer == QMessageBox.StandardButton.Disconnect
        if not accepted:
            return
        try:
            self.service.disconnect(provider)
        except Exception as exc:
            QMessageBox.warning(self, f"Unable to disconnect {title}", str(exc) or "The local connection could not be removed.")
            return
        self.refresh()
        reflow(self)

    def build_ui(self: AppsHubPage) -> None:
        original_build_ui(self)
        for card, *_meta in self._cards:
            status = card.findChild(QLabel, "AppStatus")
            if status is None:
                continue
            provider = str(status.property("provider") or "")
            supported = bool(status.property("supported"))
            title = ""
            for label in card.findChildren(QLabel):
                candidate = label.text().strip()
                if candidate and candidate not in {"CONNECTED", "AVAILABLE", "READY"} and candidate.upper() not in {"PRODUCTIVITY", "COMMUNICATION", "PROJECT MANAGEMENT"}:
                    if candidate not in {"LOCAL-FIRST"}:
                        title = candidate
                        break
            layout = card.layout()
            if layout is None or layout.count() == 0:
                continue
            last = layout.itemAt(layout.count() - 1)
            actions = last.layout()
            if not isinstance(actions, QHBoxLayout):
                continue
            button = QPushButton("Disconnect")
            button.setObjectName("AppDisconnect")
            button.setProperty("provider", provider)
            button.setProperty("supported", supported)
            button.setProperty("title", title or provider)
            button.setMinimumHeight(34)
            button.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#8A3340;border:1px solid #DFC5CA;"
                "border-radius:8px;padding:7px 11px;font-weight:800;}"
                "QPushButton:hover{background:#FFF3F5;border-color:#C98994;color:#6F2632;}"
            )
            # Insert before the stretch at the end of the actions row.
            actions.insertWidget(max(0, actions.count() - 1), button)
            button.clicked.connect(
                lambda _checked=False, p=provider, t=(title or provider): disconnect_provider(self, p, t)
            )

        installed = self.findChild(QPushButton, "InstalledAppsButton")
        if installed is not None:
            installed.toggled.connect(lambda _checked: reflow(self))

    def refresh(self: AppsHubPage) -> None:
        original_refresh(self)
        for button in self.findChildren(QPushButton, "AppDisconnect"):
            provider = str(button.property("provider") or "")
            supported = bool(button.property("supported"))
            connected = supported and self._connected(provider)
            button.setVisible(connected)
            button.setEnabled(connected)
        reflow(self)

    def filter_cards(self: AppsHubPage, text: str) -> None:
        original_filter(self, text)
        if getattr(self, "_installed_filter_active", False):
            for card, *_meta in self._cards:
                status = card.findChild(QLabel, "AppStatus")
                provider = str(status.property("provider") or "") if status is not None else ""
                card.setVisible((not card.isHidden()) and self._connected(provider))
        reflow(self)

    AppsHubPage._build_ui = build_ui
    AppsHubPage.refresh = refresh
    AppsHubPage._filter_cards = filter_cards
    AppsHubPage._reflow_visible_cards = reflow  # type: ignore[attr-defined]
    AppsHubPage._disconnect_provider = disconnect_provider  # type: ignore[attr-defined]
