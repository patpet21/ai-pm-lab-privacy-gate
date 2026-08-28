from __future__ import annotations

"""Approved 2026 Restore presentation layer.

Presentation only: the existing RestorePage keeps ownership of file loading,
Library mapping selection, DocumentRestoreService, local previews and downloads.
This module only recomposes those real controls into the same visual language as
Protect.
"""

from types import MethodType

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
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
    TEAL,
    TEAL_SOFT,
    TEXT,
    WHITE,
)
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import (
    PrivacyGateProductDialog,
)


def _secondary_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:7px 11px;font-size:8.5px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:7px 12px;font-size:8.5px;font-weight:850;}"
        "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
        "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
    )


def _tiny_step(number: str, text: str) -> QLabel:
    label = QLabel(f"{number}  {text}")
    label.setStyleSheet(
        f"background:{BLUE_SOFT};color:{BLUE};border:1px solid #D6E4FF;"
        "border-radius:8px;padding:4px 7px;font-size:7.5px;font-weight:850;"
    )
    return label


class RestoreHowItWorksDialog(PrivacyGateProductDialog):
    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            title="How Restore works",
            subtitle="Bring original values back after AI work without sending the restore key or original values anywhere.",
            icon_name="restore",
            width=650,
        )
        for title, detail in (
            ("1 · Add AI result", "Upload the AI-returned file or paste text that still contains PrivacyGate placeholders."),
            ("2 · Match original", "Choose the original protected Library entry. Only reversible documents with a local restore mapping are offered."),
            ("3 · Restore locally", "PrivacyGate matches placeholders to the encrypted local mapping and restores the values on this PC."),
            ("4 · Use result", "Review, copy, download or edit the restored text locally. Nothing is sent back to the AI."),
        ):
            self.add_notice(f"{title} — {detail}")
        self.add_notice(
            "Privacy boundary: restore mappings, original values, AI result content and restored content stay on this device.",
            privacy=True,
        )
        self.add_actions(primary_text="Got it", primary_callback=self.accept, secondary_text="Close")


def _style_page_header(page) -> None:
    page.setStyleSheet(f"background:{CANVAS};")
    page._outer_layout.setContentsMargins(20, 14, 20, 12)
    page._outer_layout.setSpacing(8)
    page.page_title.setStyleSheet(
        f"color:{INK};font-size:24px;font-weight:950;background:transparent;border:none;"
    )
    page.page_subtitle.setText(
        "Restore original values after AI processing — the mapping and restored content stay local."
    )
    page.page_subtitle.setStyleSheet(
        f"color:{MUTED};font-size:8.5px;background:transparent;border:none;"
    )
    page.local_badge.setText("LOCAL ONLY  ·  ORIGINAL VALUES STAY ON THIS PC")
    page.local_badge.setStyleSheet(
        f"background:{GREEN_SOFT};color:{GREEN};border:1px solid #BBF7D0;"
        "border-radius:9px;padding:7px 10px;font-size:8px;font-weight:900;"
    )

    page.steps_card.hide()
    page.steps_card.setMaximumHeight(0)


def _compact_result_header(page) -> None:
    layout = page.result_section.layout()
    if not isinstance(layout, QVBoxLayout) or layout.count() < 1:
        return
    header = layout.itemAt(0).layout()
    if not isinstance(header, QHBoxLayout):
        return

    title = header.itemAt(0).widget() if header.count() else None
    if isinstance(title, QLabel):
        title.setText("Restore workspace")
        title.setStyleSheet(
            f"color:{INK};font-size:13px;font-weight:900;background:transparent;border:none;"
        )

    # Insert before the pre-existing stretch / metric. This keeps the real result
    # metric as the authoritative restore status.
    index = 1
    for number, text in (("1", "AI result"), ("2", "Match original"), ("3", "Restore"), ("4", "Use result")):
        step = _tiny_step(number, text)
        header.insertWidget(index, step)
        index += 1
        if number != "4":
            arrow = QLabel("›")
            arrow.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;background:transparent;")
            header.insertWidget(index, arrow)
            index += 1

    how = QPushButton("How it works")
    how.setCursor(Qt.CursorShape.PointingHandCursor)
    how.setStyleSheet(_secondary_qss())
    how.setMinimumHeight(32)
    how.setIcon(icon("info", color=BLUE, size=14))
    how.setIconSize(QSize(14, 14))
    how.clicked.connect(lambda _checked=False: RestoreHowItWorksDialog(page).exec())
    header.insertWidget(index, how)
    page._restore_2026_how_button = how

    page.result_metric.setStyleSheet(
        f"background:{TEAL_SOFT};color:{TEAL};border:1px solid #A5F3FC;"
        "border-radius:8px;padding:5px 8px;font-size:7.5px;font-weight:900;"
    )


