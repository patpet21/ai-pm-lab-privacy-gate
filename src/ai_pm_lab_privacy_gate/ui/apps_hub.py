from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
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

from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _open_source_browser
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
TEAL = "#1595A3"
MUTED = "#61798A"
BORDER = "#D7E2EA"
GOLD = "#D3A13B"
WHITE = "#FFFFFF"


APPS = (
    ("google_drive", "Google Drive", "Search and import files, Docs, Sheets and folders.", "cloud", "Productivity", True),
    ("gmail", "Gmail", "Bring selected email threads and attachments into Protect.", "contact", "Communication", False),
    ("clickup", "ClickUp", "Workspaces, projects, tasks and project documents.", "workflow", "Business & Operations", True),
    ("asana", "Asana", "Projects, tasks and workspaces.", "workflow", "Business & Operations", True),
    ("trello", "Trello", "Boards, lists and cards.", "workflow", "Business & Operations", True),
    ("onedrive", "OneDrive / SharePoint", "Microsoft files and team document libraries.", "cloud", "Productivity", False),
    ("notion", "Notion", "Pages, databases and workspace documents.", "document", "Productivity", False),
    ("dropbox", "Dropbox", "Files and folders from approved locations.", "cloud", "Productivity", False),
    ("slack", "Slack", "Selected channels, messages and files.", "contact", "Communication", False),
)


def _secondary_style() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C5D4DE;"
        "border-radius:8px;padding:7px 12px;font-weight:750;}"
        "QPushButton:hover{background:#EDF7F7;border-color:#9BCDD1;color:#062B4F;}"
        "QPushButton:disabled{background:#F3F6F8;color:#9BA8B2;border-color:#DDE5EA;}"
    )


def _primary_style() -> str:
    return (
        "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
        "border-radius:8px;padding:7px 12px;font-weight:800;}"
        "QPushButton:hover{background:#095F6B;border-color:#095F6B;}"
    )


