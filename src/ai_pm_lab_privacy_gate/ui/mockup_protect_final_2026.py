from __future__ import annotations

"""Final 2026 Protect presentation layer.

This module intentionally does not replace ProtectionPage or any protection,
preview, connector, restore, policy, export or AI-handoff behavior.  It only
recomposes and styles the widgets that the proven Protect runtime already owns.
In particular, the existing Original/Protected document panels and their real
PDF/Office preview widgets remain the authoritative preview surface.
"""

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    CANVAS,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    PURPLE,
    PURPLE_SOFT,
    TEXT,
    WHITE,
)


BLUE_DARK = "#1D4ED8"
BLUE_BORDER = "#C7D7FE"
SOFT = "#F8FAFC"
SOFTER = "#FCFCFD"


def _secondary_button_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:8px 13px;font-size:9px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_button_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:9px 15px;font-size:9px;font-weight:900;}"
        f"QPushButton:hover{{background:{BLUE_DARK};border-color:{BLUE_DARK};}}"
        "QPushButton:disabled{background:#D0D5DD;color:#FFFFFF;border-color:#D0D5DD;}"
    )


def _soft_purple_button_qss() -> str:
    return (
        f"QToolButton{{background:{PURPLE_SOFT};color:{PURPLE};border:1px solid #DDD6FE;"
        "border-radius:9px;padding:8px 14px;font-size:9px;font-weight:850;text-align:left;}"
        "QToolButton:hover{background:#EDE9FE;border-color:#C4B5FD;}"
        "QToolButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
        "QToolButton::menu-indicator{subcontrol-origin:padding;subcontrol-position:right center;right:7px;}"
    )


def _section_copy(title: str, subtitle: str) -> QWidget:
    host = QWidget()
    host.setStyleSheet("background:transparent;border:none;")
    box = QVBoxLayout(host)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet(
        f"color:{INK};font-size:13px;font-weight:900;background:transparent;border:none;"
    )
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color:{MUTED};font-size:8px;background:transparent;border:none;"
    )
    box.addWidget(heading)
    box.addWidget(note)
    return host


