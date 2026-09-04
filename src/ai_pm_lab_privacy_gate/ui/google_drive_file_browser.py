from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    activate_selected_file_account,
    authorized_files,
    disconnect_selected_file_account,
    list_selected_file_accounts,
    pick_additional_files,
    selected_file_access_token,
    selected_file_active_account,
    stored_file_ids,
)
from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import (
    materialize_google_drive_item,
)
from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import (
    _friendly_connection_error,
    _run_busy,
)
from ai_pm_lab_privacy_gate.ui.drive_browser import (
    _kind_icon,
    _kind_label,
    _modified,
    _supported,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader
from ai_pm_lab_privacy_gate.ui.window_focus import bring_window_to_front


def open_drive_file_browser(main_window) -> None:
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None
    if service is None:
        QMessageBox.warning(
            main_window,
            "Google Drive",
            "Google Drive selected-file access is unavailable in this build.",
        )
        return

    dialog = QDialog(main_window)
    dialog.setObjectName("DriveFileBrowser")
    dialog.setWindowTitle("Google Drive — selected files only")
    dialog.resize(1040, 720)
    dialog.setMinimumSize(840, 560)
    dialog.setStyleSheet(
        "QDialog#DriveFileBrowser{background:#F8FAFC;color:#062B4F;}"
    )
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(12)

    header = QHBoxLayout()
    logo = QLabel()
    logo.setFixedSize(42, 42)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setPixmap(icon("cloud", color="#1A73E8", size=25).pixmap(25, 25))
    logo.setStyleSheet(
        "background:#FFFFFF;border:1px solid #E1E5EA;border-radius:10px;"
    )
    logo_loader = ProviderLogoLoader(service.data_dir, dialog)
    logo_loader.load(
        "google_drive",
        lambda pixmap, target=logo: target.setPixmap(
            pixmap.scaled(
                27,
                27,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        ),
    )
    dialog._drive_logo_loader = logo_loader
    header.addWidget(logo)

    titles = QVBoxLayout()
    title = QLabel("Google Drive — selected files only")
    title.setStyleSheet("color:#202124;font-size:22px;font-weight:800;")
    subtitle = QLabel(
        "Recommended privacy mode. PrivacyGate can use only files you explicitly choose."
    )
    subtitle.setStyleSheet("color:#5F6368;font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)

    badge = QLabel("DRIVE.FILE • USER SELECTED")
    badge.setStyleSheet(
        "background:#E6F4EA;color:#137333;border:1px solid #CEEAD6;"
        "border-radius:9px;padding:7px 10px;font-size:9px;font-weight:900;"
    )
    header.addWidget(badge)
    root.addLayout(header)

    notice = QFrame()
    notice.setObjectName("SelectedFileNotice")
    notice.setStyleSheet(
        "QFrame#SelectedFileNotice{background:#E8F0FE;border:1px solid #D2E3FC;border-radius:11px;}"
    )
    notice_row = QHBoxLayout(notice)
    notice_row.setContentsMargins(14, 11, 14, 11)
    shield = QLabel("✓")
    shield.setStyleSheet("color:#188038;font-size:18px;font-weight:900;")
    notice_row.addWidget(shield)
    notice_text = QLabel(
        "Google opens its official Picker briefly in your default browser. "
        "After you choose files, PrivacyGate returns to the foreground automatically."
    )
    notice_text.setWordWrap(True)
    notice_text.setStyleSheet("color:#174EA6;font-size:10px;font-weight:650;")
    notice_row.addWidget(notice_text, 1)
    root.addWidget(notice)

    account_frame = QFrame()
    account_frame.setObjectName("SelectedFileAccountFrame")
    account_frame.setStyleSheet(
        "QFrame#SelectedFileAccountFrame{background:#FFFFFF;border:1px solid #E1E5EA;border-radius:10px;}"
    )
    account_row = QHBoxLayout(account_frame)
    account_row.setContentsMargins(12, 8, 12, 8)
    account_row.setSpacing(8)

    account_title = QLabel("Selected-file account")
    account_title.setStyleSheet("color:#3C4043;font-size:10px;font-weight:800;")
    account_row.addWidget(account_title)

    account_combo = QComboBox()
    account_combo.setMinimumWidth(300)
    account_combo.setMinimumHeight(34)
    account_combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#202124;border:1px solid #DADCE0;"
        "border-radius:8px;padding:6px 10px;font-size:10px;}"
    )
    account_row.addWidget(account_combo, 1)

    remove_account = QPushButton("Remove local access")
    remove_account.setObjectName("Secondary")
    remove_account.setToolTip(
        "Remove this selected-file account and its locally stored Google credentials from PrivacyGate."
    )
    account_row.addWidget(remove_account)
    root.addWidget(account_frame)

    table = QTreeWidget()
    table.setColumnCount(3)
    table.setHeaderLabels(["Authorized file", "Type", "Modified"])
    table.setRootIsDecorated(False)
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setStyleSheet(
        "QTreeWidget{background:#FFFFFF;color:#202124;border:1px solid #DADCE0;"
        "border-radius:11px;outline:0;padding:5px;}"
        "QTreeWidget::item{height:44px;border-bottom:1px solid #F1F3F4;padding:2px 5px;}"
        "QTreeWidget::item:hover{background:#F8FAFD;}"
        "QTreeWidget::item:selected{background:#C2E7FF;color:#202124;}"
    )
    table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    root.addWidget(table, 1)

    empty = QLabel()
    empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty.setWordWrap(True)
    empty.setStyleSheet(
        "background:#FFFFFF;color:#5F6368;border:1px dashed #C8D2DA;"
        "border-radius:12px;padding:30px;font-size:12px;"
    )
    root.addWidget(empty, 1)

    footer = QHBoxLayout()
    count = QLabel("0 authorized files")
    count.setStyleSheet("color:#5F6368;font-size:10px;")

    add = QPushButton("Choose files with Google ↗")
    add.setObjectName("Secondary")
    add.setToolTip(
        "Open Google's official desktop Picker in your system browser. "
        "No Full Drive permission is requested."
    )

    close = QPushButton("Close")
    close.setObjectName("Secondary")

    use = QPushButton("Use in Protect")
    use.setObjectName("Primary")
    use.setEnabled(False)

    footer.addWidget(count)
    footer.addStretch(1)
    footer.addWidget(add)
    footer.addWidget(close)
    footer.addWidget(use)
    root.addLayout(footer)

    state = {"lookup": {}, "accounts": {}}

    def sync_accounts() -> None:
        records = tuple(list_selected_file_accounts(service))
        state["accounts"] = {record.account_id: record for record in records}
        account_combo.blockSignals(True)
        account_combo.clear()
        active_index = -1
        for index, record in enumerate(records):
            label = record.label
            account_combo.addItem(label, record.account_id)
            if record.is_active:
                active_index = index
        if active_index >= 0:
            account_combo.setCurrentIndex(active_index)
        account_combo.blockSignals(False)

        has_accounts = bool(records)
        account_combo.setEnabled(has_accounts)
        remove_account.setEnabled(has_accounts)
        if not has_accounts:
            account_combo.addItem("No selected-file account yet", "")

    def render(rows) -> None:
        table.clear()
        state["lookup"] = {}
        for remote in rows:
            row = QTreeWidgetItem(
                [remote.title, _kind_label(remote), _modified(remote.subtitle)]
            )
            row.setIcon(0, _kind_icon(remote))
            row.setData(0, Qt.ItemDataRole.UserRole, remote.item_id)
            table.addTopLevelItem(row)
            state["lookup"][remote.item_id] = remote

        total = len(state["lookup"])
        count.setText(f"{total} authorized file(s)")
        table.setVisible(bool(total))
        empty.setVisible(not total)

        if total:
            empty.setText("")
        elif selected_file_active_account(service) is None:
            empty.setText(
                "No selected-file account connected yet.\n\n"
                "Choose “Choose files with Google” to open Google's Picker. "
                "PrivacyGate will receive access only to the files you approve."
            )
        elif stored_file_ids(service):
            empty.setText(
                "No previously selected file is currently accessible.\n"
                "Use Google Picker to grant access again or select another file."
            )
        else:
            empty.setText(
                "No files authorized for this selected-file account yet.\n\n"
                "PrivacyGate cannot enumerate My Drive in this mode. "
                "Choose files explicitly with Google Picker."
            )
        use.setEnabled(False)

    def load() -> None:
        if selected_file_active_account(service) is None:
            render(())
            return
        if not stored_file_ids(service):
            render(())
            return
        try:
            rows = _run_busy(
                dialog,
                "Loading selected Drive files",
                "Checking only the files explicitly authorized for this account…",
                lambda: authorized_files(service),
            )
        except Exception as exc:
            QMessageBox.warning(
                dialog,
                "Unable to read selected Drive files",
                _friendly_connection_error("Google Drive", exc),
            )
            rows = ()
        render(rows)

    def add_files() -> None:
        try:
            pick_additional_files(service)
        except Exception as exc:
            bring_window_to_front(dialog)
            message = str(exc)
            if "without any selected" in message:
                return
            QMessageBox.warning(dialog, "Google Picker did not complete", message)
            return
        bring_window_to_front(dialog)
        sync_accounts()
        load()

    def account_changed(index: int) -> None:
        account_id = str(account_combo.itemData(index) or "").strip()
        if not account_id:
            return
        try:
            activate_selected_file_account(service, account_id)
        except Exception as exc:
            QMessageBox.warning(dialog, "Google Drive selected files", str(exc))
            return
        sync_accounts()
        load()

    def remove_current_account() -> None:
        record = selected_file_active_account(service)
        if record is None:
            return
        answer = QMessageBox.question(
            dialog,
            "Remove selected-file access",
            f"Remove local selected-file access for {record.label}?\n\n"
            "PrivacyGate will delete this account's local token and authorized-file list. "
            "Nothing in Google Drive will be deleted, and Full Drive access is unaffected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        disconnect_selected_file_account(service, record.account_id)
        sync_accounts()
        load()

    def selected():
        rows = []
        for item in table.selectedItems():
            remote = state["lookup"].get(item.data(0, Qt.ItemDataRole.UserRole))
            if remote is not None:
                rows.append(remote)
        return tuple(rows)

    def selection_changed() -> None:
        rows = selected()
        use.setEnabled(bool(rows) and all(_supported(remote) for remote in rows))
        use.setText(
            "Use in Protect" if len(rows) <= 1 else f"Use {len(rows)} in Protect"
        )

    def import_selected() -> None:
        rows = selected()
        if not rows:
            return

        account = selected_file_active_account(service)
        if account is None:
            QMessageBox.warning(
                dialog,
                "Google Drive",
                "Choose files with Google before importing.",
            )
            return

        token = selected_file_access_token(service, account.account_id)
        if not token:
            QMessageBox.warning(
                dialog,
                "Google Drive",
                "Selected-file access must be granted again.",
            )
            return

        try:
            imported = _run_busy(
                dialog,
                "Importing selected Drive files",
                "Preparing local working copies for PrivacyGate…",
                lambda: tuple(
                    (
                        remote,
                        materialize_google_drive_item(
                            service,
                            remote,
                            access_token=token,
                        ),
                    )
                    for remote in rows
                ),
            )
        except Exception as exc:
            QMessageBox.warning(
                dialog,
                "Unable to import from Google Drive",
                _friendly_connection_error("Google Drive", exc),
            )
            return

        remote, local_path = imported[0]
        protect = main_window.protection_page
        document_button = getattr(protect, "_redesign_document_mode", None)
        if document_button is not None and not document_button.isChecked():
            document_button.click()
        protect.input_tabs.setCurrentIndex(1)
        protect.pdf_path.setText(str(local_path))
        protect._external_source_name = " • ".join(
            part for part in ("Google Drive", account.label, remote.title) if part
        )
        protect._external_source_metadata = {
            "provider": "google_drive",
            "provider_label": "Google Drive",
            "account_id": account.account_id,
            "account_label": account.label,
            "item_id": remote.item_id,
            "item_title": remote.title,
            "item_kind": remote.kind,
            "access_model": "drive.file — user selected",
            "selected_ids": [item.item_id for item in rows],
            "local_paths": [str(path) for _item, path in imported],
        }
        protect._google_drive_import_queue = imported[1:]
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported with selected-file access: {remote.title}",
            10000,
        )

    table.itemSelectionChanged.connect(selection_changed)
    account_combo.currentIndexChanged.connect(account_changed)
    remove_account.clicked.connect(remove_current_account)
    add.clicked.connect(add_files)
    close.clicked.connect(dialog.reject)
    use.clicked.connect(import_selected)

    sync_accounts()
    load()
    dialog.exec()
