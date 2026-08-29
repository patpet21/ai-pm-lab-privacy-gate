from __future__ import annotations

"""Document-language control for the Protect workflow.

The selector is intentionally a thin UI boundary: the application service owns
engine selection and lazy model loading, while every existing local/Drive/Gmail
Protect route continues to use its proven controller. Changing language
invalidates only scan/protection state; the selected source itself remains in
place so the user can immediately run a fresh Scan & Protect.
"""

from types import MethodType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLayout, QVBoxLayout

from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage


_INSTALLED = False


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:  # noqa: ANN001
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _reset_privacy_check(page: ProtectionPage) -> None:
    if hasattr(page, "_privacy_check_generation"):
        page._privacy_check_generation += 1
    page._privacy_check_open_on_ready = False
    page._privacy_check_summary = None
    page._last_residual = ()

    index = int(getattr(page, "_privacy_check_tab_index", -1) or -1)
    if 0 <= index < page.preview_tabs.count():
        page.preview_tabs.setTabVisible(index, False)
    status_title = getattr(page, "_privacy_check_status_title", None)
    if status_title is not None:
        status_title.setText("WAITING FOR PROTECTED RESULT")
    status_reason = getattr(page, "_privacy_check_status_reason", None)
    if status_reason is not None:
        status_reason.setText(
            "Run Scan & Protect to create a document-specific privacy check."
        )
    for label in tuple(getattr(page, "_privacy_check_metric_values", ()) or ()):
        label.setText("0")
    sync = getattr(page, "_privacygate_sync_privacy_view_button", None)
    if callable(sync):
        QTimer.singleShot(0, sync)


def invalidate_language_scan_state(page: ProtectionPage) -> None:
    """Drop findings/results created under the previous language, keeping input."""
    page.current_document = None
    page.current_findings = ()
    page.current_result = None
    page._reviewed_row = None

    page.findings_table.blockSignals(True)
    try:
        page.findings_table.setRowCount(0)
    finally:
        page.findings_table.blockSignals(False)
    page.category_list.clear()

    # Generic/local ProtectSession compatibility state.
    page._local_protect_session_managed = False
    page._local_protect_session_analysis = None
    page._local_protect_session_result = None
    page._protect_session_results = {}

    # Gmail keeps its imported package/source metadata, but protected results
    # from the old language must never remain actionable.
    if hasattr(page, "_gmail_component_results"):
        page._gmail_component_results = {}

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.setEnabled(False)
        protect_button.setText("Protect document")

    results_card = getattr(page, "_redesign_results_card", None)
    if results_card is not None:
        results_card.hide()
    final_actions = getattr(page, "_redesign_final_actions", None)
    if final_actions is not None:
        final_actions.hide()
    quick_actions = getattr(page, "_protect_quick_actions", None)
    if quick_actions is not None:
        quick_actions.hide()

    set_final_actions = getattr(page, "_redesign_set_final_actions", None)
    if callable(set_final_actions):
        set_final_actions(False)

    page.findings_metric.setText("0 detected")
    protected_metric = getattr(page, "_redesign_protected_metric", None)
    if protected_metric is not None:
        protected_metric.setText("0 protected")
    review_metric = getattr(page, "_redesign_review_metric", None)
    if review_metric is not None:
        review_metric.setText("Language changed — scan again")
    page.verification_metric.setText("Second scan before export")

    _reset_privacy_check(page)
    update_scan_state = getattr(page, "_redesign_update_scan_state", None)
    if callable(update_scan_state):
        update_scan_state()


def _apply_document_language_selector(page: ProtectionPage) -> None:
    if getattr(page, "_privacygate_document_language_selector", False):
        return
    page._privacygate_document_language_selector = True

    panel = QFrame(objectName="ProtectDocumentLanguage")
    panel.setToolTip(
        "Choose the language of the document being scanned. Detection stays local."
    )
    box = QVBoxLayout(panel)
    box.setContentsMargins(2, 0, 2, 0)
    box.setSpacing(2)
    label = QLabel("Document language")
    label.setStyleSheet("color:#61798A;font-size:10px;font-weight:800;")
    combo = QComboBox()
    combo.addItem("English", "en")
    combo.addItem("Italiano", "it")
    combo.setMinimumHeight(38)
    combo.setMaximumWidth(132)
    combo.setToolTip(
        "English uses the existing English detector. Italiano enables the local Italian Privacy Pack."
    )
    combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#102F49;border:1px solid #C9D9E4;"
        "border-radius:8px;padding:6px 9px;font-size:11px;font-weight:700;}"
        "QComboBox:hover{border-color:#95C5CA;background:#FCFFFF;}"
        "QComboBox:focus{border-color:#55AEB5;}"
        "QComboBox QAbstractItemView{background:#FFFFFF;color:#17384E;"
        "border:1px solid #C9D9E4;selection-background-color:#E7F5F5;"
        "selection-color:#062B4F;padding:4px;}"
    )
    box.addWidget(label)
    box.addWidget(combo)

    source_parent = page.scan_button.parentWidget()
    source_layout = _find_layout(
        source_parent.layout() if source_parent is not None else None,
        page.scan_button,
    )
    if source_layout is not None and hasattr(source_layout, "insertWidget"):
        index = source_layout.indexOf(page.clear_button)
        if index < 0:
            index = source_layout.indexOf(page.scan_button)
        source_layout.insertWidget(max(0, index), panel)
    else:
        # Defensive fallback for a future layout refactor: keep the selector
        # visible in the existing settings strip rather than dropping it.
        settings = page.findChild(QFrame, "RedesignSettingsStrip")
        settings_layout = settings.layout() if settings is not None else None
        if settings_layout is not None:
            settings_layout.insertWidget(0, panel)

    page.document_language_combo = combo
    page._protect_document_language_panel = panel
    page._protect_document_language_label = label
    page._protect_document_language = "en"
    page.service.set_document_language("en")

    def language_changed(_index: int) -> None:
        code = normalize_document_language(combo.currentData())
        if code == getattr(page, "_protect_document_language", "en"):
            return
        page._protect_document_language = code
        page.service.set_document_language(code)
        invalidate_language_scan_state(page)

    combo.currentIndexChanged.connect(language_changed)

    previous_set_busy = page._set_busy

    def set_busy(self: ProtectionPage, busy: bool) -> None:
        previous_set_busy(busy)
        combo.setEnabled(not busy)

    page._set_busy = MethodType(set_busy, page)


def install_protect_document_language() -> None:
    """Install the selector after redesign widgets exist on each ProtectionPage."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_init = ProtectionPage.__init__

    def wrapped_init(self: ProtectionPage, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_document_language_selector(self)

    ProtectionPage.__init__ = wrapped_init
