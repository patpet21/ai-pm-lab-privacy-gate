from pathlib import Path

import pytest

from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource
from ai_pm_lab_privacy_gate.ui.gmail_component_capture_fix import _package_from_capture


def test_protect_package_keeps_text_and_multiple_files_independent(tmp_path: Path) -> None:
    pdf = tmp_path / "resume.pdf"
    xlsx = tmp_path / "budget.xlsx"
    pdf.write_bytes(b"pdf")
    xlsx.write_bytes(b"xlsx")

    package = ProtectPackage(
        origin="gmail",
        label="Application",
        sources=(
            ProtectSource.text_source(key="gmail_body", label="Email body", text="Hello"),
            ProtectSource.file_source(key="attachment_1", label="resume.pdf", path=pdf),
            ProtectSource.file_source(key="attachment_2", label="budget.xlsx", path=xlsx),
        ),
    )

    assert package.source_count == 3
    assert package.file_count == 2
    assert package.source("gmail_body").text == "Hello"
    assert package.source("attachment_1").path == str(pdf)
    assert package.source("attachment_2").path == str(xlsx)


def test_gmail_capture_builds_one_atomic_package_for_body_and_attachment(tmp_path: Path) -> None:
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"pdf")

    package = _package_from_capture(
        body_was_materialized=True,
        captured_body_text="Subject: Test\n\nHello",
        captured_attachments=[("resume.pdf", pdf)],
        metadata={"item_title": "Test message"},
    )

    assert package is not None
    assert [source.key for source in package.sources] == [
        "gmail_body",
        "gmail_attachment_1",
    ]
    assert [source.label for source in package.sources] == ["Email body", "resume.pdf"]
    assert package.file_count == 1


def test_package_rejects_duplicate_source_keys() -> None:
    with pytest.raises(ValueError, match="unique"):
        ProtectPackage(
            origin="gmail",
            label="Bad package",
            sources=(
                ProtectSource.text_source(key="same", label="One", text="A"),
                ProtectSource.text_source(key="same", label="Two", text="B"),
            ),
        )
