from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.connectors.search_adapter import _drive_folder_query
from ai_pm_lab_privacy_gate.infrastructure.connectors.service import RemoteItem
from ai_pm_lab_privacy_gate.ui.drive_browser import (
    FOLDER_MIME,
    GOOGLE_SLIDES,
    _is_image,
    _supported,
    _unsupported_message,
)


def test_drive_folder_query_is_scoped_to_current_parent() -> None:
    query = _drive_folder_query("folder-123", "lease")
    assert "'folder-123' in parents" in query
    assert "trashed = false" in query
    assert "name contains 'lease'" in query


def test_drive_folder_is_navigable_but_not_importable() -> None:
    folder = RemoteItem("google_drive", "1", "Client Files", kind=FOLDER_MIME)
    assert not _supported(folder)
    assert not _is_image(folder)


def test_google_slides_remains_supported_in_drive_picker() -> None:
    slides = RemoteItem("google_drive", "2", "Presentation", kind=GOOGLE_SLIDES)
    assert _supported(slides)


def test_drive_image_message_explains_ocr_limitation() -> None:
    image = RemoteItem("google_drive", "3", "scan.png", kind="image/png")
    assert _is_image(image)
    assert not _supported(image)
    message = _unsupported_message(image)
    assert "OCR" in message
    assert "cannot analyze image pixels yet" in message
