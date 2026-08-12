from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PageContent:
    page_number: int
    text: str
    location: str = \"\"


@dataclass(frozen=True, slots=True)
class AnalysisDocument:
    source_kind: str
    pages: tuple[PageContent, ...]
    source_path: Path | None = None

    @property
    def has_text(self) -> bool:
        return any(page.text.strip() for page in self.pages)


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    entity_type: str
    text: str
    start: int
    end: int
    score: float
    page_number: int
    context: str


@dataclass(frozen=True, slots=True)
class ReplacementMapping:
    token: str
    entity_type: str
    original_text: str


@dataclass(frozen=True, slots=True)
class ProtectedSpan:
    """Location and category of a replacement in one protected page."""

    page_number: int
    start: int
    end: int
    entity_type: str
    finding_id: str
    replacement_text: str


@dataclass(frozen=True, slots=True)
class ProtectionResult:
    protected_pages: tuple[PageContent, ...]
    applied_findings: tuple[Finding, ...] = field(default_factory=tuple)
    mappings: tuple[ReplacementMapping, ...] = field(default_factory=tuple)
    protected_spans: tuple[ProtectedSpan, ...] = field(default_factory=tuple)
    replacement_mode: str = "reversible"

    @property
    def combined_text(self) -> str:
        if len(self.protected_pages) == 1:
            return self.protected_pages[0].text
        return "\n\n".join(
            f"--- Page {page.page_number} ---\n{page.text}"
            for page in self.protected_pages
        )

    @property
    def combined_spans(self) -> tuple[ProtectedSpan, ...]:
        """Return replacement spans adjusted to the combined preview text."""
        if len(self.protected_pages) == 1:
            return self.protected_spans

        spans_by_page: dict[int, list[ProtectedSpan]] = {}
        for span in self.protected_spans:
            spans_by_page.setdefault(span.page_number, []).append(span)

        adjusted: list[ProtectedSpan] = []
        cursor = 0
        for page_index, page in enumerate(self.protected_pages):
            prefix = f"--- Page {page.page_number} ---\n"
            page_offset = cursor + len(prefix)
            adjusted.extend(
                ProtectedSpan(
                    page_number=span.page_number,
                    start=page_offset + span.start,
                    end=page_offset + span.end,
                    entity_type=span.entity_type,
                    finding_id=span.finding_id,
                    replacement_text=span.replacement_text,
                )
                for span in spans_by_page.get(page.page_number, ())
            )
            cursor += len(prefix) + len(page.text)
            if page_index < len(self.protected_pages) - 1:
                cursor += 2
        return tuple(adjusted)


@dataclass(frozen=True, slots=True)
class LibraryDocument:
    document_id: str
    title: str
    source_kind: str
    source_name: str
    profile_key: str
    protected_text: str
    findings_count: int
    entity_types: tuple[str, ...]
    labels: tuple[str, ...]
    replacement_mode: str
    created_at: datetime
    updated_at: datetime
    has_mapping: bool
    favorite: bool = False
    mcp_shared: bool = False
    deleted_at: datetime | None = None
