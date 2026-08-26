from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
)

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7180"
MUTED = "#64788A"
BORDER = "#DCE5EA"


def _clean_label(label: QLabel) -> None:
    current = label.styleSheet()
    label.setStyleSheet(current + "border:none;background:transparent;")


def apply_organization_visual_upgrade(main_window) -> None:
    page = getattr(main_window, "team_page", None)
    if page is None or getattr(page, "_premium_visual_applied", False):
        return
    page._premium_visual_applied = True

    root = page.layout()
    if root is not None:
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

    for label in page.findChildren(QLabel):
        _clean_label(label)
        text = label.text().strip()
        if text == "Organization":
            label.setStyleSheet(
                f"color:{NAVY};font-size:28px;font-weight:950;border:none;background:transparent;"
            )
        elif text.startswith("Manage company privacy"):
            label.setStyleSheet(
                f"color:{MUTED};font-size:10px;border:none;background:transparent;"
            )

    # Make the workspace context control read like a polished product header.
    for combo in page.findChildren(QComboBox):
        combo.setMinimumHeight(40)
        combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;"
            "border-radius:10px;padding:7px 12px;font-weight:750;}"
            "QComboBox:hover{border-color:#8DBEC2;}"
            "QComboBox:focus{border:1px solid #0B7180;}"
            "QComboBox::drop-down{border:none;width:28px;}"
            "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;border:1px solid #D5E0E7;"
            "selection-background-color:#EAF7F7;selection-color:#062B4F;padding:5px;}"
        )

    # Main company shell should be visually quiet; content cards carry hierarchy.
    shell = getattr(page, "organization_shell", None)
    if shell is not None:
        shell.setStyleSheet("background:transparent;border:none;")

    # Metric cards: large white cards, no nested label boxes.
    metric_map = (
        ("seats_card", "seats_value", "seats_detail"),
        ("members_card", "members_value", "members_detail"),
        ("devices_card", "devices_value", "devices_detail"),
        ("policy_card", "policy_value", "policy_detail"),
    )
    for card_name, value_name, detail_name in metric_map:
        card = getattr(page, card_name, None)
        if isinstance(card, QFrame):
            card.setMinimumHeight(98)
            card.setStyleSheet(
                "QFrame{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
            )
        value = getattr(page, value_name, None)
        if isinstance(value, QLabel):
            value.setStyleSheet(
                f"color:{NAVY};font-size:21px;font-weight:950;border:none;background:transparent;"
            )
        detail = getattr(page, detail_name, None)
        if isinstance(detail, QLabel):
            detail.setStyleSheet(
                f"color:{MUTED};font-size:8px;border:none;background:transparent;"
            )

    # Tabs become the thin, airy mockup navigation instead of pill buttons.
    section_buttons = list(getattr(page, "section_buttons", []))
    original_show_section = page._show_section

    def show_section(index: int) -> None:
        original_show_section(index)
        for button_index, button in enumerate(section_buttons):
            selected = button_index == index
            button.setMinimumHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                (
                    "QPushButton{background:transparent;color:#0B7180;border:none;"
                    "border-bottom:3px solid #0B7180;border-radius:0;padding:8px 14px;font-weight:900;}"
                )
                if selected
                else (
                    "QPushButton{background:transparent;color:#17384E;border:none;"
                    "border-bottom:3px solid transparent;border-radius:0;padding:8px 14px;font-weight:750;}"
                    "QPushButton:hover{color:#0B7180;background:#F4FAFA;}"
                )
            )

    page._show_section = show_section
    show_section(page.sections.currentIndex())

    # Tables should look like the mockup: soft headers, clean rows, no heavy navy bar.
    for table in page.findChildren(QTableWidget):
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:1px solid #DCE5EA;"
            "border-radius:12px;gridline-color:transparent;selection-background-color:#EAF7F7;}"
            "QTableWidget::item{border-bottom:1px solid #EEF2F4;padding:7px;}"
            "QTableWidget::item:selected{background:#EAF7F7;color:#062B4F;}"
            "QHeaderView::section{background:#F7FAFC;color:#425D70;border:none;"
            "border-bottom:1px solid #DCE5EA;padding:9px;font-size:9px;font-weight:900;}"
        )
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setMinimumHeight(36)

    # Common action buttons: quiet secondary / teal primary.
    for name in (
        "org_refresh_button",
        "edit_policy_button",
        "member_role_button",
        "member_toggle_button",
        "member_revoke_button",
        "device_toggle_button",
        "device_revoke_button",
    ):
        button = getattr(page, name, None)
        if isinstance(button, QPushButton):
            button.setMinimumHeight(36)
            button.setStyleSheet(
                "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D6DE;"
                "border-radius:9px;padding:8px 14px;font-weight:800;}"
                "QPushButton:hover{background:#F3FAFA;color:#0B7180;border-color:#9AC7CA;}"
            )

    for name in ("invite_button",):
        button = getattr(page, name, None)
        if isinstance(button, QPushButton):
            button.setMinimumHeight(36)
            button.setStyleSheet(
                "QPushButton{background:#0B7180;color:#FFFFFF;border:1px solid #0B7180;"
                "border-radius:9px;padding:8px 15px;font-weight:900;}"
                "QPushButton:hover{background:#095E6B;border-color:#095E6B;}"
            )

    # Overview summary text areas become content, not bordered text boxes.
    for name in (
        "overview_policy",
        "overview_destinations",
        "policy_rules",
        "policy_destinations",
        "boundary_text",
        "org_summary",
        "sync_label",
        "member_help",
        "device_help",
    ):
        label = getattr(page, name, None)
        if isinstance(label, QLabel):
            label.setStyleSheet(
                f"color:{MUTED};font-size:9px;border:none;background:transparent;"
            )

    org_title = getattr(page, "org_title", None)
    if isinstance(org_title, QLabel):
        org_title.setStyleSheet(
            f"color:{NAVY};font-size:18px;font-weight:950;border:none;background:transparent;"
        )

    # The top-level cards should have generous spacing and rounded white surfaces.
    for frame in page.findChildren(QFrame):
        if frame in [getattr(page, name, None) for name, _, _ in metric_map]:
            continue
        if frame.objectName() in {"", "Card"} and frame.parent() is page:
            frame.setStyleSheet(
                "QFrame{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
            )
