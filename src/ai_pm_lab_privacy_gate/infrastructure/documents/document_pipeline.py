from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, ProtectionResult
from ai_pm_lab_privacy_gate.infrastructure.documents.office_service import OfficeDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.pptx_service import PowerPointDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.text_service import TextDocumentService


class DocumentPipelineService:
    """Single local router for every document format understood by PrivacyGate."""

    SUPPORTED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}

    def __init__(
        self,
        pdf_service: PdfDocumentService | None = None,
        office_service: OfficeDocumentService | None = None,
        powerpoint_service: PowerPointDocumentService | None = None,
        text_service: TextDocumentService | None = None,
    ) -> None:
        self.pdf = pdf_service or PdfDocumentService()
        self.office = office_service or OfficeDocumentService()
        self.powerpoint = powerpoint_service or PowerPointDocumentService()
        self.text = text_service or TextDocumentService()

    def extract(self, path: str | Path) -> AnalysisDocument:
        source = Path(path)
        suffix = source.suffix.lower()
        if suffix == ".pdf":
            return self.pdf.extract(source)
        if suffix in {".docx", ".xlsx"}:
            return self.office.extract(source)
        if suffix == ".pptx":
            return self.powerpoint.extract(source)
        if suffix == ".txt":
            return self.text.extract(source)
        raise ValueError(
            "Supported document formats are PDF, Word (.docx), Excel (.xlsx), "
            "PowerPoint (.pptx) and text (.txt)."
        )

    def write_protected(
        self,
        source_document: AnalysisDocument,
        result: ProtectionResult,
        path: str | Path,
    ) -> Path:
        kind = source_document.source_kind
        if kind == "pdf":
            if source_document.source_path is None:
                raise ValueError("A PDF source path is required.")
            return self.pdf.write_layout_preserving(source_document.source_path, result, path)
        if kind in {"docx", "xlsx"}:
            return self.office.write_protected(source_document, result, path)
        if kind == "pptx":
            return self.powerpoint.write_protected(source_document, result, path)
        if kind in {"txt", "text"}:
            return self.text.write_protected(source_document, result, path)
        raise ValueError(f"Unsupported source kind: {kind}")
