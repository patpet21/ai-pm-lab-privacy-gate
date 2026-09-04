from types import SimpleNamespace

from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_document_idempotency import (
    document_contains_privacygate_tokens,
)


def test_detects_privacygate_token_in_document_pages() -> None:
    document = SimpleNamespace(
        pages=(
            SimpleNamespace(page_number=1, text="Resume for [[PG_B4A91A3A3_T0001_PERSON_001]]"),
        )
    )
    assert document_contains_privacygate_tokens(document) is True


def test_plain_document_is_not_marked_as_already_protected() -> None:
    document = SimpleNamespace(
        pages=(
            SimpleNamespace(page_number=1, text="Pietro Forestieri\nProject Manager"),
        )
    )
    assert document_contains_privacygate_tokens(document) is False
