from __future__ import annotations

"""Color-coherent, easier-to-scan review table for Protect.

The underlying QTableWidgetItems remain untouched as the authoritative review state.
Colored pills are cell widgets layered over the existing Type item so all existing
filters, category selectors, checkboxes and protection callbacks continue to work.
"""

from types import MethodType

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout, QWidget

from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import BLUE, BLUE_SOFT, BORDER, INK, MUTED, TEXT


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear(child)


def _display_name(entity_type: str) -> str:
    aliases = {
        "EMAIL_ADDRESS": "Email",
        "PHONE_NUMBER": "Phone",
        "MONEY_AMOUNT": "Money amount",
        "STREET_ADDRESS": "Street address",
        "PROPERTY_IDENTIFIER": "Property ID",
        "US_BANK_NUMBER": "Bank account",
        "US_ROUTING_NUMBER": "Routing number",
    }
    return aliases.get(entity_type, entity_type.replace("_", " ").title())


def _type_pill(page, entity_type: str, *, manual: bool = False) -> QWidget:
    host = QWidget()
    host.setStyleSheet("background:transparent;border:none;")
    row = QHBoxLayout(host)
    row.setContentsMargins(5, 3, 5, 3)
    row.setSpacing(4)
    label = QLabel(_display_name(entity_type) + ("  ·  Manual" if manual else ""))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{page._entity_color(entity_type)};color:#102A43;"
        "border:1px solid rgba(16,42,67,0.08);border-radius:8px;"
        "padding:4px 7px;font-size:7.5px;font-weight:850;"
    )
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return host


def _ensure_legend(page) -> QFrame | None:
    existing = getattr(page, "_protect_2026_findings_legend", None)
    if existing is not None:
        return existing
    card = getattr(page, "findings_card", None)
    layout = card.layout() if card is not None else None
    if not isinstance(layout, QVBoxLayout):
        return None
    table: QTableWidget = page.findings_table
    index = layout.indexOf(table)
    if index < 0:
        return None

    panel = QFrame(objectName="Protect2026FindingsLegend")
    panel.setStyleSheet(
        "QFrame#Protect2026FindingsLegend{background:#F8FAFC;border:1px solid #EAECF0;"
        "border-radius:9px;}"
    )
    row = QHBoxLayout(panel)
    row.setContentsMargins(10, 6, 10, 6)
    row.setSpacing(6)
    title = QLabel("Detected categories")
    title.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;font-weight:850;background:transparent;border:none;"
    )
    row.addWidget(title)
    chips = QHBoxLayout()
    chips.setContentsMargins(0, 0, 0, 0)
    chips.setSpacing(5)
    row.addLayout(chips, 1)
    panel._protect_chips_layout = chips
    layout.insertWidget(index, panel)
    page._protect_2026_findings_legend = panel
    return panel


def _render_legend(page) -> None:
    panel = _ensure_legend(page)
    if panel is None:
        return
    layout = getattr(panel, "_protect_chips_layout", None)
    if layout is None:
        return
    _clear(layout)

    entity_types: list[str] = []
    for finding in tuple(getattr(page, "current_findings", ()) or ()):
        entity_type = str(getattr(finding, "entity_type", "") or "")
        if entity_type and entity_type not in entity_types:
            entity_types.append(entity_type)
    for entity_type in entity_types[:8]:
        label = QLabel(_display_name(entity_type))
        label.setStyleSheet(
            f"background:{page._entity_color(entity_type)};color:#102A43;"
            "border:1px solid rgba(16,42,67,0.08);border-radius:7px;"
            "padding:3px 6px;font-size:7px;font-weight:800;"
        )
        layout.addWidget(label)
    if len(entity_types) > 8:
        more = QLabel(f"+{len(entity_types) - 8} more")
        more.setStyleSheet(
            "background:#F2F4F7;color:#667085;border:1px solid #E4E7EC;border-radius:7px;"
            "padding:3px 6px;font-size:7px;font-weight:800;"
        )
        layout.addWidget(more)
    layout.addStretch(1)
    panel.setVisible(bool(entity_types))


def _decorate_findings(page) -> None:
    table: QTableWidget = page.findings_table
    table.setAlternatingRowColors(False)
    table.setMinimumHeight(260)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setStyleSheet(
        "QTableWidget{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;border-radius:10px;"
        "gridline-color:#F2F4F7;font-size:8px;selection-background-color:#EEF4FF;selection-color:#101828;}"
        "QTableWidget::item{padding:6px;border-bottom:1px solid #F2F4F7;}"
        "QTableWidget::item:selected{background:#EEF4FF;color:#101828;}"
        "QHeaderView::section{background:#F8FAFC;color:#667085;border:none;border-bottom:1px solid #EAECF0;"
        "padding:8px;font-size:7.5px;font-weight:900;}"
    )

    for row in range(table.rowCount()):
        type_item = table.item(row, 1)
        check_item = table.item(row, 0)
        if type_item is None:
            continue
        entity_type = str(type_item.text() or "").strip()
        finding_id = str(check_item.data(Qt.ItemDataRole.UserRole) or "") if check_item is not None else ""
        type_item.setBackground(QColor("#FFFFFF"))
        table.setCellWidget(row, 1, _type_pill(page, entity_type, manual=finding_id.startswith("manual-")))

    _render_legend(page)

    for label in page.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text == "Detected items":
            label.setStyleSheet(
                f"color:{INK};font-size:14px;font-weight:950;background:transparent;border:none;"
            )
        elif text == "Checked = protect | Unchecked = keep":
            label.setText("✓ Checked = protect     ○ Unchecked = keep")
            label.setStyleSheet(
                f"background:{BLUE_SOFT};color:{BLUE};border:none;border-radius:7px;"
                "padding:5px 8px;font-size:8px;font-weight:850;"
            )
        elif text == "Select a row to inspect it":
            label.setText("Select a row for context and page location")
            label.setStyleSheet(
                f"color:{MUTED};font-size:8px;background:transparent;border:none;"
            )

    page.finding_context.setStyleSheet(
        "background:#F8FAFC;color:#344054;border:1px solid #EAECF0;border-radius:9px;"
        "padding:9px 11px;font-size:8.5px;"
    )
    page.add_sensitive_button.setText("+ Add missed sensitive value")
    page.add_sensitive_button.setMinimumHeight(34)
    page.add_sensitive_button.setToolTip(
        "Add exact text the automatic detector missed. The value stays local and the protected copy is regenerated."
    )

    page.categories_button.setMinimumHeight(34)
    page.protect_all_button.setMinimumHeight(34)
    page.keep_all_button.setMinimumHeight(34)
    page.invert_selection_button.setMinimumHeight(34)
    page.reset_selections_button.setMinimumHeight(34)

    # The preview legend already uses _entity_color; make it readable enough to
    # function as the same visual language as these table pills.
    page.color_legend.setStyleSheet(
        "background:#F8FAFC;color:#344054;border:1px solid #E4E7EC;border-radius:9px;"
        "padding:7px 9px;font-size:8px;"
    )


def apply_mockup_protect_findings_refinement_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_findings_refined", False)):
        return
    page._protect_2026_findings_refined = True

    previous = page._populate_findings

    def populate_and_decorate(self) -> None:
        previous()
        _decorate_findings(self)

    page._populate_findings = MethodType(populate_and_decorate, page)
    _decorate_findings(page)