def _build_header(page) -> QFrame:
    frame = QFrame(objectName="Protect2026Header")
    frame.setStyleSheet("QFrame#Protect2026Header{background:transparent;border:none;}")
    row = QHBoxLayout(frame)
    row.setContentsMargins(2, 0, 2, 0)
    row.setSpacing(10)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    title = QLabel("Protect")
    title.setStyleSheet(
        f"color:{INK};font-size:29px;font-weight:950;background:transparent;border:none;"
    )
    subtitle = QLabel(
        "Protect sensitive data locally before you share a document or use it with AI."
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(
        f"color:{MUTED};font-size:10px;background:transparent;border:none;"
    )
    copy.addWidget(title)
    copy.addWidget(subtitle)
    row.addLayout(copy, 1)

    local = QLabel("LOCAL PROCESSING")
    local.setStyleSheet(
        f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;border-radius:8px;"
        "padding:5px 8px;font-size:7px;font-weight:900;"
    )
    local.setToolTip("Detection, original previews and restore mappings stay on this device.")
    row.addWidget(local, 0, Qt.AlignmentFlag.AlignTop)

    status = QLabel("READY")
    status.setObjectName("Protect2026Status")
    status.setStyleSheet(
        f"background:{BLUE_SOFT};color:{BLUE};border:1px solid {BLUE_BORDER};border-radius:8px;"
        "padding:5px 8px;font-size:7px;font-weight:900;"
    )
    row.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
    page._protect_2026_status = status
    return frame


def _build_flow() -> QFrame:
    frame = QFrame(objectName="Protect2026Flow")
    frame.setStyleSheet(
        f"QFrame#Protect2026Flow{{background:{WHITE};border:1px solid {BORDER};border-radius:13px;}}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(14, 10, 14, 10)
    row.setSpacing(7)

    steps = (
        ("1", "Add source", "Upload, connected app or paste"),
        ("2", "Scan locally", "Detect sensitive information"),
        ("3", "Review", "Choose what PrivacyGate protects"),
        ("4", "Use safe copy", "Save, download or approved AI"),
    )
    for index, (number, title, detail) in enumerate(steps):
        cell = QFrame()
        cell.setStyleSheet("QFrame{background:transparent;border:none;}")
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        badge = QLabel(number)
        badge.setFixedSize(25, 25)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:{BLUE_SOFT};color:{BLUE};border:1px solid {BLUE_BORDER};"
            "border-radius:12px;font-size:8px;font-weight:950;"
        )
        layout.addWidget(badge)
        copy = QVBoxLayout()
        copy.setSpacing(0)
        name = QLabel(title)
        name.setStyleSheet(
            f"color:{TEXT};font-size:8px;font-weight:850;background:transparent;border:none;"
        )
        note = QLabel(detail)
        note.setStyleSheet(
            f"color:{MUTED};font-size:7px;background:transparent;border:none;"
        )
        copy.addWidget(name)
        copy.addWidget(note)
        layout.addLayout(copy, 1)
        row.addWidget(cell, 1)
        if index < len(steps) - 1:
            arrow = QLabel("›")
            arrow.setStyleSheet(
                "color:#98A2B3;font-size:16px;font-weight:700;background:transparent;border:none;"
            )
            row.addWidget(arrow)
    return frame


def _style_workspace_context(page) -> None:
    bar = getattr(page, "_managed_workspace_context_bar", None)
    if bar is None:
        return
    bar.setStyleSheet(
        f"QFrame#ManagedProtectContextBar{{background:{WHITE};border:1px solid {BORDER};border-radius:13px;}}"
    )
    layout = bar.layout()
    if layout is not None:
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

    for label in bar.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text.upper() == "WORKSPACE CONTEXT":
            label.setStyleSheet(
                f"color:{BLUE};font-size:8px;font-weight:950;background:transparent;border:none;"
            )
        elif text in {"Workspace", "Connected content source", "Connected source", "Account"}:
            label.setStyleSheet(
                f"color:{TEXT};font-size:7.5px;font-weight:850;background:transparent;border:none;"
            )
        elif "Personal or company context" in text or "Source of the content" in text:
            label.setStyleSheet(
                f"color:{MUTED};font-size:7px;background:transparent;border:none;"
            )

    for combo in bar.findChildren(QComboBox):
        combo.setMinimumHeight(39)
        combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
            "padding:7px 9px;font-size:9px;font-weight:700;}"
            f"QComboBox:hover{{border-color:{BLUE_BORDER};}}"
            f"QComboBox:focus{{border:1px solid {BLUE};}}"
            "QComboBox::drop-down{border:none;width:26px;}"
        )

    manage = getattr(bar, "manage", None)
    if manage is not None:
        manage.setStyleSheet(_secondary_button_qss())
        manage.setMinimumHeight(39)
    browse = getattr(bar, "browse", None)
    if browse is not None:
        browse.setStyleSheet(_primary_button_qss())
        browse.setMinimumHeight(41)
    policy = getattr(bar, "policy", None)
    if policy is not None:
        policy.setStyleSheet(
            f"background:{SOFT};color:{TEXT};border:1px solid {BORDER};border-radius:9px;"
            "padding:7px 9px;font-size:7px;font-weight:750;"
        )
        policy.setMinimumHeight(39)


def _style_source_actions(page) -> None:
    bar = getattr(page, "_protect_source_quick_bar", None)
    if bar is None:
        return
    bar.setStyleSheet(
        f"QFrame#ProtectSourceQuickBar{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;}}"
    )
    layout = bar.layout()
    if layout is not None:
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(8)

    upload = getattr(page, "_protect_source_upload", None)
    connected = getattr(page, "_protect_source_connected", None)
    paste = getattr(page, "_protect_source_paste", None)
    scan = getattr(page, "_protect_source_scan", None)
    protect = getattr(page, "_protect_source_protect", None)

    for button, icon_name in ((upload, "upload"), (connected, "cloud"), (paste, "paste")):
        if button is None:
            continue
        button.setStyleSheet(_secondary_button_qss())
        button.setMinimumHeight(39)
        button.setIcon(icon(icon_name, color=BLUE, size=17))
        button.setIconSize(QSize(17, 17))

    if scan is not None:
        scan.setText("Scan & Protect")
        scan.setStyleSheet(_primary_button_qss())
        scan.setMinimumHeight(41)
        scan.setMinimumWidth(185)
        scan.setIcon(icon("protect", color="#FFFFFF", size=18))
        scan.setIconSize(QSize(18, 18))
    if protect is not None:
        # Compatibility action remains alive underneath the single public CTA.
        protect.hide()
        protect.setMaximumWidth(0)


