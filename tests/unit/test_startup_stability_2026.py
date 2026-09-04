import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_immediate_layout_clear_detaches_replaced_widget_before_deferred_delete():
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    from ai_pm_lab_privacy_gate.ui.startup_stability_2026 import _clear_layout_immediately

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    layout = QVBoxLayout(host)
    old = QLabel("old generation", host)
    layout.addWidget(old)
    host.show()
    app.processEvents()

    _clear_layout_immediately(layout)

    assert layout.count() == 0
    assert old.isHidden()
    assert old.parent() is None
    host.close()


def test_startup_loading_guard_tracks_work_without_showing_page_popup():
    from PySide6.QtWidgets import QApplication, QWidget

    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import UnifiedLoadingController
    from ai_pm_lab_privacy_gate.ui.startup_stability_2026 import _install_startup_loading_guard

    app = QApplication.instance() or QApplication([])
    _install_startup_loading_guard()
    host = QWidget()
    host._privacygate_startup_ready = False
    controller = UnifiedLoadingController(host)
    host._unified_loading = controller
    try:
        controller.begin("team", "Team is working", "Completing this operation…")
        app.processEvents()
        assert controller.active("team")
        assert not controller.dialog.isVisible()

        host._privacygate_startup_ready = True
        controller._render()
        app.processEvents()
        assert controller.dialog.isVisible()

        controller.end("team")
        app.processEvents()
        assert not controller.dialog.isVisible()
    finally:
        controller.clear()
        host.close()
        app.processEvents()
