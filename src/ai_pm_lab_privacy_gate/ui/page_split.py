from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
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

    # Old cloud page becomes MCP/AI-only. Keep its underlying MCP functionality intact.
    connected_section = getattr(cloud, "_connected_apps_section", None)
    if connected_section is not None:
        connected_section.hide()
        connected_section.setMaximumHeight(0)

    # Update the visible page heading when possible.
    for label in cloud.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel):
        if label.text().strip() == "Cloud, MCP & Email":
            label.setText("MCP & AI Connections")
        elif label.text().startswith("Optional customer-owned"):
            label.setText("Manage PrivacyGate connections to ChatGPT, Claude and compatible MCP clients.")

    # Rename existing navigation entry.
    old_cloud_button = None
    for button in getattr(main_window, "nav_buttons", []):
        if button.text() == "Cloud / MCP / Email":
            old_cloud_button = button
            break
    if old_cloud_button is not None:
        old_cloud_button.setText("MCP & AI Connections")
        old_cloud_button.setToolTip("MCP & AI Connections")
        old_cloud_button.setIcon(icon("workflow", color=WHITE, size=20))
        old_cloud_button.setIconSize(QSize(20, 20))

    # Add dedicated Apps page to the page stack.
    apps_page = AppsHubPage(main_window, service)
    apps_index = main_window.pages.addWidget(apps_page)
    main_window.apps_hub_page = apps_page
    main_window.apps_page_index = apps_index

    # Insert Apps nav immediately before MCP & AI Connections.
    apps_button = QPushButton("Apps", objectName="NavButton")
    apps_button.setCheckable(True)
    apps_button.setToolTip("Connected Apps")
    apps_button.setIcon(icon("cloud", color=WHITE, size=20))
    apps_button.setIconSize(QSize(20, 20))
    apps_button.clicked.connect(lambda _checked=False: main_window._show_page(apps_index))
    main_window.nav_group.addButton(apps_button)

    # MainWindow keeps nav widgets in side_layout. Insert visually before MCP button.
    if old_cloud_button is not None:
        target_index = main_window.side_layout.indexOf(old_cloud_button)
        main_window.side_layout.insertWidget(max(0, target_index), apps_button)
        try:
            list_index = main_window.nav_buttons.index(old_cloud_button)
        except ValueError:
            list_index = len(main_window.nav_buttons)
        main_window.nav_buttons.insert(list_index, apps_button)
        main_window.nav_labels.insert(list_index, "Apps")
    else:
        main_window.side_layout.addWidget(apps_button)
        main_window.nav_buttons.append(apps_button)
        main_window.nav_labels.append("Apps")

    # Preserve original page indexes: Apps is appended, MCP remains index 4.
    apps_page.refresh()
