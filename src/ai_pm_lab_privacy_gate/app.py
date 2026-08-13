from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen


def _packaged_smoke_test() -> int:
    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.domain.profiles import get_profile

    text = "Contact Jane Smith at jane.smith@example.com or 212-555-5555. SSN 219-09-9999."
    service = PrivacyGateService()
    document = service.document_from_text(text)
    findings = service.analyze(document, get_profile("property_management"))
    protected = service.protect(document, findings).combined_text
    required = {"EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"}
    found = {item.entity_type for item in findings}
    return 0 if required <= found and "jane.smith@example.com" not in protected else 2


def main() -> int:
    if os.environ.get("PRIVACY_GATE_SMOKE_TEST") == "1":
        return _packaged_smoke_test()
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIPMLAB.PrivacyGate.0.1")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("AI PM LAB Privacy Gate")
    app.setOrganizationName("AI PM LAB")
    from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
    from ai_pm_lab_privacy_gate.ui.resources import resource_path
    from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE

    install_app_font(app)
    app.setStyleSheet(APP_STYLE)

    logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
    pixmap = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap(560, 260)
    if pixmap.isNull():
        pixmap = QPixmap(560, 260)
        pixmap.fill(QColor("#f4f7fb"))
    else:
        pixmap = pixmap.scaled(
            560,
            300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    splash = QSplashScreen(pixmap)
    splash.showMessage(
        "Starting local privacy protection…",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#06243c"),
    )
    splash.show()
    app.processEvents()

    # Import the full UI only after the user can see immediate startup feedback.
    # Presidio itself remains lazy and is loaded on the first analysis.
    from ai_pm_lab_privacy_gate.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
