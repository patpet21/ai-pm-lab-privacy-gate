from __future__ import annotations

from PySide6.QtCore import QSize, Qt
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
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader
from ai_pm_lab_privacy_gate.ui.window_focus import bring_window_to_front


NAVY = "#062B4F"
TEXT = "#17384E"
MUTED = "#61798A"
PETROL = "#0B7180"
BLUE = "#1A73E8"


def _primary_style() -> str:
    return (
        "QPushButton{background:#111827;color:#FFFFFF;border:1px solid #111827;"
        "border-radius:8px;padding:8px 13px;font-weight:850;}"
        "QPushButton:hover{background:#223044;border-color:#223044;}"
        "QPushButton:disabled{background:#D8DEE5;color:#8D99A6;border-color:#D8DEE5;}"
    )


def _accent_style() -> str:
    return (
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:8px 13px;font-weight:850;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
        "QPushButton:disabled{background:#AFC9CD;color:#F7FBFC;border-color:#AFC9CD;}"
    )


def _secondary_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D5DE;"
        "border-radius:8px;padding:8px 13px;font-weight:800;}"
        "QPushButton:hover{background:#F5F8FA;border-color:#AFC1CE;color:#062B4F;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9BA8B2;border-color:#DDE5EA;}"
    )


def _danger_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#8A3340;border:1px solid #DFC5CA;"
        "border-radius:8px;padding:7px 10px;font-weight:800;}"
        "QPushButton:hover{background:#FFF3F5;border-color:#C98994;}"
    )


def _button_icon(button: QPushButton, name: str, *, light: bool = False) -> None:
    button.setIcon(icon(name, color="#FFFFFF" if light else TEXT, size=17))
    button.setIconSize(QSize(17, 17))


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


def _picker(parent: QDialog, service, *, choose_account: bool) -> bool:
    try:
        pick_additional_files(service, choose_account=choose_account)
    except Exception as exc:
        bring_window_to_front(parent)
        message = str(exc)
        if "without any selected" in message:
            return False
        QMessageBox.warning(parent, "Google Picker did not complete", message)
        return False
    bring_window_to_front(parent)
    return True


