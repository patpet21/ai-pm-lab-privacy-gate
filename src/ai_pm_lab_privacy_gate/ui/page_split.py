from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.iconography import icon


WHITE = "#FFFFFF"


def apply_apps_mcp_split(main_window) -> None:
    if hasattr(main_window, "apps_hub_page"):
        return

    cloud = getattr(main_window, "cloud_automation_page", None)
    if cloud is None:
        return
    service = getattr(cloud, "_connected_apps_service", None)
    if service is None:
        return

    # Old cloud page becomes MCP/AI-only. Keep all underlying MCP functionality intact.
    connected_section = getattr(cloud, "_connected_apps_section", None)
    if connected_section is not None:
        connected_section.hide()
        connected_section.setMaximumHeight(0)

    for label in cloud.findChildren(QLabel):
        if label.text().strip() == "Cloud, MCP & Email":
            label.setText("MCP & AI Connections")
        elif label.text().startswith("Optional customer-owned"):
            label.setText("Manage PrivacyGate connections to ChatGPT, Claude and compatible MCP clients.")

    # Existing page indexes are preserved: Protect 0, Library 1, Restore 2,
    # Local Automation 3, MCP/AI 4, Settings 5, Contact 6.
    original_buttons = list(getattr(main_window, "nav_buttons", []))
    original_page_map = {button: index for index, button in enumerate(original_buttons)}

    old_cloud_button = next(
        (button for button in original_buttons if button.text() == "Cloud / MCP / Email"),
        None,
    )
    if old_cloud_button is not None:
        old_cloud_button.setText("MCP & AI Connections")
        old_cloud_button.setToolTip("MCP & AI Connections")
        old_cloud_button.setIcon(icon("workflow", color=WHITE, size=20))
        old_cloud_button.setIconSize(QSize(20, 20))

    apps_page = AppsHubPage(main_window, service)
    apps_index = main_window.pages.addWidget(apps_page)
    main_window.apps_hub_page = apps_page
    main_window.apps_page_index = apps_index

    apps_button = QPushButton("Apps", objectName="NavButton")
    apps_button.setCheckable(True)
    apps_button.setToolTip("Connected Apps")
    apps_button.setIcon(icon("cloud", color=WHITE, size=20))
    apps_button.setIconSize(QSize(20, 20))
    main_window.nav_group.addButton(apps_button)

    if old_cloud_button is not None:
        target_index = main_window.side_layout.indexOf(old_cloud_button)
        main_window.side_layout.insertWidget(max(0, target_index), apps_button)
        list_index = main_window.nav_buttons.index(old_cloud_button)
        main_window.nav_buttons.insert(list_index, apps_button)
        main_window.nav_labels.insert(list_index, "Apps")
    else:
        main_window.side_layout.addWidget(apps_button)
        main_window.nav_buttons.append(apps_button)
        main_window.nav_labels.append("Apps")

    # Explicit page-to-button mapping removes the old assumption that the nav
    # list position must equal the page stack index.
    page_buttons = {page_index: button for button, page_index in original_page_map.items()}
    page_buttons[apps_index] = apps_button
    main_window._page_nav_buttons = page_buttons

    def show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        button = self._page_nav_buttons.get(index)
        if button is not None:
            button.setChecked(True)
        if index == 1:
            self.library_page.refresh()
        elif index == 2:
            self.restore_page.refresh()
        elif index == self.apps_page_index:
            self.apps_hub_page.refresh()

    main_window._show_page = MethodType(show_page, main_window)

    # Signals created earlier call self._show_page dynamically, so replacing
    # the instance method here safely updates their destination behavior too.
    apps_button.clicked.connect(lambda _checked=False: main_window._show_page(apps_index))
    apps_page.refresh()
