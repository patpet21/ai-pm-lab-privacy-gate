from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import (
    materialize_google_drive_item,
)
from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import (
    _active_account_details,
    _drive_call_with_refresh,
    _friendly_connection_error,
    _run_busy,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDES = "application/vnd.google-apps.presentation"
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}

NAVY = "#202124"
MUTED = "#5F6368"
BLUE = "#1A73E8"


def _kind_label(remote) -> str:
    if remote.kind == FOLDER_MIME:
        return "Folder"
    if remote.kind == GOOGLE_DOC:
        return "Google Docs"
    if remote.kind == GOOGLE_SHEET:
        return "Google Sheets"
    if remote.kind == GOOGLE_SLIDES:
        return "Google Slides"
    suffix = Path(remote.title).suffix.lower()
    names = {
        ".pdf": "PDF",
        ".docx": "Word",
        ".xlsx": "Excel",
        ".pptx": "PowerPoint",
        ".txt": "Text",
        ".png": "PNG image",
        ".jpg": "JPEG image",
        ".jpeg": "JPEG image",
        ".webp": "WebP image",
    }
    if suffix in names:
        return names[suffix]
    if remote.kind.startswith("image/"):
        return "Image"
    return remote.kind.replace("application/", "") or "File"


def _kind_icon(remote):
    suffix = Path(remote.title).suffix.lower()
    if remote.kind == FOLDER_MIME:
        return icon("library", color="#F9AB00", size=20)
    if remote.kind == GOOGLE_DOC or suffix == ".docx":
        return icon("document", color="#4285F4", size=20)
    if remote.kind == GOOGLE_SHEET or suffix == ".xlsx":
        return icon("template", color="#188038", size=20)
    if remote.kind == GOOGLE_SLIDES or suffix == ".pptx":
        return icon("report", color="#F9AB00", size=20)
    if suffix == ".pdf":
        return icon("document", color="#D93025", size=20)
    if suffix == ".txt":
        return icon("document", color="#5F6368", size=20)
    if remote.kind.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return icon("document", color="#A142F4", size=20)
    return icon("document", color="#5F6368", size=20)


def _supported(remote) -> bool:
    if remote.kind in {GOOGLE_DOC, GOOGLE_SHEET, GOOGLE_SLIDES}:
        return True
    return Path(remote.title).suffix.lower() in SUPPORTED_SUFFIXES


def _is_image(remote) -> bool:
    return remote.kind.startswith("image/") or Path(remote.title).suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".heic"
    }


def _modified(value: str) -> str:
    if not value:
        return ""
    return value.replace("T", " ").replace("Z", "")[:16]


def _unsupported_message(remote) -> str:
    if _is_image(remote):
        return (
            "This image is visible in Google Drive, but PrivacyGate cannot analyze image pixels yet. "
            "Local OCR/image protection is the next document-engine block.\n\n"
            "Supported now: PDF, DOCX, XLSX, PPTX, TXT, Google Docs, Google Sheets and Google Slides."
        )
    return (
        f"{_kind_label(remote)} is visible in Drive but is not supported by Protect yet.\n\n"
        "Choose PDF, DOCX, XLSX, PPTX, TXT, Google Docs, Google Sheets or Google Slides."
    )


