from __future__ import annotations

from pathlib import Path
from types import MethodType


def _gmail_attachment_paths(page) -> set[str]:
    paths: set[str] = set()
    for component in tuple(getattr(page, "_gmail_component_manifest", ()) or ()):
        if component.get("component_kind") != "attachment":
            continue
        raw = str(component.get("path") or "").strip()
        if not raw:
            continue
        try:
            paths.add(str(Path(raw).resolve(strict=False)))
        except OSError:
            paths.add(raw)
    return paths


def _gmail_body_text(page) -> str | None:
    for component in tuple(getattr(page, "_gmail_component_manifest", ()) or ()):
        if component.get("component_kind") == "body":
            return str(component.get("text") or "")
    return None


def _source_state_reset_suspended(page) -> bool:
    """Return True while a connector is atomically replacing Protect sources."""
    return bool(getattr(page, "_protect_source_transaction", False))


def _reset_gmail_state(page, *, clear_external_metadata: bool = True) -> None:
    """Drop Gmail-only routing state without touching the newly selected source."""
    page._gmail_component_manifest = ()
    page._gmail_component_skipped = ()
    page._gmail_component_sources = {}
    page._gmail_component_results = {}
    page._gmail_component_active_key = ""
    page._gmail_package_active = False
    page._gmail_component_extra_paths = []
    page._gmail_package_components = ()

    if clear_external_metadata:
        metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
        if metadata.get("provider") == "gmail":
            page._external_source_metadata = {}
            page._external_source_name = ""

    page.current_document = None
    page.current_findings = ()
    page.current_result = None
    page._last_residual = ()
    page.findings_table.setRowCount(0)
    page.category_list.clear()
    page.preview.clear()
    page._set_result_actions(False)

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.setEnabled(False)
    final_actions = getattr(page, "_redesign_final_actions", None)
    if final_actions is not None:
        final_actions.hide()
    set_final = getattr(page, "_redesign_set_final_actions", None)
    if callable(set_final):
        set_final(False)

    try:
        from ai_pm_lab_privacy_gate.ui.gmail_component_session import (
            _refresh_component_strip,
        )

        _refresh_component_strip(page)
    except Exception:
        strip = getattr(page, "_gmail_component_strip", None)
        if strip is not None:
            strip.hide()


def _clear_preview_surfaces(page) -> None:
    """Hard-clear cached PDF/Office/text renderers after the user presses Clear."""
    try:
        page._pdf_preview_timer.stop()
    except Exception:
        pass

    for document in (
        getattr(page, "original_pdf_document", None),
        getattr(page, "protected_pdf_document", None),
    ):
        if document is not None:
            try:
                document.close()
            except Exception:
                pass

    # QPdfView can retain the last rendered page after QPdfDocument.close().
    # Detach and immediately reattach the now-empty document to flush that cache
    # while preserving the objects expected by later previews.
    pairs = (
        (
            getattr(page, "original_pdf_view", None),
            getattr(page, "original_pdf_document", None),
        ),
        (
            getattr(page, "protected_pdf_view", None),
            getattr(page, "protected_pdf_document", None),
        ),
    )
    for view, document in pairs:
        if view is None:
            continue
        try:
            view.setDocument(None)
            if document is not None:
                view.setDocument(document)
        except Exception:
            pass

    for office in (
        getattr(page, "original_office_view", None),
        getattr(page, "protected_office_view", None),
    ):
        if office is not None:
            try:
                office.clear()
            except Exception:
                pass

    for editor_name in (
        "_gmail_component_original_text",
        "_gmail_component_protected_text",
    ):
        editor = getattr(page, editor_name, None)
        if editor is not None:
            editor.clear()

    preview = getattr(page, "preview", None)
    if preview is not None:
        preview.clear()

    tabs = getattr(page, "preview_tabs", None)
    if tabs is not None:
        try:
            if tabs.count() > 1:
                tabs.setTabVisible(1, False)
            tabs.setCurrentIndex(0)
        except Exception:
            pass

    note = getattr(page, "comparison_note", None)
    if note is not None:
        note.setText(
            "Original source on the left. The secure protected copy will appear on the right."
        )
    fidelity = getattr(page, "_protect_fidelity_status", None)
    if fidelity is not None:
        fidelity.setText("Preview fidelity · waiting for a document")

    preview_path = getattr(page, "_preview_path", None)
    if preview_path is not None:
        try:
            Path(preview_path).unlink(missing_ok=True)
        except OSError:
            pass
        page._preview_path = None


def apply_protect_source_state_reset(main_window) -> None:
    """Make Protect source switching transactional instead of sticky.

    A Gmail component manifest previously remained active after the user loaded a
    Drive/local document.  Because the Gmail scan wrapper checks that manifest
    first, Scan kept re-running the old email package.  This runtime guard clears
    Gmail routing state as soon as a genuinely different document or pasted text
    source is selected.  Clear also flushes Qt's cached document renderers.

    Connector imports may update compatibility widgets in several steps.  Those
    writes are wrapped in ``_protect_source_transaction`` so the reset listeners
    do not destroy a partially-built multi-source package mid-import.
    """
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_protect_source_state_reset", False):
        return
    page._protect_source_state_reset = True
    page._protect_source_transaction = False

    def document_changed(value: str) -> None:
        if _source_state_reset_suspended(page):
            return
        manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
        if not manifest:
            return
        allowed = _gmail_attachment_paths(page)
        raw = str(value or "").strip()
        if not raw:
            # Empty document is valid only for a body-only Gmail package.
            if allowed:
                _reset_gmail_state(page)
            return
        try:
            resolved = str(Path(raw).resolve(strict=False))
        except OSError:
            resolved = raw
        if resolved not in allowed:
            _reset_gmail_state(page)

    def text_changed() -> None:
        if _source_state_reset_suspended(page):
            return
        manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
        if not manifest:
            return
        expected = _gmail_body_text(page)
        current = page.text_input.toPlainText()
        if expected is None:
            if current.strip():
                _reset_gmail_state(page)
            return
        if current != expected:
            _reset_gmail_state(page)

    page.pdf_path.textChanged.connect(document_changed)
    page.text_input.textChanged.connect(text_changed)

    previous_clear = page.clear

    def clear(self) -> None:
        # Clear routing first so text/path signals emitted by the legacy clear
        # cannot re-enter the Gmail package path.
        self._protect_source_transaction = True
        try:
            _reset_gmail_state(self)
            previous_clear()
            _reset_gmail_state(self)
            _clear_preview_surfaces(self)
        finally:
            self._protect_source_transaction = False

        helper = getattr(self, "_protect_session_source_helper", None)
        if helper is not None:
            helper.setText(
                "Add a document, pasted text, or both. A ✓ means that source will be "
                "included in the next local scan."
            )

    try:
        page.clear_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    page.clear = MethodType(clear, page)
    page.clear_button.clicked.connect(page.clear)
