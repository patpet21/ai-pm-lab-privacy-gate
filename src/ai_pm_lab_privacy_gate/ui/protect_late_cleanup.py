from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QWidget


def _layout_widgets(layout, output: set[QWidget]) -> None:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child = item.layout()
        if isinstance(widget, QWidget):
            output.add(widget)
        if child is not None:
            _layout_widgets(child, output)


def _cleanup(page) -> None:
    # These are legacy shells/metrics retained only because the redesigned
    # Protect UI reuses some of their child controls. They must never paint on the
    # final page.
    for name in (
        "setup_toggle",
        "setup_card",
        "local_badge",
        "types_metric",
        "pages_metric",
        "source_metric",
        "verification_metric",
        "workspace",
        "input_tabs",
        "profile_description",
        "scope_description",
        "mode_help",
        "_redesign_start_card",
        "_redesign_help_card",
    ):
        widget = getattr(page, name, None)
        if isinstance(widget, QWidget):
            widget.hide()

    root = page.layout()
    if root is None:
        return

    managed: set[QWidget] = set()
    _layout_widgets(root, managed)

    # The redesign creates a temporary parking QWidget while moving existing
    # controls. On some Qt/Windows combinations that anonymous direct child keeps
    # a tiny geometry and paints fragments of parked controls at the far-left
    # edge (the clipped "M.", blue info dot and small legacy icon seen in the UI).
    # Any non-dialog direct child that is not part of the final page layout is a
    # detached legacy/parking surface and can safely stay hidden.
    direct_children = page.findChildren(
        QWidget,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    )
    for child in direct_children:
        if isinstance(child, QDialog):
            continue
        if child in managed:
            continue
        child.hide()


def apply_protect_late_cleanup(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None:
        return
    _cleanup(page)
    # Some polish passes finish with zero-delay layout work. Re-assert once after
    # that event queue drains so no detached legacy widget gets shown again.
    QTimer.singleShot(0, lambda: _cleanup(page))
    QTimer.singleShot(250, lambda: _cleanup(page))
