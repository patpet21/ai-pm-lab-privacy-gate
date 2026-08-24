from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractButton,
    QLabel,
    QRadioButton,
    QCheckBox,
    QTabWidget,
    QWidget,
)

# AI PM LAB / PrivacyGate brand palette.
NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
PETROL_HOVER = "#095E6B"
PETROL_PRESSED = "#084E59"
TEAL = "#1595A3"
TEAL_SOFT = "#E8F6F6"
TEAL_PALE = "#F1FAFA"
GOLD = "#D3A13B"
GOLD_HOVER = "#B9862F"
GOLD_PALE = "#FBF5E8"
BG = "#F7FAFC"
CARD = "#FFFFFF"
BORDER = "#D7E2EA"
MUTED = "#64788A"
WHITE = "#FFFFFF"
DISABLED = "#D7E0E7"
DISABLED_TEXT = "#8796A4"


def _button_role(button: QAbstractButton) -> str:
    name = button.objectName().lower()
    text = " ".join(button.text().lower().split())

    if name == "navbutton":
        return "nav"
    if name == "gold" or any(word in text for word in ("save + download", "download restored file")):
        return "gold"
    if name in {"primary", "primaryaction"} or any(
        phrase in text
        for phrase in (
            "protect document",
            "restore locally",
            "restore your file",
            "scan locally",
            "scan for sensitive data",
            "save + copy",
            "send request",
        )
    ):
        return "primary"
    if button.isCheckable() and text in {
        "document",
        "paste text",
        "protected text",
        "compare",
        "restored text",
        "document preview",
    }:
        return "toggle"
    if name in {"secondary", "secondarytool", "tiny"}:
        return "secondary"
    return "secondary"


def _apply_button_style(button: QAbstractButton) -> None:
    role = _button_role(button)

    if role == "nav":
        button.setStyleSheet(
            f"QPushButton{{background:transparent;color:#DCE7EF;border:none;border-radius:9px;"
            "padding:12px 14px;text-align:left;font-weight:650;min-height:24px;}"
            f"QPushButton:hover{{background:#0D3A5C;color:{WHITE};}}"
            f"QPushButton:checked{{background:{PETROL};color:{WHITE};border-left:3px solid {GOLD};}}"
        )
        return

    if role == "primary":
        button.setStyleSheet(
            f"QPushButton,QToolButton{{background:{PETROL};color:{WHITE};border:1px solid {PETROL};"
            "border-radius:8px;padding:9px 15px;font-weight:800;}"
            f"QPushButton:hover,QToolButton:hover{{background:{PETROL_HOVER};border-color:{PETROL_HOVER};}}"
            f"QPushButton:pressed,QToolButton:pressed{{background:{PETROL_PRESSED};border-color:{PETROL_PRESSED};}}"
            f"QPushButton:disabled,QToolButton:disabled{{background:{DISABLED};color:{DISABLED_TEXT};border-color:{DISABLED};}}"
        )
        return

    if role == "gold":
        button.setStyleSheet(
            f"QPushButton{{background:{GOLD};color:{NAVY};border:1px solid {GOLD};"
            "border-radius:8px;padding:9px 15px;font-weight:800;}"
            f"QPushButton:hover{{background:{GOLD_HOVER};color:{WHITE};border-color:{GOLD_HOVER};}}"
            f"QPushButton:disabled{{background:#E9E0CA;color:#9B917C;border-color:#E9E0CA;}}"
        )
        return

    if role == "toggle":
        button.setStyleSheet(
            f"QPushButton{{background:{WHITE};color:{NAVY_SOFT};border:1px solid #B9CBD5;"
            "border-radius:7px;padding:7px 14px;font-weight:750;}"
            f"QPushButton:hover{{background:{TEAL_PALE};color:{PETROL};border-color:#8FB8BF;}}"
            f"QPushButton:checked{{background:{PETROL};color:{WHITE};border-color:{PETROL};}}"
            f"QPushButton:checked:hover{{background:{PETROL_HOVER};border-color:{PETROL_HOVER};}}"
        )
        return

    button.setStyleSheet(
        f"QPushButton,QToolButton{{background:{WHITE};color:{NAVY_SOFT};border:1px solid #B9CBD5;"
        "border-radius:8px;padding:8px 14px;font-weight:750;}"
        f"QPushButton:hover,QToolButton:hover{{background:{TEAL_PALE};color:{PETROL};border-color:#8FB8BF;}}"
        f"QPushButton:checked,QToolButton:checked{{background:{PETROL};color:{WHITE};border-color:{PETROL};}}"
        f"QPushButton:disabled,QToolButton:disabled{{background:#F2F5F7;color:#9AA7B2;border-color:#D8E0E6;}}"
    )


