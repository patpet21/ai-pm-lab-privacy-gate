from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget


def _activate(window: QWidget) -> None:
    try:
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
        window.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QApplication.processEvents()
    except RuntimeError:
        return

    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        user32 = ctypes.windll.user32
        sw_restore = 9
        hwnd_topmost = -1
        hwnd_notopmost = -2
        swp_nomove = 0x0002
        swp_nosize = 0x0001
        swp_showwindow = 0x0040
        flags = swp_nomove | swp_nosize | swp_showwindow

        user32.ShowWindow(hwnd, sw_restore)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        # A short TOPMOST -> NOTOPMOST pulse makes the explicit user-requested
        # return from the browser reliable on Windows without leaving the dialog
        # pinned above other applications.
        user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, flags)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        # Qt activation above is still the supported cross-platform fallback.
        return


def bring_window_to_front(window: QWidget | None) -> None:
    """Return a PrivacyGate window/dialog to the foreground after browser OAuth.

    The Google desktop Picker must run in the system browser. Once its loopback
    callback completes, PrivacyGate calls this helper so the user is returned to
    the dialog they came from instead of being left on the browser tab.
    """

    if window is None:
        return

    _activate(window)
    # Chrome/Edge may finish a focus transition a fraction later. Repeating the
    # same best-effort activation once avoids leaving the browser in front.
    QTimer.singleShot(120, lambda target=window: _activate(target))
