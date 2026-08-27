from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ai_pm_lab_privacy_gate.ui.protect_session_upgrade import (
    _kind_label,
    _kind_suffix,
    _safe_pdf_bundle,
)


def apply_protect_session_runtime_fix(main_window) -> None:
    """Repair late-bound Qt signal handlers after the Protect session upgrade."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_protect_session_runtime_fix", False):
        return
    page._protect_session_runtime_fix = True

    # Reconnect row selection explicitly. The first handler preserves the
    # original page navigation/context behavior; the second adds source-aware
    # switching for a document + pasted-text session.
    try:
        page.findings_table.cellClicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page.findings_table.cellClicked.connect(page._finding_selected)

    def select_source(row_index: int, _column: int) -> None:
        if not getattr(page, "_protect_session_active", False):
            return
        checkbox = page.findings_table.item(row_index, 0)
        if checkbox is None:
            return
        finding_id = str(checkbox.data(Qt.ItemDataRole.UserRole) or "")
        if finding_id.startswith("text::"):
            page.preview_tabs.setCurrentIndex(0)
            return
        if finding_id.startswith("document::"):
            payload = page._protect_session_sources.get("document", {})
            document = payload.get("document")
            if document is not None and document.source_kind in {
                "pdf",
                "docx",
                "xlsx",
                "pptx",
            }:
                page.preview_tabs.setCurrentIndex(1)

    page.findings_table.cellClicked.connect(select_source)

    # Replace the redesign download closure with the unified document pipeline.
    # This keeps PPTX/TXT support and always returns the protected TXT companion.
    actions = getattr(page, "_redesign_action_buttons", ())
    if len(actions) < 2:
        return
    download_action = actions[1]
    try:
        download_action.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def download_current() -> None:
        if page.current_result is None or page.current_document is None:
            return
        begin = getattr(page, "_redesign_begin_operation", None)
        end = getattr(page, "_redesign_end_operation", None)
        if callable(begin):
            begin("verify", "Running final privacy check before download…")
        try:
            if not page._confirm_residual_risk("downloading"):
                return

            if getattr(page, "_protect_session_active", False):
                document_payload = page._protect_session_sources["document"]
                document = document_payload["document"]
                result = page._protect_session_results["document"]
            else:
                document = page.current_document
                result = page.current_result

            label = _kind_label(document.source_kind)
            suffix = _kind_suffix(document.source_kind)
            suggested = f"{page._derive_title()}_protected{suffix}"
            path, _ = QFileDialog.getSaveFileName(
                page,
                f"Save protected {label}",
                suggested,
                f"{label} files (*{suffix})",
            )
            if not path:
                return

            destination = Path(path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)

            if callable(begin):
                begin("export", f"Generating protected {label} + TXT locally…")
            try:
                outputs = _safe_pdf_bundle(page, document, result, destination)
                if outputs is None:
                    return
                main_output, companion = outputs
                extra_text = None
                if getattr(page, "_protect_session_active", False):
                    text_result = page._protect_session_results["text"]
                    extra_text = page.service.save_protected_text(
                        text_result,
                        Path(main_output).with_name(
                            f"{Path(main_output).stem}_pasted_text.txt"
                        ),
                    )
            finally:
                if callable(end):
                    end("export")

            paths = [str(main_output)]
            if companion != main_output:
                paths.append(str(companion))
            if extra_text is not None:
                paths.append(str(extra_text))
            QMessageBox.information(
                page,
                "Protected files exported",
                "Saved locally:\n\n" + "\n".join(paths),
            )
        finally:
            if callable(end):
                end("verify")

    download_action.clicked.connect(download_current)
