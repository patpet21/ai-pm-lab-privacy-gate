from __future__ import annotations

"""Keep Privacy Check reachable after the user navigates Protect views.

Privacy Check belongs to the current protected session, not to one preview tab.
Once a real check has completed, the approved SOURCE / VIEW toolbar must keep a
stable way back to it while the user inspects Protected text, document previews,
or Original + Protected.  The control is hidden again only when there is no
valid check for the current protected source set (for example after Clear).
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton

from ai_pm_lab_privacy_gate.ui.iconography import icon


_BUTTON_STYLE = (
    "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #CFDCE5;"
    "border-radius:8px;padding:7px 14px;font-size:10px;font-weight:850;}"
    "QPushButton:hover{background:#F2FAFA;border-color:#9CCFD3;color:#096E75;}"
    "QPushButton:checked{background:#0B858A;color:#FFFFFF;border-color:#0B858A;}"
)


def _find_view_button(page, text: str):
    target = " ".join(text.split())
    for button in page.findChildren(QPushButton):
        if " ".join(button.text().split()) == target:
            return button
    return None


def _has_valid_privacy_check(page) -> bool:
    if getattr(page, "_privacy_check_summary", None) is None:
        return False
    try:
        from ai_pm_lab_privacy_gate.ui.protect_workflow_v2 import _protection_sources

        if not _protection_sources(page):
            return False
    except Exception:
        return False
    index = int(getattr(page, "_privacy_check_tab_index", -1) or -1)
    return 0 <= index < page.preview_tabs.count()


def apply_protect_privacy_check_persistence(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_privacygate_privacy_check_persistence", False):
        return
    page._privacygate_privacy_check_persistence = True

    compare_button = _find_view_button(page, "Original + Protected")
    protected_button = _find_view_button(page, "Protected text")
    if compare_button is None:
        return

    privacy_button = QPushButton("Privacy Check", compare_button.parentWidget())
    privacy_button.setIcon(icon("check", color="#0B858A", size=18))
    privacy_button.setMinimumHeight(40)
    privacy_button.setCheckable(True)
    privacy_button.setToolTip(
        "Return to the completed local Privacy Check for this protected session."
    )
    privacy_button.setStyleSheet(_BUTTON_STYLE)
    privacy_button.hide()

    parent_layout = compare_button.parentWidget().layout()
    if parent_layout is not None:
        compare_index = parent_layout.indexOf(compare_button)
        if compare_index >= 0 and hasattr(parent_layout, "insertWidget"):
            parent_layout.insertWidget(compare_index + 1, privacy_button)
        else:
            parent_layout.addWidget(privacy_button)

    try:
        group = compare_button.group()
    except Exception:
        group = None
    if group is not None:
        group.addButton(privacy_button)

    page._privacygate_privacy_view_button = privacy_button

    def sync() -> None:
        index = int(getattr(page, "_privacy_check_tab_index", -1) or -1)
        valid = _has_valid_privacy_check(page)
        visible = False
        if valid:
            try:
                visible = page.preview_tabs.isTabVisible(index)
            except Exception:
                visible = True
        privacy_button.setVisible(bool(valid and visible))
        privacy_button.setEnabled(bool(valid and visible))
        privacy_button.setChecked(
            bool(valid and visible and page.preview_tabs.currentIndex() == index)
        )

        # Keep the two existing VIEW controls visually truthful when Privacy
        # Check owns the current preview.
        if valid and visible and page.preview_tabs.currentIndex() == index:
            if protected_button is not None:
                protected_button.setChecked(False)
            compare_button.setChecked(False)

    page._privacygate_sync_privacy_view_button = sync

    def open_privacy_check(_checked: bool = False) -> None:
        index = int(getattr(page, "_privacy_check_tab_index", -1) or -1)
        if not _has_valid_privacy_check(page):
            sync()
            return
        try:
            page.preview_tabs.setTabVisible(index, True)
            page.preview_tabs.setCurrentIndex(index)
        finally:
            QTimer.singleShot(0, sync)

    privacy_button.clicked.connect(open_privacy_check)
    page.preview_tabs.currentChanged.connect(lambda _index: QTimer.singleShot(0, sync))
    page.clear_button.clicked.connect(lambda _checked=False: QTimer.singleShot(0, sync))
    page.scan_button.clicked.connect(lambda _checked=False: QTimer.singleShot(0, sync))
    page.pdf_path.textChanged.connect(lambda _value: QTimer.singleShot(0, sync))
    page.text_input.textChanged.connect(lambda: QTimer.singleShot(0, sync))

    # Privacy Check completes asynchronously. Wrap the summary renderer so the
    # persistent VIEW control is refreshed after the real result arrives. The
    # singleShot is intentional: later loading/runtime wrappers may still update
    # QTabWidget visibility in the same event-loop turn.
    from ai_pm_lab_privacy_gate.ui import protect_workflow_v2 as workflow

    if not getattr(workflow, "_privacy_persistence_render_patched", False):
        workflow._privacy_persistence_render_patched = True
        previous_render_summary = workflow._render_summary

        def render_summary(check_page, summary) -> None:
            previous_render_summary(check_page, summary)
            refresh = getattr(check_page, "_privacygate_sync_privacy_view_button", None)
            if callable(refresh):
                QTimer.singleShot(0, refresh)

        workflow._render_summary = render_summary

    QTimer.singleShot(0, sync)
