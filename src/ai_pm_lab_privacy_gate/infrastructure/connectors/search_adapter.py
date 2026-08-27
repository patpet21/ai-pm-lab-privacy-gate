from __future__ import annotations

import httpx

from .service import ConnectedAppsService, RemoteItem


_PREV_LIST = ConnectedAppsService.list_root_items


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _drive_rows(payload: dict) -> tuple[RemoteItem, ...]:
    return tuple(
        RemoteItem(
            "google_drive",
            str(item.get("id") or ""),
            str(item.get("name") or "Untitled"),
            str(item.get("modifiedTime") or ""),
            str(item.get("mimeType") or "file"),
            str(item.get("webViewLink") or ""),
        )
        for item in payload.get("files", [])
    )


def _drive_folder_query(folder_id: str, query: str = "") -> str:
    parent = _escape_drive_query(folder_id.strip() or "root")
    clauses = ["trashed = false", f"'{parent}' in parents"]
    search = " ".join((query or "").split()).strip()
    if search:
        escaped = _escape_drive_query(search)
        clauses.append(f"(name contains '{escaped}' or fullText contains '{escaped}')")
    return " and ".join(clauses)


def _list_drive_folder(
    self: ConnectedAppsService,
    folder_id: str = "root",
    limit: int = 100,
) -> tuple[RemoteItem, ...]:
    """List the direct children of one Drive folder, including subfolders."""
    token = self._token("google_drive")
    response = httpx.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "pageSize": str(max(1, min(int(limit), 100))),
            "orderBy": "folder,name_natural",
            "q": _drive_folder_query(folder_id),
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,parents)",
        },
        timeout=self.timeout,
    )
    response.raise_for_status()
    return _drive_rows(response.json())


def _search_drive_folder(
    self: ConnectedAppsService,
    folder_id: str,
    query: str,
    limit: int = 100,
) -> tuple[RemoteItem, ...]:
    """Search inside the currently open Drive folder without flattening navigation."""
    search = " ".join((query or "").split()).strip()
    if not search:
        return _list_drive_folder(self, folder_id, limit)
    token = self._token("google_drive")
    response = httpx.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "pageSize": str(max(1, min(int(limit), 100))),
            "orderBy": "folder,name_natural",
            "q": _drive_folder_query(folder_id, search),
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,parents)",
        },
        timeout=self.timeout,
    )
    response.raise_for_status()
    return _drive_rows(response.json())


def _search_items(
    self: ConnectedAppsService,
    provider: str,
    query: str,
    limit: int = 60,
) -> tuple[RemoteItem, ...]:
    query = " ".join((query or "").split()).strip()
    limit = max(1, min(int(limit), 100))
    if not query:
        return _PREV_LIST(self, provider, limit)

    if provider == "google_drive":
        token = self._token("google_drive")
        escaped = _escape_drive_query(query)
        response = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "pageSize": str(limit),
                "orderBy": "modifiedTime desc",
                "q": f"trashed = false and (name contains '{escaped}' or fullText contains '{escaped}')",
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _drive_rows(response.json())

    # Providers whose current first browser layer exposes workspaces/boards use
    # a local filter until their deeper provider-specific search endpoint lands.
    rows = _PREV_LIST(self, provider, min(max(limit, 60), 100))
    needle = query.casefold()
    return tuple(
        row
        for row in rows
        if needle in f"{row.title} {row.subtitle} {row.kind}".casefold()
    )[:limit]


def install_search_adapter() -> None:
    if getattr(ConnectedAppsService, "_search_adapter_installed", False):
        return
    ConnectedAppsService.search_items = _search_items  # type: ignore[attr-defined]
    ConnectedAppsService.list_drive_folder = _list_drive_folder  # type: ignore[attr-defined]
    ConnectedAppsService.search_drive_folder = _search_drive_folder  # type: ignore[attr-defined]
    ConnectedAppsService._search_adapter_installed = True  # type: ignore[attr-defined]