def _style_source_view_controls(page) -> None:
    for button, icon_name in (
        (getattr(page, "_redesign_document_mode", None), "document"),
        (getattr(page, "_redesign_paste_mode", None), "paste"),
    ):
        if button is None:
            continue
        button.setMinimumHeight(36)
        button.setIcon(icon(icon_name, color=BLUE, size=16))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
            "padding:6px 11px;font-size:8.5px;font-weight:800;}"
            f"QPushButton:hover{{background:{BLUE_SOFT};border-color:{BLUE_BORDER};color:{BLUE_DARK};}}"
            f"QPushButton:checked{{background:{BLUE};color:#FFFFFF;border-color:{BLUE};}}"
        )

    toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if toolbar is not None:
        toolbar.setStyleSheet(
            f"QFrame#EmbeddedSourceToolbar{{background:{SOFT};border:1px solid {BORDER};border-radius:10px;}}"
        )
        layout = toolbar.layout()
        if layout is not None:
            layout.setContentsMargins(9, 6, 9, 6)
            layout.setSpacing(5)

    old_steps = page.findChild(QFrame, "RedesignSteps")
    if old_steps is not None:
        old_steps.hide()
        old_steps.setMaximumHeight(0)

    helper = getattr(page, "_privacygate_source_view_helper", None)
    if helper is not None:
        helper.hide()
        helper.setMaximumHeight(0)

    for label in page.findChildren(QLabel):
        text = label.text().strip().upper()
        if text in {"SOURCE", "VIEW"}:
            label.setStyleSheet(
                f"color:{MUTED};font-size:7.5px;font-weight:950;background:transparent;border:none;"
            )


def _style_preview_tabs(page) -> None:
    tabs: QTabWidget = page.preview_tabs
    tabs.setStyleSheet(
        "QTabWidget::pane{background:transparent;border:none;margin-top:5px;}"
        "QTabBar::tab{background:#FFFFFF;color:#475467;border:1px solid #D0D5DD;border-radius:8px;"
        "padding:7px 12px;margin-right:5px;font-size:8.5px;font-weight:800;}"
        f"QTabBar::tab:hover{{background:{BLUE_SOFT};border-color:{BLUE_BORDER};color:{BLUE_DARK};}}"
        f"QTabBar::tab:selected{{background:{BLUE};color:#FFFFFF;border-color:{BLUE};}}"
    )
    tabs.tabBar().setExpanding(False)

    page.preview.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:11px;"
        "padding:14px;font-size:11px;selection-background-color:#D6E4FF;}"
    )
    page.preview.setMinimumHeight(420)

    page.text_input.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:11px;"
        "padding:12px;font-size:10px;selection-background-color:#D6E4FF;}"
        f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
    )


