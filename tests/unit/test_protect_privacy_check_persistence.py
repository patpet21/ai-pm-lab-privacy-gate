import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_privacy_check_stays_reachable_across_view_navigation(tmp_path):
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )

    from ai_pm_lab_privacy_gate.ui.protect_privacy_check_persistence import (
        apply_protect_privacy_check_persistence,
    )

    app = QApplication.instance() or QApplication([])

    page = QWidget()
    root = QVBoxLayout(page)
    toolbar = QWidget(page)
    toolbar_layout = QHBoxLayout(toolbar)
    protected = QPushButton("Protected text", toolbar)
    protected.setCheckable(True)
    compare = QPushButton("Original + Protected", toolbar)
    compare.setCheckable(True)
    toolbar_layout.addWidget(protected)
    toolbar_layout.addWidget(compare)
    root.addWidget(toolbar)

    page.preview_tabs = QTabWidget(page)
    page.preview_tabs.addTab(QWidget(), "Protected text")
    page.preview_tabs.addTab(QWidget(), "Original + Protected")
    page.preview_tabs.addTab(QWidget(), "Privacy Check")
    page._privacy_check_tab_index = 2
    page.preview_tabs.setTabVisible(2, True)
    root.addWidget(page.preview_tabs)

    page.clear_button = QPushButton("Clear", page)
    page.scan_button = QPushButton("Scan & Protect", page)
    page.pdf_path = QLineEdit(page)
    page.text_input = QPlainTextEdit(page)
    root.addWidget(page.clear_button)
    root.addWidget(page.scan_button)
    root.addWidget(page.pdf_path)
    root.addWidget(page.text_input)

    document = SimpleNamespace(
        source_kind="pdf",
        source_path=Path(tmp_path) / "sample.pdf",
    )
    result = SimpleNamespace(applied_findings=(), combined_text="protected")
    page._protect_session_sources = {
        "document": {
            "document": document,
            "findings": (),
            "label": "sample.pdf",
        }
    }
    page._protect_session_results = {"document": result}
    page._privacy_check_summary = object()

    page.show()
    app.processEvents()
    apply_protect_privacy_check_persistence(
        SimpleNamespace(protection_page=page)
    )
    app.processEvents()

    button = page._privacygate_privacy_view_button
    assert button.text() == "Privacy Check"
    assert button.isVisible()

    page.preview_tabs.setCurrentIndex(0)
    app.processEvents()
    assert button.isVisible()

    page.preview_tabs.setCurrentIndex(1)
    app.processEvents()
    assert button.isVisible()

    button.click()
    app.processEvents()
    assert page.preview_tabs.currentIndex() == 2
    assert button.isVisible()
    assert button.isChecked()

    # Loading may temporarily hide the real Privacy Check tab, but once the
    # completed summary tab is visible again the persistent VIEW control returns.
    page.preview_tabs.setTabVisible(2, False)
    page._privacygate_sync_privacy_view_button()
    assert not button.isVisible()
    page.preview_tabs.setTabVisible(2, True)
    page._privacygate_sync_privacy_view_button()
    assert button.isVisible()

    page._privacy_check_summary = None
    page.clear_button.click()
    app.processEvents()
    assert not button.isVisible()

    page.close()
    app.processEvents()
