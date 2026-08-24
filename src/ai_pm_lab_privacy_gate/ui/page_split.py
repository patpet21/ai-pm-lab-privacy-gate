from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QPushButton

from ai_pm_lab_privacy_gate.ui.apps_hub import AppsHubPage
from ai_pm_lab_privacy_gate.ui.iconography import icon


WHITE = "#FFFFFF"
NAV_TEXT = "#DCE7EF"
PETROL = "#0B7180"
GOLD = "#D3A13B"


def _nav_style() -> str:
    return (
        f"QPushButton{{background:transparent;color:{NAV_TEXT};border:none;border-radius:9px;"
        "padding:12px 14px;text-align:left;font-weight:650;min-height:24px;}"
        f"QPushButton:hover{{background:#0D3A5C;color:{WHITE};}}"
        f"QPushButton:checked{{background:{PETROL};color:{WHITE};border-left:3px solid {GOLD};}}"
    )


def apply_apps_mcp_split(main_window) -> None:
    if hasattr(main_window, "apps_hub_page"):
        return

    cloud = getattr(main_window, "cloud_automation_page", None)
    if cloud is None:
        return
    service = getattr(cloud, "_connected_apps_service", None)
    if service is None:
        return

    connected_section = getattr(cloud, "_connected_apps_section", None)
    if connected_section is not None:
        connected_section.hide()
        connected_section.setMaximumHeight(0)

    for label in cloud.findChildren(QLabel):
        if label.text().strip() == "Cloud, MCP & Email":
            label.setText("MCP & AI Connections")
        elif label.text().startswith("Optional customer-owned"):
            label.setText("Manage PrivacyGate connections to ChatGPT, Claude and compatible MCP clients.")

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

    apps_page = AppsHubPage(main_window, service)
    apps_index = main_window.pages.addWidget(apps_page)
    main_window.apps_hub_page = apps_page
    main_window.apps_page_index = apps_index

    apps_button = QPushButton("Apps", objectName="NavButton")
    apps_button.setCheckable(True)
    apps_button.setToolTip("Connected Apps")
    apps_button.setIcon(icon("cloud", color=WHITE, size=20))
    apps_button.setIconSize(QSize(20, 20))
    apps_button.setStyleSheet(_nav_style())
    apps_button.clicked.connect(lambda _checked=False: main_window._show_page(apps_index))
    main_window.nav_group.addButton(apps_button)

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

    original_show_page = main_window._show_page

    def show_page(index: int) -> None:
        main_window.pages.setCurrentIndex(index)
        for button in main_window.nav_buttons:
            button.setChecked(False)
        if index == apps_index:
            apps_button.setChecked(True)
            apps_page.refresh()
            return
        page_to_label = {
            0: "Protect",
            1: "Library",
            2: "Restore",
            3: "Local Automation / n8n",
            4: "MCP & AI Connections",
            5: "Settings",
            6: "Contact / Workflows",
        }
        wanted = page_to_label.get(index)
        for button in main_window.nav_buttons:
            if button.text() == wanted:
                button.setChecked(True)
                break
        if index == 1:
            main_window.library_page.refresh()
        elif index == 2:
            main_window.restore_page.refresh()

    main_window._show_page = show_page
    apps_page.refresh()
