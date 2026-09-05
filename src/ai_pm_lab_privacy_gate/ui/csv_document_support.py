from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QLabel


def install_csv_document_support() -> None:
    """Add CSV to the existing desktop Protect workflow without changing other formats."""
    from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage

    if getattr(ProtectionPage, "_privacygate_csv_support_installed", False):
        return

    original_build_ui = ProtectionPage._build_ui
    original_browse = ProtectionPage._browse_document
    original_download = ProtectionPage._save_and_download

    def build_ui(self) -> None:
        original_build_ui(self)
        self.pdf_path.setPlaceholderText("PDF, Word, Excel or CSV")
        for label in self.findChildren(QLabel):
            text = label.text()
            updated = text.replace(
                "PDF, Word or Excel",
                "PDF, Word, Excel or CSV",
            ).replace(
                "PDF, Word and Excel",
                "PDF, Word, Excel and CSV",
            )
            if updated != text:
                label.setText(updated)

    def browse_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a document",
            "",
            "Supported documents (*.pdf *.docx *.xlsx *.csv);;"
            "PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx);;CSV files (*.csv)",
        )
        if path:
            self.pdf_path.setText(path)
            self.input_tabs.setCurrentIndex(1)

    def save_and_download(self) -> None:
        if not self.current_document or self.current_document.source_kind != "csv":
            original_download(self)
            return
        if not self._confirm_residual_risk("downloading"):
            return
        document = self._save_to_library()
        if not document or not self.current_result:
            return
        suggested = f"{document.title}_protected.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save protected CSV",
            suggested,
            "CSV files (*.csv)",
        )
        if not path:
            return
        destination = path if path.lower().endswith(".csv") else path + ".csv"
        self.service.save_protected_document(
            self.current_result,
            destination,
            self.current_document,
        )

    ProtectionPage._build_ui = build_ui
    ProtectionPage._browse_document = browse_document
    ProtectionPage._save_and_download = save_and_download
    ProtectionPage._privacygate_csv_support_installed = True
    ProtectionPage._privacygate_csv_original_browse = original_browse
