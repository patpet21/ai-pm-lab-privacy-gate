from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QMessageBox, QProgressDialog

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import materialize_google_drive_item

from .connected_apps_browse_polish import (
    _active_account_details,
    _drive_call_with_refresh,
    _friendly_connection_error,
)
from .google_drive_embedded_picker import pick_google_drive_file_ids


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
    """Authorize/select and import one new Drive file without leaving PrivacyGate."""
    page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(page, "_connected_apps_service", None) if page is not None else None
    if service is None or not hasattr(service, "google_drive_items_from_ids"):
        QMessageBox.warning(main_window, "Google Drive", "Google Drive Picker is unavailable.")
        return

    try:
        picked_ids = pick_google_drive_file_ids(main_window, service)
    except Exception as exc:
        QMessageBox.warning(
            main_window,
            "Unable to choose from Google Drive",
            _friendly_connection_error("Google Drive", exc),
        )
        return

    if not picked_ids:
        main_window.statusBar().showMessage("Google Drive: no file selected", 5000)
        return

    try:
        rows = _run_picker_busy(
            main_window,
            "Reading Google Drive selection",
            "Reading only the Google Drive file you selected…",
            lambda: _drive_call_with_refresh(
                service,
                lambda: service.google_drive_items_from_ids(picked_ids),
            ),
        )
    except Exception as exc:
        QMessageBox.warning(
            main_window,
            "Unable to read Google Drive selection",
            _friendly_connection_error("Google Drive", exc),
        )
        return

    if not rows:
        main_window.statusBar().showMessage("Google Drive: selected file was not returned", 5000)
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
        "access_model": "drive.file + embedded Google Picker",
    }

    main_window._show_page(0)
    main_window.statusBar().showMessage(
        f"Imported from Google Drive: {remote.title} — ready for local scan",
        9000,
    )


def _open_google_drive_sources(main_window) -> None:
    """Browse already-authorized Drive files in PrivacyGate's native source UI."""
    page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(page, "_connected_apps_service", None) if page is not None else None
    if service is None:
        QMessageBox.warning(main_window, "Google Drive", "Connected Apps service is unavailable.")
        return

    # Keep the existing multi-account behavior: with more than one Drive account,
    # explicitly choose/activate the source account before showing its authorized
    # files. Import is deliberately inside the function to avoid module cycles at
    # startup.
    from ai_pm_lab_privacy_gate.ui.account_aware_routing import choose_provider_account
    from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _open_source_browser

    if not choose_provider_account(main_window, service, "google_drive", "Google Drive"):
        return
    _open_source_browser(main_window, "google_drive", "Google Drive")


def apply_google_drive_picker_ui(main_window) -> None:
    """Keep Apps browsing inside PrivacyGate while retaining Picker for new files.

    Apps -> Google Drive -> Browse uses the same native available-sources dialog
    used by Protect. The embedded Picker remains a separate authorization/import
    mechanism for a new file, so normal browsing never opens the system browser.
    Gmail and all other connectors are untouched.
    """
    page = getattr(main_window, "cloud_automation_page", None)
    if page is None:
        return
    service = getattr(page, "_connected_apps_service", None)
    if service is None:
        return

    for button in page.findChildren(QAbstractButton):
        if not _is_google_drive_browse(button):
            continue
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(lambda _checked=False: _open_google_drive_sources(main_window))
        button.setToolTip(
            "Browse Google Drive files already authorized for PrivacyGate without leaving the app."
        )