def _style_document_panels(page) -> None:
    original = getattr(page, "original_document_panel", None)
    protected = getattr(page, "protected_document_panel", None)
    if original is None or protected is None:
        return

    for panel, object_name, accent in (
        (original, "Protect2026OriginalPanel", "#98A2B3"),
        (protected, "Protect2026ProtectedPanel", BLUE),
    ):
        panel.setObjectName(object_name)
        panel.setStyleSheet(
            f"QFrame#{object_name}{{background:{WHITE};border:1px solid {BORDER};border-radius:13px;}}"
        )
        layout = panel.layout()
        if layout is not None:
            layout.setContentsMargins(12, 11, 12, 12)
            layout.setSpacing(8)
        panel.setMinimumWidth(300)
        for label in panel.findChildren(QLabel):
            text = label.text().strip()
            if text in {"Original document", "Protected document"}:
                label.setStyleSheet(
                    f"color:{INK};font-size:11px;font-weight:900;background:transparent;border:none;"
                )
            elif text in {"Local source", "Safe copy preview"}:
                label.setStyleSheet(
                    f"background:{BLUE_SOFT if 'Safe' in text else SOFT};"
                    f"color:{BLUE if 'Safe' in text else MUTED};border:1px solid {BLUE_BORDER if 'Safe' in text else BORDER};"
                    "border-radius:7px;padding:3px 7px;font-size:7px;font-weight:850;"
                )

    splitter = page.document_preview_splitter
    splitter.setChildrenCollapsible(False)
    splitter.setMinimumHeight(520)
    splitter.setSizes([650, 650])
    splitter.setHandleWidth(7)
    splitter.setStyleSheet(
        "QSplitter::handle{background:#F2F4F7;border-radius:3px;margin:8px 2px;}"
        f"QSplitter::handle:hover{{background:{BLUE_BORDER};}}"
    )

    for view in (page.original_pdf_view, page.protected_pdf_view):
        view.setStyleSheet(
            "QPdfView{background:#F2F4F7;border:1px solid #EAECF0;border-radius:8px;}"
        )


def _style_preview_workspace(page) -> None:
    card = page.preview_card
    card.setObjectName("Protect2026Workspace")
    card.setMinimumHeight(690)
    card.setStyleSheet(
        f"QFrame#Protect2026Workspace{{background:{WHITE};border:1px solid {BORDER};border-radius:15px;}}"
    )
    layout = card.layout()
    if layout is not None:
        layout.setContentsMargins(16, 14, 16, 15)
        layout.setSpacing(9)

    for label in card.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text.startswith("Protected preview"):
            label.setText("Document workspace")
            label.setStyleSheet(
                f"color:{INK};font-size:13px;font-weight:900;background:transparent;border:none;"
            )
        elif text == "Color-coded by protected category":
            label.setText("Protected values are color coded")
            label.setStyleSheet(
                f"background:{BLUE_SOFT};color:{BLUE};border:1px solid {BLUE_BORDER};border-radius:7px;"
                "padding:4px 7px;font-size:7px;font-weight:800;"
            )

    page.focus_preview_button.setStyleSheet(_secondary_button_qss())
    page.focus_preview_button.setMinimumHeight(36)
    page.focus_preview_button.setIcon(icon("compare", color=BLUE, size=16))
    page.focus_preview_button.setIconSize(QSize(16, 16))

    page.comparison_note.setText(
        "Original content stays on this device. The protected copy is created beside it for direct visual comparison."
    )
    page.comparison_note.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;background:transparent;border:none;"
    )
    page.color_legend.setStyleSheet(
        f"background:{SOFT};color:{TEXT};border:1px solid {BORDER};border-radius:8px;"
        "padding:6px 8px;font-size:7px;"
    )

    for button in (
        page.pdf_previous_button,
        page.pdf_next_button,
        page.pdf_zoom_out_button,
        page.pdf_fit_button,
        page.pdf_zoom_in_button,
        page.high_fidelity_button,
        page.install_libreoffice_button,
    ):
        button.setStyleSheet(_secondary_button_qss())
        button.setMinimumHeight(32)


