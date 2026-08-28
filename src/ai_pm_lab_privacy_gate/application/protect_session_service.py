from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable

from ai_pm_lab_privacy_gate.domain.models import (
    AnalysisDocument,
    Finding,
    ProtectionResult,
)
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile
from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource
from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService


def source_key_from_finding_id(finding_id: str) -> str:
    return finding_id.split("::", 1)[0] if "::" in finding_id else ""


def namespace_findings(
    findings: Iterable[Finding],
    source_key: str,
) -> tuple[Finding, ...]:
    """Make finding ids unique across independent Protect sources."""
    prefix = f"{source_key}::"
    return tuple(
        item
        if item.finding_id.startswith(prefix)
        else replace(item, finding_id=f"{prefix}{item.finding_id}")
        for item in findings
    )


def _clean_token_namespace(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return cleaned or "SOURCE"


def namespace_protection_result(
    result: ProtectionResult,
    namespace: str,
) -> ProtectionResult:
    """Keep reversible placeholders unique between session sources."""
    if result.replacement_mode != "reversible" or not result.mappings:
        return result

    safe_namespace = _clean_token_namespace(namespace)
    token_map: dict[str, str] = {}
    mappings = []
    for mapping in result.mappings:
        token = mapping.token
        if token.startswith("[[PG_"):
            replacement = token.replace("[[PG_", f"[[PG_{safe_namespace}_", 1)
        else:
            replacement = token
        token_map[token] = replacement
        mappings.append(replace(mapping, token=replacement))

    pages = []
    for page_content in result.protected_pages:
        text = page_content.text
        for old, new in token_map.items():
            text = text.replace(old, new)
        pages.append(replace(page_content, text=text))

    spans = tuple(
        replace(
            span,
            replacement_text=token_map.get(span.replacement_text, span.replacement_text),
        )
        for span in result.protected_spans
    )

    return replace(
        result,
        protected_pages=tuple(pages),
        mappings=tuple(mappings),
        protected_spans=spans,
    )


@dataclass(frozen=True, slots=True)
class ProtectSourceAnalysis:
    source: ProtectSource
    document: AnalysisDocument
    findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class ProtectSessionAnalysis:
    package: ProtectPackage
    sources: tuple[ProtectSourceAnalysis, ...]

    @property
    def findings(self) -> tuple[Finding, ...]:
        return tuple(
            finding
            for source in self.sources
            for finding in source.findings
        )

    def source(self, key: str) -> ProtectSourceAnalysis | None:
        return next((source for source in self.sources if source.source.key == key), None)


@dataclass(frozen=True, slots=True)
class ProtectSourceResult:
    analysis: ProtectSourceAnalysis
    result: ProtectionResult


@dataclass(frozen=True, slots=True)
class ProtectSessionResult:
    analysis: ProtectSessionAnalysis
    sources: tuple[ProtectSourceResult, ...]

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def applied_findings_count(self) -> int:
        return sum(len(source.result.applied_findings) for source in self.sources)

    @property
    def combined_text(self) -> str:
        chunks = []
        for source in self.sources:
            chunks.append(
                f"=== {source.analysis.source.label} ===\n{source.result.combined_text}"
            )
        return "\n\n".join(chunks)

    def source(self, key: str) -> ProtectSourceResult | None:
        return next((source for source in self.sources if source.analysis.source.key == key), None)


class ProtectSessionService:
    """Generic N-source Protect workflow independent from Gmail/Drive/UI state."""

    def __init__(self, privacy_service: PrivacyGateService) -> None:
        self._privacy = privacy_service

    def analyze(
        self,
        package: ProtectPackage,
        profile: PrivacyProfile,
    ) -> ProtectSessionAnalysis:
        analyzed: list[ProtectSourceAnalysis] = []
        for source in package.sources:
            if source.source_type == "text":
                document = self._privacy.document_from_text(source.text)
            else:
                document = self._privacy.document_from_file(source.path)
            findings = namespace_findings(
                self._privacy.analyze(document, profile),
                source.key,
            )
            analyzed.append(
                ProtectSourceAnalysis(
                    source=source,
                    document=document,
                    findings=findings,
                )
            )
        return ProtectSessionAnalysis(package=package, sources=tuple(analyzed))

    def protect(
        self,
        analysis: ProtectSessionAnalysis,
        selected_finding_ids: Iterable[str],
        *,
        replacement_mode: str = "reversible",
    ) -> ProtectSessionResult:
        selected_ids = set(selected_finding_ids)
        protected: list[ProtectSourceResult] = []
        multi_source = len(analysis.sources) > 1
        for index, source_analysis in enumerate(analysis.sources, start=1):
            selected = tuple(
                finding
                for finding in source_analysis.findings
                if finding.finding_id in selected_ids
            )
            raw = self._privacy.protect(
                source_analysis.document,
                selected,
                replacement_mode=replacement_mode,
            )
            # Preserve the historical token shape for a normal one-document or
            # one-paste Protect operation. Namespacing is only required when two
            # or more independent sources share the same session/AI handoff.
            result = (
                namespace_protection_result(
                    raw,
                    f"S{index}_{source_analysis.source.key}",
                )
                if multi_source
                else raw
            )
            protected.append(
                ProtectSourceResult(
                    analysis=source_analysis,
                    result=result,
                )
            )
        return ProtectSessionResult(analysis=analysis, sources=tuple(protected))

    def verify(
        self,
        result: ProtectSessionResult,
        profile: PrivacyProfile,
    ) -> dict[str, tuple[Finding, ...]]:
        return {
            source.analysis.source.key: self._privacy.verify_protected(
                source.result,
                profile,
            )
            for source in result.sources
        }
