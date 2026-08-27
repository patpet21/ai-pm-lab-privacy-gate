from types import SimpleNamespace

from ai_pm_lab_privacy_gate.ui.protect_view_experience import (
    protected_text_for_active_source,
    resolve_active_source,
)


class _Result:
    def __init__(self, text: str) -> None:
        self.combined_text = text


class _Path:
    def __init__(self, name: str) -> None:
        self.name = name


class _Document:
    def __init__(self, kind: str, name: str | None = None) -> None:
        self.source_kind = kind
        self.source_path = _Path(name) if name else None


def _base_page(**overrides):
    values = {
        "_gmail_component_results": {},
        "_gmail_component_sources": {},
        "_gmail_component_active_key": "",
        "_protect_session_results": {},
        "_protect_session_sources": {},
        "_privacygate_active_source_key": "",
        "current_document": None,
        "current_result": None,
        "_external_source_metadata": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_local_session_protected_text_follows_active_source():
    document = _Document("pdf", "lease.pdf")
    text_document = _Document("text")
    page = _base_page(
        _protect_session_results={
            "document": _Result("protected document text"),
            "text": _Result("protected pasted text"),
        },
        _protect_session_sources={
            "document": {"document": document, "label": "lease.pdf"},
            "text": {"document": text_document, "label": "Pasted text"},
        },
        _privacygate_active_source_key="text",
        current_document=document,
        current_result=_Result("stale current result"),
    )

    key, active_document, result, label = resolve_active_source(page)

    assert key == "text"
    assert active_document is text_document
    assert result.combined_text == "protected pasted text"
    assert label == "Pasted text"
    assert protected_text_for_active_source(page) == "protected pasted text"


def test_gmail_component_result_has_priority_over_stale_current_result():
    body_document = _Document("text")
    attachment_document = _Document("pdf", "agreement.pdf")
    page = _base_page(
        _gmail_component_results={
            "gmail_body": _Result("safe email body"),
            "gmail_attachment_1": _Result("safe attachment text"),
        },
        _gmail_component_sources={
            "gmail_body": {"document": body_document, "label": "Email body"},
            "gmail_attachment_1": {
                "document": attachment_document,
                "label": "agreement.pdf",
            },
        },
        _gmail_component_active_key="gmail_attachment_1",
        current_result=_Result("stale body result"),
    )

    key, active_document, result, label = resolve_active_source(page)

    assert key == "gmail_attachment_1"
    assert active_document is attachment_document
    assert result.combined_text == "safe attachment text"
    assert label == "agreement.pdf"
    assert protected_text_for_active_source(page) == "safe attachment text"


def test_migrated_drive_session_uses_session_result_not_stale_current_result():
    document = _Document("xlsx", "drive-working-copy.xlsx")
    page = _base_page(
        _protect_session_results={
            "document": _Result("protected Drive spreadsheet text"),
        },
        _protect_session_sources={
            "document": {
                "document": document,
                "label": "Client Budget.xlsx",
            },
        },
        _privacygate_active_source_key="document",
        current_document=document,
        current_result=_Result("stale pre-migration result"),
        _external_source_metadata={
            "provider": "google_drive",
            "item_title": "Client Budget.xlsx",
        },
    )

    key, active_document, result, label = resolve_active_source(page)

    assert key == "document"
    assert active_document is document
    assert result.combined_text == "protected Drive spreadsheet text"
    assert label == "Client Budget.xlsx"
    assert protected_text_for_active_source(page) == "protected Drive spreadsheet text"


def test_single_drive_or_document_source_falls_back_to_current_result():
    document = _Document("pdf", "drive-file.pdf")
    page = _base_page(
        current_document=document,
        current_result=_Result("protected drive text"),
        _external_source_metadata={"item_title": "Drive file"},
    )

    key, active_document, result, label = resolve_active_source(page)

    assert key == "source"
    assert active_document is document
    assert result.combined_text == "protected drive text"
    assert label == "Drive file"
    assert protected_text_for_active_source(page) == "protected drive text"


def test_no_protected_result_returns_empty_text():
    page = _base_page(current_document=_Document("text"))

    assert protected_text_for_active_source(page) == ""
