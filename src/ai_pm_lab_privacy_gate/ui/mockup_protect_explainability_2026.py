from __future__ import annotations

"""Reusable explainability layer for Protect.

Keep the main surface compact: short tooltips for obvious controls and one shared
product-dialog language for concepts that need more than a sentence.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QPushButton, QToolButton

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import BLUE, BLUE_SOFT, INK, MUTED
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import PrivacyGateProductDialog


class ProtectInfoDialog(PrivacyGateProductDialog):
    def __init__(self, parent, *, title: str, subtitle: str, points: tuple[str, ...]) -> None:
        super().__init__(
            parent,
            title=title,
            subtitle=subtitle,
            icon_name="protect",
            width=610,
        )
        for point in points:
            self.add_notice(point)
        self.add_notice(
            "Privacy boundary: original content, document previews, custom sensitive values and restore mappings remain local unless the user explicitly performs an approved outbound action.",
            privacy=True,
        )
        self.add_actions(primary_text="Got it", primary_callback=self.accept, secondary_text="Close")


def _open_info(parent, title: str, subtitle: str, *points: str) -> None:
    ProtectInfoDialog(parent, title=title, subtitle=subtitle, points=tuple(points)).exec()


def _find_layout(layout: QLayout | None, widget) -> QLayout | None:
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


def _info_button(parent, title: str, subtitle: str, *points: str) -> QToolButton:
    button = QToolButton(parent)
    button.setText("i")
    button.setFixedSize(24, 24)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(subtitle)
    button.setStyleSheet(
        f"QToolButton{{background:{BLUE_SOFT};color:{BLUE};border:1px solid #C7D7FE;"
        "border-radius:12px;font-size:9px;font-weight:950;padding:0;}"
        "QToolButton:hover{background:#E0EAFF;border-color:#AFC6FF;}"
    )
    button.clicked.connect(lambda _checked=False: _open_info(parent, title, subtitle, *points))
    return button


def _attach_info_after_label(page, label_text: str, title: str, subtitle: str, *points: str) -> None:
    for label in page.findChildren(QLabel):
        if " ".join(label.text().split()).lower() != label_text.lower():
            continue

        # Labels live inside nested cards (workspace bar, preview card, findings
        # card), not necessarily in ProtectionPage's direct root layout. Walk up
        # through parents until the owning box layout is found.
        layout = None
        parent = label.parentWidget()
        while parent is not None and layout is None:
            layout = _find_layout(parent.layout(), label)
            parent = parent.parentWidget()
        if layout is None:
            return

        key = "_protect_info_" + title.lower().replace(" ", "_").replace("/", "_")
        if getattr(page, key, None) is not None:
            return
        button = _info_button(page, title, subtitle, *points)
        index = layout.indexOf(label)
        layout.insertWidget(index + 1, button, 0, Qt.AlignmentFlag.AlignVCenter)
        setattr(page, key, button)
        return


def _enhance_flow(page) -> None:
    flow = getattr(page, "_protect_2026_flow", None)
    if flow is None:
        return
    row = flow.layout()
    if not isinstance(row, QHBoxLayout):
        return

    step_titles = {"Add source", "Scan locally", "Review", "Use safe copy"}
    details = {
        "Upload, connected app or paste",
        "Detect sensitive information",
        "Choose what PrivacyGate protects",
        "Save, download or approved AI",
    }
    for label in flow.findChildren(QLabel):
        text = " ".join(label.text().split())
        if text in step_titles:
            label.setStyleSheet(
                f"color:{INK};font-size:9.5px;font-weight:900;background:transparent;border:none;"
            )
        elif text in details:
            label.setStyleSheet(
                f"color:{MUTED};font-size:7.8px;font-weight:550;background:transparent;border:none;"
            )
        elif text in {"1", "2", "3", "4"}:
            label.setFixedSize(28, 28)
            label.setStyleSheet(
                f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #C7D7FE;"
                "border-radius:14px;font-size:8.5px;font-weight:950;"
            )

    how = QPushButton("How it works")
    how.setIcon(icon("info", color=BLUE, size=15))
    how.setIconSize(QSize(15, 15))
    how.setMinimumHeight(34)
    how.setCursor(Qt.CursorShape.PointingHandCursor)
    how.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:7px 10px;font-size:8px;font-weight:850;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
    )
    how.clicked.connect(
        lambda _checked=False: _open_info(
            page,
            "How Protect works",
            "Four local-first steps from source to safe copy.",
            "1 · Add source — Upload a local document, browse an approved connected account, or paste text.",
            "2 · Scan locally — PrivacyGate detects sensitive information on this device and does not upload the original document for detection.",
            "3 · Review — Checked items are protected; unchecked items intentionally remain visible. You can also add a missed sensitive value manually.",
            "4 · Use safe copy — Save locally, download the protected file, or run Privacy Preflight before an approved AI handoff.",
        )
    )
    row.addWidget(how, 0, Qt.AlignmentFlag.AlignVCenter)
    page._protect_2026_how_it_works = how


def _install_tooltips(page) -> None:
    descriptions = (
        (getattr(page, "_protect_source_upload", None), "Upload a local document. The original file stays on this device."),
        (getattr(page, "_protect_source_connected", None), "Choose content from a connected provider and bring its working copy into the local Protect session."),
        (getattr(page, "_protect_source_paste", None), "Paste text directly into this local Protect session."),
        (getattr(page, "_protect_source_scan", None), "Analyze the selected source locally, apply the selected protection choices, and create the safe copy."),
        (getattr(page, "_redesign_document_mode", None), "Use or inspect the document source in this Protect session."),
        (getattr(page, "_redesign_paste_mode", None), "Use or inspect pasted text in this Protect session."),
        (getattr(page, "focus_preview_button", None), "Expand the real Original + Protected document comparison without creating another copy of the preview."),
        (getattr(page, "categories_button", None), "Show detected categories and choose which category groups should be protected."),
        (getattr(page, "reset_selections_button", None), "Reset the review to the default state and select all detected items again."),
        (getattr(page, "protect_all_button", None), "Mark every detected item for protection."),
        (getattr(page, "keep_all_button", None), "Leave every detected value visible in the protected result."),
        (getattr(page, "invert_selection_button", None), "Reverse every Protect / Keep choice."),
        (getattr(page, "add_sensitive_button", None), "Manually add exact text that PrivacyGate should protect, then regenerate the safe copy."),
        (getattr(page, "verification_metric", None), "Open the result of PrivacyGate's second local scan of the protected copy."),
    )
    for widget, text in descriptions:
        if widget is not None:
            widget.setToolTip(text)

    if page.preview_tabs.count() > 0:
        page.preview_tabs.setTabToolTip(
            0,
            "Read the protected text version for the currently selected source.",
        )
    if page.preview_tabs.count() > 1:
        page.preview_tabs.setTabToolTip(
            1,
            "Compare the original source and the regenerated protected document side by side.",
        )

    for button in page.findChildren(QPushButton):
        text = " ".join(button.text().split())
        if text == "View Preflight summary":
            button.setToolTip(
                "Review the company-policy Privacy Preflight before an AI handoff. The document itself is not sent to the organization control plane."
            )
        elif text == "Browse connected content":
            button.setToolTip(
                "Browse the selected connected account after workspace policy and account approval checks."
            )


def apply_mockup_protect_explainability_2026(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or bool(getattr(page, "_protect_2026_explainability", False)):
        return
    page._protect_2026_explainability = True

    _enhance_flow(page)
    _install_tooltips(page)

    _attach_info_after_label(
        page,
        "WORKSPACE CONTEXT",
        "Workspace context",
        "Controls which workspace policy, provider and connected account apply to this local Protect session.",
        "Workspace selects Personal or an Organization context.",
        "Connected source chooses the provider; Account shows exactly which login is being used.",
        "Policy chips summarize the policy state already loaded in memory; they do not create additional cloud logging.",
    )
    _attach_info_after_label(
        page,
        "Document workspace",
        "Document workspace",
        "The two large panels are the real source and protected-document viewers.",
        "Original document shows the local source.",
        "Protected document is regenerated from the current checked findings.",
        "Protected text is the safe text representation; Original + Protected keeps the visual comparison.",
    )
    _attach_info_after_label(
        page,
        "Detected items",
        "Review detected items",
        "Review exactly what PrivacyGate will protect before using the safe copy.",
        "Checked = protect. Unchecked = intentionally keep visible.",
        "Category colors match the colors used in the protected document and text preview.",
        "Add sensitive item is for a value the automatic detector missed.",
    )