def _compact_source_toolbar(page) -> None:
    toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if toolbar is None or getattr(page, "_restore_2026_command_bar", None) is not None:
        return
    toolbar.setObjectName("Restore2026SourceToolbar")
    toolbar.setStyleSheet(
        f"QFrame#Restore2026SourceToolbar{{background:{WHITE};border:1px solid {BORDER};border-radius:11px;}}"
    )
    toolbar_layout = toolbar.layout()
    if not isinstance(toolbar_layout, QVBoxLayout):
        return
    toolbar_layout.setContentsMargins(8, 7, 8, 7)
    toolbar_layout.setSpacing(5)

    command = QFrame(objectName="Restore2026CommandBar")
    command.setStyleSheet("QFrame#Restore2026CommandBar{background:transparent;border:none;}")
    row = QHBoxLayout(command)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)

    # Reuse the real drag/drop zone, but collapse its chrome to a compact Upload
    # control. Drag/drop remains supported by the same RestoreDropZone instance.
    page.drop_zone.setMinimumSize(108, 36)
    page.drop_zone.setMaximumSize(126, 38)
    page.drop_zone.setStyleSheet("QFrame#RestoreDropZone{background:transparent;border:none;}")
    page.drop_zone.layout().setContentsMargins(0, 0, 0, 0)
    page.drop_zone.button.setText("Upload file")
    page.drop_zone.button.setMinimumHeight(36)
    page.drop_zone.button.setMaximumHeight(38)
    page.drop_zone.button.setStyleSheet(_secondary_qss())
    page.drop_zone.button.setIcon(icon("upload", color=BLUE, size=14))
    page.drop_zone.button.setIconSize(QSize(14, 14))
    page.drop_zone.filename.hide()
    page.drop_zone.formats.hide()

    page.paste_toggle.setText("Paste text")
    page.paste_toggle.setMinimumHeight(36)
    page.paste_toggle.setStyleSheet(_secondary_qss())
    page.paste_toggle.setIcon(icon("document", color=BLUE, size=14))
    page.paste_toggle.setIconSize(QSize(14, 14))

    page.clear_button.setText("Clear")
    page.clear_button.setMinimumHeight(36)
    page.clear_button.setMaximumWidth(70)
    page.clear_button.setStyleSheet(_secondary_qss())
    page.clear_button.show()

    original = QLabel("Original")
    original.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;font-weight:900;background:transparent;border:none;"
    )

    page.document_combo.setMinimumHeight(36)
    page.document_combo.setMinimumWidth(180)
    page.document_combo.setMaximumWidth(440)
    page.document_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    page.document_combo.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
        "padding:7px 9px;font-size:8px;}"
        f"QComboBox:focus{{border:1px solid {BLUE};}}"
        "QComboBox::drop-down{border:none;width:24px;}"
    )
    if page.document_combo.count() and page.document_combo.itemData(0) is None:
        page.document_combo.setItemText(0, "Choose original mapping…")

    page.restore_button.setText("Restore locally")
    page.restore_button.setMinimumHeight(36)
    page.restore_button.setMaximumWidth(132)
    page.restore_button.setStyleSheet(_primary_qss())
    page.restore_button.setIcon(icon("restore", color="#FFFFFF", size=14))
    page.restore_button.setIconSize(QSize(14, 14))

    row.addWidget(page.drop_zone)
    row.addWidget(page.paste_toggle)
    row.addWidget(page.clear_button)
    row.addSpacing(4)
    row.addWidget(original)
    row.addWidget(page.document_combo, 1)
    row.addWidget(page.restore_button)
    toolbar_layout.insertWidget(0, command)

    # The old nested source row now only contains labels after its controls were
    # transferred to the command bar. Hide that redundant text so it collapses.
    for label in toolbar.findChildren(QLabel):
        if label in {page.token_hint, page.library_status, original}:
            continue
        label.hide()
        label.setMaximumHeight(0)

    page.token_hint.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;background:transparent;border:none;padding:0;"
    )
    page.library_status.setMaximumHeight(26)
    page.library_status.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;background:transparent;border:none;padding:0;"
    )
    page.input_text.setMinimumHeight(90)
    page.input_text.setMaximumHeight(130)
    page.input_text.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
        "padding:10px;font-size:9px;selection-background-color:#D6E4FF;}"
        f"QPlainTextEdit:focus{{border:1px solid {BLUE};}}"
    )

    page._restore_2026_command_bar = command

    previous_refresh = page.refresh

    def refresh_and_compact(self, select_id=None) -> None:
        previous_refresh(select_id)
        if self.document_combo.count() and self.document_combo.itemData(0) is None:
            self.document_combo.setItemText(0, "Choose original mapping…")

    page.refresh = MethodType(refresh_and_compact, page)


