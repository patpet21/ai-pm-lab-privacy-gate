from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.infrastructure.documents.document_pipeline import DocumentPipelineService


def test_csv_is_first_class_document_format(tmp_path: Path) -> None:
    source = tmp_path / "operations.csv"
    original = "Name,Email,Status\nJane Smith,jane@example.com,Open\n"
    source.write_text(original, encoding="utf-8-sig")

    service = PrivacyGateService()
    document = service.document_from_file(source)

    assert ".csv" in DocumentPipelineService.SUPPORTED_SUFFIXES
    assert document.source_kind == "csv"
    assert document.source_path == source
    assert document.combined_text == original

    start = document.combined_text.index("Jane Smith")
    finding = Finding(
        finding_id="csv-person-1",
        entity_type="PERSON",
        text="Jane Smith",
        start=start,
        end=start + len("Jane Smith"),
        score=1.0,
        page_number=1,
        context=document.combined_text,
    )
    result = service.protect(document, (finding,))

    protected, companion = service.save_protected_bundle(
        result,
        tmp_path / "operations_protected.csv",
        document,
    )

    assert protected.suffix == ".csv"
    assert protected.read_text(encoding="utf-8") == result.combined_text
    assert "Jane Smith" not in protected.read_text(encoding="utf-8")
    assert "[[PG_PERSON_001]]" in protected.read_text(encoding="utf-8")
    assert ",jane@example.com,Open" in protected.read_text(encoding="utf-8")
    assert companion == tmp_path / "operations_protected.txt"
    assert companion.read_text(encoding="utf-8") == result.combined_text