class AppsHubPage(QWidget):
    """Visual app directory backed by the existing ConnectedAppsService."""

    def __init__(self, main_window, service) -> None:
        super().__init__()
        self.main_window = main_window
        self.service = service
        self._cards: list[tuple[QFrame, str, str]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Apps")
        title.setStyleSheet(f"color:{NAVY};font-size:27px;font-weight:900;")
        subtitle = QLabel(
            "Connect the tools your team already uses. PrivacyGate brings selected content into the local protection flow before AI access."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:11px;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        local = QLabel("LOCAL-FIRST")
        local.setStyleSheet(
            "background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;"
            "border-radius:10px;padding:7px 10px;font-size:9px;font-weight:900;"
        )
        header.addWidget(local, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        search_row = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Search apps")
        search.setClearButtonEnabled(True)
        search.setMinimumHeight(40)
        search.setStyleSheet(
            "QLineEdit{background:#FFFFFF;color:#10263A;border:1px solid #C8D6E0;"
            "border-radius:10px;padding:8px 12px;font-size:11px;}"
            "QLineEdit:focus{border-color:#1595A3;}"
        )
        search_row.addWidget(search, 1)
        manage_mcp = QPushButton("MCP & AI connections")
        manage_mcp.setIcon(icon("workflow", color=NAVY_SOFT, size=18))
        manage_mcp.setIconSize(QSize(18, 18))
        manage_mcp.setStyleSheet(_secondary_style())
        manage_mcp.clicked.connect(lambda: self.main_window._show_page(4))
        search_row.addWidget(manage_mcp)
        root.addLayout(search_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        for index, app in enumerate(APPS):
            card = self._build_card(*app)
            grid.addWidget(card, index // 3, index % 3)
            self._cards.append((card, app[1].lower(), app[4].lower()))

        for column in range(3):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch((len(APPS) + 2) // 3, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        search.textChanged.connect(self._filter_cards)

    def _build_card(self, key: str, title: str, description: str, icon_key: str, category: str, supported: bool) -> QFrame:
        card = QFrame(objectName="AppsHubCard")
        card.setMinimumHeight(178)
        card.setStyleSheet(
            "QFrame#AppsHubCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:12px;}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        tile = QLabel()
        tile.setFixedSize(42, 42)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(icon(icon_key, color=PETROL, size=25).pixmap(25, 25))
        tile.setStyleSheet("background:#EAF6F6;border:1px solid #CEE7E9;border-radius:10px;")
        top.addWidget(tile)
        top.addStretch(1)
        status = QLabel()
        status.setObjectName("AppStatus")
        status.setProperty("provider", key)
        status.setProperty("supported", supported)
        top.addWidget(status)
        layout.addLayout(top)

        name = QLabel(title)
        name.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
        layout.addWidget(name)
        cat = QLabel(category.upper())
        cat.setStyleSheet(f"color:{GOLD};font-size:9px;font-weight:900;letter-spacing:0.4px;")
        layout.addWidget(cat)
        info = QLabel(description)
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{MUTED};font-size:10px;")
        layout.addWidget(info)
        layout.addStretch(1)

        actions = QHBoxLayout()
        connect = QPushButton()
        connect.setObjectName("AppConnect")
        connect.setProperty("provider", key)
        connect.setProperty("supported", supported)
        connect.setStyleSheet(_primary_style())
        connect.setMinimumHeight(34)
        actions.addWidget(connect)

        browse = QPushButton("Browse")
        browse.setObjectName("AppBrowse")
        browse.setProperty("provider", key)
        browse.setProperty("title", title)
        browse.setProperty("supported", supported)
        browse.setStyleSheet(_secondary_style())
        browse.setMinimumHeight(34)
        actions.addWidget(browse)
        actions.addStretch(1)
        layout.addLayout(actions)

        connect.clicked.connect(lambda _checked=False, p=key, t=title, s=supported: self._connect(p, t, s))
        browse.clicked.connect(lambda _checked=False, p=key, t=title, s=supported: self._browse(p, t, s))
        return card

    def _connected(self, provider: str) -> bool:
        try:
            return bool(self.service and self.service.is_connected(provider))
        except Exception:
            return False

    def refresh(self) -> None:
        for status in self.findChildren(QLabel, "AppStatus"):
            provider = status.property("provider")
            supported = bool(status.property("supported"))
            if not supported:
                status.setText("COMING NEXT")
                status.setStyleSheet(
                    "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
                    "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )
                continue
            connected = self._connected(provider)
            status.setText("CONNECTED" if connected else "NOT CONNECTED")
            status.setStyleSheet(
                ("background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;" if connected else
                 "background:#F2F5F7;color:#6C7E8C;border:1px solid #D7E2EA;")
                + "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
            )
        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = button.property("provider")
            supported = bool(button.property("supported"))
            if not supported:
                button.setText("Coming next")
                button.setEnabled(False)
            else:
                button.setEnabled(True)
                button.setText("Reconnect" if self._connected(provider) else "Connect")
        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = button.property("provider")
            supported = bool(button.property("supported"))
            button.setEnabled(supported and self._connected(provider))

    def _connect(self, provider: str, title: str, supported: bool) -> None:
        if not supported:
            return
        if provider == "google_drive":
            try:
                self.service.connect_google_oauth()
                result = self.service.test_connection(provider)
                if result.ok:
                    QMessageBox.information(self, "Google Drive connected", f"{result.account_label}\n\nGoogle Drive is ready to use in PrivacyGate.")
                else:
                    QMessageBox.warning(self, "Google Drive connection", result.detail)
            except Exception as exc:
                QMessageBox.warning(self, "Google Drive connection failed", str(exc))
            self.refresh()
            return
        QMessageBox.information(
            self,
            f"{title} OAuth",
            f"{title} is visible in the Apps hub. Its browser-based OAuth connection is the next provider-specific step; manual token entry will not be used in the final customer flow.",
        )

    def _browse(self, provider: str, title: str, supported: bool) -> None:
        if not supported or not self._connected(provider):
            return
        _open_source_browser(self.main_window, provider, title)

    def _filter_cards(self, text: str) -> None:
        needle = text.strip().lower()
        for card, title, category in self._cards:
            card.setVisible(not needle or needle in title or needle in category)
