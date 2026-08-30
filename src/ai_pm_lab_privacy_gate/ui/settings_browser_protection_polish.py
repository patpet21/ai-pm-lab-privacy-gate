from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget


def _frame_containing_label(card: QWidget, text: str) -> QFrame | None:
    for label in card.findChildren(QLabel):
        if label.text().strip() != text:
            continue
        current = label.parentWidget()
        while current is not None and current is not card:
            if isinstance(current, QFrame):
                return current
            current = current.parentWidget()
    return None


def apply_browser_protection_product_polish(main_window) -> None:
    """Hide pairing mechanics once Browser Protection is already connected.

    Pairing remains available for first-time setup and new browsers, but normal
    users should only see a connected state after the one-time authorization.
    """
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return

    pages = getattr(settings, "settings_service_pages", None)
    page = pages.get("services") if isinstance(pages, dict) else None
    if not isinstance(page, QWidget):
        return

    card = page.findChild(QFrame, "SettingsBrowserProtection")
    if card is None or getattr(card, "_privacygate_product_polish", False):
        return

    code_frame = _frame_containing_label(card, "One-time pairing code")
    pair_button = None
    revoke_button = None
    boundary = None

    for button in card.findChildren(QPushButton):
        text = button.text().strip()
        if text == "Create pairing code":
            pair_button = button
        elif text == "Revoke browser access":
            revoke_button = button

    for label in card.findChildren(QLabel):
        if label.text().startswith("Local-only pairing"):
            boundary = label
            break

    manager = getattr(main_window, "local_api_manager", None)

    def refresh() -> None:
        if manager is None:
            return
        pairing = manager.browser_pairing_status
        paired_count = int(getattr(pairing, "paired_count", 0))
        paired = paired_count > 0

        if code_frame is not None:
            code_frame.setVisible(not paired)
        if pair_button is not None:
            pair_button.setVisible(not paired)
        if revoke_button is not None:
            revoke_button.setVisible(paired)
            revoke_button.setText("Disconnect browser access")
        if boundary is not None:
            if paired:
                boundary.setText(
                    "Connected locally • no action is required after normal app or extension updates • prompts and restore mappings stay on this device"
                )
            else:
                boundary.setText(
                    "Connect once on this device • browser credential is separate from the main API bearer • prompts and restore mappings stay local"
                )

    timer = QTimer(card)
    timer.setInterval(1200)
    timer.timeout.connect(refresh)
    timer.start()
    refresh()

    card._privacygate_product_polish = True
    card._privacygate_product_polish_timer = timer
