from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QMessageBox, QProgressDialog

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import materialize_google_drive_item

from .connected_apps_browse_polish import (
    _active_account_details,
    _drive_call_with_refresh,
    _friendly_connection_error,
)


def _run_picker_busy(parent, title: str, message: str, operation):
    busy = QProgressDialog(message, "", 0, 0, parent)
    busy.setWindowTitle(title)
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setCancelButton(None)
    busy.setMinimumDuration(0)
    busy.setMinimumWidth(430)
    busy.setAutoClose(False)
    busy.setAutoReset(False)
    busy.show()
    QApplication.processEvents()
    try:
        return operation()
    finally:
        busy.close()
        QApplication.processEvents()


def _restore_privacygate_focus(main_window) -> None:
    """Best-effort return to PrivacyGate after Google's system-browser Picker."""
    try:
        if main_window.isMinimized():
            main_window.showNormal()
        else:
            main_window.show()
        main_window.raise_()
        main_window.activateWindow()
        QApplication.processEvents()
    except Exception:
        # Foreground activation is ultimately controlled by the desktop OS. A
        # focus failure must never interrupt a successful Drive import.
        pass


def _is_google_drive_browse(button: QAbstractButton) -> bool:
    if button.text().strip() != "Browse":
        return False
    parent = button.parentWidget()
    while parent is not None:
        if any(label.text().strip() == "Google Drive" for label in parent.findChildren(QLabel)):
            return True
        parent = parent.parentWidget()
    return False


def _open_google_drive_picker(main_window) -> None:
    page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(page, "_connected_apps_service", None) if page is not None else None
    if service is None or not hasattr(service, "pick_google_drive_items"):
        QMessageBox.warning(main_window, "Google Drive", "Google Drive Picker is unavailable.")
        return

    try:
        rows = _run_picker_busy(
            main_window,
            "Google Drive Picker",
            "Choose a file in the Google Drive window opened in your browser. PrivacyGate will receive access only to the file you select…",
            lambda: service.pick_google_drive_items(),
        )
    except Exception as exc:
        _restore_privacygate_focus(main_window)
        QMessageBox.warning(
            main_window,
            "Unable to choose from Google Drive",
            _friendly_connection_error("Google Drive", exc),
        )
        return

    # Google requires the native desktop Picker to use the system browser. As
    # soon as Google returns the selection, bring the desktop app back forward so
    # the user continues the workflow in PrivacyGate instead of staying on the
    # callback/browser tab.
    _restore_privacygate_focus(main_window)

    if not rows:
        main_window.statusBar().showMessage("Google Drive: no file selected", 5000)
        return

    remote = rows[0]
    try:
        local_path = _run_picker_busy(
            main_window,
            "Importing from Google Drive",
            "Preparing the selected file as a local working copy for PrivacyGate…",
            lambda: _drive_call_with_refresh(
                service,
                lambda: materialize_google_drive_item(service, remote),
            ),
        )
    except Exception as exc:
        QMessageBox.warning(
            main_window,
            "Unable to import from Google Drive",
            _friendly_connection_error("Google Drive", exc),
        )
        return

    protect = main_window.protection_page
    account_id, account_label = _active_account_details(service, "google_drive")
    document_button = getattr(protect, "_redesign_document_mode", None)
    if document_button is not None and not document_button.isChecked():
        document_button.click()
    protect.input_tabs.setCurrentIndex(1)
    protect.pdf_path.setText(str(local_path))

    source_parts = ["Google Drive"]
    if account_label:
        source_parts.append(account_label)
    source_parts.append(remote.title)
    protect._external_source_name = " • ".join(source_parts)
    protect._external_source_metadata = {
        "provider": "google_drive",
        "provider_label": "Google Drive",
        "account_id": account_id,
        "account_label": account_label,
        "item_id": str(remote.item_id or ""),
        "item_title": str(remote.title or ""),
        "item_kind": str(remote.kind or ""),
        "access_model": "drive.file + Google Picker",
    }

    main_window._show_page(0)
    _restore_privacygate_focus(main_window)
    main_window.statusBar().showMessage(
        f"Imported from Google Drive: {remote.title} — ready for local scan",
        9000,
    )


def apply_google_drive_picker_ui(main_window) -> None:
    """Replace only Google Drive's Browse action with least-privilege Picker.

    Gmail and every other connected-app browser keep their existing behavior.
    This runs after the general connected-app browse polish and rewires only the
    Google Drive button.
    """
    page = getattr(main_window, "cloud_automation_page", None)
    if page is None:
        return
    service = getattr(page, "_connected_apps_service", None)
    if service is None or not hasattr(service, "pick_google_drive_items"):
        return

    for button in page.findChildren(QAbstractButton):
        if not _is_google_drive_browse(button):
            continue
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(lambda _checked=False: _open_google_drive_picker(main_window))
        button.setToolTip(
            "Open Google Picker. PrivacyGate can access only the Drive file you explicitly select."
        )
