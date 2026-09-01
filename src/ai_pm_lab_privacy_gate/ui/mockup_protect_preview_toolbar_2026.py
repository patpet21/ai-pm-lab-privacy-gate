from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QFrame, QLayout, QWidget


def _layout_containing_widget(layout: QLayout | None, widget: QWidget) -> QLayout | None:
    """Return the nested layout which directly owns ``widget``."""
    if layout is None:
        return None
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return layout
        nested = item.layout()
        if nested is not None:
            found = _layout_containing_widget(nested, widget)
            if found is not None:
                return found
    return None


def _move_high_fidelity_into_view_toolbar(page: QWidget, source_toolbar: QFrame) -> None:
    button = getattr(page, "high_fidelity_button", None)
    if button is None:
        return

    # The final Protect layer owns the visible VIEW controls. Anchor to the
    # existing compare button instead of recreating any preview action/state.
    compare_button = next(
        (
            candidate
            for candidate in source_toolbar.findChildren(QAbstractButton)
            if "original + protected" in candidate.text().casefold()
        ),
        None,
    )
    if compare_button is None:
        return

    view_row = _layout_containing_widget(source_toolbar.layout(), compare_button)
    if view_row is None or not hasattr(view_row, "insertWidget"):
        return

    old_parent = button.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(button)

    anchor_index = view_row.indexOf(compare_button)
    if anchor_index < 0:
        return
    view_row.insertWidget(anchor_index + 1, button)

    availability = getattr(page, "libreoffice_availability", None)
    availability_text = ""
    if availability is not None:
        availability_text = availability.text().strip()
        availability.hide()

    if availability_text:
        button.setToolTip(availability_text)
    else:
        button.setToolTip(
            "Open a high-fidelity local LibreOffice preview. "
            "The built-in preview remains available."
        )
    button.setVisible(bool(getattr(page, "_libreoffice_available", False)))

    # The old row only existed to host this button and the availability note.
    # Keep it at zero height even if legacy source-refresh code later calls show().
    old_options = getattr(page, "office_preview_options", None)
    if old_options is not None:
        old_options.hide()
        old_options.setMinimumHeight(0)
        old_options.setMaximumHeight(0)
        if old_options.layout() is not None:
            old_options.layout().setContentsMargins(0, 0, 0, 0)
            old_options.layout().setSpacing(0)


def _move_advanced_below_source_toolbar(page: QWidget, source_toolbar: QFrame) -> None:
    preview_card = getattr(page, "preview_card", None)
    if preview_card is None or preview_card.layout() is None:
        return

    settings_strip = page.findChild(QFrame, "RedesignSettingsStrip")
    if settings_strip is None:
        return

    preview_layout = preview_card.layout()
    source_index = preview_layout.indexOf(source_toolbar)
    if source_index < 0:
        return

    # Reuse the exact existing Advanced toggle/panel. This changes hierarchy only;
    # scope, confidence, protection mode and all callbacks remain authoritative.
    old_parent = settings_strip.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(settings_strip)
    settings_strip.setParent(preview_card)

    # Recompute after the move so the insertion stays correct if a previous layer
    # has already adjusted the preview card ordering.
    source_index = preview_layout.indexOf(source_toolbar)
    preview_layout.insertWidget(source_index + 1, settings_strip)


def apply_mockup_protect_preview_toolbar_2026(window: QWidget) -> None:
    """Compact Protect preview controls without changing protection behavior.

    High-fidelity becomes a VIEW action beside Original + Protected, while the
    existing Advanced settings strip occupies the recovered row directly below
    the source/view toolbar. No detector, document, restore or persistence logic
    is replaced here.
    """
    page = getattr(window, "protection_page", None)
    if page is None:
        return

    source_toolbar = page.findChild(QFrame, "EmbeddedSourceToolbar")
    if source_toolbar is None:
        return

    _move_high_fidelity_into_view_toolbar(page, source_toolbar)
    _move_advanced_below_source_toolbar(page, source_toolbar)
