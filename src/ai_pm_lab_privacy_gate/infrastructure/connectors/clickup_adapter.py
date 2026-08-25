from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from .service import ConnectedAppsService


CLICKUP_API = "https://api.clickup.com/api/v2"


def _headers(service: ConnectedAppsService) -> dict[str, str]:
    return {"Authorization": service._token("clickup"), "Content-Type": "application/json"}


def _get(service: ConnectedAppsService, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    response = httpx.get(
        f"{CLICKUP_API}{path}",
        headers=_headers(service),
        params=params or {},
        timeout=service.timeout,
    )
    response.raise_for_status()
    return response.json()


def _clickup_hierarchy(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    """Return ClickUp workspaces with Spaces, Folders and Lists for read-only browsing."""
    payload = _get(self, "/team")
    teams = payload.get("teams", []) if isinstance(payload, dict) else []
    workspaces: list[dict[str, Any]] = []

    for team in teams:
        team_id = str(team.get("id") or "")
        if not team_id:
            continue
        workspace: dict[str, Any] = {
            "id": team_id,
            "name": str(team.get("name") or "Workspace"),
            "kind": "workspace",
            "spaces": [],
        }
        spaces_payload = _get(self, f"/team/{team_id}/space", params={"archived": "false"})
        spaces = spaces_payload.get("spaces", []) if isinstance(spaces_payload, dict) else []
        for space in spaces:
            space_id = str(space.get("id") or "")
            if not space_id:
                continue
            space_node: dict[str, Any] = {
                "id": space_id,
                "name": str(space.get("name") or "Space"),
                "kind": "space",
                "private": bool(space.get("private")),
                "folders": [],
                "lists": [],
            }

            folder_payload = _get(self, f"/space/{space_id}/folder", params={"archived": "false"})
            folders = folder_payload.get("folders", []) if isinstance(folder_payload, dict) else []
            for folder in folders:
                folder_id = str(folder.get("id") or "")
                folder_node = {
                    "id": folder_id,
                    "name": str(folder.get("name") or "Folder"),
                    "kind": "folder",
                    "lists": [],
                }
                for list_item in folder.get("lists", []) or []:
                    list_id = str(list_item.get("id") or "")
                    if list_id:
                        folder_node["lists"].append(
                            {
                                "id": list_id,
                                "name": str(list_item.get("name") or "List"),
                                "kind": "list",
                                "status": list_item.get("status"),
                            }
                        )
                space_node["folders"].append(folder_node)

            lists_payload = _get(self, f"/space/{space_id}/list", params={"archived": "false"})
            lists = lists_payload.get("lists", []) if isinstance(lists_payload, dict) else []
            for list_item in lists:
                list_id = str(list_item.get("id") or "")
                if list_id:
                    space_node["lists"].append(
                        {
                            "id": list_id,
                            "name": str(list_item.get("name") or "List"),
                            "kind": "list",
                            "status": list_item.get("status"),
                        }
                    )
            workspace["spaces"].append(space_node)
        workspaces.append(workspace)
    return tuple(workspaces)


def _clickup_list_tasks(self: ConnectedAppsService, list_id: str, limit: int = 100) -> tuple[dict[str, Any], ...]:
    limit = max(1, min(int(limit), 100))
    payload = _get(
        self,
        f"/list/{list_id}/task",
        params={
            "archived": "false",
            "include_closed": "true",
            "page": "0",
            "order_by": "updated",
            "reverse": "true",
            "subtasks": "true",
        },
    )
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    return tuple(tasks[:limit])


def _clickup_workspace_tasks(self: ConnectedAppsService, team_id: str, limit: int = 100) -> tuple[dict[str, Any], ...]:
    limit = max(1, min(int(limit), 100))
    payload = _get(
        self,
        f"/team/{team_id}/task",
        params={
            "page": "0",
            "order_by": "updated",
            "reverse": "true",
            "include_closed": "true",
            "subtasks": "true",
        },
    )
    tasks = payload.get("tasks", []) if isinstance(payload, dict) else []
    return tuple(tasks[:limit])


def _clickup_task_detail(self: ConnectedAppsService, task_id: str) -> dict[str, Any]:
    payload = _get(self, f"/task/{task_id}", params={"include_subtasks": "true"})
    return payload if isinstance(payload, dict) else {}


def _date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(value)


def _person_name(person: dict[str, Any]) -> str:
    return str(person.get("username") or person.get("email") or person.get("id") or "").strip()


def _clickup_task_to_text(self: ConnectedAppsService, task: dict[str, Any]) -> str:
    """Create a clean local text working copy suitable for PrivacyGate Protect."""
    status = task.get("status") or {}
    priority = task.get("priority") or {}
    creator = task.get("creator") or {}
    assignees = [name for name in (_person_name(p) for p in task.get("assignees", []) or []) if name]
    watchers = [name for name in (_person_name(p) for p in task.get("watchers", []) or []) if name]
    tags = [str(tag.get("name") or "").strip() for tag in task.get("tags", []) or [] if str(tag.get("name") or "").strip()]
    list_info = task.get("list") or {}
    folder = task.get("folder") or {}
    space = task.get("space") or {}

    lines = [
        "CLICKUP TASK — LOCAL WORKING COPY",
        "",
        f"Task: {task.get('name') or 'Untitled task'}",
        f"Task ID: {task.get('id') or ''}",
        f"Status: {status.get('status') or ''}",
        f"Priority: {priority.get('priority') or ''}",
        f"Workspace/Team ID: {task.get('team_id') or ''}",
        f"Space: {space.get('name') or ''}",
        f"Folder: {folder.get('name') or ''}",
        f"List: {list_info.get('name') or ''}",
        f"Creator: {_person_name(creator)}",
        f"Assignees: {', '.join(assignees)}",
        f"Watchers: {', '.join(watchers)}",
        f"Tags: {', '.join(tags)}",
        f"Start: {_date_text(task.get('start_date'))}",
        f"Due: {_date_text(task.get('due_date'))}",
        f"Created: {_date_text(task.get('date_created'))}",
        f"Updated: {_date_text(task.get('date_updated'))}",
        f"Closed: {_date_text(task.get('date_closed'))}",
        f"URL: {task.get('url') or ''}",
        "",
        "DESCRIPTION",
        str(task.get("text_content") or task.get("description") or "").strip(),
    ]

    custom_fields = task.get("custom_fields", []) or []
    if custom_fields:
        lines.extend(["", "CUSTOM FIELDS"])
        for field in custom_fields:
            value = field.get("value")
            if value not in (None, "", [], {}):
                lines.append(f"{field.get('name') or 'Field'}: {value}")

    checklists = task.get("checklists", []) or []
    if checklists:
        lines.extend(["", "CHECKLISTS"])
        for checklist in checklists:
            lines.append(f"{checklist.get('name') or 'Checklist'}:")
            for item in checklist.get("items", []) or []:
                marker = "[x]" if item.get("resolved") else "[ ]"
                lines.append(f"  {marker} {item.get('name') or ''}")

    return "\n".join(lines).strip() + "\n"


def install_clickup_adapter() -> None:
    if getattr(ConnectedAppsService, "_clickup_adapter_installed", False):
        return
    ConnectedAppsService.clickup_hierarchy = _clickup_hierarchy  # type: ignore[attr-defined]
    ConnectedAppsService.clickup_list_tasks = _clickup_list_tasks  # type: ignore[attr-defined]
    ConnectedAppsService.clickup_workspace_tasks = _clickup_workspace_tasks  # type: ignore[attr-defined]
    ConnectedAppsService.clickup_task_detail = _clickup_task_detail  # type: ignore[attr-defined]
    ConnectedAppsService.clickup_task_to_text = _clickup_task_to_text  # type: ignore[attr-defined]
    ConnectedAppsService._clickup_adapter_installed = True  # type: ignore[attr-defined]
