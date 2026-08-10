from __future__ import annotations

import os
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "PRIVACY_GATE_DATA_DIR",
    str((Path("tmp/ui/sessions") / uuid.uuid4().hex).resolve()),
)

from PySide6.QtWidgets import QApplication

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.ui.main_window import MainWindow
from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE


def main() -> int:
    output = Path("tmp/ui/privacy_gate_main.png")
    collapsed_output = Path("tmp/ui/privacy_gate_collapsed.png")
    library_output = Path("tmp/ui/privacy_gate_library.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    install_app_font(app)
    app.setStyleSheet(APP_STYLE)
    service = PrivacyGateService()
    document = service.document_from_text(
        "Tenant Jane Smith can be reached at jane.smith@example.com or 212-555-5555. "
        "Social Security Number: 219-09-9999."
    )
    findings = service.analyze(document, get_profile("property_management"))
    window = MainWindow(service=service)
    page = window.protection_page
    page.text_input.setPlainText(document.pages[0].text)
    page._analysis_ready((document, findings))
    window.show()
    app.processEvents()
    if not window.grab().save(str(output)):
        raise RuntimeError("Unable to save UI screenshot")
    window._toggle_sidebar()
    app.processEvents()
    if window.sidebar.width() != 76:
        raise RuntimeError("Sidebar did not collapse to the expected width")
    if not window.grab().save(str(collapsed_output)):
        raise RuntimeError("Unable to save collapsed UI screenshot")
    result = service.protect(document, findings)
    saved = window.library.save(
        title="Lease 014 - Jane Smith",
        source_kind="text",
        source_name="Pasted text",
        profile_key="property_management",
        result=result,
        labels=("Lease", "Property 014"),
    )
    window.library.set_favorite(saved.document_id, True)
    window._toggle_sidebar()
    window._show_page(1)
    app.processEvents()
    if not window.library_page.backup_button.isEnabled():
        raise RuntimeError("Library backup action is unavailable")
    if not window.grab().save(str(library_output)):
        raise RuntimeError("Unable to save library UI screenshot")
    print(
        f"UI_OK {output.resolve()} {collapsed_output.resolve()} {library_output.resolve()} "
        f"{len(findings)} findings sidebar={window.sidebar.width()}"
    )
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
