from __future__ import annotations

from types import SimpleNamespace

from ai_pm_lab_privacy_gate.ui.gmail_package_ux import _document_to_analyzed_text


def test_document_to_analyzed_text_keeps_page_boundaries() -> None:
    document = SimpleNamespace(
        pages=(
            SimpleNamespace(page_number=1, location="", text="First page"),
            SimpleNamespace(page_number=2, location="", text="Second page"),
        )
    )

    rendered = _document_to_analyzed_text(document)

    assert "--- Page 1 ---" in rendered
    assert "First page" in rendered
    assert "--- Page 2 ---" in rendered
    assert "Second page" in rendered


def test_document_to_analyzed_text_prefers_document_locations() -> None:
    document = SimpleNamespace(
        pages=(
            SimpleNamespace(page_number=1, location="Slide 3", text="Leadership theory"),
        )
    )

    rendered = _document_to_analyzed_text(document)

    assert rendered == "--- Slide 3 ---\nLeadership theory"
