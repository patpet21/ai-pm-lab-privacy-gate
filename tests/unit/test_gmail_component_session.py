from __future__ import annotations

from ai_pm_lab_privacy_gate.ui.gmail_component_session import (
    _body_from_legacy_text,
    _safe_button_text,
    _source_key,
)


def test_body_from_legacy_gmail_package_text_keeps_only_email_body() -> None:
    text = (
        "=== GMAIL EMAIL BODY ===\n"
        "Subject: Lease review\n\nHello Jane\n\n"
        "=== GMAIL ATTACHMENT · lease.pdf ===\n"
        "Attachment text"
    )
    assert _body_from_legacy_text(text, True) == "Subject: Lease review\n\nHello Jane"


def test_body_from_legacy_text_is_empty_when_body_not_selected() -> None:
    assert _body_from_legacy_text("attachment fallback text", False) == ""


def test_component_helpers_keep_source_identity_and_compact_long_labels() -> None:
    assert _source_key("gmail_attachment_2::finding-123") == "gmail_attachment_2"
    value = _safe_button_text("A" * 80, limit=20)
    assert len(value) <= 20
    assert value.endswith("…")
