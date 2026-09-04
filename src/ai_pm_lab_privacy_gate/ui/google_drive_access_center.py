from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_file_access import (
    activate_selected_file_account,
    disconnect_selected_file_account,
    list_selected_file_accounts,
    pick_additional_files,
    selected_file_active_account,
    stored_file_ids,
)
from ai_pm_lab_privacy_gate.ui.drive_browser import open_drive_browser
from ai_pm_lab_privacy_gate.ui.google_drive_file_browser import open_drive_file_browser


NAVY = "#062B4F"
TEXT = "#17384E"
MUTED = "#61798A"
PETROL = "#0B7180"


def _primary_style() -> str:
    return (
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:8px 13px;font-weight:850;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
        "QPushButton:disabled{background:#AFC9CD;color:#F7FBFC;border-color:#AFC9CD;}"
    )


def _secondary_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
        "border-radius:8px;padding:8px 13px;font-weight:800;}"
        "QPushButton:hover{background:#EDF7F7;border-color:#9BCDD1;color:#062B4F;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9BA8B2;border-color:#DDE5EA;}"
    )


def _danger_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#8A3340;border:1px solid #DFC5CA;"
        "border-radius:8px;padding:7px 10px;font-weight:800;}"
        "QPushButton:hover{background:#FFF3F5;border-color:#C98994;}"
    )


def _full_drive_accounts(apps_page) -> tuple:
    service = getattr(apps_page, "service", None)
    if service is None:
        return ()
    if hasattr(service, "list_connected_accounts"):
        try:
            return tuple(service.list_connected_accounts("google_drive"))
        except Exception:
            pass
    try:
        return (object(),) if apps_page._connected("google_drive") else ()
    except Exception:
        return ()


def _picker(parent, service, *, choose_account: bool) -> bool:
    try:
        pick_additional_files(service, choose_account=choose_account)
    except Exception as exc:
        message = str(exc)
        if "without any selected" in message:
            return False
        QMessageBox.warning(parent, "Google Picker did not complete", message)
        return False
    return True


