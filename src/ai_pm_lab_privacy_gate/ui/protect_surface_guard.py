from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QDialog, QWidget


_LEGACY_WIDGET_NAMES = (
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
)


def _collect_layout_widgets(layout, output: set[QWidget]) -> None:
    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        child_layout = item.layout()
        if isinstance(widget, QWidget):
            output.add(widget)
            nested = widget.layout()
            if nested is not None:
                _collect_layout_widgets(nested, output)
        if child_layout is not None:
            _collect_layout_widgets(child_layout, output)


class _ProtectSurfaceGuard(QObject):
    """Keep detached legacy Protect widgets from painting over the final UI.

    The previous implementation needed multiple delayed cleanup passes because
    several feature layers reparented controls after the initial redesign.  This
    guard instead observes structural/layout changes and re-evaluates the final
    page tree only when something actually changes.
    """

    _WATCHED_EVENTS = {
        QEvent.Type.Show,
        QEvent.Type.LayoutRequest,
        QEvent.Type.ChildAdded,
        QEvent.Type.Resize,
    }

    def __init__(self, page: QWidget) -> None:
        super().__init__(page)
        self._page = page
        self._scheduled = False
        page.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if watched is self._page and event.type() in self._WATCHED_EVENTS:
            self.schedule()
        return False

    def schedule(self) -> None:
        if self._scheduled:
            return
        self._scheduled = True
        QTimer.singleShot(0, self._run)

    def _run(self) -> None:
        self._scheduled = False
        self.stabilize()

    def stabilize(self) -> None:
        page = self._page

        # Explicitly keep shells that are retained only for compatibility from
        # ever becoming visible again.
        for name in _LEGACY_WIDGET_NAMES:
            widget = getattr(page, name, None)
            if isinstance(widget, QWidget):
                widget.hide()

        managed: set[QWidget] = set()
        _collect_layout_widgets(page.layout(), managed)

        direct_children = page.findChildren(
            QWidget,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        )
        for child in direct_children:
            if child in managed:
                continue
            if isinstance(child, QDialog) or child.isWindow():
                continue
            if bool(child.property("privacygate_surface_keep")):
                continue
            # This catches the anonymous parking QWidget used by the historical
            # redesign as well as any later detached compatibility surface.
            child.hide()


def apply_protect_surface_guard(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_protect_surface_guard", None) is not None:
        return

    guard = _ProtectSurfaceGuard(page)
    page._protect_surface_guard = guard

    def schedule(*_args) -> None:
        guard.schedule()

    # Source switches, scans and preview changes are the operations that used to
    # expose clipped labels/icons on Windows.  Re-check only around those events.
    for signal_owner, signal_name in (
        (getattr(page, "text_input", None), "textChanged"),
        (getattr(page, "pdf_path", None), "textChanged"),
        (getattr(page, "scan_button", None), "clicked"),
        (getattr(page, "clear_button", None), "clicked"),
        (getattr(page, "preview_tabs", None), "currentChanged"),
    ):
        signal = getattr(signal_owner, signal_name, None) if signal_owner is not None else None
        if signal is not None:
            signal.connect(schedule)

    protect_button = getattr(page, "_redesign_protect_button", None)
    if protect_button is not None:
        protect_button.clicked.connect(schedule)

    guard.stabilize()
