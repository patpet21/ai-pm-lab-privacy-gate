from __future__ import annotations

import os
import sys
from pathlib import Path


# Always run the package from this checkout first, even when the Python
# interpreter comes from another PrivacyGate virtual environment that has an
# editable install pointing at a different repository.
_repo_root = Path(__file__).resolve().parent
_src = _repo_root / "src"
if _src.exists():
    src_text = str(_src)
    if src_text in sys.path:
        sys.path.remove(src_text)
    sys.path.insert(0, src_text)

    # app.py launches the branded startup splash in a child Python process via
    # ``python -m ai_pm_lab_privacy_gate.app``. sys.path changes are process-local,
    # so also publish this checkout through PYTHONPATH. The child then imports the
    # exact same FreeV1 sources instead of an editable install from an older venv.
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
    pythonpath_parts = [part for part in pythonpath_parts if os.path.normcase(part) != os.path.normcase(src_text)]
    os.environ["PYTHONPATH"] = os.pathsep.join([src_text, *pythonpath_parts])

# The packaged Windows app also uses run_app.py as its PyInstaller entrypoint.
# Install the additive CSV UI adapter before MainWindow imports ProtectionPage,
# so both source runs and packaged builds expose the same CSV workflow.
from ai_pm_lab_privacy_gate.ui.csv_document_support import install_csv_document_support

install_csv_document_support()

# Settings service pages are built after several visual layers have already
# reparented the original controls. The legacy lookup used to accept any ancestor
# QFrame containing a matching label, which could accidentally move the whole
# Settings control center inside the Updates service page. Restrict discovery to
# the original functional SettingsPremiumCard so Updates keeps only its own real
# update controls and the Settings launcher remains separate.
from PySide6.QtWidgets import QFrame, QLabel, QWidget
import ai_pm_lab_privacy_gate.ui.settings_service_pages_2026 as _settings_service_pages_2026


def _find_exact_settings_card(settings: QWidget, heading: str) -> QFrame | None:
    for frame in settings.findChildren(QFrame, "SettingsPremiumCard"):
        for label in frame.findChildren(QLabel):
            if label.text().strip() == heading:
                return frame

    # Compatibility fallback: walk upward from the exact heading, but still
    # accept only the canonical functional card. Never return a broad container.
    for label in settings.findChildren(QLabel):
        if label.text().strip() != heading:
            continue
        current = label.parentWidget()
        while current is not None and current is not settings:
            if isinstance(current, QFrame) and current.objectName() == "SettingsPremiumCard":
                return current
            current = current.parentWidget()
    return None


_settings_service_pages_2026._find_card = _find_exact_settings_card

from ai_pm_lab_privacy_gate.app import main


if __name__ == "__main__":
    raise SystemExit(main())
