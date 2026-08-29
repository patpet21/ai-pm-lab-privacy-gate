from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyzeRequest:
    text: str
    profile_key: str
    language: str = "en"


@dataclass(frozen=True, slots=True)
class AnalyzeResponse:
    findings: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class ProtectRequest:
    text: str
    profile_key: str
    finding_ids: tuple[str, ...] | None = None
    language: str = "en"
    replacement_mode: str = "reversible"


@dataclass(frozen=True, slots=True)
class ProtectResponse:
    protected_text: str
    applied_finding_ids: tuple[str, ...]
    entity_types: tuple[str, ...]


# These contracts are intentionally text-only. The localhost bridge never returns
# original values, restore mappings, source files, or Library records to clients.
