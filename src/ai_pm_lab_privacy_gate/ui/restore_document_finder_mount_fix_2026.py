from __future__ import annotations

"""Guaranteed visible mount for the Restore original-document finder.

Qt can keep layout ownership from the legacy Restore source row even after widgets
are visually recomposed. This layer deliberately creates one dedicated command
bar as a sibling of the legacy source toolbar and moves the *same real controls*
into it. No restore behavior is duplicated.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    TEAL,
    TEAL_SOFT,
    WHITE,
)


def _secondary_qss() -> str:
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:9px;padding:7px 10px;font-size:8px;font-weight:850;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        "QPushButton:disabled{background:#F2F4F7;color:#98A2B3;border-color:#EAECF0;}"
    )


def _primary_qss() -> str:
    return (
        f"QPushButton{{background:{BLUE};color:#FFFFFF;border:1px solid {BLUE};"
        "border-radius:9px;padding:7px 11px;font-size:8px;font-weight:900;}"
        "QPushButton:hover{background:#1D4ED8;border-color:#1D4ED8;}"
        "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
    )


def _descriptor(controller):
    try:
        return controller._active_descriptor()
    except Exception:
        return None


def _context_text(controller) -> tuple[str, bool]:
    descriptor = _descriptor(controller)
    organization = bool(descriptor is not None and not descriptor.personal)
    return (str(descriptor.name) if organization else "Personal Library"), organization


def apply_restore_document_finder_mount_fix_2026(main_window) -> None:
    page = getattr(main_window, "restore_page", None)
    controller = getattr(main_window, "_restore_document_finder_controller", None)
    if page is None or controller is None:
        return
    if bool(getattr(page, "_restore_document_finder_mount_fix_2026", False)):
        return
    page._restore_document_finder_mount_fix_2026 = True

    legacy_toolbar = page.findChild(QFrame, "Restore2026SourceToolbar")
    if legacy_toolbar is None:
        legacy_toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if legacy_toolbar is None:
        return

    parent = legacy_toolbar.parentWidget()
    parent_layout = parent.layout() if parent is not None else None
    if not isinstance(parent_layout, QVBoxLayout):
        return

    # Hide the intermediate command frame. Its controls are moved into the
    # dedicated bar below, so the real callbacks/signals remain untouched.
    old_command = getattr(page, "_restore_2026_command_bar", None)
    if old_command is not None:
        old_command.hide()
        old_command.setMaximumHeight(0)

    bar = QFrame(objectName="RestoreFinderCommandBar")
    bar.setStyleSheet(
        f"QFrame#RestoreFinderCommandBar{{background:{WHITE};border:1px solid {BORDER};border-radius:11px;}}"
    )
    row = QHBoxLayout(bar)
    row.setContentsMargins(8, 7, 8, 7)
    row.setSpacing(6)

    # Existing real source controls.
    page.drop_zone.setMinimumSize(108, 36)
    page.drop_zone.setMaximumSize(126, 38)
    page.drop_zone.setStyleSheet("QFrame#RestoreDropZone{background:transparent;border:none;}")
    if page.drop_zone.layout() is not None:
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
    page.paste_toggle.setIcon(icon("paste", color=BLUE, size=14))
    page.paste_toggle.setIconSize(QSize(14, 14))

    page.clear_button.setText("Clear")
    page.clear_button.setMinimumHeight(36)
    page.clear_button.setMaximumWidth(72)
    page.clear_button.setStyleSheet(_secondary_qss())
    page.clear_button.show()

    # Finder controls. Reuse them if the first mount created them; otherwise
    # create them here and bind them to the already-existing controller.
    context_badge = getattr(controller, "context_badge", None)
    if context_badge is None:
        context_badge = QLabel()
        controller.context_badge = context_badge
    context_badge.setMaximumWidth(150)

    find_button = getattr(controller, "find_button", None)
    if find_button is None:
        find_button = QPushButton("Find original")
        find_button.clicked.connect(lambda _checked=False: controller.open_finder())
        controller.find_button = find_button
    find_button.setText("Find original")
    find_button.setCursor(Qt.CursorShape.PointingHandCursor)
    find_button.setIcon(icon("search", color=BLUE, size=14))
    find_button.setIconSize(QSize(14, 14))
    find_button.setMinimumHeight(36)
    find_button.setMinimumWidth(118)
    find_button.setStyleSheet(_secondary_qss())

    selection = getattr(controller, "selection", None)
    if selection is None:
        selection = QPushButton("No original selected · click Find original")
        selection.clicked.connect(lambda _checked=False: controller.open_finder())
        controller.selection = selection
    selection.setCursor(Qt.CursorShape.PointingHandCursor)
    selection.setMinimumHeight(36)
    selection.setMinimumWidth(220)
    selection.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    selection.setStyleSheet(
        "QPushButton{background:#F8FAFC;color:#475467;border:1px solid #EAECF0;"
        "border-radius:9px;padding:7px 10px;text-align:left;font-size:8px;font-weight:750;}"
        f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE};border-color:#D6E4FF;}}"
    )

    page.document_combo.hide()
    page.document_combo.setMaximumWidth(0)

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
    row.addWidget(context_badge)
    row.addWidget(find_button)
    row.addWidget(selection, 1)
    row.addWidget(page.restore_button)

    legacy_index = parent_layout.indexOf(legacy_toolbar)
    parent_layout.insertWidget(max(0, legacy_index), bar)

    # The legacy toolbar is now only a compact helper for pasted text/status.
    # Hide every leftover label except the two real status messages. This removes
    # the oversized half-width Upload/Original row seen in the Windows runtime.
    for label in legacy_toolbar.findChildren(QLabel):
        if label in {page.token_hint, page.library_status}:
            continue
        label.hide()
        label.setMaximumHeight(0)

    # With no pasted text there is no reason for the helper surface to consume
    # vertical space. It becomes visible automatically when Paste text is used.
    def sync_helper_visibility() -> None:
        show_editor = bool(page.input_text.isVisible())
        page.token_hint.setVisible(show_editor)
        page.library_status.setVisible(show_editor)
        legacy_toolbar.setVisible(show_editor)
        legacy_toolbar.setMaximumHeight(170 if show_editor else 0)

    page.paste_toggle.toggled.connect(lambda _checked=False: sync_helper_visibility())
    sync_helper_visibility()

    page._restore_finder_command_bar = bar

    # Make the context and selected-document copy authoritative on the new bar.
    name, organization = _context_text(controller)
    context_badge.setText(name)
    context_badge.setStyleSheet(
        f"background:{TEAL_SOFT if organization else BLUE_SOFT};"
        f"color:{TEAL if organization else BLUE};"
        f"border:1px solid {'#A5F3FC' if organization else '#D6E4FF'};"
        "border-radius:8px;padding:6px 8px;font-size:7.5px;font-weight:900;"
    )
    try:
        controller._update_selection_copy()
    except Exception:
        selection.setText("No original selected · click Find original")
