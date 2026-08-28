import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_apps_route_resolves_live_widget_not_stale_index():
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from ai_pm_lab_privacy_gate.ui.organization_apps_routing_fix import (
        open_apps_page,
        resolve_apps_page_index,
    )

    app = _app()
    pages = QStackedWidget()
    pages.addWidget(QWidget())
    pages.addWidget(QWidget())
    apps_page = QWidget()
    pages.addWidget(apps_page)

    opened = []
    main_window = SimpleNamespace(
        pages=pages,
        apps_hub_page=apps_page,
        apps_page_index=0,  # deliberately stale
        _show_page=lambda index: opened.append(index),
    )

    assert resolve_apps_page_index(main_window) == 2
    assert open_apps_page(main_window) is True
    assert opened == [2]
    assert main_window.apps_page_index == 2

    pages.close()
    app.processEvents()


def test_team_apps_slot_is_created_once_at_index_four():
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from ai_pm_lab_privacy_gate.ui.organization_apps_routing_fix import (
        ensure_team_apps_slot,
    )

    app = _app()
    stack = QStackedWidget()
    for _ in range(4):
        stack.addWidget(QWidget())
    dashboard = SimpleNamespace(stack=stack)

    assert stack.count() == 4
    assert ensure_team_apps_slot(dashboard) is True
    assert stack.count() == 5
    assert stack.widget(4) is not None
    assert ensure_team_apps_slot(dashboard) is False
    assert stack.count() == 5

    stack.close()
    app.processEvents()


def test_missing_apps_hub_fails_closed_without_using_cached_index():
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from ai_pm_lab_privacy_gate.ui.organization_apps_routing_fix import open_apps_page

    app = _app()
    pages = QStackedWidget()
    pages.addWidget(QWidget())
    opened = []
    main_window = SimpleNamespace(
        pages=pages,
        apps_hub_page=None,
        apps_page_index=0,
        _show_page=lambda index: opened.append(index),
    )

    assert open_apps_page(main_window) is False
    assert opened == []

    pages.close()
    app.processEvents()
