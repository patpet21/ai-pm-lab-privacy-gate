from __future__ import annotations

"""Keep the approved Protect review surface authoritative after image/OCR support.

This module is deliberately a compatibility bridge only. It does not build a
second Protect or Drive UI: it keeps the proven review surface authoritative and
teaches the existing Drive browser that the central document engine now supports
PNG/JPG/JPEG images.
"""

from pathlib import Path
from types import MethodType

from PySide6.QtCore import QTimer


def _enable_drive_image_import() -> None:
    """Extend the existing Drive browser with the formats the pipeline now owns."""
    from ai_pm_lab_privacy_gate.ui import drive_browser

    drive_browser.SUPPORTED_SUFFIXES.update({".png", ".jpg", ".jpeg"})
    if getattr(drive_browser, "_privacygate_image_ocr_enabled", False):
        return

    previous_supported = drive_browser._supported

    def supported(remote) -> bool:
        # Drive files can be named simply "Untitled", so suffix-only checks are
        # insufficient. Accept only the image MIME types supported by the local
        # OCR pipeline; WEBP/TIFF/HEIC remain intentionally excluded from v1.
        if str(getattr(remote, "kind", "") or "").lower() in {
            "image/png",
            "image/jpeg",
            "image/jpg",
        }:
            return True
        suffix = Path(str(getattr(remote, "title", "") or "")).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg"}:
            return True
        return previous_supported(remote)

    drive_browser._supported = supported
    drive_browser._privacygate_image_ocr_enabled = True


def _restore_review_surface(page) -> None:
    if getattr(page, "current_document", None) is None:
        return

    focus = getattr(page, "focus_preview_button", None)
    if focus is not None and focus.isChecked():
        # The existing toggled signal owns the real layout transition. Reuse it
        # rather than duplicating the approved review/document layout logic.
        focus.setChecked(False)

    findings = getattr(page, "findings_card", None)
    if findings is not None:
        findings.setVisible(True)
        findings.setMaximumWidth(16777215)
        findings.setMaximumHeight(16777215)

    table = getattr(page, "findings_table", None)
    if table is not None:
        table.setVisible(True)

    # These are the established controls the user uses to inspect categories and
    # add exact local-only sensitive values. Never replace or recreate them.
    for name in (
        "categories_button",
        "reset_selections_button",
        "protect_all_button",
        "keep_all_button",
        "invert_selection_button",
        "add_sensitive_button",
    ):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.setVisible(True)

    workspace = getattr(page, "workspace", None)
    if workspace is not None and workspace.count() >= 2:
        workspace.setSizes([430, 1050])


def apply_protect_image_review_regression_fix(main_window) -> None:
    """Enable image import while preserving the existing Protect review UI."""
    _enable_drive_image_import()

    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_image_review_regression_fix_applied", False):
        return

    previous_analysis_ready = page._analysis_ready

    def analysis_ready(self, payload: object) -> None:
        previous_analysis_ready(payload)
        # Run after any queued review/preview work scheduled by the existing
        # controller so this only corrects final visibility/navigation state.
        QTimer.singleShot(0, lambda: _restore_review_surface(self))

    page._analysis_ready = MethodType(analysis_ready, page)
    page._image_review_regression_fix_applied = True
