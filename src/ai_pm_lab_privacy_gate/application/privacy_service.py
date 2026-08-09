from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    PageContent,
    ProtectionResult,
    ReplacementMapping,
)
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.infrastructure.documents.pdf_service import PdfDocumentService
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


class PrivacyGateService:
    """Single reusable application boundary for the UI and a future local API."""

    def __init__(
        self,
        pii_engine: PresidioPrivacyEngine | None = None,
        pdf_service: PdfDocumentService | None = None,
    ) -> None:
        self._pii = pii_engine or PresidioPrivacyEngine()
        self._pdf = pdf_service or PdfDocumentService()

    def document_from_text(self, text: str) -> AnalysisDocument:
        return AnalysisDocument(
            source_kind="text",
            pages=(PageContent(page_number=1, text=text),),
        )

    def document_from_pdf(self, path: str | Path) -> AnalysisDocument:
        return self._pdf.extract(path)

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

        def replacement_for(finding: Finding) -> str:
            if replacement_mode == "redact":
                return "[REDACTED]"
            if replacement_mode == "generic":
                return f"[[{finding.entity_type}]]"
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
            protected = page.text
            page_findings = sorted(by_page.get(page.page_number, []), key=lambda item: item.start, reverse=True)
            replacements = [(item, replacement_for(item)) for item in page_findings]
            for item, token in replacements:
                protected = protected[: item.start] + token + protected[item.end :]
            protected_pages.append(PageContent(page_number=page.page_number, text=protected))
        return ProtectionResult(
            protected_pages=tuple(protected_pages),
            applied_findings=selected,
            mappings=tuple(mappings),
            replacement_mode=replacement_mode,
        )

    @staticmethod
    def restore_text(text: str, mappings: Iterable[ReplacementMapping]) -> str:
        restored = text
        for mapping in sorted(mappings, key=lambda item: len(item.token), reverse=True):
            restored = restored.replace(mapping.token, mapping.original_text)
        return restored

    @staticmethod
    def _without_overlaps(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
        """Keep the strongest non-overlapping spans on each page."""
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
        destination.write_text(result.combined_text, encoding="utf-8")
        return destination

    def save_protected_pdf(self, result: ProtectionResult, path: str | Path) -> Path:
        return self._pdf.write_protected(result.protected_pages, path)
