from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyzeRequest:
    text: str
    profile_key: str


@dataclass(frozen=True, slots=True)
class AnalyzeResponse:
    findings: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class ProtectRequest:
    text: str
    profile_key: str
    finding_ids: tuple[str, ...]


# No HTTP server is started in v0.1. These contracts reserve a stable boundary
# for a future opt-in localhost API used by n8n.

