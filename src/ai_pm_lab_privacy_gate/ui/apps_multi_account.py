from __future__ import annotations

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_registry import MULTI_ACCOUNT_PROVIDERS
from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage, _primary_style, _secondary_style


_INSTALLED = False


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if child is not None:
            _clear_layout(child)
        if widget is not None:
            widget.deleteLater()


def install_apps_multi_account() -> None:
    """Turn connected provider cards into a multi-account manager."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_build = AppsHubPage._build_ui
    previous_refresh = AppsHubPage.refresh
    previous_connect = AppsHubPage._connect
    previous_browse = AppsHubPage._browse

    def account_count(self: AppsHubPage, provider: str) -> int:
        if provider not in MULTI_ACCOUNT_PROVIDERS or not hasattr(self.service, "account_count"):
            return 1 if self._connected(provider) else 0
        try:
            return int(self.service.account_count(provider))
        except Exception:
            return 1 if self._connected(provider) else 0

    def build_ui(self: AppsHubPage) -> None:
        previous_build(self)
        for button in self.findChildren(QPushButton, "AppDisconnect"):
            provider = str(button.property("provider") or "")
            if provider in MULTI_ACCOUNT_PROVIDERS:
                button.hide()

    def refresh(self: AppsHubPage) -> None:
        previous_refresh(self)
        for status in self.findChildren(QLabel, "AppStatus"):
            provider = str(status.property("provider") or "")
            if provider not in MULTI_ACCOUNT_PROVIDERS:
                continue
            count = account_count(self, provider)
            if count:
                suffix = "ACCOUNT" if count == 1 else "ACCOUNTS"
                status.setText(f"CONNECTED · {count} {suffix}")
                status.setStyleSheet(
                    "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                    "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )
        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = str(button.property("provider") or "")
            if provider in MULTI_ACCOUNT_PROVIDERS and account_count(self, provider):
                button.setText("Manage accounts")
                button.setToolTip("Add, select, set default or disconnect individual accounts")
        for button in self.findChildren(QPushButton, "AppDisconnect"):
            provider = str(button.property("provider") or "")
            if provider in MULTI_ACCOUNT_PROVIDERS:
                button.hide()
        reflow = getattr(self, "_reflow_visible_cards", None)
        if callable(reflow):
            reflow()

    def open_manager(
        self: AppsHubPage,
        provider: str,
        title: str,
        supported: bool,
        integration_path: str,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{title} accounts")
        dialog.setMinimumWidth(690)
        dialog.resize(760, 520)
        dialog.setStyleSheet("QDialog{background:#F7F9FA;color:#17384E;}")

        root = QVBoxLayout(dialog)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        heading = QLabel(f"{title} accounts")
        heading.setStyleSheet("color:#062B4F;font-size:22px;font-weight:950;")
        root.addWidget(heading)
        subtitle = QLabel(
            "Each account keeps its own encrypted credentials on this device. "
            "Choose a default account, or browse another account without changing the default."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#61798A;font-size:10px;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        rows = QVBoxLayout(body)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(9)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        add = QPushButton("+ Add another account")
        add.setStyleSheet(_primary_style())
        close = QPushButton("Close")
        close.setStyleSheet(_secondary_style())
        footer.addWidget(add)
        footer.addStretch(1)
        footer.addWidget(close)
        root.addLayout(footer)
        close.clicked.connect(dialog.accept)

        def records():
            try:
                return tuple(self.service.list_connected_accounts(provider))
            except Exception:
                return ()

        def rebuild() -> None:
            _clear_layout(rows)
            current = records()
            if not current:
                empty = QFrame()
                empty.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:12px;}")
                box = QVBoxLayout(empty)
                box.setContentsMargins(16, 16, 16, 16)
                text = QLabel("No accounts connected yet.")
                text.setStyleSheet("color:#61798A;font-size:11px;font-weight:750;")
                box.addWidget(text)
                rows.addWidget(empty)
                rows.addStretch(1)
                return

            for record in current:
                card = QFrame()
                card.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:12px;}")
                line = QHBoxLayout(card)
                line.setContentsMargins(14, 12, 14, 12)
                line.setSpacing(10)

                text_box = QVBoxLayout()
                label = QLabel(record.label)
                label.setStyleSheet("color:#062B4F;font-size:12px;font-weight:900;")
                text_box.addWidget(label)
                if record.subtitle:
                    sub = QLabel(record.subtitle)
                    sub.setStyleSheet("color:#718696;font-size:9px;")
                    text_box.addWidget(sub)
                line.addLayout(text_box, 1)

                if record.is_default:
                    badge = QLabel("DEFAULT")
                    badge.setStyleSheet(
                        "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
                        "border-radius:7px;padding:4px 7px;font-size:8px;font-weight:900;"
                    )
                    line.addWidget(badge)
                elif record.is_active:
                    badge = QLabel("SELECTED")
                    badge.setStyleSheet(
                        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                        "border-radius:7px;padding:4px 7px;font-size:8px;font-weight:900;"
                    )
                    line.addWidget(badge)

                default = QPushButton("Default" if not record.is_default else "Default ✓")
                default.setEnabled(not record.is_default)
                default.setStyleSheet(_secondary_style())
                browse = QPushButton("Browse")
                browse.setStyleSheet(_primary_style())
                remove = QPushButton("Disconnect")
                remove.setStyleSheet(
                    "QPushButton{background:#FFFFFF;color:#8A3340;border:1px solid #DFC5CA;"
                    "border-radius:8px;padding:7px 10px;font-weight:800;}"
                    "QPushButton:hover{background:#FFF3F5;border-color:#C98994;}"
                )
                line.addWidget(default)
                line.addWidget(browse)
                line.addWidget(remove)

                def set_default(_checked=False, account_id=record.account_id) -> None:
                    try:
                        self.service.activate_account(provider, account_id, make_default=True)
                    except Exception as exc:
                        QMessageBox.warning(dialog, f"{title} account", str(exc))
                        return
                    rebuild()
                    self.refresh()

                def browse_account(_checked=False, account_id=record.account_id) -> None:
                    try:
                        self.service.activate_account(provider, account_id)
                    except Exception as exc:
                        QMessageBox.warning(dialog, f"{title} account", str(exc))
                        return
                    dialog.accept()
                    self.refresh()
                    previous_browse(self, provider, title, supported)

                def disconnect_account(_checked=False, account_id=record.account_id, label_text=record.label) -> None:
                    answer = QMessageBox.question(
                        dialog,
                        f"Disconnect {title} account",
                        f"Disconnect {label_text} from PrivacyGate on this device?\n\n"
                        "Only this account's local credentials will be removed. "
                        f"Nothing in {title} will be deleted.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Cancel,
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return
                    try:
                        self.service.disconnect_account(provider, account_id)
                    except Exception as exc:
                        QMessageBox.warning(dialog, f"Unable to disconnect {title}", str(exc))
                        return
                    rebuild()
                    self.refresh()

                default.clicked.connect(set_default)
                browse.clicked.connect(browse_account)
                remove.clicked.connect(disconnect_account)
                rows.addWidget(card)
            rows.addStretch(1)

        def add_account() -> None:
            # Bypass this patch's Manage-accounts branch and invoke the provider's
            # normal OAuth flow. The service registry captures it as a separate
            # account (or refreshes the existing matching identity).
            previous_connect(self, provider, title, supported, integration_path)
            try:
                self.service.refresh_account_labels(provider)
            except Exception:
                pass
            rebuild()
            self.refresh()

        add.clicked.connect(add_account)

        try:
            self.service.refresh_account_labels(provider)
        except Exception:
            pass
        rebuild()
        dialog.exec()
        self.refresh()

    def connect(self: AppsHubPage, provider: str, title: str, supported: bool, integration_path: str) -> None:
        if supported and provider in MULTI_ACCOUNT_PROVIDERS and account_count(self, provider):
            open_manager(self, provider, title, supported, integration_path)
            return
        previous_connect(self, provider, title, supported, integration_path)
        self.refresh()

    def browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if provider not in MULTI_ACCOUNT_PROVIDERS or not hasattr(self.service, "list_connected_accounts"):
            previous_browse(self, provider, title, supported)
            return

        try:
            current = tuple(self.service.list_connected_accounts(provider))
        except Exception:
            current = ()
        if len(current) <= 1:
            if current:
                try:
                    self.service.activate_account(provider, current[0].account_id)
                except Exception:
                    pass
            previous_browse(self, provider, title, supported)
            return

        menu = QMenu(self)
        menu.setTitle(f"Choose {title} account")
        for record in current:
            text = record.label + ("  ·  Default" if record.is_default else "")
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(record.is_active)
            action.setData(record.account_id)
        menu.addSeparator()
        manage = menu.addAction("Manage accounts…")
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        if chosen == manage:
            path = "OAuth / API"
            for button in self.findChildren(QPushButton, "AppConnect"):
                if str(button.property("provider") or "") == provider:
                    path = str(button.property("integration_path") or path)
                    break
            open_manager(self, provider, title, supported, path)
            return
        account_id = str(chosen.data() or "")
        if not account_id:
            return
        try:
            self.service.activate_account(provider, account_id)
        except Exception as exc:
            QMessageBox.warning(self, f"{title} account", str(exc))
            return
        self.refresh()
        previous_browse(self, provider, title, supported)

    AppsHubPage._build_ui = build_ui
    AppsHubPage.refresh = refresh
    AppsHubPage._connect = connect
    AppsHubPage._browse = browse
    AppsHubPage._open_account_manager = open_manager  # type: ignore[attr-defined]
