from __future__ import annotations

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication, QTableWidget

from ai_pm_lab_privacy_gate.ui.office_internal_preview import OfficeInternalPreview


def test_xlsx_preview_supports_merged_cells_in_first_row(tmp_path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Register"
    worksheet.merge_cells("A1:C1")
    worksheet["A1"] = "Project initiation register"
    worksheet["A2"] = "Owner"
    worksheet["B2"] = "[[PG_PERSON_001]]"
    source = tmp_path / "merged-header.xlsx"
    workbook.save(source)

    owns_app = QApplication.instance() is None
    app = QApplication.instance() or QApplication([])
    preview = OfficeInternalPreview({"PERSON": "#DDE7FF"})
    preview.load(source, protected=True)

    assert preview.tabs.count() == 1
    table = preview.tabs.widget(0)
    assert isinstance(table, QTableWidget)
    assert table.horizontalHeaderItem(0).text() == "A"
    assert table.horizontalHeaderItem(1).text() == "B"
    assert table.columnSpan(0, 0) == 3
    assert table.item(1, 1).text() == "[[PG_PERSON_001]]"
    assert preview.focus_location("Register!B2") is True
    assert preview.tabs.currentIndex() == 0
    assert table.currentRow() == 1
    assert table.currentColumn() == 1
    preview.close()
    app.processEvents()
    if owns_app:
        app.quit()
