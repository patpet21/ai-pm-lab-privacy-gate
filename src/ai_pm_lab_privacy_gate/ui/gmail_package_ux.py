from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui import gmail_component_session, gmail_package_browser
from ai_pm_lab_privacy_gate.ui.gmail_component_preview_polish import (
    _ensure_source_document,
    _show_unprotected_source,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


VIEW_ORIGINAL = "original"
VIEW_TEXT = "text"
VIEW_COMPARE = "compare"


def _document_to_analyzed_text(document) -> str:
    """Return the exact local text representation inspected by the detector."""
    chunks: list[str] = []
    pages = tuple(getattr(document, "pages", ()) or ())
    for page in pages:
        text = str(getattr(page, "text", "") or "").strip()
        if not text:
            continue
        location = str(getattr(page, "location", "") or "").strip()
        page_number = int(getattr(page, "page_number", 0) or 0)
        if location:
            heading = location
        elif len(pages) > 1:
            heading = f"Page {page_number}"
        else:
            heading = "Analyzed text"
        chunks.append(f"--- {heading} ---\n{text}")
    return "\n\n".join(chunks)


def _animated_run_busy(parent, title: str, message: str, operation):
    """Run connector I/O off the UI thread so the loading UI really animates."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumWidth(430)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)

    heading = QLabel(message)
    heading.setWordWrap(True)
    heading.setStyleSheet("color:#17384E;font-size:12px;font-weight:800;")
    layout.addWidget(heading)

    progress = QProgressBar()
    progress.setRange(0, 0)
    progress.setTextVisible(False)
    progress.setMinimumHeight(9)
    progress.setStyleSheet(
        "QProgressBar{background:#EAF2F5;border:0;border-radius:4px;}"
        "QProgressBar::chunk{background:#0B7180;border-radius:4px;}"
    )
    layout.addWidget(progress)

    activity = QLabel("Working locally")
    activity.setStyleSheet("color:#61798A;font-size:10px;font-weight:700;")
    layout.addWidget(activity)

    dots = {"value": 0}
    animation = QTimer(dialog)

    def tick() -> None:
        dots["value"] = (dots["value"] + 1) % 4
        activity.setText("Working locally" + "." * dots["value"])

    animation.timeout.connect(tick)
    animation.start(320)

    result_box: dict[str, object] = {}
    error_box: dict[str, str] = {}
    loop = QEventLoop()
    worker = FunctionWorker(operation)
    worker.signals.result.connect(lambda value: result_box.__setitem__("value", value))
    worker.signals.error.connect(lambda message: error_box.__setitem__("message", message))
    worker.signals.finished.connect(loop.quit)

    dialog.show()
    QThreadPool.globalInstance().start(worker)
    loop.exec()

    animation.stop()
    dialog.close()
    if error_box:
        raise RuntimeError(error_box["message"])
    return result_box.get("value")


def _ensure_view_toolbar(page) -> None:
    if getattr(page, "_gmail_view_toolbar", None) is not None:
        return
    strip = getattr(page, "_gmail_component_strip", None)
    if strip is None or strip.parentWidget() is None:
        return
    parent = strip.parentWidget()
    parent_layout = parent.layout()
    if parent_layout is None:
        return

    toolbar = QFrame(objectName="GmailPackageViewToolbar")
    toolbar.setStyleSheet(
        "QFrame#GmailPackageViewToolbar{background:#FFFFFF;border:1px solid #D7E3EA;"
        "border-radius:9px;}"
    )
    row = QHBoxLayout(toolbar)
    row.setContentsMargins(10, 6, 10, 6)
    row.setSpacing(7)

    label = QLabel("VIEW")
    label.setStyleSheet("color:#61798A;font-size:8px;font-weight:900;")
    row.addWidget(label)

    group = QButtonGroup(toolbar)
    group.setExclusive(True)
    buttons: dict[str, QPushButton] = {}
    for key, text in (
        (VIEW_ORIGINAL, "Original"),
        (VIEW_TEXT, "Text analyzed"),
        (VIEW_COMPARE, "Protected comparison"),
    ):
        button = QPushButton(text)
        button.setCheckable(True)
        button.setMinimumHeight(30)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#35536A;border:1px solid #D4E0E8;"
            "border-radius:7px;padding:5px 10px;font-size:9px;font-weight:800;}"
            "QPushButton:hover{background:#F1F7FA;border-color:#9FC7CF;}"
            "QPushButton:checked{background:#0B7180;color:#FFFFFF;border-color:#0B7180;}"
            "QPushButton:disabled{background:#F5F7F8;color:#9AA8B2;border-color:#E1E7EB;}"
        )
        group.addButton(button)
        buttons[key] = button
        row.addWidget(button)

    row.addStretch(1)
    status = QLabel("Choose a source above")
    status.setStyleSheet("color:#61798A;font-size:8px;font-weight:750;")
    row.addWidget(status)

    index = parent_layout.indexOf(strip)
    parent_layout.insertWidget(index + 1 if index >= 0 else 0, toolbar)
    toolbar.hide()

    page._gmail_view_toolbar = toolbar
    page._gmail_view_group = group
    page._gmail_view_buttons = buttons
    page._gmail_view_status = status
    page._gmail_view_mode = VIEW_ORIGINAL


def _generic_source_toolbar(page):
    return page.findChild(QFrame, "EmbeddedSourceToolbar")


def _active_manifest_item(page):
    key = str(getattr(page, "_gmail_component_active_key", "") or "")
    return next(
        (
            item
            for item in tuple(getattr(page, "_gmail_component_manifest", ()) or ())
            if str(item.get("key") or "") == key
        ),
        None,
    )


def _sync_view_capabilities(page) -> None:
    _ensure_view_toolbar(page)
    toolbar = getattr(page, "_gmail_view_toolbar", None)
    if toolbar is None:
        return

    manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
    active = bool(manifest)
    toolbar.setVisible(active)
    generic = _generic_source_toolbar(page)
    if generic is not None:
        generic.setVisible(not active)
    if not active:
        return

    item = _active_manifest_item(page)
    key = str(getattr(page, "_gmail_component_active_key", "") or "")
    payload = getattr(page, "_gmail_component_sources", {}).get(key)
    result = getattr(page, "_gmail_component_results", {}).get(key)
    is_body = bool(item and item.get("component_kind") == "body")

    buttons = page._gmail_view_buttons
    buttons[VIEW_ORIGINAL].setEnabled(item is not None)
    buttons[VIEW_TEXT].setEnabled(payload is not None and not is_body)
    buttons[VIEW_TEXT].setToolTip(
        "Show the exact text extracted locally and analyzed by PrivacyGate."
        if not is_body
        else "The email body is already plain text, so Original is the analyzed text."
    )
    buttons[VIEW_COMPARE].setEnabled(result is not None)
    buttons[VIEW_COMPARE].setToolTip(
        "Compare the original source with the protected result."
        if result is not None
        else "Available after Protect creates the safe copy."
    )

    mode = str(getattr(page, "_gmail_view_mode", VIEW_ORIGINAL) or VIEW_ORIGINAL)
    if mode == VIEW_TEXT and not buttons[VIEW_TEXT].isEnabled():
        mode = VIEW_ORIGINAL
    if mode == VIEW_COMPARE and not buttons[VIEW_COMPARE].isEnabled():
        mode = VIEW_ORIGINAL
    page._gmail_view_mode = mode
    buttons[mode].setChecked(True)

    label = str(item.get("label") or "Source") if item else "Source"
    if is_body:
        detail = "email body"
    elif payload is None:
        detail = "original ready · scan to inspect extracted text"
    elif result is None:
        detail = "scanned · analyzed text available"
    else:
        detail = "protected · comparison available"
    page._gmail_view_status.setText(f"{label} · {detail}")


def _show_analyzed_text(page) -> None:
    key = str(getattr(page, "_gmail_component_active_key", "") or "")
    payload = _ensure_source_document(page, key)
    if payload is None:
        return
    document = payload["document"]
    page.current_document = document
    page.preview.setPlainText(_document_to_analyzed_text(document))
    page.preview_tabs.setTabVisible(0, True)
    page.preview_tabs.setCurrentIndex(0)
    metric = getattr(page, "_redesign_review_metric", None)
    if metric is not None:
        metric.setText(f"Text analyzed · {payload.get('label', 'Source')}")
    status = getattr(page, "_gmail_view_status", None)
    if status is not None:
        page_count = len(tuple(getattr(document, "pages", ()) or ()))
        status.setText(
            f"{payload.get('label', 'Source')} · exact local text analyzed"
            + (f" · {page_count} pages/segments" if page_count else "")
        )


def _apply_view(page, mode: str) -> None:
    key = str(getattr(page, "_gmail_component_active_key", "") or "")
    if not key:
        return
    page._gmail_view_mode = mode

    if mode == VIEW_TEXT:
        _show_analyzed_text(page)
    elif mode == VIEW_COMPARE:
        selector = getattr(page, "_gmail_view_base_selector", None)
        if callable(selector):
            selector(key)
    else:
        _show_unprotected_source(page, key)

    _sync_view_capabilities(page)


def apply_gmail_package_ux(main_window) -> None:
    """Make Gmail multi-source inspection explicit and remove generic toolbar overlap."""
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_gmail_package_ux_applied", False):
        return
    page._gmail_package_ux_applied = True

    _ensure_view_toolbar(page)

    # Replace the fake-looking modal wait with a real, animated, responsive loader.
    if not getattr(gmail_package_browser, "_gmail_animated_busy_installed", False):
        gmail_package_browser._run_busy = _animated_run_busy
        gmail_package_browser._gmail_animated_busy_installed = True

    base_selector = getattr(page, "_gmail_component_select", None)
    if callable(base_selector):
        page._gmail_view_base_selector = base_selector

        def select_component(self, key: str) -> None:
            result = getattr(self, "_gmail_component_results", {}).get(key)
            # Source switches default to the most useful view: original before
            # protection, comparison once a protected result exists.
            self._gmail_component_active_key = key
            self._gmail_view_mode = VIEW_COMPARE if result is not None else VIEW_ORIGINAL
            _apply_view(self, self._gmail_view_mode)

        page._gmail_component_select = MethodType(select_component, page)

    buttons = getattr(page, "_gmail_view_buttons", {})
    if buttons:
        buttons[VIEW_ORIGINAL].clicked.connect(lambda: _apply_view(page, VIEW_ORIGINAL))
        buttons[VIEW_TEXT].clicked.connect(lambda: _apply_view(page, VIEW_TEXT))
        buttons[VIEW_COMPARE].clicked.connect(lambda: _apply_view(page, VIEW_COMPARE))

    # The package installer calls this module function dynamically. Wrapping it
    # keeps the contextual toolbar in sync after import, Scan, Clear and source changes.
    if not getattr(gmail_component_session, "_gmail_package_ux_refresh_installed", False):
        previous_refresh = gmail_component_session._refresh_component_strip

        def refresh_with_context(target_page) -> None:
            previous_refresh(target_page)
            QTimer.singleShot(0, lambda: _sync_view_capabilities(target_page))

        gmail_component_session._refresh_component_strip = refresh_with_context
        gmail_component_session._gmail_package_ux_refresh_installed = True

    # Update capabilities when Scan/Protect changes source/result state.
    page.scan_button.clicked.connect(lambda: QTimer.singleShot(50, lambda: _sync_view_capabilities(page)))
    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.clicked.connect(
            lambda: QTimer.singleShot(50, lambda: _sync_view_capabilities(page))
        )

    page.pdf_path.textChanged.connect(
        lambda _value: QTimer.singleShot(0, lambda: _sync_view_capabilities(page))
    )
    page.text_input.textChanged.connect(
        lambda: QTimer.singleShot(0, lambda: _sync_view_capabilities(page))
    )

    _sync_view_capabilities(page)
