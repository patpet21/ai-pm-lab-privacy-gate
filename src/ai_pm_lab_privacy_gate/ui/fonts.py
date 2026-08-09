from __future__ import annotations

from pathlib import Path

import reportlab
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


def install_app_font(app: QApplication) -> str:
    """Load the redistributable Bitstream Vera font shipped with ReportLab."""
    fonts_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    regular = fonts_dir / "Vera.ttf"
    bold = fonts_dir / "VeraBd.ttf"
    families: list[str] = []
    for font_path in (regular, bold):
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                families.extend(QFontDatabase.applicationFontFamilies(font_id))
    family = families[0] if families else "Arial"
    app.setFont(QFont(family, 10))
    return family