def open_drive_browser(main_window) -> None:
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None
    from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_picker_access import (
        embedded_picker_enabled,
    )

    if service is not None and embedded_picker_enabled():
        from ai_pm_lab_privacy_gate.ui.google_drive_embedded_picker import (
            open_embedded_drive_picker,
        )

        open_embedded_drive_picker(main_window, service)
        return
    if service is None or not hasattr(service, "list_drive_folder"):
        QMessageBox.warning(main_window, "Google Drive", "Google Drive folder navigation is unavailable in this build.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Google Drive — import to Protect")
    dialog.resize(1040, 720)
    dialog.setMinimumSize(840, 560)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(10)

    header = QHBoxLayout()
    logo = QLabel()
    logo.setFixedSize(42, 42)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setStyleSheet("background:#FFFFFF;border:1px solid #E1E5EA;border-radius:10px;")
    logo.setPixmap(icon("cloud", color=BLUE, size=24).pixmap(24, 24))
    header.addWidget(logo)
    titles = QVBoxLayout()
    title = QLabel("Google Drive")
    title.setStyleSheet(f"color:{NAVY};font-size:23px;font-weight:800;")
    subtitle = QLabel("Open folders just like a file picker, then choose one supported file to bring into PrivacyGate locally.")
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    subtitle.setWordWrap(True)
    titles.addWidget(title)
    titles.addWidget(subtitle)
    header.addLayout(titles, 1)
    local = QLabel("READ-ONLY • LOCAL IMPORT")
    local.setStyleSheet("background:#E8F0FE;color:#174EA6;border-radius:9px;padding:6px 9px;font-size:9px;font-weight:800;")
    header.addWidget(local)
    root.addLayout(header)

    try:
        logo_loader = ProviderLogoLoader(service.data_dir, dialog)
        logo_loader.load(
            "google_drive",
            lambda pixmap: logo.setPixmap(
                pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )
        dialog._drive_logo_loader = logo_loader
    except Exception:
        pass

    navigation = QFrame()
    navigation.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #E1E5EA;border-radius:10px;}")
    nav_layout = QHBoxLayout(navigation)
    nav_layout.setContentsMargins(9, 6, 9, 6)
    nav_layout.setSpacing(5)
    back = QPushButton("‹")
    back.setFixedSize(34, 32)
    back.setToolTip("Back one folder")
    back.setStyleSheet("QPushButton{border:0;background:transparent;font-size:20px;color:#3C4043;} QPushButton:hover{background:#F1F3F4;border-radius:8px;}")
    nav_layout.addWidget(back)
    breadcrumb_host = QHBoxLayout()
    breadcrumb_host.setSpacing(2)
    nav_layout.addLayout(breadcrumb_host, 1)
    root.addWidget(navigation)

    search_row = QHBoxLayout()
    search = QLineEdit()
    search.setPlaceholderText("Search this folder")
    search.setClearButtonEnabled(True)
    search.setMinimumHeight(40)
    search.setStyleSheet(
        "QLineEdit{background:#EDF2FA;color:#202124;border:1px solid #EDF2FA;border-radius:20px;padding:8px 15px;font-size:11px;}"
        "QLineEdit:focus{background:#FFFFFF;border-color:#AECBFA;}"
    )
    search_button = QPushButton("Search")
    search_button.setObjectName("Primary")
    all_button = QPushButton("Show all")
    all_button.setObjectName("Secondary")
    search_row.addWidget(search, 1)
    search_row.addWidget(search_button)
    search_row.addWidget(all_button)
    root.addLayout(search_row)

    table = QTreeWidget()
    table.setColumnCount(3)
    table.setHeaderLabels(["Name", "Type", "Modified"])
    table.setRootIsDecorated(False)
    table.setAlternatingRowColors(False)
    table.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
    table.setStyleSheet(
        "QTreeWidget{background:#FFFFFF;color:#202124;border:1px solid #DADCE0;border-radius:11px;outline:0;padding:5px;}"
        "QTreeWidget::item{height:42px;border-bottom:1px solid #F1F3F4;padding:2px 5px;}"
        "QTreeWidget::item:hover{background:#F8FAFD;}"
        "QTreeWidget::item:selected{background:#C2E7FF;color:#202124;}"
    )
    header_view = table.header()
    header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    root.addWidget(table, 1)

    footer = QHBoxLayout()
    count = QLabel("0 items")
    count.setStyleSheet(f"color:{MUTED};font-size:10px;")
    hint = QLabel("Select a file")
    hint.setStyleSheet(f"color:{MUTED};font-size:10px;")
    hint.setWordWrap(True)
    close = QPushButton("Close")
    close.setObjectName("Secondary")
    action = QPushButton("Use in Protect")
    action.setObjectName("Primary")
    action.setEnabled(False)
    footer.addWidget(count)
    footer.addWidget(hint, 1)
    footer.addWidget(close)
    footer.addWidget(action)
    root.addLayout(footer)

    state = {"trail": [("root", "My Drive")], "lookup": {}}

    def current_folder() -> str:
        return state["trail"][-1][0]

    def render_breadcrumbs() -> None:
        while breadcrumb_host.count():
            item = breadcrumb_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, (_folder_id, label) in enumerate(state["trail"]):
            crumb = QPushButton(label)
            crumb.setStyleSheet(
                "QPushButton{border:0;background:transparent;color:#3C4043;padding:5px 7px;font-weight:700;}"
                "QPushButton:hover{background:#F1F3F4;border-radius:7px;}"
            )
            crumb.clicked.connect(lambda _checked=False, i=index: go_to_breadcrumb(i))
            breadcrumb_host.addWidget(crumb)
            if index < len(state["trail"]) - 1:
                arrow = QLabel("›")
                arrow.setStyleSheet("color:#80868B;")
                breadcrumb_host.addWidget(arrow)
        breadcrumb_host.addStretch(1)
        back.setEnabled(len(state["trail"]) > 1)

    def populate(rows) -> None:
        table.clear()
        state["lookup"] = {}
        for remote in rows:
            if not remote.item_id:
                continue
            row = QTreeWidgetItem([remote.title, _kind_label(remote), _modified(remote.subtitle)])
            row.setIcon(0, _kind_icon(remote))
            row.setData(0, Qt.ItemDataRole.UserRole, remote.item_id)
            if remote.kind == FOLDER_MIME:
                font = row.font(0)
                font.setBold(True)
                row.setFont(0, font)
            elif not _supported(remote):
                row.setToolTip(0, _unsupported_message(remote))
            table.addTopLevelItem(row)
            state["lookup"][remote.item_id] = remote
        count.setText(f"{len(state['lookup'])} item(s)")
        action.setEnabled(False)
        action.setText("Use in Protect")
        hint.setText("Open a folder or select a supported file.")

    def load() -> None:
        query = search.text().strip()
        if query:
            operation = lambda: service.search_drive_folder(current_folder(), query, 100)
        else:
            operation = lambda: service.list_drive_folder(current_folder(), 100)
        try:
            rows = _run_busy(
                dialog,
                "Loading Google Drive",
                f"Searching {state['trail'][-1][1]}…" if query else f"Opening {state['trail'][-1][1]}…",
                lambda: _drive_call_with_refresh(service, operation),
            )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to read Google Drive", _friendly_connection_error("Google Drive", exc))
            return
        render_breadcrumbs()
        populate(rows)

    def open_folder(remote) -> None:
        search.clear()
        state["trail"].append((remote.item_id, remote.title))
        load()

    def go_to_breadcrumb(index: int) -> None:
        if index < 0 or index >= len(state["trail"]):
            return
        search.clear()
        state["trail"] = state["trail"][: index + 1]
        load()

    def go_back() -> None:
        if len(state["trail"]) <= 1:
            return
        search.clear()
        state["trail"].pop()
        load()

    def selected_remote():
        current = table.currentItem()
        if current is None:
            return None
        return state["lookup"].get(current.data(0, Qt.ItemDataRole.UserRole))

    def selection_changed() -> None:
        remote = selected_remote()
        if remote is None:
            action.setEnabled(False)
            hint.setText("Open a folder or select a supported file.")
            return
        if remote.kind == FOLDER_MIME:
            action.setText("Open folder")
            action.setEnabled(True)
            hint.setText(f"Open {remote.title}")
            return
        action.setText("Use in Protect")
        if _supported(remote):
            action.setEnabled(True)
            hint.setText(f"Ready to import {_kind_label(remote)} locally into Protect.")
        else:
            action.setEnabled(False)
            hint.setText(
                "Image OCR is not available yet." if _is_image(remote) else "This file type is not supported by Protect yet."
            )

    def import_remote(remote) -> None:
        try:
            local_path = _run_busy(
                dialog,
                "Importing from Google Drive",
                "Preparing a local working copy for PrivacyGate…",
                lambda: _drive_call_with_refresh(
                    service, lambda: materialize_google_drive_item(service, remote)
                ),
            )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to import from Google Drive", _friendly_connection_error("Google Drive", exc))
            return

        protect = main_window.protection_page
        document_button = getattr(protect, "_redesign_document_mode", None)
        if document_button is not None and not document_button.isChecked():
            document_button.click()
        protect.input_tabs.setCurrentIndex(1)
        protect.pdf_path.setText(str(local_path))
        account_id, account_label = _active_account_details(service, "google_drive")
        source_parts = ["Google Drive"]
        if account_label:
            source_parts.append(account_label)
        source_parts.extend(label for _folder_id, label in state["trail"][1:])
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
            "folder_path": "/".join(label for _folder_id, label in state["trail"]),
        }
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(
            f"Imported from Google Drive: {remote.title} — ready for local scan", 9000
        )

    def activate_selected() -> None:
        remote = selected_remote()
        if remote is None:
            return
        if remote.kind == FOLDER_MIME:
            open_folder(remote)
            return
        if not _supported(remote):
            QMessageBox.information(dialog, "This file needs another protection engine", _unsupported_message(remote))
            return
        import_remote(remote)

    def double_clicked(_item, _column) -> None:
        remote = selected_remote()
        if remote is None:
            return
        if remote.kind == FOLDER_MIME:
            open_folder(remote)
        elif _supported(remote):
            import_remote(remote)
        else:
            QMessageBox.information(dialog, "This file needs another protection engine", _unsupported_message(remote))

    table.currentItemChanged.connect(lambda _current, _previous: selection_changed())
    table.itemDoubleClicked.connect(double_clicked)
    action.clicked.connect(activate_selected)
    back.clicked.connect(go_back)
    close.clicked.connect(dialog.reject)
    search.returnPressed.connect(load)
    search_button.clicked.connect(load)
    all_button.clicked.connect(lambda: (search.clear(), load()))

    render_breadcrumbs()
    load()
    dialog.exec()