def _move_and_style_result_actions(page) -> None:
    bar = getattr(page, "_protect_quick_actions", None)
    preview_layout = page.preview_card.layout()
    if bar is None or preview_layout is None:
        return

    old_parent = bar.parentWidget()
    if old_parent is not page.preview_card:
        old_layout = old_parent.layout() if old_parent is not None else None
        if old_layout is not None:
            old_layout.removeWidget(bar)
        bar.setParent(page.preview_card)
        index = preview_layout.indexOf(page.preview_tabs)
        preview_layout.insertWidget(index + 1 if index >= 0 else preview_layout.count(), bar)

    bar.setStyleSheet(
        f"QFrame#ProtectQuickActions{{background:{SOFT};border:1px solid {BORDER};border-radius:11px;}}"
    )
    layout = bar.layout()
    if layout is not None:
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(7)

    for label in bar.findChildren(QLabel):
        if "Protected copy ready" in label.text():
            label.setText("Protected copy ready — choose the next action")
            label.setStyleSheet(
                f"color:{TEXT};font-size:8px;font-weight:800;background:transparent;border:none;"
            )

    save_only = getattr(page, "_protect_save_only", None)
    save_copy = getattr(page, "_protect_save_copy", None)
    save_download = getattr(page, "_protect_save_download", None)
    open_ai = getattr(page, "_protect_open_ai", None)
    for button in (save_only, save_download):
        if button is not None:
            button.setStyleSheet(_secondary_button_qss())
            button.setMinimumHeight(39)
    if save_copy is not None:
        save_copy.setStyleSheet(_primary_button_qss())
        save_copy.setMinimumHeight(39)
    if isinstance(open_ai, QToolButton):
        open_ai.setStyleSheet(_soft_purple_button_qss())
        open_ai.setMinimumHeight(39)
        open_ai.setIcon(icon("workflow", color=PURPLE, size=16))
        open_ai.setIconSize(QSize(16, 16))


def _style_review(page) -> None:
    results = getattr(page, "_redesign_results_card", None)
    findings = getattr(page, "findings_card", None)
    if results is not None:
        results.setObjectName("Protect2026Review")
        results.setStyleSheet(
            f"QFrame#Protect2026Review{{background:{WHITE};border:1px solid {BORDER};border-radius:15px;}}"
        )
        layout = results.layout()
        if layout is not None:
            layout.setContentsMargins(15, 13, 15, 14)
            layout.setSpacing(10)
    if findings is not None:
        findings.setObjectName("Protect2026Findings")
        findings.setStyleSheet(
            "QFrame#Protect2026Findings{background:#FFFFFF;border:none;border-radius:10px;}"
        )
        findings.setMinimumHeight(300)
        layout = findings.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

    page.findings_table.setStyleSheet(
        "QTableWidget{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;border-radius:10px;"
        "gridline-color:#F2F4F7;font-size:8px;selection-background-color:#EEF4FF;selection-color:#101828;}"
        "QTableWidget::item{padding:6px;border-bottom:1px solid #F2F4F7;}"
        "QHeaderView::section{background:#F8FAFC;color:#667085;border:none;border-bottom:1px solid #EAECF0;"
        "padding:7px;font-size:7px;font-weight:850;}"
    )
    page.filter_input.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
        "padding:7px 9px;font-size:8px;}"
        f"QLineEdit:focus{{border:1px solid {BLUE};}}"
    )
    for button in (
        page.categories_button,
        page.reset_selections_button,
        page.protect_all_button,
        page.keep_all_button,
        page.invert_selection_button,
        page.add_sensitive_button,
        page.keep_this_button,
    ):
        button.setStyleSheet(_secondary_button_qss())
    page.protect_this_button.setStyleSheet(_primary_button_qss())


def _style_advanced(page) -> None:
    strip = page.findChild(QFrame, "RedesignSettingsStrip")
    if strip is None:
        return
    strip.setStyleSheet(
        f"QFrame#RedesignSettingsStrip{{background:{WHITE};border:1px solid {BORDER};border-radius:13px;}}"
    )
    layout = strip.layout()
    if layout is not None:
        layout.setContentsMargins(12, 7, 12, 8)
        layout.setSpacing(5)
    panel = page.findChild(QFrame, "RedesignAdvanced")
    if panel is not None:
        panel.setStyleSheet(
            f"QFrame#RedesignAdvanced{{background:{SOFT};border:1px solid {BORDER};border-radius:10px;}}"
        )
    for combo in (page.profile_combo, page.scope_combo, page.mode_combo):
        combo.setMinimumHeight(36)
        combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
            "padding:6px 8px;font-size:8px;}"
            f"QComboBox:focus{{border:1px solid {BLUE};}}"
            "QComboBox::drop-down{border:none;width:24px;}"
        )
    page.threshold_input.setMinimumHeight(36)
    page.threshold_input.setStyleSheet(
        "QDoubleSpinBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;"
        "padding:6px 8px;font-size:8px;}"
        f"QDoubleSpinBox:focus{{border:1px solid {BLUE};}}"
    )


