from pathlib import Path

from pypdf import PdfReader

from ai_pm_lab_privacy_gate.domain.models import PageContent
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

