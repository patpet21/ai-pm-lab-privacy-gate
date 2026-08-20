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
        assert hasattr(page, "_redesign_scan_button")
        assert hasattr(page, "_redesign_protect_button")
        assert not page._redesign_scan_button.isEnabled()
    finally:
        page.close()
        app.processEvents()