def _hide_legacy_explanations(page) -> None:
    for label in page.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text.startswith("START HERE"):
            label.hide()
            label.setMaximumHeight(0)

    old_title = getattr(page, "_redesign_title", None)
    old_subtitle = getattr(page, "_redesign_subtitle", None)
    old_help = getattr(page, "_redesign_help_button", None)
    for widget in (old_title, old_subtitle, old_help):
        if widget is not None:
            widget.hide()
            widget.setMaximumHeight(0)
    for pill in tuple(getattr(page, "_redesign_header_pills", ()) or ()):
        pill.hide()
        pill.setMaximumHeight(0)


def _install_status_sync(page) -> None:
    if getattr(page, "_protect_2026_status_timer", None) is not None:
        return
    timer = QTimer(page)
    timer.setInterval(300)

    def sync() -> None:
        badge = getattr(page, "_protect_2026_status", None)
        if badge is None:
            return
        result = getattr(page, "current_result", None)
        has_text = bool(str(page.text_input.toPlainText() or "").strip())
        has_file = bool(str(page.pdf_path.text() or "").strip())
        busy = bool(getattr(page, "_redesign_active_operations", {}) or {})
        if busy:
            text, bg, fg, border = "WORKING LOCALLY", "#FFF7ED", "#D97706", "#FED7AA"
        elif result is not None:
            text, bg, fg, border = "PROTECTED", GREEN_SOFT, GREEN, "#BBF7D0"
        elif has_text or has_file:
            text, bg, fg, border = "READY TO SCAN", BLUE_SOFT, BLUE, BLUE_BORDER
        else:
            text, bg, fg, border = "READY", "#F2F4F7", "#475467", BORDER
        badge.setText(text)
        badge.setStyleSheet(
            f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;"
            "padding:5px 8px;font-size:7px;font-weight:900;"
        )

    timer.timeout.connect(sync)
    timer.start()
    sync()
    page._protect_2026_status_timer = timer


def apply_mockup_protect_final_2026(main_window) -> None:
    """Apply the approved Protect visual hierarchy over the existing runtime."""
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_privacygate_mockup_protect_final_2026", False)):
        return
    page._privacygate_mockup_protect_final_2026 = True

    scroll = getattr(page, "_redesign_scroll", None)
    content = scroll.widget() if scroll is not None else None
    body = content.layout() if content is not None else None
    if not isinstance(body, QVBoxLayout):
        return

    page.setStyleSheet(f"background:{CANVAS};")
    if scroll is not None:
        scroll.setStyleSheet(
            f"QScrollArea#RedesignScroll{{background:{CANVAS};border:none;}}"
            "QScrollBar:vertical{background:transparent;width:7px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#D0D5DD;border-radius:3px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
    if content is not None:
        content.setStyleSheet(f"background:{CANVAS};")
    body.setContentsMargins(26, 20, 26, 26)
    body.setSpacing(13)

    _hide_legacy_explanations(page)

    header = _build_header(page)
    flow = _build_flow()
    body.insertWidget(0, header)
    body.insertWidget(1, flow)
    page._protect_2026_header = header
    page._protect_2026_flow = flow

    _style_workspace_context(page)
    _style_source_actions(page)
    _style_source_view_controls(page)
    _style_preview_workspace(page)
    _style_preview_tabs(page)
    _style_document_panels(page)
    _move_and_style_result_actions(page)
    _style_review(page)
    _style_advanced(page)
    _install_status_sync(page)

    # The proven comparison widgets remain the visual center of Protect.  These
    # sizing changes only reduce unnecessary vertical chrome from the previous
    # compatibility layout; they never swap or clone a preview widget.
    page.preview_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    page.document_preview_splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
