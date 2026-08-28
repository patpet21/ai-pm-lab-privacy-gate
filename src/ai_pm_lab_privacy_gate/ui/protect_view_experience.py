from __future__ import annotations

"""Make Protect source/view navigation explicit and keep protected text reliable.

This module deliberately does not own detection/protection logic.  It resolves
whatever source/result the existing local/Gmail/Drive runtimes already produced,
then makes the visible view controls truthful and easier to understand.
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B858A"
TEAL_DARK = "#096E75"
MUTED = "#61798A"
BORDER = "#D4E1E9"

_DOCUMENT_KINDS = {"pdf", "docx", "xlsx", "pptx"}


def resolve_active_source(page):
    """Return (key, document, result, label) for the source currently being viewed."""

    gmail_results = dict(getattr(page, "_gmail_component_results", {}) or {})
    gmail_sources = dict(getattr(page, "_gmail_component_sources", {}) or {})
    if gmail_results:
        key = str(getattr(page, "_gmail_component_active_key", "") or "")
        if key not in gmail_results:
            key = next(iter(gmail_results), "")
        payload = gmail_sources.get(key, {})
        document = payload.get("document")
        result = gmail_results.get(key)
        label = str(payload.get("label") or "Source")
        return key, document, result, label

    session_results = dict(getattr(page, "_protect_session_results", {}) or {})
    session_sources = dict(getattr(page, "_protect_session_sources", {}) or {})
    if session_results:
        preferred = str(getattr(page, "_privacygate_active_source_key", "") or "")
        if preferred not in session_results:
            current_document = getattr(page, "current_document", None)
            source_path = getattr(current_document, "source_path", None)
            if "document" in session_results and source_path is not None:
                preferred = "document"
            elif "text" in session_results and getattr(current_document, "source_kind", "") == "text":
                preferred = "text"
            elif "document" in session_results:
                preferred = "document"
            else:
                preferred = next(iter(session_results), "")
        payload = session_sources.get(preferred, {})
        document = payload.get("document")
        result = session_results.get(preferred)
        label = str(payload.get("label") or ("Pasted text" if preferred == "text" else "Document"))
        return preferred, document, result, label

    document = getattr(page, "current_document", None)
    result = getattr(page, "current_result", None)
    metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
    source_path = getattr(document, "source_path", None) if document is not None else None
    label = str(metadata.get("item_title") or "").strip()
    if not label and source_path is not None:
        label = str(getattr(source_path, "name", source_path))
    if not label:
        label = "Pasted text" if getattr(document, "source_kind", "") == "text" else "Current source"
    return "source", document, result, label


def protected_text_for_active_source(page) -> str:
    """Return exactly the protected text belonging to the active source."""

    _key, _document, result, _label = resolve_active_source(page)
    if result is None:
        return ""
    return str(getattr(result, "combined_text", "") or "")


def _render_protected_text(page) -> None:
    key, document, result, label = resolve_active_source(page)
    preview = getattr(page, "preview", None)
    if preview is None:
        return

    if document is not None:
        page.current_document = document
    if result is not None:
        page.current_result = result

    text = protected_text_for_active_source(page)
    if text:
        preview.setPlainText(text)
        preview.setToolTip(f"Protected text for {label}")
    else:
        preview.setPlainText(
            "Protected text is not available yet for this source. Run Scan & Protect first."
        )
        preview.setToolTip("Run Scan & Protect to create the protected text view.")

    preview.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D2DEE7;"
        "border-radius:9px;padding:14px;font-size:12px;selection-background-color:#D8EEEE;}"
    )
    page._privacygate_active_source_key = key


def _open_protected_text(page) -> None:
    _render_protected_text(page)
    page.preview_tabs.setCurrentIndex(0)


def _open_original_protected(page) -> None:
    key, document, result, _label = resolve_active_source(page)
    if document is not None:
        page.current_document = document
    if result is not None:
        page.current_result = result
    page._privacygate_active_source_key = key

    # Gmail body/non-document sources have their dedicated text comparison tab.
    gmail_compare = getattr(page, "_gmail_component_text_compare_index", None)
    if (
        dict(getattr(page, "_gmail_component_results", {}) or {})
        and document is not None
        and getattr(document, "source_kind", "") not in _DOCUMENT_KINDS
        and gmail_compare is not None
    ):
        page.preview_tabs.setCurrentIndex(int(gmail_compare))
        return

    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabVisible(1, True)
        page.preview_tabs.setCurrentIndex(1)
        if (
            document is not None
            and result is not None
            and getattr(document, "source_kind", "") in _DOCUMENT_KINDS
        ):
            try:
                page._pdf_preview_timer.start()
            except Exception:
                pass


def _session_source_available(page, key: str) -> bool:
    sources = dict(getattr(page, "_protect_session_sources", {}) or {})
    if key in sources:
        return True
    if key == "document":
        return bool(str(page.pdf_path.text() or "").strip())
    if key == "text":
        return bool(str(page.text_input.toPlainText() or "").strip())
    return False


def _activate_local_source(page, key: str) -> None:
    # Gmail source selection is owned by the Email contents chips, not these
    # generic Document/Paste controls.
    if tuple(getattr(page, "_gmail_component_manifest", ()) or ()):
        return

    sources = dict(getattr(page, "_protect_session_sources", {}) or {})
    results = dict(getattr(page, "_protect_session_results", {}) or {})
    payload = sources.get(key)
    if payload is None:
        return

    page._privacygate_active_source_key = key
    document = payload.get("document")
    result = results.get(key)
    if document is not None:
        page.current_document = document
    if result is not None:
        page.current_result = result

    if page.preview_tabs.currentIndex() == 0:
        _render_protected_text(page)
    elif key == "document" and result is not None:
        try:
            page._pdf_preview_timer.start()
        except Exception:
            pass


def _sync_source_controls(page) -> None:
    document_button = getattr(page, "_redesign_document_mode", None)
    paste_button = getattr(page, "_redesign_paste_mode", None)
    if document_button is None or paste_button is None:
        return

    # Gmail has its own source strip. Keep the generic buttons usable for the
    # underlying compatibility UI but do not reinterpret them as Gmail sources.
    if tuple(getattr(page, "_gmail_component_manifest", ()) or ()):
        document_button.setEnabled(True)
        paste_button.setEnabled(True)
        return

    results = dict(getattr(page, "_protect_session_results", {}) or {})
    has_result = bool(results or getattr(page, "current_result", None) is not None)
    has_document = _session_source_available(page, "document")
    has_text = _session_source_available(page, "text")

    # Before Scan, both controls remain available because they are also entry
    # points for adding content. After a result exists, they become truthful
    # source selectors and an absent source cannot be selected accidentally.
    if has_result:
        document_button.setEnabled(has_document)
        paste_button.setEnabled(has_text)
        document_button.setToolTip(
            "View the document source used in this Scan & Protect session."
            if has_document
            else "No document source was included in this protected session."
        )
        paste_button.setToolTip(
            "View the pasted-text source used in this Scan & Protect session."
            if has_text
            else "No pasted text was included. Use Paste text above to add it, then run Scan & Protect again."
        )

        active = str(getattr(page, "_privacygate_active_source_key", "") or "")
        if active not in results:
            active = "document" if "document" in results else "text" if "text" in results else ""
            page._privacygate_active_source_key = active
        if active:
            document_button.setChecked(active == "document")
            paste_button.setChecked(active == "text")
            _activate_local_source(page, active)
    else:
        document_button.setEnabled(True)
        paste_button.setEnabled(True)


def _style_source_and_view_bar(page) -> None:
    if page.preview_tabs.count() > 0:
        page.preview_tabs.setTabText(0, "Protected text")
        page.preview_tabs.setTabToolTip(
            0,
            "Read the protected text for the source currently selected under SOURCE.",
        )
    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabText(1, "Original + Protected")
        page.preview_tabs.setTabToolTip(
            1,
            "See the original source beside the protected copy.",
        )

    bar = page.preview_tabs.tabBar()
    bar.setStyleSheet(
        "QTabBar::tab{background:#FFFFFF;color:#17384E;border:1px solid #CFDCE5;"
        "border-radius:8px;padding:8px 14px;margin-right:6px;font-size:10px;font-weight:800;}"
        "QTabBar::tab:hover{background:#F2FAFA;border-color:#9CCFD3;color:#096E75;}"
        "QTabBar::tab:selected{background:#0B858A;color:#FFFFFF;border-color:#0B858A;}"
        "QTabBar::tab:disabled{background:#F3F6F8;color:#9AA8B2;border-color:#E0E7EC;}"
    )

    for label in page.findChildren(QLabel):
        if label.text().strip().upper() in {"SOURCE", "VIEW"}:
            label.setStyleSheet(
                "color:#4D6A7E;font-size:9px;font-weight:950;letter-spacing:.4px;"
            )

    # Compatibility passes may expose these as QPushButtons instead of QTabBar
    # tabs. Rename/style those too without changing their location.
    for button in page.findChildren(QPushButton):
        text = " ".join(button.text().split())
        if text == "Compare":
            button.setText("Original + Protected")
            text = button.text()
        if text not in {"Protected text", "Original + Protected"}:
            continue
        button.setMinimumHeight(40)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #CFDCE5;"
            "border-radius:8px;padding:7px 14px;font-size:10px;font-weight:850;}"
            "QPushButton:hover{background:#F2FAFA;border-color:#9CCFD3;color:#096E75;}"
            "QPushButton:checked{background:#0B858A;color:#FFFFFF;border-color:#0B858A;}"
        )
        if text == "Protected text":
            button.setToolTip("Read the protected text for the selected source.")
            button.clicked.connect(lambda _checked=False: _open_protected_text(page))
        else:
            button.setToolTip("See the original source beside the protected copy.")
            button.clicked.connect(lambda _checked=False: _open_original_protected(page))

    toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if toolbar is not None and getattr(page, "_privacygate_source_view_helper", None) is None:
        layout = toolbar.layout()
        if isinstance(layout, QVBoxLayout):
            helper = QLabel(
                "Choose the content under SOURCE, then choose how to inspect it under VIEW: "
                "Protected text or Original + Protected."
            )
            helper.setWordWrap(True)
            helper.setStyleSheet(
                "background:#F7FBFC;color:#536F80;border:1px solid #E0E8ED;"
                "border-radius:7px;padding:6px 9px;font-size:8px;font-weight:650;"
            )
            layout.addWidget(helper)
            page._privacygate_source_view_helper = helper


def _privacy_guidance_text(page) -> tuple[str, str]:
    risk = str(getattr(page, "_privacy_check_risk_badge", None).text() if getattr(page, "_privacy_check_risk_badge", None) is not None else "").strip().upper()
    residual = ""
    values = tuple(getattr(page, "_privacy_check_metric_values", ()) or ())
    if len(values) >= 4:
        residual = str(values[3].text()).strip()

    if risk == "HIGH":
        count = residual if residual and residual != "0" else "Some"
        return (
            "Review the protected result",
            f"{count} residual item(s) were found. Open Protected text to inspect the safe copy, then adjust Review choices and run Scan & Protect again if needed.",
        )
    if risk == "MEDIUM":
        return (
            "Check what you intentionally left visible",
            "Open Protected text to verify the safe copy. If those visible detections should be hidden, change them in Review and run Scan & Protect again.",
        )
    if risk == "LOW":
        return (
            "Protected copy is ready",
            "Open Protected text to read the safe text version, or Original + Protected to visually compare the document before saving or using it with AI.",
        )
    return (
        "After Scan & Protect",
        "Use Protected text for the safe text result, or Original + Protected for the visual document comparison.",
    )


def _install_privacy_check_actions(page) -> None:
    scroll = getattr(page, "_privacy_check_tab", None)
    if scroll is None or getattr(page, "_privacygate_privacy_actions", None) is not None:
        return
    host = scroll.widget()
    root = host.layout() if host is not None else None
    if not isinstance(root, QVBoxLayout):
        return

    panel = QFrame(objectName="PrivacyCheckNextActions")
    panel.setStyleSheet(
        "QFrame#PrivacyCheckNextActions{background:#FFFFFF;border:1px solid #D6E3EA;"
        "border-radius:10px;}"
    )
    row = QHBoxLayout(panel)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(10)

    copy = QVBoxLayout()
    copy.setContentsMargins(0, 0, 0, 0)
    copy.setSpacing(2)
    heading = QLabel("Protected result")
    heading.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:950;")
    detail = QLabel("")
    detail.setWordWrap(True)
    detail.setStyleSheet(f"color:{MUTED};font-size:9px;font-weight:600;")
    copy.addWidget(heading)
    copy.addWidget(detail)
    row.addLayout(copy, 1)

    view_text = QPushButton("View protected text")
    view_text.setIcon(icon("document", color=TEAL, size=18))
    view_text.setMinimumHeight(38)
    view_text.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#0A6F77;border:1px solid #91C8CC;"
        "border-radius:8px;padding:7px 12px;font-size:9px;font-weight:900;}"
        "QPushButton:hover{background:#F0FAFA;border-color:#69B2B8;}"
    )
    view_compare = QPushButton("Original + Protected")
    view_compare.setIcon(icon("compare", color="#FFFFFF", size=18))
    view_compare.setMinimumHeight(38)
    view_compare.setStyleSheet(
        "QPushButton{background:#0B858A;color:#FFFFFF;border:1px solid #0B858A;"
        "border-radius:8px;padding:7px 12px;font-size:9px;font-weight:900;}"
        "QPushButton:hover{background:#096E75;border-color:#096E75;}"
    )
    view_text.clicked.connect(lambda _checked=False: _open_protected_text(page))
    view_compare.clicked.connect(lambda _checked=False: _open_original_protected(page))
    row.addWidget(view_text)
    row.addWidget(view_compare)

    # Header layout is item 0 and risk/status is item 1. Put the next-step actions
    # immediately after the risk result instead of leaving the user to guess what
    # the view controls above mean.
    root.insertWidget(2, panel)

    page._privacygate_privacy_actions = panel
    page._privacygate_privacy_actions_heading = heading
    page._privacygate_privacy_actions_detail = detail
    page._privacygate_privacy_view_text = view_text
    page._privacygate_privacy_view_compare = view_compare

    # Improve readability of the existing persistent Privacy Check elements.
    title = getattr(page, "_privacy_check_status_title", None)
    reason = getattr(page, "_privacy_check_status_reason", None)
    policy = getattr(page, "_privacy_check_policy", None)
    if title is not None:
        title.setStyleSheet("color:#17384E;font-size:12px;font-weight:950;")
    if reason is not None:
        reason.setStyleSheet("color:#2E4A5E;font-size:10px;font-weight:600;")
    if policy is not None:
        policy.setStyleSheet(
            "background:#FFFFFF;color:#496173;border:1px solid #D7E2EA;border-radius:9px;"
            "padding:9px 11px;font-size:9px;font-weight:750;"
        )

    for value in tuple(getattr(page, "_privacy_check_metric_values", ()) or ()):
        value.setStyleSheet("color:#062B4F;font-size:22px;font-weight:950;")

    def refresh_guidance() -> None:
        title_text, detail_text = _privacy_guidance_text(page)
        heading.setText(title_text)
        detail.setText(detail_text)
        _key, document, result, _label = resolve_active_source(page)
        view_text.setEnabled(result is not None)
        can_compare = bool(
            result is not None
            and document is not None
            and (
                getattr(document, "source_kind", "") in _DOCUMENT_KINDS
                or getattr(page, "_gmail_component_text_compare_index", None) is not None
                or page.preview_tabs.count() > 1
            )
        )
        view_compare.setEnabled(can_compare)

    page._privacygate_refresh_privacy_guidance = refresh_guidance
    page.preview_tabs.currentChanged.connect(
        lambda _index: QTimer.singleShot(0, refresh_guidance)
    )
    page.scan_button.clicked.connect(
        lambda: QTimer.singleShot(0, refresh_guidance)
    )
    QTimer.singleShot(0, refresh_guidance)


def apply_protect_view_experience(main_window) -> None:
    """Clarify source/view navigation without changing the underlying Protect engine."""

    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_view_experience", False):
        return
    page._privacygate_view_experience = True
    page._privacygate_active_source_key = ""

    _style_source_and_view_bar(page)
    _install_privacy_check_actions(page)

    document_button = getattr(page, "_redesign_document_mode", None)
    paste_button = getattr(page, "_redesign_paste_mode", None)
    if document_button is not None:
        document_button.clicked.connect(
            lambda _checked=False: QTimer.singleShot(
                0, lambda: _activate_local_source(page, "document")
            )
        )
    if paste_button is not None:
        paste_button.clicked.connect(
            lambda _checked=False: QTimer.singleShot(
                0, lambda: _activate_local_source(page, "text")
            )
        )

    def tab_changed(index: int) -> None:
        if index == 0:
            _render_protected_text(page)
        _sync_source_controls(page)
        refresh = getattr(page, "_privacygate_refresh_privacy_guidance", None)
        if callable(refresh):
            QTimer.singleShot(0, refresh)

    page.preview_tabs.currentChanged.connect(tab_changed)
    page.pdf_path.textChanged.connect(lambda _value: QTimer.singleShot(0, lambda: _sync_source_controls(page)))
    page.text_input.textChanged.connect(lambda: QTimer.singleShot(0, lambda: _sync_source_controls(page)))
    page.scan_button.clicked.connect(lambda: QTimer.singleShot(0, lambda: _sync_source_controls(page)))

    # Gmail source buttons are rebuilt dynamically. Wrap their existing selector
    # only to refresh the generic Protected text view if the user is currently on it.
    selector = getattr(page, "_gmail_component_select", None)
    if callable(selector):
        def select_and_refresh(key: str):
            value = selector(key)
            if page.preview_tabs.currentIndex() == 0:
                _render_protected_text(page)
            refresh = getattr(page, "_privacygate_refresh_privacy_guidance", None)
            if callable(refresh):
                QTimer.singleShot(0, refresh)
            return value

        page._gmail_component_select = select_and_refresh

    _sync_source_controls(page)
