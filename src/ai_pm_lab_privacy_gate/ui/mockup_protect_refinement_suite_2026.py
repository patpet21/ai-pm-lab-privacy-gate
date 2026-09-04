from __future__ import annotations

"""One ordered activation point for the post-mockup Protect refinements."""

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from .mockup_protect_workspace_refinement_2026 import (
    apply_mockup_protect_workspace_refinement_2026,
)
from .mockup_protect_explainability_2026 import (
    apply_mockup_protect_explainability_2026,
)
from .mockup_protect_findings_refinement_2026 import (
    apply_mockup_protect_findings_refinement_2026,
)
from .mockup_protect_manual_sensitive_2026 import (
    apply_mockup_protect_manual_sensitive_2026,
)
from .mockup_protect_compact_workflow_2026 import (
    apply_mockup_protect_compact_workflow_2026,
)
from .mockup_protect_compact_steps_2026 import (
    apply_mockup_protect_compact_steps_2026,
)
from .mockup_protect_manual_sensitive_runtime_fix_2026 import (
    apply_mockup_protect_manual_sensitive_runtime_fix_2026,
)
from .mockup_protect_review_experience_2026 import (
    apply_mockup_protect_review_experience_2026,
)
from .mockup_protect_review_controls_2026 import (
    apply_mockup_protect_review_controls_2026,
)
from .protect_image_review_regression_fix import (
    apply_protect_image_review_regression_fix,
)
from .mockup_protect_entry_surface_2026 import (
    apply_mockup_protect_entry_surface_2026,
)


BLUE = "#2563EB"
TEAL = "#0B858A"


