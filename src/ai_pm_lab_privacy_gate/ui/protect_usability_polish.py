from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.iconography import icon


NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7180"
MUTED = "#61798A"
BORDER = "#D7E2EA"
SOFT_TEAL = "#F2FAFA"

_EMPTY_GUIDANCE = (
    "START HERE  •  Choose Upload, Connected sources, or Paste text — then Scan locally. "
    "Review what PrivacyGate finds before creating the protected copy."
)


def _find_label(root, text: str) -> QLabel | None:
    for label in root.findChildren(QLabel):
        if label.text().strip() == text:
            return label
    return None


def _style_empty_guidance(label: QLabel, empty: bool) -> None:
    if empty:
        label.setStyleSheet(
            f"QLabel{{background:{SOFT_TEAL};color:{INK};border:1px solid #CDE7E9;"
            "border-radius:8px;padding:7px 10px;font-size:9px;font-weight:750;}"
        )
        return
    label.setStyleSheet(
        f"QLabel{{background:#FFFFFF;color:{MUTED};border:1px solid #E1E8ED;"
        "border-radius:8px;padding:6px 9px;font-size:9px;}"
    )


def _install_legend_guidance(page) -> None:
    legend = getattr(page, "color_legend", None)
    if legend is None:
        return

    def refresh() -> None:
        empty = not bool(getattr(page, "current_findings", ()))
        if empty:
            legend.setText(_EMPTY_GUIDANCE)
        _style_empty_guidance(legend, empty)

    original_update = getattr(page, "_update_color_legend", None)
    if callable(original_update) and not bool(
        getattr(page, "_privacygate_usability_legend_wrapped", False)
    ):
        page._privacygate_usability_legend_wrapped = True

        def update_color_legend(self) -> None:
            original_update()
            refresh()

        page._update_color_legend = MethodType(update_color_legend, page)

    for signal_owner, signal_name in (
        (getattr(page, "scan_button", None), "clicked"),
        (getattr(page, "clear_button", None), "clicked"),
        (getattr(page, "text_input", None), "textChanged"),
        (getattr(page, "pdf_path", None), "textChanged"),
    ):
        signal = getattr(signal_owner, signal_name, None) if signal_owner is not None else None
        if signal is not None:
            signal.connect(lambda *_args: QTimer.singleShot(0, refresh))

    refresh()


def _polish_source_actions(page) -> None:
    bar = getattr(page, "_protect_source_quick_bar", None)
    if bar is not None:
        bar.setStyleSheet(
            "QFrame#ProtectSourceQuickBar{background:#FBFEFE;border:1px solid #CFE2E5;"
            "border-radius:10px;}"
        )

    specs = (
        (
            "_protect_source_upload",
            "Choose a local PDF, Word, or Excel file. The original stays on this device.",
        ),
        (
            "_protect_source_connected",
            "Import from a connected app into the local Protect workflow before anything is sent to AI.",
        ),
        (
            "_protect_source_paste",
            "Paste text or email content directly into the Original document area.",
        ),
        (
            "_protect_source_scan",
            "Step 2 — detect sensitive data locally. Scanning does not change the original document.",
        ),
        (
            "_protect_source_protect",
            "Step 4 — create the safe copy using the items you reviewed and chose to protect.",
        ),
    )
    for name, tooltip in specs:
        button = getattr(page, name, None)
        if button is not None:
            button.setToolTip(tooltip)

    mode_bar = getattr(page, "_polish_protect_mode_bar", None)
    if mode_bar is not None:
        mode_bar.setStyleSheet(
            "QFrame#ProtectModeBar{background:#FFFFFF;border:1px solid #D7E2EA;"
            "border-radius:9px;}"
        )


