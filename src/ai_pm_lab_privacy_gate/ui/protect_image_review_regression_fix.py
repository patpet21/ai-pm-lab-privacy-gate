from __future__ import annotations

"""Keep the approved Protect review surface authoritative after document analysis.

The image/OCR extension must not own navigation state.  In particular it must not
leave Protect in the legacy full-document focus mode, because that mode hides the
existing findings/tags/manual-sensitive controls.  This compatibility layer runs
last in the approved Protect refinement suite and restores the normal review
surface after every completed analysis while preserving the user's ability to
enter full-document view manually afterwards.
"""

from types import MethodType

from PySide6.QtCore import QTimer


def _restore_review_surface(page) -> None:
    if getattr(page, "current_document", None) is None:
        return

    focus = getattr(page, "focus_preview_button", None)
    if focus is not None and focus.isChecked():
        # The existing toggled signal owns the real layout transition.  Reuse it
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
    # add exact local-only sensitive values.  Never replace or recreate them.
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
    """Prevent OCR/image support from hiding the existing Protect review UI."""
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