def _language_flag(code: str) -> QIcon:
    """Draw crisp local flag icons without adding image assets."""
    pixmap = QPixmap(24, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    if code == "it":
        painter.fillRect(1, 1, 7, 14, QColor("#169B62"))
        painter.fillRect(8, 1, 8, 14, QColor("#FFFFFF"))
        painter.fillRect(16, 1, 7, 14, QColor("#CE2B37"))
    else:
        painter.fillRect(1, 1, 22, 14, QColor("#FFFFFF"))
        for y in range(1, 15, 4):
            painter.fillRect(1, y, 22, 2, QColor("#B22234"))
        painter.fillRect(1, 1, 10, 8, QColor("#3C3B6E"))
    painter.end()
    return QIcon(pixmap)


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
    """Find the exact nested layout that owns ``widget``."""
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for index in range(layout.count()):
        item = layout.itemAt(index)
        child_layout = item.layout()
        found = _find_layout(child_layout, widget)
        if found is not None:
            return found
        child_widget = item.widget()
        if child_widget is not None:
            found = _find_layout(child_widget.layout(), widget)
            if found is not None:
                return found
    return None


def _remove_from_layout_tree(root: QLayout | None, widget) -> None:
    owner = _find_layout(root, widget)
    if owner is not None:
        owner.removeWidget(widget)


def _find_label(root, text: str) -> QLabel | None:
    wanted = " ".join(text.split()).lower()
    for label in root.findChildren(QLabel):
        if " ".join(label.text().split()).lower() == wanted:
            return label
    return None


def _move_scan_settings(page, row: QHBoxLayout, context_bar) -> None:
    """Reuse the real Advanced panel as the compact Scan settings control."""
    settings_strip = page.findChild(QFrame, "RedesignSettingsStrip")
    advanced_panel = page.findChild(QFrame, "RedesignAdvanced")
    if settings_strip is None or advanced_panel is None:
        return

    toggles = tuple(settings_strip.findChildren(QToolButton))
    toggle = next(
        (
            item
            for item in toggles
            if "advanced protection settings" in " ".join(item.text().split()).lower()
        ),
        toggles[0] if toggles else None,
    )
    if toggle is None:
        return

    strip_layout = settings_strip.layout()
    if strip_layout is not None:
        strip_layout.removeWidget(toggle)
    toggle.setParent(page.preview_card)
    toggle.setCheckable(True)
    toggle.setMinimumHeight(46)
    toggle.setMaximumHeight(50)
    toggle.setMinimumWidth(138)
    toggle.setMaximumWidth(170)
    toggle.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    toggle.setToolTip(
        "Change scan profile, protection scope, protection mode, or confidence threshold."
    )
    toggle.setStyleSheet(
        "QToolButton{background:#FFFFFF;color:#17384E;border:1px solid #D0D5DD;"
        "border-radius:10px;padding:6px 4px;font-size:7.3px;font-weight:900;text-align:left;}"
        "QToolButton:hover{background:#F8FAFC;border-color:#9DB7F8;color:#1D4ED8;}"
        "QToolButton:checked{background:#EFF6FF;border-color:#9DB7F8;color:#1D4ED8;}"
    )

    browse = getattr(context_bar, "browse", None) if context_bar is not None else None
    insert_at = row.indexOf(browse) if browse is not None else -1
    if insert_at < 0:
        scan = getattr(page, "_protect_source_scan", None)
        insert_at = row.indexOf(scan) if scan is not None else row.count()
    row.insertWidget(max(0, insert_at), toggle)

    old_parent = settings_strip.parentWidget()
    old_layout = old_parent.layout() if old_parent is not None else None
    if old_layout is not None:
        old_layout.removeWidget(settings_strip)
    settings_strip.setParent(page.preview_card)
    preview_layout = page.preview_card.layout()
    command = getattr(page, "_protect_2026_unified_row", None)
    command_index = preview_layout.indexOf(command) if preview_layout is not None else -1
    if preview_layout is not None:
        preview_layout.insertWidget(
            command_index + 1 if command_index >= 0 else 1,
            settings_strip,
        )

    settings_strip.setStyleSheet(
        "QFrame#RedesignSettingsStrip{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:11px;}"
    )
    if strip_layout is not None:
        strip_layout.setContentsMargins(10, 8, 10, 9)
        strip_layout.setSpacing(5)

    try:
        toggle.toggled.disconnect()
    except (RuntimeError, TypeError):
        pass

    def sync_scan_settings(opened: bool) -> None:
        advanced_panel.setVisible(opened)
        settings_strip.setVisible(opened)
        toggle.setText("Hide settings" if opened else "Scan settings")

    toggle.toggled.connect(sync_scan_settings)
    toggle.setChecked(False)
    sync_scan_settings(False)
    page._protect_2026_scan_settings_toggle = toggle


def _restore_empty_document_surface(page) -> None:
    """Keep the large two-panel workspace visible after the real Clear action."""
    if str(page.pdf_path.text() or "").strip():
        return
    if str(page.text_input.toPlainText() or "").strip():
        return

    page._protect_entry_force_empty = True

    preview_card = getattr(page, "preview_card", None)
    splitter = getattr(page, "document_preview_splitter", None)
    original_panel = getattr(page, "original_document_panel", None)
    protected_panel = getattr(page, "protected_document_panel", None)
    empty_state = getattr(page, "_protect_source_empty_state", None)
    original_stack = getattr(page, "original_view_stack", None)
    text_input = getattr(page, "text_input", None)

    for widget in (preview_card, splitter, original_panel, protected_panel):
        if widget is not None:
            widget.show()

    if empty_state is not None:
        empty_state.setMinimumHeight(420)
        empty_state.show()
    if text_input is not None:
        text_input.hide()
    if original_stack is not None:
        original_stack.hide()

    document = getattr(page, "_redesign_document_mode", None)
    paste = getattr(page, "_redesign_paste_mode", None)
    if document is not None:
        document.setChecked(True)
    if paste is not None:
        paste.setChecked(False)

    tabs = getattr(page, "preview_tabs", None)
    if tabs is not None and tabs.count() > 1:
        tabs.setTabVisible(1, True)
        tabs.setCurrentIndex(1)

    sync_entry = getattr(page, "_protect_source_empty_state_sync", None)
    if callable(sync_entry):
        sync_entry()
    sync_protected = getattr(page, "_protect_protected_empty_state_sync", None)
    if callable(sync_protected):
        sync_protected()


def _install_clear_empty_state_guard(page) -> None:
    clear = getattr(page, "clear_button", None)
    if clear is None or bool(getattr(page, "_protect_2026_clear_guard", False)):
        return
    page._protect_2026_clear_guard = True

    def schedule(*_args) -> None:
        for delay in (0, 80, 250, 500):
            QTimer.singleShot(delay, lambda p=page: _restore_empty_document_surface(p))

    clear.clicked.connect(schedule)


def _style_figure_two_mode_row(page) -> None:
    """Make the real mode bar read like the approved light tab/status row."""
    mode_bar = getattr(page, "_polish_protect_mode_bar", None)
    mode_row = mode_bar.layout() if mode_bar is not None else None
    if not isinstance(mode_row, QHBoxLayout):
        return

    mode_bar.setStyleSheet(
        "QFrame#ProtectModeBar{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:11px;}"
    )
    mode_row.setContentsMargins(6, 6, 6, 6)
    mode_row.setSpacing(4)

    for label in mode_bar.findChildren(QLabel):
        if label.text().strip().upper() in {"SOURCE", "VIEW"}:
            label.hide()
            label.setMaximumWidth(0)

    for frame in mode_bar.findChildren(
        QFrame,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    ):
        if frame.layout() is None:
            frame.hide()
            frame.setMaximumWidth(0)

    document = getattr(page, "_redesign_document_mode", None)
    paste = getattr(page, "_redesign_paste_mode", None)
    for button in (document, paste):
        if button is None:
            continue
        button.setMinimumHeight(40)
        button.setMaximumHeight(42)
        button.setMinimumWidth(102)
        button.setMaximumWidth(110)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#475467;border:none;"
            "border-bottom:2px solid transparent;padding:8px 7px;"
            "font-size:7.6px;font-weight:850;text-align:left;}"
            "QPushButton:hover{background:#F8FCFC;color:#0B7180;}"
            "QPushButton:checked{background:#F8FCFC;color:#0B858A;"
            "border-bottom:2px solid #0B858A;}"
        )

    connected = getattr(page, "_protect_source_connected", None)
    if connected is not None:
        _remove_from_layout_tree(page.preview_card.layout(), connected)
        connected.setParent(mode_bar)
        connected.setText("Import source")
        connected.setMinimumHeight(38)
        connected.setMaximumHeight(40)
        connected.setMinimumWidth(116)
        connected.setMaximumWidth(124)
        connected.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#1D4ED8;border:1px solid #BFD1FE;"
            "border-radius:8px;padding:6px 5px;font-size:7.2px;font-weight:900;}"
            "QPushButton:hover{background:#EFF6FF;border-color:#9DB7F8;}"
        )
        paste_index = mode_row.indexOf(paste) if paste is not None else -1
        mode_row.insertWidget(paste_index + 1 if paste_index >= 0 else 0, connected)
        connected.show()

    view_buttons = {}
    for button in mode_bar.findChildren(QPushButton):
        text = " ".join(button.text().split())
        if text not in {"Protected text", "Original + Protected"}:
            continue
        view_buttons[text] = button
        button.hide()
        button.setMaximumWidth(0)

    if len(view_buttons) == 2 and getattr(page, "_protect_2026_view_menu", None) is None:
        view_menu = QToolButton(mode_bar)
        view_menu.setText("View")
        view_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        view_menu.setMinimumHeight(38)
        view_menu.setMaximumHeight(40)
        view_menu.setMinimumWidth(72)
        view_menu.setMaximumWidth(80)
        view_menu.setStyleSheet(
            "QToolButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:8px;padding:6px 10px;font-size:8px;font-weight:850;}"
            "QToolButton:hover{background:#F8FAFC;border-color:#9DB7F8;color:#1D4ED8;}"
            "QToolButton::menu-indicator{width:10px;}"
        )
        menu = QMenu(view_menu)
        protected_action = menu.addAction("Protected text")
        compare_action = menu.addAction("Original + Protected")
        protected_action.triggered.connect(
            lambda _checked=False: view_buttons["Protected text"].click()
        )
        compare_action.triggered.connect(
            lambda _checked=False: view_buttons["Original + Protected"].click()
        )
        view_menu.setMenu(menu)

        connected_index = mode_row.indexOf(connected) if connected is not None else -1
        paste_index = mode_row.indexOf(paste) if paste is not None else -1
        insert_after = connected_index if connected_index >= 0 else paste_index
        mode_row.insertWidget(insert_after + 1 if insert_after >= 0 else 0, view_menu)

        def sync_view_menu(index: int) -> None:
            view_menu.setText("View")
            view_menu.setToolTip(
                "Current view: Protected text"
                if index == 0
                else "Current view: Original + Protected"
            )

        page.preview_tabs.currentChanged.connect(sync_view_menu)
        sync_view_menu(page.preview_tabs.currentIndex())
        page._protect_2026_view_menu = view_menu

    language_panel = getattr(page, "_protect_document_language_panel", None)
    language = getattr(page, "document_language_combo", None)
    settings = getattr(page, "_protect_2026_scan_settings_toggle", None)
    clear = getattr(page, "clear_button", None)
    scan = getattr(page, "_protect_source_scan", None)

    if language_panel is not None and language is not None:
        _remove_from_layout_tree(page.preview_card.layout(), language_panel)
        language_panel.setParent(mode_bar)
        language_panel.setMinimumWidth(112)
        language_panel.setMaximumWidth(120)
        language.setMinimumWidth(112)
        language.setMaximumWidth(120)
        language.setMinimumHeight(34)
        language.setIconSize(QSize(20, 14))
        mode_row.addWidget(language_panel)

    for widget, minimum, maximum in (
        (settings, 128, 138),
        (clear, 62, 70),
        (scan, 128, 140),
    ):
        if widget is None:
            continue
        _remove_from_layout_tree(page.preview_card.layout(), widget)
        widget.setParent(mode_bar)
        widget.setMinimumHeight(40)
        widget.setMaximumHeight(44)
        widget.setMinimumWidth(minimum)
        widget.setMaximumWidth(maximum)
        mode_row.addWidget(widget)
        widget.show()

    comparison_note = getattr(page, "comparison_note", None)
    if comparison_note is not None:
        # The approved mode row keeps only actionable controls.
        comparison_note.hide()
        comparison_note.setMaximumHeight(0)

    fidelity = getattr(page, "_protect_fidelity_status", None)
    if isinstance(fidelity, QLabel):
        _remove_from_layout_tree(page.preview_card.layout(), fidelity)
        fidelity.hide()
        fidelity.setMaximumHeight(0)

    legend = getattr(page, "color_legend", None)
    if isinstance(legend, QLabel):
        _remove_from_layout_tree(page.preview_card.layout(), legend)
        legend.setParent(mode_bar)
        legend.setWordWrap(False)
        legend.setMinimumHeight(36)
        legend.setMaximumHeight(38)
        legend.setMinimumWidth(172)
        legend.setMaximumWidth(225)
        legend.setStyleSheet(
            "QLabel{background:#F8FAFC;color:#475467;border:1px solid #E4E7EC;"
            "border-radius:8px;padding:6px 10px;font-size:8px;font-weight:750;}"
        )
        mode_row.addWidget(legend)

    safe_badge = _find_label(page.protected_document_panel, "Safe copy preview")
    if safe_badge is not None:
        _remove_from_layout_tree(page.protected_document_panel.layout(), safe_badge)
        safe_badge.setParent(mode_bar)
        safe_badge.setMinimumHeight(36)
        safe_badge.setMaximumHeight(38)
        safe_badge.setText("Safe preview")
        safe_badge.setMinimumWidth(118)
        safe_badge.setMaximumWidth(130)
        safe_badge.setStyleSheet(
            "QLabel{background:#FFFFFF;color:#2563EB;border:1px solid #BFD1FE;"
            "border-radius:8px;padding:6px 8px;font-size:7.3px;font-weight:850;}"
        )
        mode_row.addWidget(safe_badge)


