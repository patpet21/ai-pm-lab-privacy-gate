from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.apps_hub import APPS
from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _open_source_browser
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
MUTED = "#607789"


# Compact picker catalog is generated from the full Apps directory so the two
# surfaces never drift apart. key, title, description, fallback icon, availability.
_PROVIDER_CATALOG = tuple(
    (key, title, description, icon_key, "live" if supported else "ready")
    for key, title, description, icon_key, _category, supported, _path in APPS
)


def _button_style(primary: bool = False) -> str:
    if primary:
        return (
            "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
            "border-radius:8px;padding:8px 13px;font-weight:800;}"
            "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
            "QPushButton:disabled{background:#D9E2E8;color:#8A99A5;border-color:#D9E2E8;}"
        )
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C4D3DE;"
        "border-radius:8px;padding:8px 13px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;color:#062B4F;border-color:#9BCDD1;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9AA8B3;border-color:#DCE4E9;}"
    )


def _provider_status(service, key: str, availability: str) -> tuple[str, str, str]:
    if availability != "live":
        return "READY", "#FFF6DF", "#8B641C"
    try:
        connected = bool(service and service.is_connected(key))
    except Exception:
        connected = False
    if connected:
        return "CONNECTED", "#E8F6F6", PETROL
    return "AVAILABLE", "#EAF2FA", "#355F87"


def _provider_row(service, key: str, title: str, description: str, icon_key: str, availability: str):
    row = QPushButton()
    row.setObjectName("SourceProviderRow")
    row.setCursor(Qt.CursorShape.PointingHandCursor)
    row.setMinimumHeight(70)
    row.setStyleSheet(
        "QPushButton#SourceProviderRow{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:10px;text-align:left;padding:0;}"
        "QPushButton#SourceProviderRow:hover{background:#F3FAFA;border-color:#9CCFD3;}"
    )

    shell = QHBoxLayout(row)
    shell.setContentsMargins(12, 9, 12, 9)
    shell.setSpacing(11)

    mark = QLabel()
    mark.setFixedSize(38, 38)
    mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mark.setPixmap(icon(icon_key, color=PETROL, size=24).pixmap(24, 24))
    mark.setStyleSheet("background:#EAF6F6;border:1px solid #CFE7E8;border-radius:9px;")
    shell.addWidget(mark)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    name = QLabel(title)
    name.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:850;")
    sub = QLabel(description)
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color:{MUTED};font-size:9px;")
    copy.addWidget(name)
    copy.addWidget(sub)
    shell.addLayout(copy, 1)

    status_text, status_bg, status_fg = _provider_status(service, key, availability)
    status = QLabel(status_text)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setStyleSheet(
        f"background:{status_bg};color:{status_fg};border:1px solid {status_bg};"
        "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
    )
    shell.addWidget(status)

    for child in (mark, name, sub, status):
        child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    row._source_provider_key = key
    row._source_provider_title = title
    row._source_provider_availability = availability
    return row


def _apps_page(main_window) -> int:
    return int(getattr(main_window, "apps_page_index", 4))


