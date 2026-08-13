from __future__ import annotations

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage
from ai_pm_lab_privacy_gate.ui.contact_page import ContactPage
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.resources import resource_path
from ai_pm_lab_privacy_gate.ui.restore_page import RestorePage


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: PrivacyGateService | None = None,
        library: LibraryRepository | None = None,
    ) -> None:
        super().__init__()
        self.service = service or PrivacyGateService()
        self.library = library or LibraryRepository()
        self.connection_identity = ConnectionIdentityStore(self.library.data_dir)
        self.remote_mcp = RemoteMcpManager(self.connection_identity)
        self.setWindowTitle(f"AI PM LAB Privacy Gate — {__version__}")
        self.resize(1460, 920)
        self.setMinimumSize(1120, 720)
        icon_path = resource_path("resources", "branding", "privacy-gate.ico")
        display_logo_path = resource_path("resources", "branding", "privacy-gate-icon.png")
        logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        elif logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self._build_ui(display_logo_path if display_logo_path.exists() else logo_path)
        self.statusBar().showMessage(
            f"Version {__version__}  •  Local library: {self.library.data_dir}"
        )

    def _build_ui(self, logo_path) -> None:
        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar_expanded = True
        self.sidebar = QFrame(objectName="Sidebar")
        self.sidebar.setFixedWidth(258)
        self.side_layout = QVBoxLayout(self.sidebar)
        self.side_layout.setContentsMargins(18, 16, 18, 18)
        self.side_layout.setSpacing(8)

        self.sidebar_toggle = QPushButton("‹", objectName="SidebarToggle")
        self.sidebar_toggle.setToolTip("Collapse navigation")
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        self.side_layout.addWidget(self.sidebar_toggle, alignment=Qt.AlignmentFlag.AlignRight)

        brand = QFrame(objectName="BrandPanel")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_logo = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            self.sidebar_logo.setPixmap(pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.sidebar_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(self.sidebar_logo)
        self.brand_name = QLabel("AI PM LAB", objectName="SidebarBrand")
        self.brand_product = QLabel("PRIVACY GATE", objectName="SidebarProduct")
        brand_layout.addWidget(self.brand_name, alignment=Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(self.brand_product, alignment=Qt.AlignmentFlag.AlignCenter)
        self.side_layout.addWidget(brand)
        self.side_layout.addSpacing(14)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        self.nav_labels: list[str] = []
        navigation = [
            ("Protect", "nav-protect.svg", 0),
            ("Library", "nav-library.svg", 1),
            ("Restore", "nav-restore.svg", 2),
            ("Local Automation / n8n", "nav-automation.svg", 3),
            ("Cloud / MCP / Email", "nav-cloud.svg", 4),
            ("Contact / Workflows", "nav-contact.svg", 5),
        ]
        for label, icon_name, page_index in navigation:
            button = QPushButton(label, objectName="NavButton")
            button.setIcon(QIcon(str(resource_path("resources", "branding", icon_name))))
            button.setIconSize(QSize(22, 22))
            button.setCheckable(True)
            button.setToolTip(label)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, page=page_index: self._show_page(page))
            self.nav_group.addButton(button)
            self.nav_buttons.append(button)
            self.nav_labels.append(label)
            self.side_layout.addWidget(button)
        self.side_layout.addStretch(1)
        self.privacy_note = QLabel("LOCAL-FIRST\nNo mandatory cloud", objectName="SidebarNote")
        self.privacy_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_layout.addWidget(self.privacy_note)

        content = QFrame(objectName="Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.protection_page = ProtectionPage(self.service, self.library)
        self.library_page = LibraryPage(self.library)
        self.restore_page = RestorePage(self.service, self.library)
        self.local_automation_page = ConnectionsPage("local", self.library)
        self.cloud_automation_page = ConnectionsPage(
            "cloud", self.library, remote_mcp=self.remote_mcp
        )
        self.contact_page = ContactPage()
        for page in (
            self.protection_page,
            self.library_page,
            self.restore_page,
            self.local_automation_page,
            self.cloud_automation_page,
            self.contact_page,
        ):
            self.pages.addWidget(page)
        content_layout.addWidget(self.pages)
        product_footer = QLabel(
            'Created by Pietro Forestieri  •  Presented by Trigosat Consulting &amp; PropertyDex  •  '
            '<a href="https://aipmlab.propertydex.xyz">AI PM LAB</a>  •  '
            '<a href="https://framework.propertydex.xyz/?open=signup">PropertyDex Framework</a>',
            objectName="ProductFooter",
        )
        product_footer.setOpenExternalLinks(True)
        product_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(product_footer)

        shell.addWidget(self.sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)

        self.protection_page.library_changed.connect(self._library_changed)
        self.protection_page.open_connections.connect(lambda: self._show_page(4))
        self.library_page.restore_requested.connect(self._open_restore)
        self.nav_buttons[0].setChecked(True)
        self._show_page(0)
        if self.connection_identity.is_remote_enabled():
            self.remote_mcp.start()
        QTimer.singleShot(3500, lambda: self.contact_page.check_updates(silent=True))

    def _toggle_sidebar(self) -> None:
        self.sidebar_expanded = not self.sidebar_expanded
        if self.sidebar_expanded:
            self.sidebar.setFixedWidth(258)
            self.side_layout.setContentsMargins(18, 16, 18, 18)
            self.sidebar_toggle.setText("‹")
            self.sidebar_toggle.setToolTip("Collapse navigation")
            self.brand_name.show()
            self.brand_product.show()
            self.privacy_note.show()
            logo_size = 92
        else:
            self.sidebar.setFixedWidth(76)
            self.side_layout.setContentsMargins(10, 16, 10, 18)
            self.sidebar_toggle.setText("›")
            self.sidebar_toggle.setToolTip("Expand navigation")
            self.brand_name.hide()
            self.brand_product.hide()
            self.privacy_note.hide()
            logo_size = 44
        logo_path = resource_path("resources", "branding", "privacy-gate-icon.png")
        if not logo_path.exists():
            logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            self.sidebar_logo.setPixmap(
                pixmap.scaled(
                    logo_size,
                    logo_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        for button, full_label in zip(self.nav_buttons, self.nav_labels):
            button.setText(full_label if self.sidebar_expanded else "")

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        if index == 1:
            self.library_page.refresh()
        elif index == 2:
            self.restore_page.refresh()

    def _library_changed(self, document_id: str) -> None:
        self.library_page.select_document(document_id)
        self.restore_page.refresh(document_id)
        self.statusBar().showMessage("Protected document saved to the encrypted local library", 7000)

    def _open_restore(self, document_id: str) -> None:
        self.restore_page.select_document(document_id)
        self._show_page(2)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.protection_page.cleanup_pdf_preview()
        self.remote_mcp.stop()
        super().closeEvent(event)
