import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_redesigned_protection_page_constructs(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
    from ai_pm_lab_privacy_gate.ui.protect_runtime import (
        _wire_privacy_check_refresh_triggers,
    )
    from ai_pm_lab_privacy_gate.ui.protect_workflow_v2 import apply_protect_workflow_v2

    app = QApplication.instance() or QApplication([])
    page = ProtectionPage(PrivacyGateService(), LibraryRepository(tmp_path / "data"))
    try:
        assert hasattr(page, "_redesign_protect_button")
        assert hasattr(page, "_redesign_scroll")
        assert hasattr(page, "_protect_quick_actions")
        assert page._protect_save_only.text() == "Save to Library"
        assert page._protect_save_copy.text() == "Save + Copy"
        assert page._protect_save_download.text() == "Save + Download"
        assert page._protect_open_ai.text() == "Copy & Open ChatGPT"
        assert page._protect_quick_actions.isHidden()
        assert page._protect_quick_actions.parent() is page._redesign_results_card
        assert page.setup_toggle.isHidden()
        assert page._redesign_results_card.isHidden()
        assert not page.scan_button.isEnabled()
        assert not page._redesign_protect_button.isEnabled()

        apply_protect_workflow_v2(SimpleNamespace(protection_page=page))
        assert page.scan_button.text() == "Scan & Protect"
        assert page._redesign_protect_button.isHidden()
        assert page.preview_tabs.tabText(page._privacy_check_tab_index) == "Privacy Check"
        assert not page.preview_tabs.isTabVisible(page._privacy_check_tab_index)

        # Compatibility regression: the protected-copy completion signal must
        # still request Privacy Check even if an older bound _refresh_preview
        # callable bypasses the workflow wrapper. This is the desktop path that
        # previously left the Privacy Check tab hidden after protection.
        refresh_calls = []

        def record_privacy_refresh():
            refresh_calls.append(True)
            page._privacy_check_generation += 1

        page._refresh_privacy_check = record_privacy_refresh
        _wire_privacy_check_refresh_triggers(page)
        page._redesign_protect_button.setEnabled(True)
        page._redesign_protect_button.click()
        app.processEvents()
        assert refresh_calls == [True]

        page.text_input.setPlainText(
            "Daniel Mercer lives at 26 Meridian Street"
        )
        app.processEvents()
        assert page.scan_button.isEnabled()
        assert page.scan_button.text() == "Scan & Protect"
        assert page._redesign_results_card.isHidden()
        assert page._protect_quick_actions.isHidden()

        page.clear()
        app.processEvents()
        assert not page.scan_button.isEnabled()
        assert page._redesign_results_card.isHidden()
        assert page._protect_quick_actions.isHidden()
        assert page.setup_toggle.isHidden()
        assert not page.preview_tabs.isTabVisible(page._privacy_check_tab_index)

        page.pdf_path.setText(str(tmp_path / "sample.pdf"))
        app.processEvents()
        assert page.scan_button.isEnabled()
    finally:
        page.close()
        app.processEvents()
