from pathlib import Path

from pypdf import PdfReader

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import Finding, PageContent
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService


def test_protected_pdf_is_readable_and_contains_placeholders(tmp_path: Path):
    service = PdfDocumentService()
    path = tmp_path / "protected.pdf"
    service.write_protected(
        (
            PageContent(1, "Tenant <PERSON>\nPhone <PHONE_NUMBER>"),
            PageContent(2, "Account <US_BANK_NUMBER>"),
        ),
        path,
    )
    reader = PdfReader(str(path))
    assert len(reader.pages) == 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "<PERSON>" in text
    assert "<PHONE_NUMBER>" in text
    assert "<US_BANK_NUMBER>" in text


def test_layout_preserving_pdf_removes_original_selectable_text(tmp_path: Path):
    pdf_service = PdfDocumentService()
    source = tmp_path / "source.pdf"
    pdf_service.write_protected((PageContent(1, "Tenant Jane Smith\nEmail jane@example.com"),), source)
    privacy_service = PrivacyGateService(pdf_service=pdf_service)
    document = privacy_service.document_from_pdf(source)
    page_text = document.pages[0].text
    start = page_text.index("Jane Smith")
    finding = Finding(
        finding_id="person-layout-1",
        entity_type="PERSON",
        text="Jane Smith",
        start=start,
        end=start + len("Jane Smith"),
        score=1.0,
        page_number=1,
        context=page_text,
    )
    result = privacy_service.protect(document, (finding,))
    destination = tmp_path / "layout-protected.pdf"
    privacy_service.save_protected_pdf(result, destination, source_document=document)

    reader = PdfReader(str(destination))
    assert len(reader.pages) == 1
    assert "Jane Smith" not in (reader.pages[0].extract_text() or "")
    assert reader.pages[0].images


def test_pdf_locator_splits_values_joined_from_adjacent_table_cells():
    class FakePage:
        def search(self, value, regex=True, case=False):  # noqa: ARG002
            matches = {
                "Liam\\ Brooks\\ /\\ 3B": [],
                "Liam\\ Brooks": [{"x0": 1, "top": 2, "x1": 3, "bottom": 4}],
                "3B": [{"x0": 5, "top": 2, "x1": 6, "bottom": 4}],
            }
            return matches.get(value, [])

    matches = PdfDocumentService._locate_finding(
        FakePage(), "Liam Brooks / 3B", {}, exact_occurrence=0
    )
    assert len(matches) == 2
