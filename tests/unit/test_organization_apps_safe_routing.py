import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_safe_routing_uses_live_apps_widget_and_does_not_touch_stack():
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from ai_pm_lab_privacy_gate.ui.organization_apps_safe_routing import (
        open_apps_page,
        resolve_apps_page_index,
    )

    app = _app()
    pages = QStackedWidget()
    pages.addWidget(QWidget())
    apps = QWidget()
    pages.addWidget(apps)
    pages.addWidget(QWidget())
    opened = []
    window = SimpleNamespace(
        pages=pages,
        apps_hub_page=apps,
        apps_page_index=99,
        _show_page=lambda index: opened.append(index),
    )

    before = pages.count()
    assert resolve_apps_page_index(window) == 1
    assert open_apps_page(window) is True
    assert opened == [1]
    assert window.apps_page_index == 1
    assert pages.count() == before

    pages.close()
    app.processEvents()


def test_safe_routing_fails_closed_when_apps_page_missing():
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from ai_pm_lab_privacy_gate.ui.organization_apps_safe_routing import open_apps_page

    app = _app()
    pages = QStackedWidget()
    pages.addWidget(QWidget())
    opened = []
    window = SimpleNamespace(
        pages=pages,
        apps_hub_page=None,
        apps_page_index=0,
        _show_page=lambda index: opened.append(index),
    )

    before = pages.count()
    assert open_apps_page(window) is False
    assert opened == []
    assert pages.count() == before

    pages.close()
    app.processEvents()