def _open_selected_account_manager(apps_page, parent: QDialog) -> None:
    service = getattr(apps_page, "service", None)
    if service is None:
        return

    dialog = QDialog(parent)
    dialog.setWindowTitle("Google Drive — selected-file accounts")
    dialog.resize(760, 520)
    dialog.setMinimumSize(680, 460)
    dialog.setStyleSheet("QDialog{background:#F7F9FA;color:#17384E;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(12)

    title = QLabel("Selected-file accounts")
    title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:950;")
    root.addWidget(title)

    subtitle = QLabel(
        "Each Google account keeps its own drive.file token and its own list of files "
        "authorized for PrivacyGate on this device."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    root.addWidget(subtitle)

    hint = QLabel(
        "Adding another account opens Google's official Picker in your default browser. "
        "Google requires you to choose at least one file when granting drive.file access."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet(
        "background:#E8F0FE;color:#174EA6;border:1px solid #D2E3FC;"
        "border-radius:10px;padding:10px;font-size:10px;font-weight:650;"
    )
    root.addWidget(hint)

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
    add_account = QPushButton("+ Add Google account")
    add_account.setStyleSheet(_primary_style())
    close = QPushButton("Close")
    close.setStyleSheet(_secondary_style())
    footer.addWidget(add_account)
    footer.addStretch(1)
    footer.addWidget(close)
    root.addLayout(footer)

    def clear_rows() -> None:
        while rows.count():
            item = rows.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if child is not None:
                while child.count():
                    nested = child.takeAt(0)
                    if nested.widget() is not None:
                        nested.widget().deleteLater()
            if widget is not None:
                widget.deleteLater()

    def rebuild() -> None:
        clear_rows()
        records = tuple(list_selected_file_accounts(service))
        if not records:
            empty = QLabel(
                "No selected-file account is connected yet.\n\n"
                "Use “Add Google account” and choose at least one file in Google's Picker."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                "background:#FFFFFF;color:#61798A;border:1px dashed #C8D2DA;"
                "border-radius:12px;padding:28px;font-size:11px;"
            )
            rows.addWidget(empty)
            rows.addStretch(1)
            return

        for record in records:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:12px;}"
            )
            line = QHBoxLayout(card)
            line.setContentsMargins(14, 12, 14, 12)
            line.setSpacing(10)

            text_box = QVBoxLayout()
            label = QLabel(record.label)
            label.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
            text_box.addWidget(label)
            count = len(stored_file_ids(service, record.account_id))
            detail = QLabel(f"{count} authorized file(s) on this device")
            detail.setStyleSheet(f"color:{MUTED};font-size:9px;")
            text_box.addWidget(detail)
            line.addLayout(text_box, 1)

            if record.is_active:
                badge = QLabel("ACTIVE")
                badge.setStyleSheet(
                    "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
                    "border-radius:7px;padding:4px 7px;font-size:8px;font-weight:900;"
                )
                line.addWidget(badge)

            use = QPushButton("Active ✓" if record.is_active else "Use account")
            use.setEnabled(not record.is_active)
            use.setStyleSheet(_secondary_style())
            remove = QPushButton("Disconnect")
            remove.setStyleSheet(_danger_style())
            line.addWidget(use)
            line.addWidget(remove)

            def activate(_checked=False, account_id=record.account_id) -> None:
                try:
                    activate_selected_file_account(service, account_id)
                except Exception as exc:
                    QMessageBox.warning(dialog, "Google Drive account", str(exc))
                    return
                rebuild()
                apps_page.refresh()

            def disconnect(
                _checked=False,
                account_id=record.account_id,
                account_label=record.label,
            ) -> None:
                answer = QMessageBox.question(
                    dialog,
                    "Disconnect selected-file account",
                    f"Disconnect {account_label} from Selected files only?\n\n"
                    "PrivacyGate will remove this account's local drive.file token and "
                    "authorized-file list. Full Drive access is not affected.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                disconnect_selected_file_account(service, account_id)
                rebuild()
                apps_page.refresh()

            use.clicked.connect(activate)
            remove.clicked.connect(disconnect)
            rows.addWidget(card)

        rows.addStretch(1)

    def add_new_account() -> None:
        if _picker(dialog, service, choose_account=True):
            rebuild()
            apps_page.refresh()

    add_account.clicked.connect(add_new_account)
    close.clicked.connect(dialog.accept)
    rebuild()
    dialog.exec()
    apps_page.refresh()


def open_google_drive_access_center(apps_page) -> None:
    """Present Google Drive as two explicit access models instead of three flat buttons."""

    service = getattr(apps_page, "service", None)
    main_window = getattr(apps_page, "main_window", None)
    if service is None or main_window is None:
        QMessageBox.warning(apps_page, "Google Drive", "Google Drive is unavailable in this build.")
        return

    dialog = QDialog(apps_page)
    dialog.setObjectName("GoogleDriveAccessCenter")
    dialog.setWindowTitle("Google Drive")
    dialog.resize(880, 660)
    dialog.setMinimumSize(760, 600)
    dialog.setStyleSheet(
        "QDialog#GoogleDriveAccessCenter{background:#F7F9FA;color:#17384E;}"
    )

    root = QVBoxLayout(dialog)
    root.setContentsMargins(24, 20, 24, 20)
    root.setSpacing(14)

    title = QLabel("Google Drive")
    title.setStyleSheet(f"color:{NAVY};font-size:26px;font-weight:950;")
    root.addWidget(title)

    subtitle = QLabel(
        "Choose how much access PrivacyGate receives. The two modes are independent, "
        "and you can connect or disconnect accounts separately."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:11px;")
    root.addWidget(subtitle)

    selected = QFrame()
    selected.setStyleSheet(
        "QFrame{background:#FFFFFF;border:1px solid #B8E1E4;border-radius:14px;}"
    )
    selected_box = QVBoxLayout(selected)
    selected_box.setContentsMargins(18, 16, 18, 16)
    selected_box.setSpacing(9)

    selected_top = QHBoxLayout()
    selected_title = QLabel("Selected files only")
    selected_title.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:950;")
    selected_top.addWidget(selected_title)
    selected_top.addStretch(1)
    recommended = QLabel("RECOMMENDED")
    recommended.setStyleSheet(
        "background:#E6F4EA;color:#137333;border:1px solid #CEEAD6;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
    )
    selected_top.addWidget(recommended)
    selected_box.addLayout(selected_top)

    selected_desc = QLabel(
        "PrivacyGate can access only files you explicitly choose with Google Picker. "
        "It cannot browse or enumerate the rest of My Drive."
    )
    selected_desc.setWordWrap(True)
    selected_desc.setStyleSheet(f"color:{TEXT};font-size:10px;")
    selected_box.addWidget(selected_desc)

    selected_status = QLabel()
    selected_status.setWordWrap(True)
    selected_status.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:750;")
    selected_box.addWidget(selected_status)

    selected_actions = QHBoxLayout()
    choose_files = QPushButton("Choose files")
    choose_files.setStyleSheet(_primary_style())
    manage_files = QPushButton("Manage selected files")
    manage_files.setStyleSheet(_secondary_style())
    manage_selected_accounts = QPushButton("Manage accounts")
    manage_selected_accounts.setStyleSheet(_secondary_style())
    selected_actions.addWidget(choose_files)
    selected_actions.addWidget(manage_files)
    selected_actions.addWidget(manage_selected_accounts)
    selected_actions.addStretch(1)
    selected_box.addLayout(selected_actions)
    root.addWidget(selected)

    full = QFrame()
    full.setStyleSheet(
        "QFrame{background:#FFFFFF;border:1px solid #E3D2A5;border-radius:14px;}"
    )
    full_box = QVBoxLayout(full)
    full_box.setContentsMargins(18, 16, 18, 16)
    full_box.setSpacing(9)

    full_top = QHBoxLayout()
    full_title = QLabel("Full Drive access")
    full_title.setStyleSheet(f"color:{NAVY};font-size:17px;font-weight:950;")
    full_top.addWidget(full_title)
    full_top.addStretch(1)
    optional = QLabel("OPTIONAL · DRIVE.READONLY")
    optional.setStyleSheet(
        "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
    )
    full_top.addWidget(optional)
    full_box.addLayout(full_top)

    full_desc = QLabel(
        "Browse folders and files directly inside PrivacyGate, then import a local working copy. "
        "This mode uses Google's broader drive.readonly permission."
    )
    full_desc.setWordWrap(True)
    full_desc.setStyleSheet(f"color:{TEXT};font-size:10px;")
    full_box.addWidget(full_desc)

    pending = QLabel(
        "Google authorization pending: PrivacyGate has not yet been approved by Google for "
        "public use of drive.readonly. This option remains visible in this development build "
        "so we can test it with authorized/test accounts."
    )
    pending.setWordWrap(True)
    pending.setStyleSheet(
        "background:#FFF8E7;color:#7A5A16;border:1px solid #E8CE8A;"
        "border-radius:10px;padding:10px;font-size:10px;font-weight:700;"
    )
    full_box.addWidget(pending)

    full_status = QLabel()
    full_status.setWordWrap(True)
    full_status.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:750;")
    full_box.addWidget(full_status)

    full_actions = QHBoxLayout()
    browse_full = QPushButton("Browse Full Drive")
    browse_full.setStyleSheet(_primary_style())
    manage_full = QPushButton()
    manage_full.setStyleSheet(_secondary_style())
    full_actions.addWidget(browse_full)
    full_actions.addWidget(manage_full)
    full_actions.addStretch(1)
    full_box.addLayout(full_actions)
    root.addWidget(full)

    root.addStretch(1)
    footer = QHBoxLayout()
    footer.addStretch(1)
    close = QPushButton("Close")
    close.setStyleSheet(_secondary_style())
    footer.addWidget(close)
    root.addLayout(footer)

    def refresh() -> None:
        selected_accounts = tuple(list_selected_file_accounts(service))
        active = selected_file_active_account(service)
        if active is None:
            selected_status.setText("No selected-file account connected yet.")
            manage_files.setEnabled(False)
        else:
            file_count = len(stored_file_ids(service, active.account_id))
            suffix = "account" if len(selected_accounts) == 1 else "accounts"
            selected_status.setText(
                f"Active: {active.label} · {len(selected_accounts)} {suffix} connected · "
                f"{file_count} file(s) authorized for the active account."
            )
            manage_files.setEnabled(True)

        full_accounts = _full_drive_accounts(apps_page)
        full_count = len(full_accounts)
        if full_count:
            suffix = "account" if full_count == 1 else "accounts"
            full_status.setText(f"{full_count} Full Drive {suffix} connected on this device.")
            browse_full.setEnabled(True)
            manage_full.setText("Manage Full Drive accounts")
        else:
            full_status.setText("No Full Drive account connected.")
            browse_full.setEnabled(False)
            manage_full.setText("Connect Full Drive")

    def choose() -> None:
        # Normal use stays on the active selected-file account. The connector
        # supplies login_hint and avoids forcing Google's account chooser again.
        if _picker(dialog, service, choose_account=False):
            refresh()
            apps_page.refresh()

    def selected_files() -> None:
        open_drive_file_browser(main_window)
        refresh()
        apps_page.refresh()

    def selected_accounts() -> None:
        _open_selected_account_manager(apps_page, dialog)
        refresh()

    def browse() -> None:
        open_drive_browser(main_window)

    def full_accounts() -> None:
        records = _full_drive_accounts(apps_page)
        if records:
            manager = getattr(apps_page, "_open_account_manager", None)
            if callable(manager):
                manager("google_drive", "Google Drive", True, "OAuth / API")
            else:
                apps_page._connect("google_drive", "Google Drive", True, "OAuth / API")
        else:
            apps_page._connect("google_drive", "Google Drive", True, "OAuth / API")
        refresh()
        apps_page.refresh()

    choose_files.clicked.connect(choose)
    manage_files.clicked.connect(selected_files)
    manage_selected_accounts.clicked.connect(selected_accounts)
    browse_full.clicked.connect(browse)
    manage_full.clicked.connect(full_accounts)
    close.clicked.connect(dialog.accept)

    refresh()
    dialog.exec()
    apps_page.refresh()