def _load_drive_logo(service, parent, target: QLabel, size: int = 28) -> ProviderLogoLoader:
    target.setPixmap(icon("cloud", color=BLUE, size=size).pixmap(size, size))
    loader = ProviderLogoLoader(service.data_dir, parent)
    loader.load(
        "google_drive",
        lambda pixmap, label=target, px=size: label.setPixmap(
            pixmap.scaled(
                px,
                px,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        ),
    )
    return loader


def _open_selected_account_manager(apps_page, parent: QDialog) -> None:
    service = getattr(apps_page, "service", None)
    if service is None:
        return

    dialog = QDialog(parent)
    dialog.setObjectName("SelectedDriveAccounts")
    dialog.setWindowTitle("Google Drive — selected-file accounts")
    dialog.resize(780, 540)
    dialog.setMinimumSize(700, 480)
    dialog.setStyleSheet(
        "QDialog#SelectedDriveAccounts{background:#EEF2F5;color:#17384E;}"
        "QFrame#AccountShell{background:#FFFFFF;border:1px solid #D6DEE5;border-radius:14px;}"
        "QFrame#AccountCard{background:#FFFFFF;border:1px solid #DCE4EA;border-radius:11px;}"
    )

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(18, 18, 18, 18)
    shell = QFrame()
    shell.setObjectName("AccountShell")
    outer.addWidget(shell, 1)

    root = QVBoxLayout(shell)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(12)

    header = QHBoxLayout()
    logo = QLabel()
    logo.setFixedSize(42, 42)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setStyleSheet(
        "background:#FFFFFF;border:1px solid #DCE4EA;border-radius:10px;padding:6px;"
    )
    dialog._drive_logo_loader = _load_drive_logo(service, dialog, logo, 27)
    header.addWidget(logo)

    titles = QVBoxLayout()
    title = QLabel("Selected-file accounts")
    title.setStyleSheet(f"color:{NAVY};font-size:21px;font-weight:950;")
    subtitle = QLabel(
        "Each account keeps its own Google token and its own authorized-file list."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)

    close_top = QPushButton("×")
    close_top.setFixedSize(34, 34)
    close_top.setStyleSheet(
        "QPushButton{background:transparent;color:#7B8792;border:0;font-size:21px;}"
        "QPushButton:hover{background:#F1F4F6;border-radius:17px;color:#263746;}"
    )
    header.addWidget(close_top)
    root.addLayout(header)

    hint = QFrame()
    hint.setObjectName("AccountHint")
    hint.setStyleSheet(
        "QFrame#AccountHint{background:#F4F8FF;border:1px solid #D9E5F7;border-radius:10px;}"
    )
    hint_row = QHBoxLayout(hint)
    hint_row.setContentsMargins(12, 9, 12, 9)
    hint_icon = QLabel()
    hint_icon.setPixmap(icon("protect", color=BLUE, size=17).pixmap(17, 17))
    hint_row.addWidget(hint_icon)
    hint_text = QLabel(
        "Add another Google account only when you want a separate set of selected files. "
        "Normal file selection keeps using the active account."
    )
    hint_text.setWordWrap(True)
    hint_text.setStyleSheet("color:#405A70;font-size:10px;")
    hint_row.addWidget(hint_text, 1)
    root.addWidget(hint)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:0;}")
    body = QWidget()
    body.setStyleSheet("background:transparent;")
    rows = QVBoxLayout(body)
    rows.setContentsMargins(0, 0, 0, 0)
    rows.setSpacing(9)
    scroll.setWidget(body)
    root.addWidget(scroll, 1)

    footer = QHBoxLayout()
    add_account = QPushButton("Add Google account")
    add_account.setStyleSheet(_accent_style())
    _button_icon(add_account, "contact", light=True)
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
            if widget is not None:
                widget.deleteLater()

    def rebuild() -> None:
        clear_rows()
        records = tuple(list_selected_file_accounts(service))
        if not records:
            empty = QLabel(
                "No selected-file account is connected yet.\n\n"
                "Choose “Add Google account” and select at least one file in Google's Picker."
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
            card.setObjectName("AccountCard")
            line = QHBoxLayout(card)
            line.setContentsMargins(14, 12, 14, 12)
            line.setSpacing(10)

            avatar = QLabel()
            avatar.setFixedSize(34, 34)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setPixmap(icon("contact", color=BLUE, size=19).pixmap(19, 19))
            avatar.setStyleSheet(
                "background:#F4F8FF;border:1px solid #D9E5F7;border-radius:9px;"
            )
            line.addWidget(avatar)

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

            use = QPushButton("Active" if record.is_active else "Use account")
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
    close_top.clicked.connect(dialog.accept)
    rebuild()
    dialog.exec()
    apps_page.refresh()


def open_google_drive_access_center(apps_page) -> None:
    """Open the Google Drive control center using the same visual language as Protect."""

    service = getattr(apps_page, "service", None)
    main_window = getattr(apps_page, "main_window", None)
    if service is None or main_window is None:
        QMessageBox.warning(
            apps_page,
            "Google Drive",
            "Google Drive is unavailable in this build.",
        )
        return

    dialog = QDialog(apps_page)
    dialog.setObjectName("GoogleDriveAccessCenter")
    dialog.setWindowTitle("Google Drive")
    dialog.resize(960, 690)
    dialog.setMinimumSize(860, 620)
    dialog.setStyleSheet(
        "QDialog#GoogleDriveAccessCenter{background:#AAB3BA;color:#17384E;}"
        "QFrame#DriveShell{background:#F9FBFC;border:1px solid #D4DEE6;border-radius:16px;}"
        "QFrame#ModeCard{background:#FFFFFF;border:1px solid #D8E1E8;border-radius:12px;}"
        "QFrame#ModeCardSelected{background:#FFFFFF;border:1px solid #C9DDE1;border-radius:12px;}"
        "QFrame#ModeCardFull{background:#FFFFFF;border:1px solid #E5D5AE;border-radius:12px;}"
        "QFrame#MetaStrip{background:#F8FAFC;border:1px solid #E1E7EC;border-radius:9px;}"
        "QFrame#WarningStrip{background:#FFF8E8;border:1px solid #E8CE8A;border-radius:9px;}"
    )
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(28, 26, 28, 26)
    outer.setSpacing(0)

    shell = QFrame()
    shell.setObjectName("DriveShell")
    outer.addWidget(shell, 1)

    root = QVBoxLayout(shell)
    root.setContentsMargins(18, 18, 18, 14)
    root.setSpacing(12)

    header = QHBoxLayout()
    logo = QLabel()
    logo.setFixedSize(44, 44)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setStyleSheet(
        "background:#FFFFFF;border:1px solid #DCE4EA;border-radius:10px;padding:6px;"
    )
    dialog._drive_logo_loader = _load_drive_logo(service, dialog, logo, 28)
    header.addWidget(logo)

    titles = QVBoxLayout()
    titles.setSpacing(2)
    title = QLabel("Google Drive — import to Protect")
    title.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:950;")
    subtitle = QLabel(
        "Choose how PrivacyGate should access Drive. Both modes stay separate."
    )
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)

    header_badge = QLabel("GOOGLE DRIVE · LOCAL IMPORT")
    header_badge.setStyleSheet(
        "background:#EEF3FF;color:#1D4ED8;border:0;border-radius:8px;"
        "padding:8px 11px;font-size:8px;font-weight:900;"
    )
    header.addWidget(header_badge)

    close_top = QPushButton("×")
    close_top.setFixedSize(34, 34)
    close_top.setStyleSheet(
        "QPushButton{background:transparent;color:#7B8792;border:0;font-size:21px;}"
        "QPushButton:hover{background:#EEF2F5;border-radius:17px;color:#263746;}"
    )
    header.addWidget(close_top)
    root.addLayout(header)

    body = QFrame()
    body.setObjectName("ModeCard")
    body_box = QVBoxLayout(body)
    body_box.setContentsMargins(14, 12, 14, 12)
    body_box.setSpacing(12)

    chooser_header = QHBoxLayout()
    chooser_icon = QLabel()
    chooser_icon.setFixedSize(26, 26)
    chooser_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chooser_icon.setPixmap(icon("cloud", color=BLUE, size=18).pixmap(18, 18))
    chooser_header.addWidget(chooser_icon)
    chooser_text = QLabel("Choose your Google Drive access mode")
    chooser_text.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
    chooser_header.addWidget(chooser_text)
    chooser_header.addStretch(1)
    body_box.addLayout(chooser_header)

    selected = QFrame()
    selected.setObjectName("ModeCardSelected")
    selected_box = QVBoxLayout(selected)
    selected_box.setContentsMargins(14, 13, 14, 13)
    selected_box.setSpacing(9)

    selected_top = QHBoxLayout()
    selected_icon = QLabel()
    selected_icon.setFixedSize(36, 36)
    selected_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    selected_icon.setPixmap(icon("protect", color=PETROL, size=21).pixmap(21, 21))
    selected_icon.setStyleSheet(
        "background:#EAF7F7;border:1px solid #CDE8E8;border-radius:9px;"
    )
    selected_top.addWidget(selected_icon)

    selected_titles = QVBoxLayout()
    selected_titles.setSpacing(1)
    selected_title = QLabel("Selected files only")
    selected_title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:950;")
    selected_desc = QLabel(
        "More private: PrivacyGate can use only files you explicitly choose in Google's Picker."
    )
    selected_desc.setWordWrap(True)
    selected_desc.setStyleSheet(f"color:{MUTED};font-size:9px;")
    selected_titles.addWidget(selected_title)
    selected_titles.addWidget(selected_desc)
    selected_top.addLayout(selected_titles, 1)

    recommended = QLabel("RECOMMENDED")
    recommended.setStyleSheet(
        "background:#E6F4EA;color:#137333;border:1px solid #CEEAD6;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
    )
    selected_top.addWidget(recommended)
    selected_box.addLayout(selected_top)

    selected_meta = QFrame()
    selected_meta.setObjectName("MetaStrip")
    selected_meta_row = QHBoxLayout(selected_meta)
    selected_meta_row.setContentsMargins(11, 7, 11, 7)
    selected_meta_row.setSpacing(8)
    account_icon = QLabel()
    account_icon.setPixmap(icon("contact", color=BLUE, size=16).pixmap(16, 16))
    selected_meta_row.addWidget(account_icon)
    selected_status = QLabel()
    selected_status.setStyleSheet(f"color:{TEXT};font-size:9px;font-weight:700;")
    selected_status.setWordWrap(True)
    selected_meta_row.addWidget(selected_status, 1)
    selected_box.addWidget(selected_meta)

    selected_actions = QHBoxLayout()
    choose_files = QPushButton("Choose files")
    choose_files.setStyleSheet(_primary_style())
    _button_icon(choose_files, "external", light=True)
    manage_files = QPushButton("View selected files")
    manage_files.setStyleSheet(_secondary_style())
    _button_icon(manage_files, "document")
    manage_selected_accounts = QPushButton("Manage selected accounts")
    manage_selected_accounts.setStyleSheet(_secondary_style())
    _button_icon(manage_selected_accounts, "contact")
    selected_actions.addWidget(choose_files)
    selected_actions.addWidget(manage_files)
    selected_actions.addWidget(manage_selected_accounts)
    selected_actions.addStretch(1)
    selected_box.addLayout(selected_actions)
    body_box.addWidget(selected)

    full = QFrame()
    full.setObjectName("ModeCardFull")
    full_box = QVBoxLayout(full)
    full_box.setContentsMargins(14, 13, 14, 13)
    full_box.setSpacing(9)

    full_top = QHBoxLayout()
    full_icon = QLabel()
    full_icon.setFixedSize(36, 36)
    full_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    full_icon.setPixmap(icon("cloud", color="#9A6A0A", size=21).pixmap(21, 21))
    full_icon.setStyleSheet(
        "background:#FFF8E8;border:1px solid #EAD9AA;border-radius:9px;"
    )
    full_top.addWidget(full_icon)

    full_titles = QVBoxLayout()
    full_titles.setSpacing(1)
    full_title = QLabel("Full Drive access")
    full_title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:950;")
    full_desc = QLabel(
        "Browse folders and files inside PrivacyGate using Google's broader read-only permission."
    )
    full_desc.setWordWrap(True)
    full_desc.setStyleSheet(f"color:{MUTED};font-size:9px;")
    full_titles.addWidget(full_title)
    full_titles.addWidget(full_desc)
    full_top.addLayout(full_titles, 1)

    optional = QLabel("OPTIONAL · DRIVE.READONLY")
    optional.setStyleSheet(
        "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
        "border-radius:8px;padding:5px 8px;font-size:8px;font-weight:900;"
    )
    full_top.addWidget(optional)
    full_box.addLayout(full_top)

    pending = QFrame()
    pending.setObjectName("WarningStrip")
    pending_row = QHBoxLayout(pending)
    pending_row.setContentsMargins(11, 8, 11, 8)
    pending_row.setSpacing(9)
    warning_mark = QLabel("!")
    warning_mark.setFixedSize(22, 22)
    warning_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    warning_mark.setStyleSheet(
        "background:#F7D98A;color:#6B4B0B;border:0;border-radius:11px;"
        "font-size:12px;font-weight:950;"
    )
    pending_row.addWidget(warning_mark)
    pending_text = QLabel(
        "<b>Google approval pending.</b> PrivacyGate is not yet approved for public "
        "use of drive.readonly. This development option is for authorized/test accounts only."
    )
    pending_text.setWordWrap(True)
    pending_text.setStyleSheet("color:#72541B;font-size:9px;")
    pending_row.addWidget(pending_text, 1)
    full_box.addWidget(pending)

    full_meta = QFrame()
    full_meta.setObjectName("MetaStrip")
    full_meta_row = QHBoxLayout(full_meta)
    full_meta_row.setContentsMargins(11, 7, 11, 7)
    full_meta_row.setSpacing(8)
    full_account_icon = QLabel()
    full_account_icon.setPixmap(icon("contact", color="#9A6A0A", size=16).pixmap(16, 16))
    full_meta_row.addWidget(full_account_icon)
    full_status = QLabel()
    full_status.setStyleSheet(f"color:{TEXT};font-size:9px;font-weight:700;")
    full_meta_row.addWidget(full_status, 1)
    full_box.addWidget(full_meta)

    full_actions = QHBoxLayout()
    browse_full = QPushButton("Browse Full Drive")
    browse_full.setStyleSheet(_accent_style())
    _button_icon(browse_full, "cloud", light=True)
    manage_full = QPushButton()
    manage_full.setStyleSheet(_secondary_style())
    _button_icon(manage_full, "contact")
    full_actions.addWidget(browse_full)
    full_actions.addWidget(manage_full)
    full_actions.addStretch(1)
    full_box.addLayout(full_actions)
    body_box.addWidget(full)

    root.addWidget(body, 1)

    footer = QHBoxLayout()
    privacy_icon = QLabel()
    privacy_icon.setPixmap(icon("protect", color=PETROL, size=16).pixmap(16, 16))
    footer.addWidget(privacy_icon)
    privacy_note = QLabel(
        "Google controls the Picker interface. PrivacyGate receives access only to the files you select."
    )
    privacy_note.setStyleSheet(f"color:{MUTED};font-size:9px;")
    footer.addWidget(privacy_note)
    footer.addStretch(1)
    close = QPushButton("Close")
    close.setStyleSheet(_secondary_style())
    footer.addWidget(close)
    root.addLayout(footer)

    def refresh() -> None:
        selected_accounts = tuple(list_selected_file_accounts(service))
        active = selected_file_active_account(service)
        if active is None:
            selected_status.setText(
                "No selected-file account connected · choose files to connect one."
            )
            manage_files.setEnabled(False)
        else:
            file_count = len(stored_file_ids(service, active.account_id))
            account_word = "account" if len(selected_accounts) == 1 else "accounts"
            file_word = "file" if file_count == 1 else "files"
            selected_status.setText(
                f"{active.label}   ·   {len(selected_accounts)} {account_word} connected"
                f"   ·   {file_count} authorized {file_word}"
            )
            manage_files.setEnabled(True)

        full_accounts = _full_drive_accounts(apps_page)
        full_count = len(full_accounts)
        if full_count:
            suffix = "account" if full_count == 1 else "accounts"
            full_status.setText(
                f"{full_count} Full Drive {suffix} connected on this device."
            )
            browse_full.setEnabled(True)
            manage_full.setText("Manage Full Drive accounts")
        else:
            full_status.setText("No Full Drive account connected.")
            browse_full.setEnabled(False)
            manage_full.setText("Connect Full Drive")

    def choose() -> None:
        if _picker(dialog, service, choose_account=False):
            refresh()
            apps_page.refresh()

    def selected_files() -> None:
        open_drive_file_browser(main_window)
        bring_window_to_front(dialog)
        refresh()
        apps_page.refresh()

    def selected_accounts() -> None:
        _open_selected_account_manager(apps_page, dialog)
        bring_window_to_front(dialog)
        refresh()

    def browse() -> None:
        open_drive_browser(main_window)
        bring_window_to_front(dialog)

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
        bring_window_to_front(dialog)
        refresh()
        apps_page.refresh()

    choose_files.clicked.connect(choose)
    manage_files.clicked.connect(selected_files)
    manage_selected_accounts.clicked.connect(selected_accounts)
    browse_full.clicked.connect(browse)
    manage_full.clicked.connect(full_accounts)
    close.clicked.connect(dialog.accept)
    close_top.clicked.connect(dialog.accept)

    refresh()
    dialog.exec()
    apps_page.refresh()
