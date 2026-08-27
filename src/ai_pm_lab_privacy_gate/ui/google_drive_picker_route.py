from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.google_drive_picker_ui import _open_google_drive_picker


_INSTALLED = False


def _confirm_google_drive_connection(parent) -> bool:
    """Explain Drive's least-privilege model before opening Google OAuth."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Connect Google Drive")
    dialog.setModal(True)
    dialog.setMinimumWidth(610)
    dialog.setStyleSheet("QDialog{background:#F7F9FA;color:#17384E;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 22, 24, 20)
    root.setSpacing(13)

    badge = QLabel("PRIVACY-FIRST · SELECTED-FILE ACCESS")
    badge.setStyleSheet(
        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
        "border-radius:9px;padding:6px 9px;font-size:9px;font-weight:900;"
    )
    badge.setMaximumWidth(245)
    root.addWidget(badge)

    heading = QLabel("Connect Google Drive securely")
    heading.setStyleSheet("color:#062B4F;font-size:22px;font-weight:950;")
    root.addWidget(heading)

    intro = QLabel(
        "PrivacyGate uses Google's least-privilege file access. Connecting your account does not give "
        "PrivacyGate broad access to browse your entire Drive."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet("color:#526C7D;font-size:11px;line-height:1.45;")
    root.addWidget(intro)

    points = (
        "You choose the file you want to use in Google's own Drive Picker.",
        "PrivacyGate receives access only to Drive files you explicitly select for the app.",
        "The selected document is prepared as a local working copy for Scan and Protect.",
        "PrivacyGate does not modify or delete the original file in Google Drive.",
    )
    for text in points:
        line = QLabel(f"✓  {text}")
        line.setWordWrap(True)
        line.setStyleSheet("color:#17384E;font-size:10px;font-weight:650;padding:2px 0;")
        root.addWidget(line)

    note = QLabel(
        "Google's authorization window will open in your browser next. You can cancel there at any time."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        "background:#FFFFFF;color:#61798A;border:1px solid #DCE5EA;"
        "border-radius:9px;padding:10px 12px;font-size:9px;"
    )
    root.addWidget(note)

    actions = QHBoxLayout()
    actions.addStretch(1)
    cancel = QPushButton("Cancel")
    cancel.setMinimumHeight(36)
    cancel.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
        "border-radius:8px;padding:7px 15px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;border-color:#9BCDD1;}"
    )
    proceed = QPushButton("Continue to Google")
    proceed.setMinimumHeight(36)
    proceed.setDefault(True)
    proceed.setStyleSheet(
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:7px 16px;font-weight:850;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
    )
    actions.addWidget(cancel)
    actions.addWidget(proceed)
    root.addLayout(actions)

    cancel.clicked.connect(dialog.reject)
    proceed.clicked.connect(dialog.accept)
    return dialog.exec() == QDialog.DialogCode.Accepted


def install_google_drive_picker_route() -> None:
    """Route only Google Drive through Picker while preserving other connectors.

    Install this before AppsMultiAccount. The multi-account wrapper then keeps its
    existing account selection/management behavior and delegates the selected
    Drive account to this Picker route.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_connect = AppsHubPage._connect
    previous_browse = AppsHubPage._browse

    def connect(self: AppsHubPage, provider: str, title: str, supported: bool, integration_path: str) -> None:
        if provider != "google_drive":
            previous_connect(self, provider, title, supported, integration_path)
            return
        if not supported:
            previous_connect(self, provider, title, supported, integration_path)
            return
        if not _confirm_google_drive_connection(self):
            return
        if not hasattr(self.service, "connect_google_oauth"):
            QMessageBox.warning(self, "Google Drive connection", "This connector is not available in the current build.")
            return

        try:
            self.service.connect_google_oauth()
            result = self.service.test_connection("google_drive")
            if result.ok:
                QMessageBox.information(
                    self,
                    "Google Drive connected",
                    f"{result.account_label}\n\n"
                    "Least-privilege connection active.\n\n"
                    "PrivacyGate does not request broad access to browse your entire Drive. "
                    "Use Browse to open Google Picker and explicitly choose the file you want to import. "
                    "Selected files are prepared locally for Scan and Protect; PrivacyGate does not modify or delete the originals in Google Drive.",
                )
            else:
                QMessageBox.warning(self, "Google Drive connection", result.detail)
        except Exception as exc:
            message = str(exc)
            if "not configured" in message.lower():
                message += (
                    "\n\nPrivacyGate is ready for Google Drive, but its developer OAuth app still needs to be registered once. "
                    "No customer will need to paste a personal token."
                )
            QMessageBox.warning(self, "Google Drive connection failed", message)
        self.refresh()

    def browse(self: AppsHubPage, provider: str, title: str, supported: bool) -> None:
        if provider != "google_drive":
            previous_browse(self, provider, title, supported)
            return
        if not supported or not self._connected(provider):
            return
        _open_google_drive_picker(self.main_window)

    AppsHubPage._connect = connect
    AppsHubPage._browse = browse
