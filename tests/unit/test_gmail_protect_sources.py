from pathlib import Path

from ai_pm_lab_privacy_gate.application.gmail_protect_sources import (
    GmailProtectAttachment,
    build_gmail_protect_package,
    build_gmail_protect_package_from_manifest,
)


def test_gmail_package_keeps_body_and_attachments_as_independent_sources(tmp_path: Path):
    first = tmp_path / "lease.pdf"
    second = tmp_path / "notes.docx"
    first.write_bytes(b"pdf")
    second.write_bytes(b"docx")

    package = build_gmail_protect_package(
        email_body="Tenant John Smith asked for a copy.",
        attachments=(
            GmailProtectAttachment(first, "lease.pdf"),
            GmailProtectAttachment(second, "notes.docx"),
        ),
        source_metadata={
            "provider": "gmail",
            "account_id": "acct-1",
            "account_label": "Work Gmail",
            "item_id": "message-123",
            "item_title": "Lease request",
        },
    )

    assert package is not None
    assert package.origin == "gmail"
    assert package.source_count == 3
    assert tuple(source.key for source in package.sources) == (
        "gmail_body",
        "gmail_attachment_1",
        "gmail_attachment_2",
    )
    assert package.source("gmail_body").source_type == "text"
    assert package.source("gmail_attachment_1").path == str(first)
    assert package.source("gmail_attachment_2").path == str(second)
    assert package.metadata["adapter"] == "gmail_v1"
    assert package.metadata["source_count"] == 3


def test_gmail_package_metadata_never_contains_body_or_attachment_content(tmp_path: Path):
    attachment = tmp_path / "private.txt"
    attachment.write_text("secret attachment contents", encoding="utf-8")
    body = "very private email body"

    package = build_gmail_protect_package(
        email_body=body,
        attachments=(GmailProtectAttachment(attachment),),
        source_metadata={"provider": "gmail", "item_id": "message-1"},
    )

    assert package is not None
    serialized_metadata = repr(dict(package.metadata))
    assert body not in serialized_metadata
    assert "secret attachment contents" not in serialized_metadata
    assert package.source("gmail_body").text == body


def test_manifest_bridge_matches_current_gmail_component_keys(tmp_path: Path):
    attachment = tmp_path / "report.pdf"
    attachment.write_bytes(b"pdf")
    manifest = (
        {
            "key": "gmail_body",
            "label": "Email body",
            "component_kind": "body",
            "text": "Hello from Gmail",
            "path": "",
        },
        {
            "key": "gmail_attachment_1",
            "label": "report.pdf",
            "component_kind": "attachment",
            "text": "",
            "path": str(attachment),
        },
    )

    package = build_gmail_protect_package_from_manifest(
        manifest,
        source_metadata={"provider": "gmail", "package_mode": "gmail_message_package"},
    )

    assert package is not None
    assert tuple(source.key for source in package.sources) == (
        "gmail_body",
        "gmail_attachment_1",
    )
    assert package.source("gmail_attachment_1").label == "report.pdf"


def test_empty_gmail_selection_does_not_create_a_protect_package():
    assert build_gmail_protect_package() is None


def test_non_gmail_provenance_is_rejected():
    try:
        build_gmail_protect_package(
            email_body="hello",
            source_metadata={"provider": "google_drive"},
        )
    except ValueError as exc:
        assert "gmail provenance" in str(exc).lower()
    else:
        raise AssertionError("Expected non-Gmail provenance to be rejected")
