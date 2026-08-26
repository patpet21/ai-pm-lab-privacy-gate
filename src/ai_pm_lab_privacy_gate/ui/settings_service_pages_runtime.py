from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPushButton, QTableWidgetItem

from ai_pm_lab_privacy_gate.ui.settings_service_pages_2026 import (
    WorkspaceFilesPage,
    apply_settings_service_pages_2026 as _apply_service_pages,
)


def _safe_refresh_table(self: WorkspaceFilesPage) -> None:
    context = self._context()
    if context is None:
        return
    self.table.setRowCount(len(context.workspaces))
    for row, (key, descriptor) in enumerate(context.workspaces.items()):
        route = self.routes.route_for(key, descriptor.name)
        root = Path(route.root)
        values = (
            descriptor.name,
            "Personal" if descriptor.personal else f"Company · {descriptor.plan.label}",
            str(root),
            "Ready" if root.exists() else "Not created",
        )
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))


def _open_apps_safely(main_window) -> None:
    index = getattr(main_window, "apps_page_index", None)
    pages = getattr(main_window, "pages", None)
    if index is None or pages is None or not 0 <= int(index) < pages.count():
        return
    pages.setCurrentIndex(int(index))
    for button in getattr(main_window, "nav_buttons", []):
        button.setChecked(False)
    if int(index) < len(getattr(main_window, "nav_buttons", [])):
        main_window.nav_buttons[int(index)].setChecked(True)


def apply_settings_service_pages_2026_runtime(main_window) -> None:
    """Apply the dedicated service shell with Windows-safe table/navigation behavior."""
    WorkspaceFilesPage._refresh_table = _safe_refresh_table
    _apply_service_pages(main_window)

    settings = getattr(main_window, "settings_page", None)
    pages = getattr(settings, "settings_service_pages", {}) if settings is not None else {}
    workspace_page = pages.get("workspaces") if isinstance(pages, dict) else None
    if workspace_page is not None:
        for button in workspace_page.findChildren(QPushButton):
            if button.text().strip() != "Apps & AI":
                continue
            try:
                button.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            button.clicked.connect(lambda: _open_apps_safely(main_window))
            break
