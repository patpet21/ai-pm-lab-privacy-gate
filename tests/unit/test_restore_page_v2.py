import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_restore_page_v2_guides_user_and_requires_match(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    from ai_pm_lab_privacy_gate.ui.restore_page import RestorePage

    app = QApplication.instance() or QApplication([])
    page = RestorePage(PrivacyGateService(), LibraryRepository(tmp_path / "data"))
    try:
        page.show()
        app.processEvents()
        assert page.restore_button.text() == "Restore your file"
        assert page.download_text_button.text() == "Download restored text"
        assert not page.restore_button.isEnabled()
        assert page.document_combo.itemText(0) == "Choose from Privacy Gate Library..."
        assert page.full_preview_button.text() == "Full screen preview"
        assert page.input_text.isHidden()
        page.paste_toggle.setChecked(True)
        app.processEvents()
        assert page.input_text.isVisible()
        page.paste_toggle.setChecked(False)

        page.result_section.show()
        page.full_preview_button.setChecked(True)
        app.processEvents()
        assert page.input_card.isHidden()
        assert page.match_card.isHidden()
        assert page.result_section.isVisible()
        assert page.full_preview_button.text() == "Exit full screen"
        page.full_preview_button.setChecked(False)
        app.processEvents()
        assert page.input_card.isVisible()

        page.input_text.setPlainText("Hello [[PG_PERSON_001]]")
        app.processEvents()
        assert "placeholder" in page.token_hint.text().lower()
        assert not page.restore_button.isEnabled()
    finally:
        page.close()
        app.processEvents()
