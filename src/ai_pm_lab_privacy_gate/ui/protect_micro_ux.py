from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication

from ai_pm_lab_privacy_gate.infrastructure.documents.colored_reflow_pdf import (
    _replacement_entities,
    write_colored_reflow_pdf,
)
from ai_pm_lab_privacy_gate.ui.office_internal_preview import OfficeInternalPreview


_DOCUMENT_KINDS = {"pdf", "docx", "xlsx", "pptx"}
_SOURCE_SWITCH_KEY = "protect.source-switch"


class _NamespaceAwareColors(dict):
    """Resolve PG source namespaces back to the canonical entity palette."""

    def get(self, key, default=None):
        value = super().get(key)
        if value is not None:
            return value
        raw = str(key or "")
        for entity in sorted(self.keys(), key=len, reverse=True):
            if raw.endswith("_" + entity):
                return super().get(entity, default)
        return default


def _install_namespace_aware_office_colors(main_window) -> None:
    for preview in main_window.findChildren(OfficeInternalPreview):
        if isinstance(preview.colors, _NamespaceAwareColors):
            continue
        preview.colors = _NamespaceAwareColors(preview.colors)


def _color_result_tokens(page, editor, result) -> None:
    """Apply category colors by exact token text, independent of namespaced offsets."""

    if editor is None or result is None:
        return
    text = str(getattr(result, "combined_text", "") or "")
    if editor.toPlainText() != text:
        editor.setPlainText(text)

    token_entities = _replacement_entities(
        tuple(getattr(result, "protected_spans", ()) or ())
    )
    for token, entity_type in token_entities.items():
        if not token:
            continue
        start = 0
        while True:
            start = text.find(token, start)
            if start < 0:
                break
            cursor = QTextCursor(editor.document())
            cursor.setPosition(start)
            cursor.setPosition(start + len(token), QTextCursor.MoveMode.KeepAnchor)
            formatting = QTextCharFormat()
            formatting.setBackground(QColor(page._entity_color(entity_type)))
            formatting.setForeground(QColor("#102A43"))
            formatting.setFontWeight(int(QFont.Weight.DemiBold))
            cursor.mergeCharFormat(formatting)
            start += len(token)


def _apply_result_token_colors(page, result) -> None:
    """Apply the canonical category palette to the main protected-text preview."""

    _color_result_tokens(page, getattr(page, "preview", None), result)


def _install_protected_text_colors(page) -> None:
    from ai_pm_lab_privacy_gate.ui import protect_view_experience as view

    if not getattr(view, "_privacygate_category_color_patch", False):
        view._privacygate_category_color_patch = True
        previous = view._render_protected_text

        def render_protected_text(target_page) -> None:
            previous(target_page)
            _key, _document, result, _label = view.resolve_active_source(target_page)
            _apply_result_token_colors(target_page, result)

        view._render_protected_text = render_protected_text

    # Gmail body/non-document comparison has its own editor and historically used
    # numeric spans. Namespacing makes those offsets stale, so use the exact token
    # text here as well while retaining the original renderer contract.
    from ai_pm_lab_privacy_gate.ui import gmail_component_session as gmail

    if not getattr(gmail, "_privacygate_category_color_patch", False):
        gmail._privacygate_category_color_patch = True

        def render_gmail_tokens(target_page, editor, result) -> None:
            _color_result_tokens(target_page, editor, result)

        gmail._render_tokens = render_gmail_tokens


def _install_colored_safe_reflow(page) -> None:
    service = getattr(page, "service", None)
    if service is None or getattr(service, "_privacygate_colored_safe_reflow", False):
        return
    service._privacygate_colored_safe_reflow = True
    previous = service.save_protected_pdf

    def save_protected_pdf(result, path, source_document=None):
        if source_document is None:
            return write_colored_reflow_pdf(service._pdf, result, path)
        return previous(result, path, source_document=source_document)

    service.save_protected_pdf = save_protected_pdf


def _source_label(page, key: str) -> str:
    payload = dict(getattr(page, "_gmail_component_sources", {}) or {}).get(key, {})
    label = str(payload.get("label") or "").strip()
    if label:
        return label
    for item in tuple(getattr(page, "_gmail_component_manifest", ()) or ()):
        if str(item.get("key") or "") == key:
            return str(item.get("label") or "Source")
    return "Source"


