from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QLayout


def _find_owner_layout(layout: QLayout | None, widget) -> QLayout | None:
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        item = layout.itemAt(index)
        child_layout = item.layout()
        found = _find_owner_layout(child_layout, widget)
        if found is not None:
            return found
        child_widget = item.widget()
        if child_widget is not None:
            found = _find_owner_layout(child_widget.layout(), widget)
            if found is not None:
                return found
    return None


def _install_csv_entry_surface_support() -> None:
    """Expose CSV in the final Protect empty-state without replacing that UI layer."""
    from ai_pm_lab_privacy_gate.ui import mockup_protect_entry_surface_2026 as entry_surface

    entry_surface.SUPPORTED_DROP_SUFFIXES.add(".csv")
    if getattr(entry_surface, "_privacygate_csv_entry_surface_installed", False):
        return

    original_build_empty_state = entry_surface._build_empty_state

    def build_empty_state(page):
        surface = original_build_empty_state(page)
        root = surface.layout()

        choose = getattr(page, "_protect_empty_choose", None)
        upload = getattr(page, "_protect_empty_upload", None)
        if choose is not None and upload is not None:
            actions = _find_owner_layout(root, choose)
            if actions is not None and actions.indexOf(upload) < 0:
                actions.insertWidget(actions.indexOf(choose) + 1, upload)
                actions.setSpacing(10)
            upload.setMaximumWidth(180)
            upload.setMinimumWidth(145)
            upload.show()

            # Use a dedicated full-format picker here. Later presentation layers
            # can replace the legacy browse callback, but this visible local-upload
            # action must always keep every unified desktop format, including CSV.
            try:
                upload.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass

            def upload_local_file() -> None:
                path, _ = QFileDialog.getOpenFileName(
                    page,
                    "Choose a document",
                    "",
                    "Supported documents (*.pdf *.docx *.xlsx *.pptx *.csv *.txt *.png *.jpg *.jpeg);;"
                    "PDF files (*.pdf);;Word files (*.docx);;Excel files (*.xlsx);;"
                    "PowerPoint files (*.pptx);;CSV files (*.csv);;Text files (*.txt);;"
                    "Image files (*.png *.jpg *.jpeg)",
                )
                if not path:
                    return
                page._protect_entry_force_empty = False
                document_mode = getattr(page, "_redesign_document_mode", None)
                paste_mode = getattr(page, "_redesign_paste_mode", None)
                if document_mode is not None:
                    document_mode.setChecked(True)
                if paste_mode is not None:
                    paste_mode.setChecked(False)
                page.pdf_path.setText(path)
                page.pdf_path.setToolTip(path)
                try:
                    page.input_tabs.setCurrentIndex(1)
                except Exception:
                    pass

            upload.clicked.connect(upload_local_file)

        formats_label = None
        if root is not None:
            for label in surface.findChildren(QLabel):
                if label.text().strip() == "Supported local formats":
                    formats_label = label
                    break

        if root is not None and formats_label is not None:
            # The approved surface created the drag hint but never inserted it.
            # Mount a visible hint immediately above the format badges.
            hint = QLabel("or drag & drop a local file here", surface)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                "color:#096E75;font-size:8.5px;font-weight:800;"
                "background:transparent;border:none;"
            )
            insert_at = root.indexOf(formats_label)
            root.insertWidget(max(0, insert_at), hint)
            page._privacygate_csv_drag_hint = hint

            # Find the existing badge row and add CSV before its trailing stretch.
            for index in range(root.count()):
                nested = root.itemAt(index).layout()
                if nested is None:
                    continue
                labels: set[str] = set()
                for child_index in range(nested.count()):
                    widget = nested.itemAt(child_index).widget()
                    if widget is None:
                        continue
                    labels.update(
                        child.text().strip()
                        for child in widget.findChildren(QLabel)
                        if child.text().strip()
                    )
                if {"PDF", "DOCX", "XLSX", "TXT"}.issubset(labels) and "CSV" not in labels:
                    csv_chip = entry_surface._format_chip("CSV", "#0B7180", "#E8F6F6")
                    nested.insertWidget(max(1, nested.count() - 1), csv_chip)
                    page._privacygate_csv_format_chip = csv_chip
                    break

        subtitle = getattr(page, "_protect_empty_source_subtitle", None)
        context_bar = getattr(page, "_managed_workspace_context_bar", None)

        def refresh_local_copy(*_args) -> None:
            if subtitle is None:
                return
            provider = ""
            if context_bar is not None:
                provider = str(context_bar.source_combo.currentData() or "")
            if provider == "gmail":
                subtitle.setText(
                    "Choose an email from Gmail, upload a local file, or switch to Paste text."
                )
            elif provider == "google_drive":
                subtitle.setText(
                    "Choose a Drive file, upload a local file, or switch to Paste text."
                )
            else:
                subtitle.setText(
                    "Choose a source above, upload a local file, or drag & drop it here."
                )

        if context_bar is not None:
            context_bar.source_combo.currentIndexChanged.connect(refresh_local_copy)
        refresh_local_copy()
        return surface

    entry_surface._build_empty_state = build_empty_state
    entry_surface._privacygate_csv_entry_surface_installed = True


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
    _install_csv_entry_surface_support()
