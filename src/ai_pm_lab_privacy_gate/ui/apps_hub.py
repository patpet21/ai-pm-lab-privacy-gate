from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
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
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader


NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
MUTED = "#61798A"
GOLD = "#D3A13B"


# key, title, description, fallback icon, category, live connector, preferred integration path
APPS = (
    # Google / Microsoft productivity
    ("google_drive", "Google Drive", "Files, Docs, Sheets and folders.", "cloud", "Productivity", True, "OAuth / API"),
    ("gmail", "Gmail", "Selected email messages and attachments.", "contact", "Communication", True, "OAuth / API"),
    ("google_calendar", "Google Calendar", "Meetings, inspections and project calendars.", "history", "Productivity", False, "OAuth / API"),
    ("google_contacts", "Google Contacts", "Clients, owners, tenants and vendors.", "contact", "CRM & Contacts", False, "OAuth / API"),
    ("onedrive", "OneDrive", "Microsoft files and folders.", "cloud", "Productivity", False, "MCP / OAuth review"),
    ("sharepoint", "SharePoint", "Team sites and document libraries.", "cloud", "Productivity", False, "MCP / OAuth review"),
    ("outlook", "Outlook", "Email, attachments and business correspondence.", "contact", "Communication", False, "MCP / OAuth review"),
    ("teams", "Microsoft Teams", "Channels, messages, meetings and files.", "contact", "Communication", False, "MCP / OAuth review"),

    # Documents / knowledge / storage
    ("notion", "Notion", "Pages, databases and workspace documents.", "document", "Productivity", False, "MCP / OAuth review"),
    ("dropbox", "Dropbox", "Files and folders from approved locations.", "cloud", "Productivity", False, "OAuth / API"),
    ("box", "Box", "Enterprise files, folders and document workflows.", "cloud", "Productivity", False, "OAuth / API"),
    ("airtable", "Airtable", "Property, asset, vendor and project databases.", "template", "Productivity", False, "MCP / OAuth review"),
    ("docusign", "DocuSign", "Leases, agreements, envelopes and signed documents.", "document", "Documents & Agreements", False, "OAuth / API"),
    ("adobe_sign", "Adobe Acrobat Sign", "Signed agreements and approval documents.", "document", "Documents & Agreements", False, "OAuth / API"),

    # Project / work management
    ("clickup", "ClickUp", "Workspaces, projects, tasks and project documents.", "workflow", "Project Management", True, "OAuth / API"),
    ("asana", "Asana", "Projects, tasks and workspaces.", "workflow", "Project Management", True, "OAuth / API"),
    ("trello", "Trello", "Boards, lists and cards.", "workflow", "Project Management", True, "OAuth / API"),
    ("monday", "monday.com", "Boards, projects, CRM and operations workflows.", "workflow", "Project Management", False, "MCP / OAuth review"),
    ("smartsheet", "Smartsheet", "Project plans, trackers, schedules and reports.", "workflow", "Project Management", False, "OAuth / API"),
    ("jira", "Jira", "Issues, projects, development and operations work.", "workflow", "Project Management", False, "MCP / OAuth review"),

    # Communication
    ("slack", "Slack", "Channels, messages and files.", "contact", "Communication", False, "MCP / OAuth review"),
    ("zoom", "Zoom", "Meetings, transcripts and recordings metadata.", "contact", "Communication", False, "OAuth / API"),
    ("calendly", "Calendly", "Appointments, tours and client scheduling.", "history", "Communication", False, "OAuth / API"),

    # CRM / sales / brokerage
    ("hubspot", "HubSpot", "Contacts, companies, deals and CRM notes.", "contact", "CRM & Brokerage", False, "MCP / OAuth review"),
    ("pipedrive", "Pipedrive", "Deals, contacts and brokerage pipelines.", "contact", "CRM & Brokerage", False, "OAuth / API"),
    ("zoho_crm", "Zoho CRM", "Leads, contacts, deals and customer records.", "contact", "CRM & Brokerage", False, "OAuth / API"),
    ("salesforce", "Salesforce", "Accounts, contacts, opportunities and CRM records.", "contact", "CRM & Brokerage", False, "MCP / OAuth review"),
    ("follow_up_boss", "Follow Up Boss", "Real-estate leads, contacts and follow-up activity.", "contact", "CRM & Brokerage", False, "API / partner review"),
    ("kvcore", "kvCORE", "Real-estate CRM, leads and brokerage workflows.", "contact", "CRM & Brokerage", False, "API / partner review"),
    ("boomtown", "BoomTown", "Real-estate leads, CRM and agent workflows.", "contact", "CRM & Brokerage", False, "API / partner review"),
    ("brokermint", "Brokermint", "Transactions, commissions and brokerage back office.", "report", "CRM & Brokerage", False, "API / partner review"),
    ("dotloop", "dotloop", "Transactions, forms, signatures and compliance documents.", "document", "CRM & Brokerage", False, "API / partner review"),

    # Accounting / finance
    ("quickbooks", "QuickBooks Online", "Invoices, vendors, expenses and accounting records.", "report", "Finance", False, "OAuth / API"),
    ("xero", "Xero", "Invoices, contacts, bills and accounting data.", "report", "Finance", False, "OAuth / API"),

    # Construction / capital projects
    ("procore", "Procore", "Projects, RFIs, submittals, drawings and documents.", "workflow", "Construction", False, "OAuth / API"),
    ("autodesk_construction", "Autodesk Construction Cloud", "Project files, issues, RFIs, drawings and BIM data.", "workflow", "Construction", False, "OAuth / API"),
    ("buildertrend", "Buildertrend", "Construction projects, schedules, clients and documents.", "workflow", "Construction", False, "API / partner review"),

    # Property management / real estate operations
    ("appfolio", "AppFolio", "Property management, residents, accounting and operations.", "library", "Property Management", False, "API / partner review"),
    ("buildium", "Buildium", "Properties, residents, leases, maintenance and accounting.", "library", "Property Management", False, "API / partner review"),
    ("yardi", "Yardi", "Property, lease, resident and financial operations.", "library", "Property Management", False, "API / partner review"),
    ("realpage", "RealPage", "Property operations, leasing and resident data.", "library", "Property Management", False, "API / partner review"),
    ("entrata", "Entrata", "Property operations, leasing and resident workflows.", "library", "Property Management", False, "API / partner review"),
    ("doorloop", "DoorLoop", "Properties, leases, tenants and maintenance.", "library", "Property Management", False, "API / partner review"),
    ("rent_manager", "Rent Manager", "Property management, accounting and resident records.", "library", "Property Management", False, "API / partner review"),
    ("propertyware", "Propertyware", "Single-family property management operations.", "library", "Property Management", False, "API / partner review"),
    ("mri", "MRI Software", "Property, lease and real-estate management data.", "library", "Property Management", False, "API / partner review"),
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
    def __init__(self, main_window, service) -> None:
        super().__init__()
        self.main_window = main_window
        self.service = service
        self.logo_loader = ProviderLogoLoader(service.data_dir, self)
        self._cards: list[tuple[QFrame, str, str, str]] = []
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
            "Connect business tools to PrivacyGate. Live connectors work today; the broader catalog is ready for OAuth, API or MCP integration as each provider is enabled."
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
        search.setPlaceholderText("Search apps, categories or providers")
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
            self._cards.append((card, app[1].lower(), app[4].lower(), app[6].lower()))

        for column in range(3):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch((len(APPS) + 2) // 3, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        search.textChanged.connect(self._filter_cards)

    def _build_card(
        self,
        key: str,
        title: str,
        description: str,
        icon_key: str,
        category: str,
        supported: bool,
        integration_path: str,
    ) -> QFrame:
        card = QFrame(objectName="AppsHubCard")
        card.setMinimumHeight(190)
        card.setStyleSheet("QFrame#AppsHubCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:12px;}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(7)

        top = QHBoxLayout()
        tile = QLabel()
        tile.setFixedSize(44, 44)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(icon(icon_key, color=PETROL, size=25).pixmap(25, 25))
        tile.setStyleSheet("background:#FFFFFF;border:1px solid #DCE6EC;border-radius:10px;")
        top.addWidget(tile)
        top.addStretch(1)
        status = QLabel()
        status.setObjectName("AppStatus")
        status.setProperty("provider", key)
        status.setProperty("supported", supported)
        top.addWidget(status)
        layout.addLayout(top)

        # Replace the fallback glyph asynchronously with the provider's public
        # site/brand icon; cache keeps subsequent launches instant.
        self.logo_loader.load(
            key,
            lambda pixmap, target=tile: target.setPixmap(
                pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            ),
        )

        name = QLabel(title)
        name.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
        layout.addWidget(name)

        meta = QHBoxLayout()
        cat = QLabel(category.upper())
        cat.setStyleSheet(f"color:{GOLD};font-size:9px;font-weight:900;letter-spacing:0.35px;")
        method = QLabel(integration_path.upper())
        method.setStyleSheet(
            "background:#F1F6F8;color:#526C7D;border:1px solid #DCE5EA;"
            "border-radius:7px;padding:3px 6px;font-size:8px;font-weight:800;"
        )
        meta.addWidget(cat)
        meta.addStretch(1)
        meta.addWidget(method)
        layout.addLayout(meta)

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
        connect.setProperty("title", title)
        connect.setProperty("integration_path", integration_path)
        connect.setStyleSheet(_primary_style() if supported else _secondary_style())
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

        connect.clicked.connect(
            lambda _checked=False, p=key, t=title, s=supported, path=integration_path: self._connect(p, t, s, path)
        )
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
                status.setText("READY")
                status.setStyleSheet(
                    "background:#FFF6DF;color:#8B641C;border:1px solid #E8CE8A;"
                    "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
                )
                continue
            connected = self._connected(provider)
            status.setText("CONNECTED" if connected else "AVAILABLE")
            status.setStyleSheet(
                ("background:#E8F6F6;color:#0B7180;border:1px solid #B8E1E4;" if connected else
                 "background:#EAF2FA;color:#355F87;border:1px solid #C9DAEA;")
                + "border-radius:8px;padding:4px 7px;font-size:9px;font-weight:900;"
            )
        for button in self.findChildren(QPushButton, "AppConnect"):
            provider = button.property("provider")
            supported = bool(button.property("supported"))
            if not supported:
                button.setText("Integration details")
                button.setEnabled(True)
            else:
                button.setEnabled(True)
                button.setText("Reconnect" if self._connected(provider) else "Connect")
        for button in self.findChildren(QPushButton, "AppBrowse"):
            provider = button.property("provider")
            supported = bool(button.property("supported"))
            button.setEnabled(supported and self._connected(provider))

    def _connect(self, provider: str, title: str, supported: bool, integration_path: str) -> None:
        if not supported:
            QMessageBox.information(
                self,
                f"{title} integration",
                f"{title} is already in the PrivacyGate integration catalog.\n\n"
                f"Preferred path: {integration_path}.\n\n"
                "Before enabling it we will check whether the provider offers a stable official MCP connection; "
                "otherwise PrivacyGate will use OAuth/API. Customer passwords and manual personal tokens are not part of the target flow.",
            )
            return
        connector = {
            "google_drive": "connect_google_oauth",
            "gmail": "connect_gmail_oauth",
            "clickup": "connect_clickup_oauth",
            "asana": "connect_asana_oauth",
            "trello": "connect_trello_oauth",
        }.get(provider)
        if not connector or not hasattr(self.service, connector):
            QMessageBox.warning(self, f"{title} connection", "This connector is not available in the current build.")
            return
        try:
            getattr(self.service, connector)()
            result = self.service.test_connection(provider)
            if result.ok:
                QMessageBox.information(
                    self,
                    f"{title} connected",
                    f"{result.account_label}\n\n{title} is connected to PrivacyGate in read-only mode where supported.",
                )
            else:
                QMessageBox.warning(self, f"{title} connection", result.detail)
        except Exception as exc:
            message = str(exc)
            if "not configured" in message.lower():
                message += (
                    "\n\nPrivacyGate is ready for this provider, but its developer OAuth app still needs to be registered once. "
                    "No customer will need to paste a personal token."
                )
            QMessageBox.warning(self, f"{title} connection failed", message)
        self.refresh()

    def _browse(self, provider: str, title: str, supported: bool) -> None:
        if not supported or not self._connected(provider):
            return
        _open_source_browser(self.main_window, provider, title)

    def _filter_cards(self, text: str) -> None:
        needle = text.strip().lower()
        for card, title, category, method in self._cards:
            card.setVisible(not needle or needle in title or needle in category or needle in method)
