from __future__ import annotations

from pathlib import Path
from types import MethodType

from ai_pm_lab_privacy_gate.ui.document_pipeline_v2_ui import _load_pptx_internal


_DOCUMENT_KINDS = {"pdf", "docx", "xlsx", "pptx"}


def _manifest_item(page, key: str):
    return next(
        (
            item
            for item in tuple(getattr(page, "_gmail_component_manifest", ()) or ())
            if str(item.get("key") or "") == key
        ),
        None,
    )


def _ensure_source_document(page, key: str):
    payload = getattr(page, "_gmail_component_sources", {}).get(key)
    if payload is not None:
        return payload

    component = _manifest_item(page, key)
    if component is None:
        return None
    if component.get("component_kind") == "body":
        document = page.service.document_from_text(str(component.get("text") or ""))
    else:
        path = str(component.get("path") or "")
        if not path:
            return None
        document = page.service.document_from_file(path)
    payload = {
        "document": document,
        "findings": (),
        "label": str(component.get("label") or "Source"),
        "component_kind": str(component.get("component_kind") or "attachment"),
    }
    page._gmail_component_sources[key] = payload
    return payload


def _show_unprotected_source(page, key: str) -> None:
    payload = _ensure_source_document(page, key)
    if payload is None:
        return
    document = payload["document"]
    page.current_document = document
    page.current_result = None

    if document.source_kind not in _DOCUMENT_KINDS or document.source_path is None:
        index = getattr(page, "_gmail_component_text_compare_index", 0)
        page.preview_tabs.setTabVisible(1, False)
        page.preview_tabs.setCurrentIndex(index)
        original = getattr(page, "_gmail_component_original_text", None)
        protected = getattr(page, "_gmail_component_protected_text", None)
        if original is not None:
            original.setPlainText(
                "\n\n".join(item.text for item in document.pages if item.text.strip())
            )
        if protected is not None:
            protected.setPlainText("Protect this source to create the safe copy preview.")
        return

    source = Path(document.source_path)
    page.preview_tabs.setTabVisible(1, True)
    page.preview_tabs.setCurrentIndex(1)
    page.original_pdf_document.close()
    page.protected_pdf_document.close()
    page.original_office_view.clear()
    page.protected_office_view.clear()

    if document.source_kind == "pdf":
        page.office_preview_options_widget.setVisible(False)
        page.original_view_stack.setCurrentIndex(0)
        page.protected_view_stack.setCurrentIndex(0)
        page._set_pdf_controls_enabled(True)
        page.original_pdf_document.load(str(source))
        page.comparison_note.setText(
            f"Original Gmail attachment · {payload.get('label', source.name)}. "
            "Protect to generate the safe copy on the right."
        )
        page._set_pdf_page(0)
        return

    page.office_preview_options_widget.setVisible(False)
    page.original_view_stack.setCurrentIndex(1)
    page.protected_view_stack.setCurrentIndex(1)
    page._set_pdf_controls_enabled(False)
    if document.source_kind in {"docx", "xlsx"}:
        page.original_office_view.load(source, protected=False)
    else:
        _load_pptx_internal(page.original_office_view, source, False)
    page.comparison_note.setText(
        f"Original Gmail attachment · {payload.get('label', source.name)}. "
        "Protect to generate the safe editable copy on the right."
    )


def apply_gmail_component_preview_polish(main_window) -> None:
    """Let Gmail source buttons open the original source immediately after import/scan."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_gmail_component_preview_polish", False):
        return
    selector = getattr(page, "_gmail_component_select", None)
    if not callable(selector):
        return
    page._gmail_component_preview_polish = True
    previous = selector

    def select_component(self, key: str) -> None:
        previous(key)
        if not tuple(getattr(self, "_gmail_component_manifest", ()) or ()):
            return
        result = getattr(self, "_gmail_component_results", {}).get(key)
        if result is not None:
            return
        _show_unprotected_source(self, key)
        metric = getattr(self, "_redesign_review_metric", None)
        payload = getattr(self, "_gmail_component_sources", {}).get(key, {})
        if metric is not None:
            metric.setText(f"Original source · {payload.get('label', 'Source')}")

    page._gmail_component_select = MethodType(select_component, page)
