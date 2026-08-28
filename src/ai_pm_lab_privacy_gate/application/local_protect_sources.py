from __future__ import annotations

"""Local Upload/Paste adapter for the generic ProtectSession contract.

This module is deliberately UI-free.  It converts the two legacy local inputs
(`pdf_path` and `text_input`) into the same ProtectPackage model that connector
adapters will use later.  Compatibility dictionaries are exposed temporarily so
the current desktop UI can keep rendering/exporting exactly as before while the
engine underneath moves to ProtectSessionService.
"""

from pathlib import Path
from typing import Mapping

from ai_pm_lab_privacy_gate.application.protect_session_service import (
    ProtectSessionAnalysis,
    ProtectSessionResult,
)
from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource


LOCAL_DOCUMENT_KEY = "document"
LOCAL_TEXT_KEY = "text"


def build_local_protect_package(
    *,
    document_path: str = "",
    pasted_text: str = "",
) -> ProtectPackage | None:
    """Build one atomic local package from Upload, Paste, or both.

    Source order is stable on purpose: a document is first when present, followed
    by pasted text. Stable ordering keeps reversible token namespaces and preview
    selection deterministic across runs.
    """

    path_value = str(document_path or "").strip()
    text_value = str(pasted_text or "").strip()
    sources: list[ProtectSource] = []

    if path_value:
        path = Path(path_value)
        sources.append(
            ProtectSource.file_source(
                key=LOCAL_DOCUMENT_KEY,
                label=path.name or "Document",
                path=path,
                metadata={
                    "origin": "local_upload",
                    "source_kind": "file",
                },
            )
        )

    if text_value:
        sources.append(
            ProtectSource.text_source(
                key=LOCAL_TEXT_KEY,
                label="Pasted text",
                text=text_value,
                metadata={
                    "origin": "paste",
                    "source_kind": "text",
                },
            )
        )

    if not sources:
        return None

    if len(sources) == 2:
        origin = "local_mixed"
        label = "Document + Pasted text"
    elif sources[0].key == LOCAL_DOCUMENT_KEY:
        origin = "local_upload"
        label = sources[0].label
    else:
        origin = "paste"
        label = "Pasted text"

    return ProtectPackage(
        origin=origin,
        label=label,
        sources=tuple(sources),
        metadata={"adapter": "local_v1"},
    )


def should_use_local_adapter(external_metadata: Mapping[str, object] | None) -> bool:
    """Keep connector migrations isolated from the first local migration.

    Drive/Gmail/other connected providers still use their proven compatibility
    paths until their dedicated migration phases. Local Upload/Paste normally has
    no provider metadata at all.
    """

    metadata = dict(external_metadata or {})
    provider = str(metadata.get("provider") or "").strip().lower()
    return provider in {"", "local", "upload", "paste"}


def compatibility_sources(analysis: ProtectSessionAnalysis) -> dict[str, dict[str, object]]:
    """Mirror session analysis into the dictionaries the current UI still reads."""

    return {
        item.source.key: {
            "document": item.document,
            "findings": item.findings,
            "label": item.source.label,
            "source": item.source,
        }
        for item in analysis.sources
    }


def compatibility_results(result: ProtectSessionResult) -> dict[str, object]:
    """Mirror session results into the current UI until its controller is replaced."""

    return {
        item.analysis.source.key: item.result
        for item in result.sources
    }
