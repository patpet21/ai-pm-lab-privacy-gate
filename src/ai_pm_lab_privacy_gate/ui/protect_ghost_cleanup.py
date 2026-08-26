from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ai_pm_lab_privacy_gate.ui import redesign

_INSTALLED = False


def _hide_layout_tree(layout) -> None:
    """Hide every widget reachable from a detached Qt layout tree.

    The old Protect redesign only hid widgets one layout level deep. Nested labels
    and info icons could therefore remain painted at the far-left edge after their
    parent layout was removed, producing the tiny clipped letters/icons visible in
    the UI. Recursing through child layouts removes those ghosts without deleting
    reusable controls that the redesign reparents later.
    """
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child = item.layout()
        if isinstance(widget, QWidget):
            widget.hide()
        if child is not None:
            _hide_layout_tree(child)


def install_protect_ghost_cleanup() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    def hide_old_root(root) -> None:
        while root.count():
            item = root.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if isinstance(widget, QWidget):
                widget.hide()
            if child is not None:
                _hide_layout_tree(child)

    redesign._hide_old_root = hide_old_root
