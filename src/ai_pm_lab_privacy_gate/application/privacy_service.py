from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectedSpan,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.documents.document_pipeline import DocumentPipelineService
from ai_pm_lab_privacy_gate.infrastructure.documents.office_service import OfficeDocumentService
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


class PrivacyGateService:
    """Single reusable application boundary for the UI and a future local API."""

    def __init__(
        self,
        pii_engine: PresidioPrivacyEngine | None = None,
        pdf_service: PdfDocumentService | None = None,
        office_service: OfficeDocumentService | None = None,
        document_pipeline: DocumentPipelineService | None = None,
    ) -> None:
        self._pii = pii_engine or PresidioPrivacyEngine()
        self._pipeline = document_pipeline or DocumentPipelineService(
            pdf_service=pdf_service,
            office_service=office_service,
        )
        self._pdf = self._pipeline.pdf
        self._office = self._pipeline.office

    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument(
            source_kind="text",
            pages=(PageContent(page_number=1, text=text),),
        )

    def document_from_pdf(self, path: str | Path) -> AnalysisDocument:
        return self._pdf.extract(path)

    def document_from_file(self, path: str | Path) -> AnalysisDocument:
        return self._pipeline.extract(path)

    def analyze(self, document: AnalysisDocument, profile: PrivacyProfile) -> tuple[Finding, ...]:
        if not document.has_text:
            raise ValueError(
                "No selectable text was found. Scanned/image-only PDFs are not supported in this build."
            )
        findings: list[Finding] = []
        for page in document.pages:
            findings.extend(self._pii.analyze_page(page, profile))
        return tuple(findings)

    def protect(
        self,
        document: AnalysisDocument,
        findings: Iterable[Finding],
        replacement_mode: str = "reversible",
    ) -> ProtectionResult:
        selected = self._without_overlaps(tuple(findings))
        by_page: dict[int, list[Finding]] = defaultdict(list)
        for finding in selected:
            by_page[finding.page_number].append(finding)

        counters: Counter[str] = Counter()
        token_by_value: dict[tuple[str, str], str] = {}
        mappings: list[ReplacementMapping] = []
        protected_spans: list[ProtectedSpan] = []

        def replacement_for(finding: Finding) -> str:
            if replacement_mode == "redact":
                return "[REDACTED]"
            if replacement_mode == "generic":
                return f"[[{finding.entity_type}]]"
            if replacement_mode == "mask":
                return self._mask_value(finding.text)
            key = (finding.entity_type, finding.text.casefold())
            token = token_by_value.get(key)
            if token is None:
                counters[finding.entity_type] += 1
                token = f"[[PG_{finding.entity_type}_{counters[finding.entity_type]:03d}]]"
                token_by_value[key] = token
                mappings.append(
                    ReplacementMapping(
                        token=token,
                        entity_type=finding.entity_type,
                        original_text=finding.text,
                    )
                )
            return token

        protected_pages: list[PageContent] = []
        for page in document.pages:
            chunks: list[str] = []
            source_cursor = 0
            protected_cursor = 0
            page_findings = sorted(by_page.get(page.page_number, []), key=lambda item: item.start)
            for item in page_findings:
                untouched = page.text[source_cursor : item.start]
                chunks.append(untouched)
                protected_cursor += len(untouched)

                replacement = replacement_for(item)
                span_start = protected_cursor
                chunks.append(replacement)
                protected_cursor += len(replacement)
                protected_spans.append(
                    ProtectedSpan(
                        page_number=page.page_number,
                        start=span_start,
                        end=protected_cursor,
                        entity_type=item.entity_type,
                        finding_id=item.finding_id,
                        replacement_text=replacement,
                    )
                )
                source_cursor = item.end

            chunks.append(page.text[source_cursor:])
            protected_pages.append(
                PageContent(
                    page_number=page.page_number,
                    text="".join(chunks),
                    location=page.location,
                )
            )
        return ProtectionResult(
            protected_pages=tuple(protected_pages),
            applied_findings=selected,
            mappings=tuple(mappings),
            protected_spans=tuple(protected_spans),
            replacement_mode=replacement_mode,
        )

    def verify_protected(
        self,
        result: ProtectionResult,
        profile: PrivacyProfile,
    ) -> tuple[Finding, ...]:
        protected_document = AnalysisDocument(
            source_kind="protected",
            pages=result.protected_pages,
        )
        return self.analyze(protected_document, profile)

    @staticmethod
    def _mask_value(value: str) -> str:
        visible = 4
        alphanumeric_positions = [index for index, char in enumerate(value) if char.isalnum()]
        keep = set(alphanumeric_positions[-visible:])
        return "".join(
            char if index in keep or not char.isalnum() else "*"
            for index, char in enumerate(value)
        )

    @staticmethod
    def restore_text(text: str, mappings: Iterable[ReplacementMapping]) -> str:
        restored = text
        for mapping in sorted(mappings, key=lambda item: len(item.token), reverse=True):
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored

    @staticmethod
    def _without_overlaps(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
        accepted: list[Finding] = []
        for candidate in sorted(
            findings,
            key=lambda item: (item.page_number, -item.score, -(item.end - item.start), item.start),
        ):
            overlaps = any(
                current.page_number == candidate.page_number
                and candidate.start < current.end
                and current.start < candidate.end
                for current in accepted
            )
            if not overlaps:
                accepted.append(candidate)
        return tuple(sorted(accepted, key=lambda item: (item.page_number, item.start, item.end)))

    def save_protected_text(self, result: ProtectionResult, path: str | Path) -> Path:
        destination = Path(path)
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result.combined_text, encoding="utf-8")
        return destination

    def save_protected_pdf(
        self,
        result: ProtectionResult,
        path: str | Path,
        source_document: AnalysisDocument | None = None,
    ) -> Path:
        if (
            source_document is not None
            and source_document.source_kind == "pdf"
            and source_document.source_path is not None
        ):
            return self._pdf.write_layout_preserving(source_document.source_path, result, path)
        return self._pdf.write_protected(result.protected_pages, path)

    def save_protected_office(
        self,
        result: ProtectionResult,
        path: str | Path,
        source_document: AnalysisDocument,
    ) -> Path:
        return self._office.write_protected(source_document, result, path)

    def save_protected_document(
        self,
        result: ProtectionResult,
        path: str | Path,
        source_document: AnalysisDocument,
    ) -> Path:
        """Write the safe copy in the same supported format as its source."""
        return self._pipeline.write_protected(source_document, result, path)
