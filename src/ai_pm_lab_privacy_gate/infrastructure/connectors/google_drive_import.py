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
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}
_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".heic"}


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip().strip(".")
    return cleaned or "Google Drive document"


def materialize_google_drive_item(service: ConnectedAppsService, item: RemoteItem) -> Path:
    """Download/export one approved Drive item to a managed local working file."""
    if item.provider != "google_drive":
        raise ValueError("This importer currently supports Google Drive only.")
    if item.kind == "application/vnd.google-apps.folder":
        raise ValueError("Open the folder first, then choose a file to import into Protect.")

    token = service._token("google_drive")
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
            if item.kind.startswith("image/") or suffix in _IMAGE_SUFFIXES:
                raise ValueError(
                    "This image is visible in Google Drive, but PrivacyGate cannot analyze image pixels yet. "
                    "Local OCR/image protection is the next document-engine block. "
                    "Supported now: PDF, DOCX, XLSX, PPTX, TXT, Google Docs, Google Sheets and Google Slides."
                )
            raise ValueError(
                "This Drive file type is not supported by Protect yet. Supported now: PDF, Word (.docx), "
                "Excel (.xlsx), PowerPoint (.pptx), text (.txt), Google Docs, Google Sheets and Google Slides."
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
