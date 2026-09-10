from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.autostart import set_mcp_autostart
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import PreferencesStore
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
from ai_pm_lab_privacy_gate.ui.resources import resource_path


_PAGE_COUNT = 7
_PAGE_PROTECT = 0
_PAGE_LIBRARY = 1
_PAGE_RESTORE = 2
_PAGE_LOCAL_AUTOMATION = 3
_PAGE_CLOUD_AUTOMATION = 4
_PAGE_SETTINGS = 5
_PAGE_CONTACT = 6


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: PrivacyGateService | None = None,
        library: LibraryRepository | None = None,
    ) -> None:
        super().__init__()
        self.service = service or PrivacyGateService()
        self.library = library or LibraryRepository()
        self.preferences = PreferencesStore(self.library.data_dir)
        self.connection_identity = ConnectionIdentityStore(self.library.data_dir)
        self.remote_mcp = RemoteMcpManager(self.connection_identity)
        self.local_api_manager: Any | None = None

        # Only Protect is constructed during the startup-critical path. The other
        # pages are imported and instantiated when first requested.
        self.library_page: Any | None = None
        self.restore_page: Any | None = None
        self.local_automation_page: Any | None = None
        self.cloud_automation_page: Any | None = None
        self.settings_page: Any | None = None
        self.contact_page: Any | None = None
        self._page_instances: dict[int, QWidget] = {}
        self._pending_library_document_id: str | None = None

        self._quit_requested = False
        self._tray_notice_shown = False
        self._pending_update = None
        self._pending_store_event = None
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
        self._setup_system_tray()
        self.statusBar().showMessage(
            f"Version {__version__}  •  Local library: {self.library.data_dir}"
        )

    def _setup_system_tray(self) -> None:
        self.tray_icon: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip("AI PM LAB Privacy Gate")
        menu = QMenu(self)
        show_action = QAction("Open Privacy Gate", menu)
        quit_action = QAction("Quit Privacy Gate and take MCP offline", menu)
        show_action.triggered.connect(self.show_from_background)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self.show_from_background()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        tray.messageClicked.connect(self._show_pending_update)
        tray.show()
        self.tray_icon = tray

    def show_from_background(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _cleanup_optional_pages(self) -> None:
        if self.restore_page is not None:
            self.restore_page.cleanup_previews()

    def _quit_from_tray(self) -> None:
        self._quit_requested = True
        self.protection_page.cleanup_pdf_preview()
        self._cleanup_optional_pages()
        self.remote_mcp.stop()
        QApplication.quit()

    def _build_ui(self, logo_path) -> None:
        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar_expanded = True
        self._sidebar_auto_collapsed = False
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
            self.sidebar_logo.setPixmap(
                pixmap.scaled(
                    92,
                    92,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
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
            ("Protect", "nav-protect.svg", _PAGE_PROTECT),
            ("Library", "nav-library.svg", _PAGE_LIBRARY),
            ("Restore", "nav-restore.svg", _PAGE_RESTORE),
            ("Local Automation / n8n", "nav-automation.svg", _PAGE_LOCAL_AUTOMATION),
            ("Cloud / MCP / Email", "nav-cloud.svg", _PAGE_CLOUD_AUTOMATION),
            ("Settings", "nav-automation.svg", _PAGE_SETTINGS),
            ("Contact / Workflows", "nav-contact.svg", _PAGE_CONTACT),
        ]
        for label, icon_name, page_index in navigation:
            button = QPushButton(label, objectName="NavButton")
            button.setIcon(QIcon(str(resource_path("resources", "branding", icon_name))))
            button.setIconSize(QSize(22, 22))
            button.setCheckable(True)
            button.setToolTip(label)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, page=page_index: self._show_page(page)
            )
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
        self._page_instances[_PAGE_PROTECT] = self.protection_page
        self.pages.addWidget(self.protection_page)

        # Keep stable stack indexes without paying the import/constructor cost of
        # every feature page during startup.
        for index in range(1, _PAGE_COUNT):
            placeholder = QWidget()
            placeholder.setObjectName(f"LazyPagePlaceholder{index}")
            self.pages.addWidget(placeholder)

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
        self.protection_page.open_connections.connect(
            lambda: self._show_page(_PAGE_CLOUD_AUTOMATION)
        )
        self.nav_buttons[_PAGE_PROTECT].setChecked(True)
        self._show_page(_PAGE_PROTECT)

        if self.connection_identity.is_remote_enabled():
            set_mcp_autostart(True)
            self.remote_mcp.start()

        # Preserve the existing background update behavior, but move ContactPage
        # construction outside the startup-critical path.
        QTimer.singleShot(3500, self._run_deferred_update_check)

    def _replace_placeholder(self, index: int, page: QWidget) -> QWidget:
        current = self.pages.widget(index)
        if current is page:
            return page
        self.pages.removeWidget(current)
        current.deleteLater()
        self.pages.insertWidget(index, page)
        self._page_instances[index] = page
        return page

    def _ensure_page(self, index: int) -> QWidget:
        existing = self._page_instances.get(index)
        if existing is not None:
            return existing

        if index == _PAGE_LIBRARY:
            from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage

            page = LibraryPage(self.library)
            page.restore_requested.connect(self._open_restore)
            self.library_page = page
            if self._pending_library_document_id:
                page.select_document(self._pending_library_document_id)

        elif index == _PAGE_RESTORE:
            from ai_pm_lab_privacy_gate.ui.restore_page import RestorePage

            page = RestorePage(self.service, self.library)
            self.restore_page = page
            if self._pending_library_document_id:
                page.refresh(self._pending_library_document_id)

        elif index == _PAGE_LOCAL_AUTOMATION:
            from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage

            page = ConnectionsPage("local", self.library)
            self.local_automation_page = page

        elif index == _PAGE_CLOUD_AUTOMATION:
            from ai_pm_lab_privacy_gate.ui.connections_page import ConnectionsPage

            page = ConnectionsPage(
                "cloud",
                self.library,
                remote_mcp=self.remote_mcp,
            )
            self.cloud_automation_page = page

        elif index == _PAGE_SETTINGS:
            from ai_pm_lab_privacy_gate.ui.settings_page import SettingsPage

            page = SettingsPage(self.library.data_dir)
            self.settings_page = page
            self._configure_settings_page(page)

        elif index == _PAGE_CONTACT:
            from ai_pm_lab_privacy_gate.ui.contact_page import ContactPage

            page = ContactPage()
            page.update_available.connect(self._handle_update_available)
            page.store_update_event.connect(self._handle_store_update_event)
            self.contact_page = page

        else:
            raise IndexError(f"Unknown PrivacyGate page index: {index}")

        return self._replace_placeholder(index, page)

    def set_local_api_manager(self, manager: Any) -> None:
        """Attach the runtime bridge without forcing SettingsPage to exist."""
        self.local_api_manager = manager
        if self.settings_page is not None:
            self._configure_settings_page(self.settings_page)
        self._apply_local_api_preferences()

    def _configure_settings_page(self, settings) -> None:
        manager = self.local_api_manager
        if manager is not None:
            settings.local_api_manager = manager
            if not bool(
                getattr(settings, "_privacygate_main_window_local_api_bound", False)
            ):
                settings.local_api_preferences_changed.connect(
                    self._apply_local_api_preferences
                )
                settings._privacygate_main_window_local_api_bound = True
            settings.refresh_local_api_status()

        # These presentation layers used to run immediately after MainWindow
        # construction. Apply them when Settings is actually created instead.
        from ai_pm_lab_privacy_gate.ui.settings_services_cleanup_2026 import (
            apply_settings_services_cleanup_2026,
        )
        from ai_pm_lab_privacy_gate.ui.settings_browser_protection_polish import (
            apply_browser_protection_product_polish,
        )

        apply_settings_services_cleanup_2026(self)
        apply_browser_protection_product_polish(self)

    def _apply_local_api_preferences(self) -> None:
        manager = self.local_api_manager
        if manager is None:
            return
        manager.apply_preferences(self.preferences.load())
        if self.settings_page is not None:
            self.settings_page.refresh_local_api_status()

    def _run_deferred_update_check(self) -> None:
        contact = self._ensure_page(_PAGE_CONTACT)
        contact.check_updates(silent=True)

    def _handle_update_available(self, result) -> None:
        self._pending_update = result
        self._pending_store_event = None
        if self.isVisible() and not self.isMinimized():
            contact = self._ensure_page(_PAGE_CONTACT)
            contact.show_update_dialog(result)
            return
        if self.tray_icon is not None:
            self.tray_icon.showMessage(
                f"PrivacyGate {result.version} is available",
                "Click to open the PrivacyGate download options. Your local Library remains on this device.",
                QSystemTrayIcon.MessageIcon.Information,
                10000,
            )

    def _handle_store_update_event(self, event) -> None:
        self._pending_store_event = event
        self._pending_update = None
        if self.isVisible() and not self.isMinimized():
            contact = self._ensure_page(_PAGE_CONTACT)
            contact.show_store_update_event(event)
            return
        if self.tray_icon is None:
            return
        status = event.get("status", "")
        release = event.get("release")
        version = getattr(release, "version", "new")
        if status == "installed":
            title = f"PrivacyGate {version} installed"
            message = "Click to restart PrivacyGate and use the new version."
        elif status == "action_required":
            title = f"PrivacyGate {version} is ready"
            message = "Click to install the Microsoft Store update."
        elif status == "preparing":
            title = "Microsoft Store is preparing the update"
            message = (
                "The release is approved but is not available to this device yet. "
                "Click for details."
            )
        else:
            title = "PrivacyGate Store update"
            message = (
                "The Microsoft Store update could not complete right now. "
                "Click for options."
            )
        self.tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            10000,
        )

    def _show_pending_update(self) -> None:
        if self._pending_store_event is not None:
            event = self._pending_store_event
            self.show_from_background()
            contact = self._ensure_page(_PAGE_CONTACT)
            contact.show_store_update_event(event)
            return
        if self._pending_update is None:
            return
        self.show_from_background()
        contact = self._ensure_page(_PAGE_CONTACT)
        contact.show_update_dialog(self._pending_update)

    def _toggle_sidebar(self) -> None:
        self._sidebar_auto_collapsed = False
        self._set_sidebar_expanded(not self.sidebar_expanded)

    def _set_sidebar_expanded(self, expanded: bool) -> None:
        self.sidebar_expanded = expanded
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

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if not hasattr(self, "sidebar") or not hasattr(self, "nav_buttons"):
            return
        if self.width() < 1180 and self.sidebar_expanded:
            self._sidebar_auto_collapsed = True
            self._set_sidebar_expanded(False)
        elif (
            self.width() > 1320
            and self._sidebar_auto_collapsed
            and not self.sidebar_expanded
        ):
            self._set_sidebar_expanded(True)
            self._sidebar_auto_collapsed = False

    def _show_page(self, index: int) -> None:
        if index < 0 or index >= _PAGE_COUNT:
            raise IndexError(f"Unknown PrivacyGate page index: {index}")
        page = self._ensure_page(index)
        self.pages.setCurrentWidget(page)
        self.nav_buttons[index].setChecked(True)
        if index == _PAGE_LIBRARY:
            self.library_page.refresh()
        elif index == _PAGE_RESTORE:
            self.restore_page.refresh()

    def _library_changed(self, document_id: str) -> None:
        self._pending_library_document_id = document_id
        if self.library_page is not None:
            self.library_page.select_document(document_id)
        if self.restore_page is not None:
            self.restore_page.refresh(document_id)
        self.statusBar().showMessage(
            "Protected document saved to the encrypted local library",
            7000,
        )

    def _open_restore(self, document_id: str) -> None:
        restore = self._ensure_page(_PAGE_RESTORE)
        restore.select_document(document_id)
        self._show_page(_PAGE_RESTORE)

    def _send_to_background(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()
        if self.tray_icon is not None and not self._tray_notice_shown:
            self.tray_icon.showMessage(
                "PrivacyGate is running in the background",
                "Your local Library remains saved. Open PrivacyGate from the notification area or choose Quit to stop MCP connections.",
                QSystemTrayIcon.MessageIcon.Information,
                6000,
            )
            self._tray_notice_shown = True

    def _ask_close_behavior(self) -> tuple[str, bool]:
        box = QMessageBox(self)
        box.setWindowTitle("Close PrivacyGate?")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("What should PrivacyGate do when you close this window?")
        box.setInformativeText(
            "Your protected documents, mappings and Library are stored locally and will not be deleted whichever option you choose."
        )
        background = box.addButton(
            "Keep running in background",
            QMessageBox.ButtonRole.AcceptRole,
        )
        quit_button = box.addButton(
            "Quit PrivacyGate",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        remember = QCheckBox("Remember my choice")
        box.setCheckBox(remember)
        box.exec()
        clicked = box.clickedButton()
        if clicked is background:
            return "background", remember.isChecked()
        if clicked is quit_button:
            return "quit", remember.isChecked()
        return "cancel", False

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quit_requested:
            self.protection_page.cleanup_pdf_preview()
            self._cleanup_optional_pages()
            self.remote_mcp.stop()
            super().closeEvent(event)
            return

        prefs = self.preferences.load()
        behavior = prefs.close_behavior
        remember = False
        if behavior == "ask":
            behavior, remember = self._ask_close_behavior()
        if behavior == "cancel":
            event.ignore()
            return
        if remember and behavior in {"background", "quit"}:
            prefs.close_behavior = behavior
            self.preferences.save(prefs)
            if self.settings_page is not None:
                self.settings_page.prefs = prefs
        if behavior == "background":
            if self.tray_icon is None:
                behavior = "quit"
            else:
                self._send_to_background(event)
                return

        if behavior == "quit":
            self._quit_requested = True
            self.protection_page.cleanup_pdf_preview()
            self._cleanup_optional_pages()
            self.remote_mcp.stop()
            super().closeEvent(event)
