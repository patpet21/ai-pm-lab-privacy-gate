import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_unified_loading_controller_tracks_real_operation_lifetime():
    from PySide6.QtWidgets import QApplication, QWidget

    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import UnifiedLoadingController

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    controller = UnifiedLoadingController(host)
    host._unified_loading = controller
    try:
        controller.begin("scan", "Scan & Protect", "Scanning locally…")
        app.processEvents()
        assert controller.active("scan")
        assert controller.dialog.isVisible()
        assert controller.dialog.title_label.text() == "Scan & Protect"

        controller.update("scan", message="Running Privacy Check…")
        app.processEvents()
        assert controller.dialog.message_label.text() == "Running Privacy Check…"

        controller.end("scan")
        app.processEvents()
        assert not controller.active()
        assert not controller.dialog.isVisible()
    finally:
        controller.clear()
        host.close()
        app.processEvents()


def test_run_with_unified_loading_returns_result_and_closes_popup():
    from PySide6.QtWidgets import QApplication, QWidget

    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import (
        UnifiedLoadingController,
        run_with_unified_loading,
    )

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    controller = UnifiedLoadingController(host)
    host._unified_loading = controller
    try:
        result = run_with_unified_loading(
            host,
            "Importing",
            "Preparing local working copy…",
            lambda: 42,
            key="test.import",
        )
        app.processEvents()
        assert result == 42
        assert not controller.active("test.import")
        assert not controller.dialog.isVisible()
    finally:
        controller.clear()
        host.close()
        app.processEvents()


def test_run_with_unified_loading_preserves_original_exception_type():
    import pytest
    from PySide6.QtWidgets import QApplication, QWidget

    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import (
        UnifiedLoadingController,
        run_with_unified_loading,
    )

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    controller = UnifiedLoadingController(host)
    host._unified_loading = controller

    class ExpectedError(RuntimeError):
        pass

    def fail():
        raise ExpectedError("boom")

    try:
        with pytest.raises(ExpectedError, match="boom"):
            run_with_unified_loading(
                host,
                "Loading",
                "Testing failure cleanup…",
                fail,
                key="test.failure",
            )
        app.processEvents()
        assert not controller.active("test.failure")
        assert not controller.dialog.isVisible()
    finally:
        controller.clear()
        host.close()
        app.processEvents()
