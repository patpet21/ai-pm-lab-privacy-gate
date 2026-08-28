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


def test_policy_history_orphan_is_hidden_and_reparented_inside_policy_view():
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QPushButton,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )

    from ai_pm_lab_privacy_gate.ui.organization_apps_safe_routing import (
        _repair_policy_history_control,
    )

    app = _app()

    class FakeTeamPage(QWidget):
        state_changed = Signal(object)

        def __init__(self):
            super().__init__()
            self.state = SimpleNamespace(
                organization_id="org-1",
                role="owner",
                policy=SimpleNamespace(version=1),
            )
            self.team_client = SimpleNamespace(list_policy_versions=lambda *_args: [])
            self._run_team_action = lambda *_args, **_kwargs: None

    team_page = FakeTeamPage()
    dashboard = QWidget(team_page)
    dashboard.stack = QStackedWidget(dashboard)
    for _ in range(2):
        dashboard.stack.addWidget(QWidget())

    policy_view = QWidget()
    policy_root = QVBoxLayout(policy_view)
    actions_host = QWidget(policy_view)
    actions = QHBoxLayout(actions_host)
    edit = QPushButton("Edit policy", actions_host)
    actions.addWidget(edit)
    policy_root.addWidget(actions_host)
    dashboard.stack.addWidget(policy_view)
    team_page._privacygate_premium_dashboard = dashboard

    main_window = SimpleNamespace(team_page=team_page)

    # Reproduce the legacy bug: a parentless visible QPushButton becomes its own window.
    orphan = QPushButton("Policy history")
    orphan.show()
    app.processEvents()
    assert orphan.parentWidget() is None
    assert orphan.isVisible()
    assert orphan in QApplication.topLevelWidgets()

    _repair_policy_history_control(main_window)
    app.processEvents()

    assert not orphan.isVisible()
    safe_buttons = [
        button
        for button in policy_view.findChildren(QPushButton)
        if button.text().strip().lower() == "policy history"
    ]
    assert len(safe_buttons) == 1
    safe = safe_buttons[0]
    assert safe.parentWidget() is actions_host
    assert safe.window() is not safe
    assert safe.isVisible()
    assert dashboard.stack.count() == 3

    team_page.close()
    app.processEvents()
