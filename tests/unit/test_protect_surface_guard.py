import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_final_surface_guard_hides_detached_direct_child(tmp_path):
    from PySide6.QtWidgets import QApplication, QLabel

    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
    from ai_pm_lab_privacy_gate.ui.protect_surface_guard import apply_protect_surface_guard

    app = QApplication.instance() or QApplication([])
    page = ProtectionPage(PrivacyGateService(), LibraryRepository(tmp_path / "data"))
    try:
        page.show()
        app.processEvents()

        ghost = QLabel("ghost", page)
        ghost.move(1, 140)
        ghost.show()
        app.processEvents()
        assert ghost.isVisible()

        apply_protect_surface_guard(SimpleNamespace(protection_page=page))
        app.processEvents()

        assert ghost.isHidden()
        assert not page._redesign_scroll.isHidden()
        assert page.setup_toggle.isHidden()
    finally:
        page.close()
        app.processEvents()


def test_surface_guard_is_idempotent(tmp_path):
    from PySide6.QtWidgets import QApplication

    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
    from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage
    from ai_pm_lab_privacy_gate.ui.protect_surface_guard import apply_protect_surface_guard

    app = QApplication.instance() or QApplication([])
    page = ProtectionPage(PrivacyGateService(), LibraryRepository(tmp_path / "data"))
    window = SimpleNamespace(protection_page=page)
    try:
        apply_protect_surface_guard(window)
        first = page._protect_surface_guard
        apply_protect_surface_guard(window)
        assert page._protect_surface_guard is first
    finally:
        page.close()
        app.processEvents()
