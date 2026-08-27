from __future__ import annotations

import html
from pathlib import Path
from types import MethodType

from pptx import Presentation
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QTextBrowser


_DOCUMENT_KINDS = {"pdf", "docx", "xlsx", "pptx"}


def _pptx_slide_texts(path: Path) -> list[tuple[str, str]]:
    presentation = Presentation(str(path))
    slides: list[tuple[str, str]] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                for paragraph in shape.text_frame.paragraphs:
                    if paragraph.text.strip():
                        lines.append(paragraph.text)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    values = [cell.text.strip() for cell in row.cells]
                    if any(values):
                        lines.append(" | ".join(values))
        slides.append((f"Slide {index}", "\n".join(lines)))
    return slides


def _load_pptx_internal(view, path: Path, protected: bool) -> None:
    view.clear()
    for title, text in _pptx_slide_texts(path):
        browser = QTextBrowser()
        browser.setObjectName("OfficeDocumentView")
        escaped = html.escape(text).replace("\n", "<br>") or "&nbsp;"
        if protected:
            escaped = view._highlight(escaped, True)
        browser.setHtml(
            "<html><body style='font-family:Segoe UI;color:#102A43;background:#fff;margin:20px'>"
            f"<h3>{html.escape(title)}</h3><p>{escaped}</p></body></html>"
        )
        view.tabs.addTab(browser, title)


def apply_document_pipeline_v2_ui(main_window) -> None:
    """Expose PDF/DOCX/XLSX/PPTX/TXT uniformly in the existing Protect layout."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_document_pipeline_v2_applied", False):
        return

    page.pdf_path.setPlaceholderText("PDF, Word, Excel, PowerPoint or TXT")
    page.high_fidelity_button.setToolTip(
        "Use LibreOffice locally for a page-accurate Word, Excel or PowerPoint preview."
    )
    page.save_download_button.setToolTip(
        "Save locally and export the protected source-format copy plus a protected TXT companion."
    )

    def browse_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a document",
            "",
            "Supported documents (*.pdf *.docx *.xlsx *.pptx *.txt);;"
            "PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx);;"
            "PowerPoint files (*.pptx);;Text files (*.txt)",
        )
        if path:
            self.pdf_path.setText(path)
            self.input_tabs.setCurrentIndex(1)

    try:
        page.browse_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page._browse_document = MethodType(browse_document, page)
    page.browse_button.clicked.connect(page._browse_document)

    original_refresh = page._refresh_preview

    def refresh_preview(self, *args) -> None:
        original_refresh(*args)
        if self.current_document is not None and self.current_document.source_kind == "pptx":
            self.preview_tabs.setTabVisible(1, True)
            self._pdf_preview_timer.start()

    page._refresh_preview = MethodType(refresh_preview, page)

    original_comparison = page._update_document_comparison

    def update_document_comparison(self) -> None:
        if (
            self.current_document is None
            or self.current_result is None
            or self.current_document.source_path is None
            or self.current_document.source_kind != "pptx"
        ):
            original_comparison()
            return
        try:
            self.protected_pdf_document.close()
            self.original_pdf_document.close()
            protected_path = self._preview_directory / f"protected-office-{Path(self.current_document.source_path).stem}.pptx"
            self.service.save_protected_document(
                self.current_result,
                protected_path,
                source_document=self.current_document,
            )
            self.office_preview_options_widget.setVisible(True)
            self.high_fidelity_button.setVisible(self._libreoffice_available)
            self.install_libreoffice_button.setVisible(not self._libreoffice_available)
            if self._libreoffice_available and self.high_fidelity_button.isChecked():
                original_path = self._office_preview_renderer.render(
                    self.current_document.source_path, self._office_original_directory
                )
                protected_pdf = self._office_preview_renderer.render(
                    protected_path, self._office_protected_directory
                )
                self.original_view_stack.setCurrentIndex(0)
                self.protected_view_stack.setCurrentIndex(0)
                self._set_pdf_controls_enabled(True)
                self.original_pdf_document.load(str(original_path))
                self.protected_pdf_document.load(str(protected_pdf))
                self.comparison_note.setText(
                    "High-fidelity local PowerPoint rendering: original on the left and protected deck on the right."
                )
                self._set_pdf_page(0)
            else:
                self.high_fidelity_button.setChecked(False)
                self.libreoffice_note.setText(
                    "Built-in slide preview active. Install LibreOffice for page-accurate rendering."
                )
                _load_pptx_internal(self.original_office_view, self.current_document.source_path, False)
                _load_pptx_internal(self.protected_office_view, protected_path, True)
                self.original_office_view.synchronize_with(self.protected_office_view)
                self.original_view_stack.setCurrentIndex(1)
                self.protected_view_stack.setCurrentIndex(1)
                self._set_pdf_controls_enabled(False)
                self.comparison_note.setText(
                    "Built-in PowerPoint preview: original on the left and editable protected deck on the right."
                )
        except Exception as exc:
            self.preview_tabs.setTabToolTip(1, f"Preview unavailable: {exc}")
            self.comparison_note.setText(str(exc))
            self.preview_tabs.setCurrentIndex(0)
        else:
            self.preview_tabs.setTabToolTip(
                1, "Compare the local PowerPoint source with its protected editable copy."
            )
            self.preview_tabs.setCurrentIndex(1)

    try:
        page._pdf_preview_timer.timeout.disconnect()
    except (RuntimeError, TypeError):
        pass
    page._update_document_comparison = MethodType(update_document_comparison, page)
    page._pdf_preview_timer.timeout.connect(page._update_document_comparison)

    def save_and_download(self) -> None:
        if not self._confirm_residual_risk("downloading"):
            return
        document = self._save_to_library()
        if not document or not self.current_result or not self.current_document:
            return

        kind = self.current_document.source_kind
        labels = {
            "pdf": ("PDF", ".pdf"),
            "docx": ("Word", ".docx"),
            "xlsx": ("Excel", ".xlsx"),
            "pptx": ("PowerPoint", ".pptx"),
            "txt": ("Text", ".txt"),
            "text": ("Text", ".txt"),
        }
        label, suffix = labels.get(kind, ("Document", ".txt"))
        suggested = f"{document.title}_protected{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save protected {label}",
            suggested,
            f"{label} files (*{suffix})",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != suffix:
            destination = destination.with_suffix(suffix)

        if kind in {"text", "txt"}:
            self.service.save_protected_text(self.current_result, destination)
            QMessageBox.information(
                self,
                "Protected file exported",
                f"Protected TXT saved to:\n{destination}",
            )
            return

        self.service.save_protected_document(
            self.current_result,
            destination,
            source_document=self.current_document,
        )
        companion = destination.with_suffix(".txt")
        self.service.save_protected_text(self.current_result, companion)
        QMessageBox.information(
            self,
            "Protected files exported",
            f"Protected {suffix.upper().lstrip('.')} and TXT companion saved locally:\n"
            f"{destination}\n{companion}",
        )

    try:
        page.save_download_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page._save_and_download = MethodType(save_and_download, page)
    page.save_download_button.clicked.connect(page._save_and_download)

    page._document_pipeline_v2_applied = True
