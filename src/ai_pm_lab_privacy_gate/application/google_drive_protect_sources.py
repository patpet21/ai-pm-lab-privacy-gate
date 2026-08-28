from __future__ import annotations

"""Google Drive adapter for the generic ProtectSession contract.

The Drive browser remains responsible only for navigation and for materializing a
supported remote item into PrivacyGate's managed local workspace.  This adapter
turns that local working copy plus its connector provenance into a ProtectPackage
without leaking Drive-specific state into ProtectSessionService.

The document keeps the compatibility key ``document`` during this first Drive
migration so the approved preview/export UI continues to work unchanged.  A
pasted-text source can participate in the same package and remains independent.
"""

from pathlib import Path
from typing import Mapping

from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource


DRIVE_DOCUMENT_KEY = "document"
DRIVE_TEXT_KEY = "text"


def should_use_google_drive_adapter(
    external_metadata: Mapping[str, object] | None,
) -> bool:
    """Return True only for a source explicitly imported from Google Drive."""

    metadata = dict(external_metadata or {})
    return str(metadata.get("provider") or "").strip().lower() == "google_drive"


def build_google_drive_protect_package(
    *,
    document_path: str,
    pasted_text: str = "",
    source_metadata: Mapping[str, object] | None = None,
    source_name: str = "",
) -> ProtectPackage | None:
    """Build a Drive-backed ProtectPackage from the already-local working copy.

    Connector provenance is copied onto the Drive document source.  The generic
    service therefore sees only a normal file/text contract while later UI,
    governance, Library, and export migrations can still identify the provider,
    account, remote item, and Drive folder path.
    """

    metadata = dict(source_metadata or {})
    if not should_use_google_drive_adapter(metadata):
        raise ValueError("Google Drive Protect adapter requires google_drive provenance.")

    path_value = str(document_path or "").strip()
    if not path_value:
        return None

    path = Path(path_value)
    item_title = str(metadata.get("item_title") or "").strip() or path.name or "Drive document"
    display_name = str(source_name or "").strip()

    document_metadata = dict(metadata)
    document_metadata.update(
        {
            "origin": "google_drive",
            "source_kind": "file",
        }
    )
    if display_name:
        document_metadata["source_name"] = display_name

    sources: list[ProtectSource] = [
        ProtectSource.file_source(
            key=DRIVE_DOCUMENT_KEY,
            label=item_title,
            path=path,
            metadata=document_metadata,
        )
    ]

    text_value = str(pasted_text or "").strip()
    if text_value:
        sources.append(
            ProtectSource.text_source(
                key=DRIVE_TEXT_KEY,
                label="Pasted text",
                text=text_value,
                metadata={
                    "origin": "paste",
                    "source_kind": "text",
                },
            )
        )

    mixed = len(sources) > 1
    return ProtectPackage(
        origin="google_drive_mixed" if mixed else "google_drive",
        label=(
            f"{item_title} + Pasted text"
            if mixed
            else (display_name or item_title)
        ),
        sources=tuple(sources),
        metadata={"adapter": "google_drive_v1"},
    )
