import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_redesigned_protection_page_constructs(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage

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

        page.text_input.setPlainText(
            "Daniel Mercer lives at 26 Meridian Street"
        )
        app.processEvents()
        assert page.scan_button.isEnabled()
        assert page._redesign_results_card.isHidden()
        assert page._protect_quick_actions.isHidden()
        assert not page._redesign_protect_button.isEnabled()

        page.clear()
        app.processEvents()
        assert not page.scan_button.isEnabled()
        assert page._redesign_results_card.isHidden()
        assert page._protect_quick_actions.isHidden()
        assert page.setup_toggle.isHidden()

        page.pdf_path.setText(str(tmp_path / "sample.pdf"))
        app.processEvents()
        assert page.scan_button.isEnabled()
    finally:
        page.close()
        app.processEvents()