def apply_brand_palette(root: QWidget) -> None:
    """Apply only brand colors to the existing UI; no geometry/layout changes."""
    root.setStyleSheet(
        root.styleSheet()
        + f"""
        QWidget {{ color:{NAVY_SOFT}; }}
        QFrame#Content {{ background:{BG}; }}
        QFrame#Sidebar {{ background:{NAVY}; border:none; }}
        QFrame#Card, QFrame#ConnectionCard, QFrame#RedesignResults, QFrame#RedesignSettingsStrip {{
            background:{CARD}; border:1px solid {BORDER};
        }}
        QLabel#PageTitle {{ color:{NAVY}; }}
        QLabel#SectionTitle, QLabel#PdfTitle, QLabel#FieldLabel {{ color:{NAVY_SOFT}; }}
        QLabel#Muted {{ color:{MUTED}; }}
        QLabel#SafeBadge, QLabel#PdfBadge, QLabel#ConnectionBadge {{
            background:{TEAL_SOFT}; color:{PETROL}; border-color:#C9E8E8;
        }}
        QLabel#Metric {{ background:#EDF4F8;color:{NAVY_SOFT};border-color:#CEDDE6; }}
        QLabel#SourceMetric {{ background:{GOLD_PALE};color:#775A1F;border-color:#E7D4AA; }}
        QFrame#PdfPanel {{ background:#FAFCFD;border-color:{BORDER}; }}
        QFrame#EmbeddedSourceToolbar,QFrame#EmbeddedSourceFooter,QFrame#ProtectWorkspaceActions,QFrame#RestoreWorkspaceActions {{
            background:#F8FBFC;border:1px solid {BORDER};
        }}
        QHeaderView::section {{ background:{NAVY};color:{WHITE};border:none; }}
        QTableWidget::item:selected {{ background:#DCEFF1;color:{NAVY}; }}
        QTabBar::tab {{ background:#EAF0F4;color:#38566B;border-radius:6px;padding:8px 18px; }}
        QTabBar::tab:hover {{ background:{TEAL_SOFT};color:{PETROL}; }}
        QTabBar::tab:selected {{ background:{PETROL};color:{WHITE}; }}
        QMenu::item:selected {{ background:{TEAL_SOFT};color:{NAVY}; }}
        QPlainTextEdit {{ selection-background-color:{GOLD}; }}
        QRadioButton:checked {{ background:{TEAL_SOFT};color:{PETROL}; }}
        QRadioButton::indicator:hover {{ border-color:{TEAL}; }}
        QRadioButton::indicator:checked {{ border:6px solid {PETROL};background:{WHITE}; }}
        QCheckBox::indicator:checked {{ background:{PETROL};border-color:{PETROL}; }}
        QSplitter::handle:hover {{ background:{TEAL}; }}
        QStatusBar,QLabel#ProductFooter {{ background:#EAF0F4;color:#5B7182; }}
        """
    )

    for button in root.findChildren(QAbstractButton):
        # Keep special tiny info controls compact; only recolor them.
        if button.objectName() == "InfoButton":
            button.setStyleSheet(
                f"QToolButton{{background:{TEAL_SOFT};color:{PETROL};border:1px solid #BBDCDD;"
                "border-radius:9px;padding:0;min-width:18px;max-width:18px;min-height:18px;max-height:18px;font-weight:800;}"
                f"QToolButton:hover{{background:{PETROL};color:{WHITE};}}"
            )
            continue
        _apply_button_style(button)

    for tabs in root.findChildren(QTabWidget):
        tabs.setStyleSheet(
            f"QTabBar::tab{{background:#EAF0F4;color:#38566B;padding:8px 18px;margin-right:3px;border-radius:6px;}}"
            f"QTabBar::tab:hover{{background:{TEAL_SOFT};color:{PETROL};}}"
            f"QTabBar::tab:selected{{background:{PETROL};color:{WHITE};}}"
            f"QTabWidget::pane{{background:{WHITE};border:1px solid #C9D6DF;border-radius:8px;}}"
        )

    for radio in root.findChildren(QRadioButton):
        radio.setStyleSheet(
            f"QRadioButton{{color:{NAVY_SOFT};spacing:10px;padding:7px 10px;border-radius:8px;font-weight:650;}}"
            f"QRadioButton:hover{{background:{TEAL_PALE};}}"
            f"QRadioButton:checked{{background:{TEAL_SOFT};color:{PETROL};font-weight:800;}}"
            "QRadioButton::indicator{width:19px;height:19px;border-radius:10px;border:2px solid #8AA6B7;background:white;}"
            f"QRadioButton::indicator:hover{{border:2px solid {TEAL};}}"
            f"QRadioButton::indicator:checked{{border:6px solid {PETROL};background:white;}}"
        )

    for checkbox in root.findChildren(QCheckBox):
        checkbox.setStyleSheet(
            f"QCheckBox{{color:{NAVY_SOFT};spacing:9px;font-weight:650;}}"
            "QCheckBox::indicator{width:18px;height:18px;border:2px solid #8AA6B7;border-radius:4px;background:white;}"
            f"QCheckBox::indicator:checked{{background:{PETROL};border:2px solid {PETROL};}}"
        )