def _finalize_command_and_view_rows(main_window) -> None:
    """Apply the approved figure-two hierarchy using existing real widgets."""
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    row_frame = getattr(page, "_protect_2026_unified_row", None)
    row = row_frame.layout() if row_frame is not None else None
    context_bar = getattr(page, "_managed_workspace_context_bar", None)
    if not isinstance(row, QHBoxLayout):
        return

    row.setContentsMargins(8, 7, 8, 7)
    row.setSpacing(6)

    for name in (
        "_protect_2026_workflow_button",
        "_protect_source_upload",
        "_protect_source_paste",
    ):
        button = getattr(page, name, None)
        if button is None:
            continue
        _remove_from_layout_tree(page.preview_card.layout(), button)
        button.hide()
        button.setMaximumWidth(0)

    if context_bar is not None:
        source = context_bar.source_combo
        source.setMinimumWidth(130)
        source.setMaximumWidth(175)
        source.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        source.view().setMinimumWidth(235)
        source.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:9px;padding:7px 5px;font-size:7.5px;font-weight:750;}"
            "QComboBox:hover{border-color:#AFC7FA;background:#FCFDFF;}"
            f"QComboBox:focus{{border:1px solid {BLUE};}}"
            "QComboBox::drop-down{border:none;width:20px;}"
            "QComboBox QAbstractItemView{background:#FFFFFF;color:#344054;"
            "border:1px solid #D0D5DD;selection-background-color:#EEF4FF;"
            "selection-color:#101828;padding:4px;}"
        )
        source_host = source.parentWidget()
        if source_host is not None:
            source_host.setMinimumWidth(130)
            source_host.setMaximumWidth(175)
            source_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        context_bar.workspace_combo.setMinimumWidth(145)
        context_bar.workspace_combo.setMaximumWidth(195)
        context_bar.workspace_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        workspace_host = context_bar.workspace_combo.parentWidget()
        if workspace_host is not None:
            workspace_host.setMinimumWidth(145)
            workspace_host.setMaximumWidth(195)
            workspace_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        context_bar.account_combo.setMinimumWidth(170)
        context_bar.account_combo.setMaximumWidth(230)
        context_bar.account_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        account_host = context_bar.account_combo.parentWidget()
        if account_host is not None:
            account_host.setMinimumWidth(170)
            account_host.setMaximumWidth(230)
            account_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    language = getattr(page, "document_language_combo", None)
    language_panel = getattr(page, "_protect_document_language_panel", None)
    if language is not None:
        for index in range(language.count()):
            code = str(language.itemData(index) or "")
            if code == "en":
                language.setItemText(index, "English")
                language.setItemIcon(index, _language_flag("en"))
            elif code == "it":
                language.setItemText(index, "Italiano")
                language.setItemIcon(index, _language_flag("it"))
        language.setMinimumWidth(105)
        language.setMaximumWidth(125)
    if language_panel is not None:
        language_panel.setMinimumWidth(105)
        language_panel.setMaximumWidth(125)

    _move_scan_settings(page, row, context_bar)

    # Figure 2 keeps source selection in the large Original-document card. The
    # real connected-source action stays alive and is triggered from that card.
    browse = getattr(context_bar, "browse", None) if context_bar is not None else None
    if browse is not None:
        if row.indexOf(browse) >= 0:
            row.removeWidget(browse)
        browse.hide()
        page._protect_2026_connected_browse_action = browse

    scan = getattr(page, "_protect_source_scan", None)
    if scan is not None:
        scan.setText("Scan + Protect")
        scan.setMinimumHeight(46)
        scan.setMaximumHeight(50)
        scan.setMinimumWidth(140)
        scan.setMaximumWidth(165)
        scan.setStyleSheet(
            "QPushButton{background:#2563EB;color:#FFFFFF;border:1px solid #2563EB;"
            "border-radius:10px;padding:9px 5px;font-size:7.4px;font-weight:900;}"
            "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
            "QPushButton:disabled{background:#D0D5DD;color:#FFFFFF;border-color:#D0D5DD;}"
        )

    clear = getattr(page, "clear_button", None)
    if clear is not None:
        _remove_from_layout_tree(page.preview_card.layout(), clear)
        clear.setParent(row_frame)
        scan_index = row.indexOf(scan) if scan is not None else -1
        row.insertWidget(scan_index if scan_index >= 0 else row.count(), clear)
        clear.setText("Clear")
        clear.setMinimumHeight(46)
        clear.setMaximumHeight(50)
        clear.setMinimumWidth(76)
        clear.setMaximumWidth(90)
        clear.setToolTip("Clear this Protect session and return to the empty workspace.")
        clear.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:10px;padding:8px 7px;font-size:8.2px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
            "QPushButton:pressed{background:#F2F4F7;}"
        )
        clear.show()

    bottom_bar = getattr(page, "_polish_protect_bottom_bar", None)
    if bottom_bar is not None:
        bottom_bar.hide()
        bottom_bar.setMinimumHeight(0)
        bottom_bar.setMaximumHeight(0)

    _style_figure_two_mode_row(page)

    # Workspace, provider and account selection now live in the connected-source
    # picker. Their original widgets remain alive there, while this redundant row
    # is removed from the Protect surface.
    row_frame.hide()
    row_frame.setMinimumHeight(0)
    row_frame.setMaximumHeight(0)

    splitter = getattr(page, "document_preview_splitter", None)
    if splitter is not None:
        splitter.setMinimumHeight(430)
        splitter.setSizes([650, 650])
    empty_state = getattr(page, "_protect_source_empty_state", None)
    if empty_state is not None:
        empty_state.setMinimumHeight(360)
    text_input = getattr(page, "text_input", None)
    if text_input is not None:
        text_input.setMinimumHeight(360)

    _install_clear_empty_state_guard(page)


def apply_mockup_protect_refinement_suite_2026(main_window) -> None:
    """Apply the approved presentation and local-only review behavior in order."""
    apply_mockup_protect_workspace_refinement_2026(main_window)
    apply_mockup_protect_explainability_2026(main_window)
    apply_mockup_protect_findings_refinement_2026(main_window)
    apply_mockup_protect_manual_sensitive_2026(main_window)
    apply_mockup_protect_compact_workflow_2026(main_window)
    apply_mockup_protect_compact_steps_2026(main_window)
    apply_mockup_protect_manual_sensitive_runtime_fix_2026(main_window)
    apply_mockup_protect_review_experience_2026(main_window)
    apply_mockup_protect_review_controls_2026(main_window)
    apply_protect_image_review_regression_fix(main_window)
    apply_mockup_protect_entry_surface_2026(main_window)
    _finalize_command_and_view_rows(main_window)
