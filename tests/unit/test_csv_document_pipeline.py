from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.documents.document_pipeline import DocumentPipelineService


def test_csv_is_first_class_document_format(tmp_path: Path) -> None:
    source = tmp_path / "operations.csv"
    original = "Name,Email,Status\nJane Smith,jane@example.com,Open\n"
    source.write_text(original, encoding="utf-8-sig")
    source_text = source.read_bytes().decode("utf-8-sig")

    service = PrivacyGateService()
    document = service.document_from_file(source)
    text = document.pages[0].text

    assert ".csv" in DocumentPipelineService.SUPPORTED_SUFFIXES
    assert document.source_kind == "csv"
    assert document.source_path == source
    assert text == source_text
    assert text.replace("\r\n", "\n") == original

    start = text.index("Jane Smith")
    finding = Finding(
        finding_id="csv-person-1",
        entity_type="PERSON",
        text="Jane Smith",
        start=start,
        end=start + len("Jane Smith"),
        score=1.0,
        page_number=1,
        context=text,
    )
    result = service.protect(document, (finding,))

    protected, companion = service.save_protected_bundle(
        result,
        tmp_path / "operations_protected.csv",
        document,
    )

    protected_bytes = protected.read_bytes()
    protected_text = protected_bytes.decode("utf-8")
    assert protected.suffix == ".csv"
    assert protected_text == result.combined_text
    assert b"\r\r\n" not in protected_bytes
    assert "Jane Smith" not in protected_text
    assert "[[PG_PERSON_001]]" in protected_text
    assert ",jane@example.com,Open" in protected_text
    assert companion == tmp_path / "operations_protected.txt"
    companion_bytes = companion.read_bytes()
    assert companion_bytes.decode("utf-8") == result.combined_text
    assert b"\r\r\n" not in companion_bytes
