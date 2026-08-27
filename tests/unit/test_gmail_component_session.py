from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ai_pm_lab_privacy_gate.ui.gmail_component_session import (
    _body_from_legacy_text,
    _safe_button_text,
    _source_key,
)
from ai_pm_lab_privacy_gate.ui.protect_source_state_reset import (
    _gmail_attachment_paths,
    _gmail_body_text,
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


def test_gmail_reset_helpers_keep_body_and_attachment_identity(tmp_path: Path) -> None:
    attachment = tmp_path / "resume.pdf"
    attachment.write_bytes(b"pdf")
    page = SimpleNamespace(
        _gmail_component_manifest=(
            {
                "key": "gmail_body",
                "component_kind": "body",
                "text": "Subject: Test\n\nHello",
                "path": "",
            },
            {
                "key": "gmail_attachment_1",
                "component_kind": "attachment",
                "text": "",
                "path": str(attachment),
            },
        )
    )

    assert _gmail_body_text(page) == "Subject: Test\n\nHello"
    assert str(attachment.resolve()) in _gmail_attachment_paths(page)


def test_attachment_only_manifest_has_no_gmail_body(tmp_path: Path) -> None:
    attachment = tmp_path / "deck.pptx"
    attachment.write_bytes(b"pptx")
    page = SimpleNamespace(
        _gmail_component_manifest=(
            {
                "key": "gmail_attachment_1",
                "component_kind": "attachment",
                "text": "",
                "path": str(attachment),
            },
        )
    )

    assert _gmail_body_text(page) is None
    assert _gmail_attachment_paths(page) == {str(attachment.resolve())}
