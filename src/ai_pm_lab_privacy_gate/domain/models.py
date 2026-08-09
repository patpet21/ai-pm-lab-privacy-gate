from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PageContent:
    page_number: int
    text: str


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
class ProtectionResult:
    protected_pages: tuple[PageContent, ...]
    applied_findings: tuple[Finding, ...] = field(default_factory=tuple)
    mappings: tuple[ReplacementMapping, ...] = field(default_factory=tuple)
    replacement_mode: str = "reversible"

    @property
    def combined_text(self) -> str:
        if len(self.protected_pages) == 1:
            return self.protected_pages[0].text
        return "\n\n".join(
            f"--- Page {page.page_number} ---\n{page.text}"
            for page in self.protected_pages
        )


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