def _polish_advanced_settings(page) -> None:
    settings_strip = page.findChild(QFrame, "RedesignSettingsStrip")
    advanced_panel = page.findChild(QFrame, "RedesignAdvanced")
    if settings_strip is None or advanced_panel is None:
        return
    layout = settings_strip.layout()
    if not isinstance(layout, QVBoxLayout):
        return

    settings_strip.setStyleSheet(
        "QFrame#RedesignSettingsStrip{background:#FFFFFF;border:1px solid #D7E2EA;"
        "border-radius:12px;}"
        "QFrame#RedesignAdvanced{background:#F8FBFC;border:1px solid #DFE8ED;"
        "border-radius:9px;}"
    )

    toggles = settings_strip.findChildren(
        QToolButton,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    )
    toggle = toggles[0] if toggles else None
    if toggle is not None:
        toggle.setObjectName("AdvancedProtectionToggle")
        toggle.setIcon(icon("protect", color=TEAL, size=18))
        toggle.setIconSize(QSize(18, 18))
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setToolTip(
            "Optional controls for detection rules, protected data categories, replacement method, and detection sensitivity."
        )
        toggle.setStyleSheet(
            "QToolButton#AdvancedProtectionToggle{background:transparent;color:#062B4F;border:none;"
            "padding:7px 8px;text-align:left;font-size:10px;font-weight:900;}"
            "QToolButton#AdvancedProtectionToggle:hover{color:#0B7180;}"
        )

        def sync_toggle(checked: bool) -> None:
            toggle.setText(
                "Advanced protection settings  —  hide"
                if checked
                else "Advanced protection settings  —  optional"
            )

        toggle.toggled.connect(sync_toggle)
        sync_toggle(toggle.isChecked())

    helper = QLabel(
        "What these settings do:  Industry profile adapts detection to the document context  •  "
        "Protection scope chooses which sensitive-data categories are scanned  •  "
        "Protection mode decides how detected values are replaced  •  "
        "Confidence controls detection sensitivity. Recommended defaults work for most documents."
    )
    helper.setObjectName("AdvancedProtectionExplanation")
    helper.setWordWrap(True)
    helper.setStyleSheet(
        "QLabel#AdvancedProtectionExplanation{background:#F2FAFA;color:#496A72;"
        "border:1px solid #D4E9EA;border-radius:8px;padding:8px 10px;"
        "font-size:9px;font-weight:700;}"
    )

    panel_index = layout.indexOf(advanced_panel)
    layout.insertWidget(panel_index + 1, helper)
    helper.setVisible(advanced_panel.isVisible())
    if toggle is not None:
        toggle.toggled.connect(helper.setVisible)

    tooltips = {
        getattr(page, "profile_combo", None): (
            "Industry profile adapts detection rules to the kind of document you are protecting."
        ),
        getattr(page, "scope_combo", None): (
            "Protection scope controls which groups of sensitive data PrivacyGate scans for."
        ),
        getattr(page, "mode_combo", None): (
            "Protection mode controls how detected values are replaced. Reversible placeholders can be restored locally."
        ),
        getattr(page, "threshold_input", None): (
            "Confidence controls detection sensitivity: lower catches more possibilities; higher is stricter and reduces false positives."
        ),
    }
    for widget, tooltip in tooltips.items():
        if widget is not None:
            widget.setToolTip(tooltip)


def _polish_copy_and_hierarchy(page) -> None:
    subtitle = getattr(page, "_redesign_subtitle", None)
    if subtitle is not None:
        subtitle.setText(
            "Choose a source → scan locally → review detections → create the protected copy."
        )
        subtitle.setStyleSheet(f"font-size:12px;color:{MUTED};font-weight:600;")

    heading = _find_label(page, "Protected preview")
    if heading is not None:
        heading.setText("Protected preview  •  source → safe copy")
        heading.setToolTip(
            "Work from left to right: add the source, scan it, review detections, then create the protected copy."
        )
        heading.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")

    comparison_note = getattr(page, "comparison_note", None)
    if comparison_note is not None:
        comparison_note.setText(
            "Original source on the left. After Scan and review, Protect creates the safe copy on the right."
        )
        comparison_note.setStyleSheet(
            f"color:{MUTED};font-size:9px;font-weight:650;padding:1px 0 3px 0;"
        )


def apply_protect_usability_polish(main_window) -> None:
    """Make Protect self-explanatory without moving or replacing existing controls."""
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_privacygate_usability_polished", False)):
        return
    page._privacygate_usability_polished = True

    _polish_copy_and_hierarchy(page)
    _polish_source_actions(page)
    _polish_advanced_settings(page)
    _install_legend_guidance(page)