def _open_picker(main_window) -> None:
    cloud_page = getattr(main_window, "cloud_automation_page", None)
    service = getattr(cloud_page, "_connected_apps_service", None) if cloud_page else None

    dialog = QDialog(main_window)
    dialog.setWindowTitle("Connected sources")
    dialog.resize(760, 650)
    dialog.setMinimumSize(660, 520)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(11)

    head = QHBoxLayout()
    titles = QVBoxLayout()
    title = QLabel("Connected sources")
    title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:900;")
    subtitle = QLabel(
        "Choose a connected source, or open Apps to activate another provider. PrivacyGate brings selected data into the local protection flow first."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:11px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    head.addLayout(titles, 1)
    shield = QLabel("LOCAL FIRST")
    shield.setStyleSheet(
        "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
        "border-radius:9px;padding:6px 9px;font-size:9px;font-weight:900;"
    )
    head.addWidget(shield, alignment=Qt.AlignmentFlag.AlignTop)
    root.addLayout(head)

    search = QLineEdit()
    search.setPlaceholderText("Search all sources")
    search.setClearButtonEnabled(True)
    search.setMinimumHeight(38)
    search.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#10263A;border:1px solid #C8D6E0;"
        "border-radius:9px;padding:7px 11px;font-size:11px;}"
        "QLineEdit:focus{border-color:#1595A3;}"
    )
    root.addWidget(search)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    body = QWidget()
    grid = QGridLayout(body)
    grid.setContentsMargins(0, 2, 0, 2)
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(9)
    rows = []

    for index, provider in enumerate(_PROVIDER_CATALOG):
        row = _provider_row(service, *provider)
        rows.append(row)
        grid.addWidget(row, index // 2, index % 2)

        key, provider_title, _description, _icon_key, availability = provider

        def choose(_checked=False, p=key, t=provider_title, available=availability):
            if available != "live":
                dialog.accept()
                main_window._show_page(_apps_page(main_window))
                return
            try:
                connected = bool(service and service.is_connected(p))
            except Exception:
                connected = False
            if not connected:
                answer = QMessageBox.question(
                    dialog,
                    f"Connect {t}",
                    f"{t} is available but not connected yet. Open Apps to connect it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    dialog.accept()
                    main_window._show_page(_apps_page(main_window))
                return
            dialog.accept()
            _open_source_browser(main_window, p, t)

        row.clicked.connect(choose)

    scroll.setWidget(body)
    root.addWidget(scroll, 1)

    def filter_rows(text: str) -> None:
        needle = text.strip().lower()
        for row in rows:
            title_text = getattr(row, "_source_provider_title", "").lower()
            key_text = getattr(row, "_source_provider_key", "").lower()
            row.setVisible(not needle or needle in title_text or needle in key_text)

    search.textChanged.connect(filter_rows)

    footer = QHBoxLayout()
    note = QLabel("Apps is the central place to connect and review provider integrations.")
    note.setStyleSheet(f"color:{MUTED};font-size:10px;")
    manage = QPushButton("Open Apps")
    manage.setIcon(icon("settings", color=NAVY_SOFT, size=17))
    manage.setIconSize(QSize(17, 17))
    manage.setStyleSheet(_button_style(False))
    close = QPushButton("Close")
    close.setStyleSheet(_button_style(False))
    footer.addWidget(note, 1)
    footer.addWidget(manage)
    footer.addWidget(close)
    root.addLayout(footer)

    manage.clicked.connect(lambda: (dialog.accept(), main_window._show_page(_apps_page(main_window))))
    close.clicked.connect(dialog.reject)
    dialog.exec()


def apply_protect_source_picker(main_window) -> None:
    """Add a compact source/action bar above Protect without replacing existing controls."""
    page = getattr(main_window, "protection_page", None)
    if page is None or hasattr(page, "_protect_source_quick_bar"):
        return

    preview_layout = page.preview_card.layout()
    mode_bar = getattr(page, "_polish_protect_mode_bar", None)
    insert_at = preview_layout.indexOf(mode_bar) if mode_bar is not None else preview_layout.indexOf(page.preview_tabs)
    if insert_at < 0:
        insert_at = 0

    bar = QFrame(objectName="ProtectSourceQuickBar")
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(7)
    bar.setStyleSheet("QFrame#ProtectSourceQuickBar{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:10px;}")

    upload = QPushButton("Upload")
    sources = QPushButton("Connected sources")
    paste = QPushButton("Paste text")
    scan = QPushButton("Scan")
    protect = QPushButton("Protect")

    upload.setIcon(icon("upload", color=NAVY_SOFT, size=18))
    sources.setIcon(icon("cloud", color=NAVY_SOFT, size=18))
    paste.setIcon(icon("paste", color=NAVY_SOFT, size=18))
    scan.setIcon(icon("scan", color="#FFFFFF", size=18))
    protect.setIcon(icon("protect", color="#FFFFFF", size=18))
    for button in (upload, sources, paste, scan, protect):
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(38)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

    for button in (upload, sources, paste):
        button.setStyleSheet(_button_style(False))
    for button in (scan, protect):
        button.setStyleSheet(_button_style(True))

    layout.addWidget(upload)
    layout.addWidget(sources)
    layout.addWidget(paste)
    layout.addStretch(1)
    layout.addWidget(scan)
    layout.addWidget(protect)
    preview_layout.insertWidget(insert_at, bar)

    def upload_local() -> None:
        document_mode = getattr(page, "_redesign_document_mode", None)
        if document_mode is not None and not document_mode.isChecked():
            document_mode.click()
        page.browse_button.click()

    def paste_text() -> None:
        paste_mode = getattr(page, "_redesign_paste_mode", None)
        if paste_mode is not None and not paste_mode.isChecked():
            paste_mode.click()
        else:
            page.text_input.setFocus()

    upload.clicked.connect(upload_local)
    sources.clicked.connect(lambda: _open_picker(main_window))
    paste.clicked.connect(paste_text)
    scan.clicked.connect(page.scan_button.click)

    original_protect = getattr(page, "_redesign_protect_button", None)
    if original_protect is not None:
        protect.clicked.connect(original_protect.click)
    else:
        protect.setEnabled(False)

    timer = QTimer(bar)
    timer.setInterval(250)

    def sync_state() -> None:
        scan.setEnabled(page.scan_button.isEnabled())
        if original_protect is not None:
            protect.setEnabled(original_protect.isEnabled())
        connected_count = 0
        if service := getattr(getattr(main_window, "cloud_automation_page", None), "_connected_apps_service", None):
            for provider in ("google_drive", "gmail", "clickup", "asana", "trello"):
                try:
                    connected_count += int(service.is_connected(provider))
                except Exception:
                    pass
        sources.setText(f"Connected sources  {connected_count}" if connected_count else "Connected sources")

    timer.timeout.connect(sync_state)
    timer.start()
    sync_state()

    page._protect_source_quick_bar = bar
    page._protect_source_upload = upload
    page._protect_source_connected = sources
    page._protect_source_paste = paste
    page._protect_source_scan = scan
    page._protect_source_protect = protect
    page._protect_source_timer = timer