def _style_previews(page) -> None:
    page.result_section.setObjectName("Restore2026Workspace")
    page.result_section.setStyleSheet(
        f"QFrame#Restore2026Workspace{{background:{WHITE};border:1px solid {BORDER};border-radius:15px;}}"
    )
    layout = page.result_section.layout()
    if isinstance(layout, QVBoxLayout):
        layout.setContentsMargins(14, 12, 14, 13)
        layout.setSpacing(8)

    page.preview_tabs.setStyleSheet(
        "QTabWidget::pane{background:transparent;border:none;margin-top:4px;}"
        "QTabBar::tab{background:#FFFFFF;color:#475467;border:1px solid #D0D5DD;border-radius:8px;"
        "padding:7px 12px;margin-right:5px;font-size:8px;font-weight:800;}"
        f"QTabBar::tab:selected{{background:{BLUE};color:#FFFFFF;border-color:{BLUE};}}"
        f"QTabBar::tab:hover{{background:{BLUE_SOFT};color:{BLUE};}}"
    )
    page.preview_tabs.tabBar().setExpanding(False)

    page.protected_result_view.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;border-radius:10px;"
        "padding:12px;font-size:10px;}"
    )
    page.output_text.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;border-radius:10px;"
        "padding:12px;font-size:10px;}"
    )

    for panel in page.findChildren(QFrame, "PdfPanel"):
        panel.setStyleSheet(
            f"QFrame#PdfPanel{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;}}"
        )
        panel_layout = panel.layout()
        if panel_layout is not None:
            panel_layout.setContentsMargins(10, 9, 10, 10)
            panel_layout.setSpacing(6)
        for label in panel.findChildren(QLabel):
            text = " ".join(label.text().split())
            if text in {"AI result", "AI result with placeholders", "Restored result"}:
                label.setStyleSheet(
                    f"color:{INK};font-size:10px;font-weight:900;background:transparent;border:none;"
                )
            elif text in {"Placeholders retained", "Local only"}:
                local = text == "Local only"
                label.setText("RESTORED LOCALLY" if local else "CONTAINS PLACEHOLDERS")
                label.setStyleSheet(
                    f"background:{GREEN_SOFT if local else BLUE_SOFT};"
                    f"color:{GREEN if local else BLUE};border:1px solid {'#BBF7D0' if local else '#D6E4FF'};"
                    "border-radius:7px;padding:3px 7px;font-size:7px;font-weight:850;"
                )

    for view in (page.input_pdf_view, page.output_pdf_view):
        view.setStyleSheet("QPdfView{background:#F2F4F7;border:1px solid #EAECF0;border-radius:8px;}")

    for button in (
        page.high_fidelity_button,
        page.full_preview_button,
        page.install_libreoffice_button,
        page.pdf_previous_button,
        page.pdf_next_button,
        page.pdf_zoom_out_button,
        page.pdf_fit_button,
        page.pdf_zoom_in_button,
    ):
        button.setStyleSheet(_secondary_qss())
        button.setMinimumHeight(31)

    page.preview_note.setText(
        "AI result with placeholders on the left · locally restored result on the right."
    )
    page.preview_note.setStyleSheet(
        f"color:{MUTED};font-size:7.5px;background:transparent;border:none;"
    )

    page.safety_note.setText(
        "Restore mapping, original values and restored content stay on this device. Nothing is sent back to the AI."
    )
    page.safety_note.setMaximumHeight(34)
    page.safety_note.setStyleSheet(
        f"background:{GREEN_SOFT};color:#166534;border:1px solid #BBF7D0;border-radius:9px;"
        "padding:7px 10px;font-size:7.5px;font-weight:750;"
    )


def _style_existing_actions(page) -> None:
    page.copy_button.setText("Copy restored text")
    page.download_text_button.setText("Download text")
    for button in (page.copy_button, page.download_text_button):
        button.setStyleSheet(_secondary_qss())
        button.setMinimumHeight(38)
    page.download_button.setStyleSheet(_primary_qss())
    page.download_button.setMinimumHeight(38)


def apply_mockup_restore_final_2026(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    if page is None or bool(getattr(page, "_privacygate_mockup_restore_final_2026", False)):
        return
    page._privacygate_mockup_restore_final_2026 = True

    _style_page_header(page)
    _compact_result_header(page)
    _compact_source_toolbar(page)
    _style_previews(page)
    _style_existing_actions(page)