def _finish_source_switch(page, controller) -> None:
    if not getattr(page, "_privacygate_source_switch_waiting", False):
        return
    page._privacygate_source_switch_waiting = False
    controller.end(_SOURCE_SWITCH_KEY)


def _install_source_switch_loading(page, controller) -> None:
    if getattr(page, "_privacygate_source_switch_loading", False):
        return
    page._privacygate_source_switch_loading = True
    page._privacygate_source_switch_waiting = False

    timer = getattr(page, "_pdf_preview_timer", None)
    if timer is not None:
        timer.timeout.connect(lambda: _finish_source_switch(page, controller))

    selector = getattr(page, "_gmail_component_select", None)
    if callable(selector):
        previous_selector = selector

        def select_component(self, key: str):
            old_key = str(getattr(self, "_gmail_component_active_key", "") or "")
            if key == old_key:
                return previous_selector(key)

            current_controller = getattr(self, "_unified_loading", None)
            if current_controller is None:
                return previous_selector(key)

            label = _source_label(self, key)
            current_controller.begin(
                _SOURCE_SWITCH_KEY,
                "Opening source preview",
                f"Loading {label} locally…",
            )
            self._privacygate_source_switch_waiting = True
            QApplication.processEvents()
            try:
                value = previous_selector(key)
            except Exception:
                self._privacygate_source_switch_waiting = False
                current_controller.end(_SOURCE_SWITCH_KEY)
                raise

            payload = dict(getattr(self, "_gmail_component_sources", {}) or {}).get(key, {})
            document = payload.get("document")
            result = dict(getattr(self, "_gmail_component_results", {}) or {}).get(key)
            waits_for_document_preview = bool(
                result is not None
                and document is not None
                and getattr(document, "source_kind", "") in _DOCUMENT_KINDS
                and timer is not None
                and timer.isActive()
            )
            if not waits_for_document_preview:
                QTimer.singleShot(
                    120,
                    lambda: _finish_source_switch(self, current_controller),
                )
            return value

        page._gmail_component_select = MethodType(select_component, page)

    from ai_pm_lab_privacy_gate.ui import protect_view_experience as view

    if not getattr(view, "_privacygate_local_source_loading_patch", False):
        view._privacygate_local_source_loading_patch = True
        previous_activate = view._activate_local_source

        def activate_local_source(target_page, key: str) -> None:
            if tuple(getattr(target_page, "_gmail_component_manifest", ()) or ()):
                previous_activate(target_page, key)
                return
            old_key = str(getattr(target_page, "_privacygate_active_source_key", "") or "")
            results = dict(getattr(target_page, "_protect_session_results", {}) or {})
            if key == old_key or key not in results:
                previous_activate(target_page, key)
                return

            target_controller = getattr(target_page, "_unified_loading", None)
            if target_controller is None:
                previous_activate(target_page, key)
                return

            label = "document" if key == "document" else "pasted text"
            target_controller.begin(
                _SOURCE_SWITCH_KEY,
                "Opening source preview",
                f"Loading {label} locally…",
            )
            target_page._privacygate_source_switch_waiting = True
            QApplication.processEvents()
            previous_activate(target_page, key)

            payload = dict(getattr(target_page, "_protect_session_sources", {}) or {}).get(key, {})
            document = payload.get("document")
            result = results.get(key)
            local_timer = getattr(target_page, "_pdf_preview_timer", None)
            waits_for_document_preview = bool(
                result is not None
                and document is not None
                and getattr(document, "source_kind", "") in _DOCUMENT_KINDS
                and local_timer is not None
                and local_timer.isActive()
            )
            if not waits_for_document_preview:
                QTimer.singleShot(
                    120,
                    lambda: _finish_source_switch(target_page, target_controller),
                )

        view._activate_local_source = activate_local_source


def apply_protect_micro_ux(main_window) -> None:
    """Small post-stability UX fixes that do not change Protect business logic."""

    page = getattr(main_window, "protection_page", None)
    controller = getattr(main_window, "_unified_loading", None)
    if page is None or controller is None or getattr(page, "_protect_micro_ux", False):
        return
    page._protect_micro_ux = True

    _install_namespace_aware_office_colors(main_window)
    _install_protected_text_colors(page)
    _install_colored_safe_reflow(page)
    _install_source_switch_loading(page, controller)
