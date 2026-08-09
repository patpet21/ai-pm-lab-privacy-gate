from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
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
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage
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
        self.setWindowTitle("AI PM LAB Privacy Gate")
        self.resize(1460, 920)
        self.setMinimumSize(1120, 720)
        logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self._build_ui(logo_path)
        self.statusBar().showMessage(f"Local library: {self.library.data_dir}")

    def _build_ui(self, logo_path) -> None:
        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame(objectName="Sidebar")
        sidebar.setFixedWidth(238)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 20, 18, 18)
        side.setSpacing(8)

        brand = QFrame(objectName="BrandPanel")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            logo.setPixmap(pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(logo)
        brand_layout.addWidget(QLabel("AI PM LAB", objectName="SidebarBrand"), alignment=Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(QLabel("PRIVACY GATE", objectName="SidebarProduct"), alignment=Qt.AlignmentFlag.AlignCenter)
        side.addWidget(brand)
        side.addSpacing(14)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, label in enumerate(
            ["Protect", "Library", "Restore", "Connections"]
        ):
            button = QPushButton(label, objectName="NavButton")
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, page=index: self._show_page(page))
            self.nav_group.addButton(button)
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch(1)
        privacy = QLabel("LOCAL-FIRST\nNo mandatory cloud", objectName="SidebarNote")
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(privacy)

        content = QFrame(objectName="Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.protection_page = ProtectionPage(self.service, self.library)
        self.library_page = LibraryPage(self.library)
        self.restore_page = RestorePage(self.service, self.library)
        self.connections_page = ConnectionsPage()
        for page in (self.protection_page, self.library_page, self.restore_page, self.connections_page):
            self.pages.addWidget(page)
        content_layout.addWidget(self.pages)

        shell.addWidget(sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)

        self.protection_page.library_changed.connect(self._library_changed)
        self.protection_page.open_connections.connect(lambda: self._show_page(3))
        self.library_page.restore_requested.connect(self._open_restore)
        self.nav_buttons[0].setChecked(True)
        self._show_page(0)

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
