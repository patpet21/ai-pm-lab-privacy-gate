from __future__ import annotations

import re
from pathlib import Path

import httpx

from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService, RemoteItem
from ai_pm_lab_privacy_gate.infrastructure.security.temporary_workspace import new_working_path


_GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}
_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".xlsx"}


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip().strip(".")
    return cleaned or "Google Drive document"


def materialize_google_drive_item(service: ConnectedAppsService, item: RemoteItem) -> Path:
    """Download/export one approved Drive item to a managed local working file.

    Nothing is uploaded elsewhere. Native Google Docs/Sheets/Slides are exported
    to formats already understood by PrivacyGate's local protection pipeline.
    The returned path is inside PrivacyGate's isolated temporary workspace and is
    eligible for automatic cleanup after the protection workflow finishes.
    """
    if item.provider != "google_drive":
        raise ValueError("This importer currently supports Google Drive only.")
    if item.kind == "application/vnd.google-apps.folder":
        raise ValueError("Choose a file, not a folder.")

    token = service._token("google_drive")  # connector-local credential accessor
    headers = {"Authorization": f"Bearer {token}"}
    export = _GOOGLE_EXPORTS.get(item.kind)

    if export:
        export_mime, suffix = export
        filename = _safe_filename(item.title)
        if not filename.lower().endswith(suffix):
            filename += suffix
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{item.item_id}/export",
            headers=headers,
            params={"mimeType": export_mime},
            timeout=30.0,
        )
    else:
        suffix = Path(item.title).suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                "PrivacyGate can currently import PDF, Word (.docx), Excel (.xlsx), "
                "Google Docs, Google Sheets and Google Slides from Drive."
            )
        filename = _safe_filename(item.title)
        response = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{item.item_id}",
            headers=headers,
            params={"alt": "media"},
            timeout=30.0,
        )

    response.raise_for_status()
    target = new_working_path("google_drive", filename)
    target.write_bytes(response.content)
    return target
