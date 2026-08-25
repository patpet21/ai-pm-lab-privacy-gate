from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .extended_oauth import connect_jira, connect_monday, connect_notion
from .service import ConnectedAppsService, ConnectionTestResult, RemoteItem


def _store_payload(service: ConnectedAppsService, provider: str, payload: dict[str, Any]) -> None:
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError(f"{service.provider_name(provider)} did not return an access token")
    service.secret_store.set(f"connected.{provider}.token", token)
    refresh = str(payload.get("refresh_token") or "")
    if refresh:
        service.secret_store.set(f"connected.{provider}.refresh_token", refresh)
    for key in ("workspace_id", "workspace_name", "workspace_icon", "bot_id", "owner"):
        value = payload.get(key)
        if value not in (None, ""):
            service.secret_store.set(f"connected.{provider}.{key}", json.dumps(value) if isinstance(value, (dict, list)) else str(value))


def _connect_notion(self: ConnectedAppsService) -> None:
    _store_payload(self, "notion", connect_notion())


def _connect_monday(self: ConnectedAppsService) -> None:
    _store_payload(self, "monday", connect_monday())


def _connect_jira(self: ConnectedAppsService) -> None:
    _store_payload(self, "jira", connect_jira())


def _bearer(self: ConnectedAppsService, provider: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {self._token(provider)}", "Content-Type": "application/json"}


def _asana_projects(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    token = self._token("asana")
    workspaces = httpx.get("https://app.asana.com/api/1.0/workspaces", headers={"Authorization": f"Bearer {token}"}, timeout=self.timeout)
    workspaces.raise_for_status()
    rows: list[dict[str, Any]] = []
    for workspace in workspaces.json().get("data", []):
        wid = str(workspace.get("gid") or "")
        response = httpx.get(
            "https://app.asana.com/api/1.0/projects",
            headers={"Authorization": f"Bearer {token}"},
            params={"workspace": wid, "archived": "false", "limit": "100", "opt_fields": "name,modified_at,color"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        for project in response.json().get("data", []):
            project["workspace_name"] = workspace.get("name") or "Workspace"
            rows.append(project)
    return tuple(rows)


def _asana_tasks(self: ConnectedAppsService, project_id: str) -> tuple[dict[str, Any], ...]:
    token = self._token("asana")
    response = httpx.get(
        f"https://app.asana.com/api/1.0/projects/{project_id}/tasks",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": "100", "opt_fields": "name,completed,due_on,due_at,assignee.name,assignee.email,memberships.section.name,tags.name,modified_at"},
        timeout=self.timeout,
    )
    response.raise_for_status()
    return tuple(response.json().get("data", []))


def _asana_detail(self: ConnectedAppsService, task_id: str) -> dict[str, Any]:
    token = self._token("asana")
    response = httpx.get(
        f"https://app.asana.com/api/1.0/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"opt_fields": "name,notes,html_notes,completed,completed_at,due_on,due_at,start_on,start_at,assignee.name,assignee.email,created_by.name,created_at,modified_at,permalink_url,tags.name,memberships.project.name,memberships.section.name,custom_fields.name,custom_fields.display_value"},
        timeout=self.timeout,
    )
    response.raise_for_status()
    return response.json().get("data", {})


def _trello_boards(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    key = self.secret_store.get("connected.trello.key") or ""
    token = self.secret_store.get("connected.trello.token") or ""
    response = httpx.get("https://api.trello.com/1/members/me/boards", params={"key": key, "token": token, "fields": "name,url,desc,dateLastActivity", "filter": "open"}, timeout=self.timeout)
    response.raise_for_status()
    return tuple(response.json())


def _trello_cards(self: ConnectedAppsService, board_id: str) -> tuple[dict[str, Any], ...]:
    key = self.secret_store.get("connected.trello.key") or ""
    token = self.secret_store.get("connected.trello.token") or ""
    lists = httpx.get(f"https://api.trello.com/1/boards/{board_id}/lists", params={"key": key, "token": token, "fields": "name", "filter": "open"}, timeout=self.timeout)
    lists.raise_for_status()
    list_names = {str(x.get("id")): x.get("name") for x in lists.json()}
    response = httpx.get(f"https://api.trello.com/1/boards/{board_id}/cards", params={"key": key, "token": token, "fields": "name,desc,due,dueComplete,idList,url,labels,dateLastActivity", "members": "true", "member_fields": "fullName,username"}, timeout=self.timeout)
    response.raise_for_status()
    rows = response.json()
    for card in rows:
        card["list_name"] = list_names.get(str(card.get("idList")), "")
    return tuple(rows)


def _trello_detail(self: ConnectedAppsService, card_id: str) -> dict[str, Any]:
    key = self.secret_store.get("connected.trello.key") or ""
    token = self.secret_store.get("connected.trello.token") or ""
    response = httpx.get(f"https://api.trello.com/1/cards/{card_id}", params={"key": key, "token": token, "fields": "all", "members": "true", "member_fields": "fullName,username", "checklists": "all"}, timeout=self.timeout)
    response.raise_for_status()
    return response.json()


def _notion_items(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    response = httpx.post(
        "https://api.notion.com/v1/search",
        headers={**_bearer(self, "notion"), "Notion-Version": "2022-06-28"},
        json={"page_size": 100, "sort": {"direction": "descending", "timestamp": "last_edited_time"}},
        timeout=self.timeout,
    )
    response.raise_for_status()
    return tuple(response.json().get("results", []))


def _notion_title(obj: dict[str, Any]) -> str:
    if obj.get("object") == "database":
        bits = obj.get("title", []) or []
        return "".join(str(x.get("plain_text") or "") for x in bits).strip() or "Untitled database"
    props = obj.get("properties") or {}
    for value in props.values():
        if value.get("type") == "title":
            return "".join(str(x.get("plain_text") or "") for x in value.get("title", []) or []).strip() or "Untitled page"
    return "Untitled page"


def _notion_detail(self: ConnectedAppsService, item_id: str) -> dict[str, Any]:
    headers = {**_bearer(self, "notion"), "Notion-Version": "2022-06-28"}
    page = httpx.get(f"https://api.notion.com/v1/pages/{item_id}", headers=headers, timeout=self.timeout)
    if page.status_code >= 400:
        page = httpx.get(f"https://api.notion.com/v1/databases/{item_id}", headers=headers, timeout=self.timeout)
    page.raise_for_status()
    blocks = httpx.get(f"https://api.notion.com/v1/blocks/{item_id}/children", headers=headers, params={"page_size": "100"}, timeout=self.timeout)
    block_rows = blocks.json().get("results", []) if blocks.status_code < 400 else []
    result = page.json()
    result["_blocks"] = block_rows
    return result


def _monday_graphql(self: ConnectedAppsService, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    response = httpx.post("https://api.monday.com/v2", headers={"Authorization": self._token("monday"), "Content-Type": "application/json"}, json={"query": query, "variables": variables or {}}, timeout=self.timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"][0].get("message") or payload["errors"][0]))
    return payload.get("data", {})


def _monday_boards(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    data = _monday_graphql(self, "query { boards(limit: 100, state: active) { id name description board_kind updated_at workspace { id name } } }")
    return tuple(data.get("boards", []))


def _monday_items(self: ConnectedAppsService, board_id: str) -> tuple[dict[str, Any], ...]:
    data = _monday_graphql(self, "query($ids:[ID!]) { boards(ids:$ids) { items_page(limit:100) { items { id name created_at updated_at group { id title } column_values { id type text value } } } } }", {"ids": [board_id]})
    boards = data.get("boards", [])
    return tuple((boards[0].get("items_page", {}) if boards else {}).get("items", []))


def _monday_detail(self: ConnectedAppsService, item_id: str) -> dict[str, Any]:
    data = _monday_graphql(self, "query($ids:[ID!]) { items(ids:$ids) { id name created_at updated_at url board { id name } group { id title } column_values { id type text value column { title } } updates(limit:20) { id body created_at creator { name email } } } }", {"ids": [item_id]})
    rows = data.get("items", [])
    return rows[0] if rows else {}


def _jira_cloud(self: ConnectedAppsService) -> tuple[str, str]:
    response = httpx.get("https://api.atlassian.com/oauth/token/accessible-resources", headers=_bearer(self, "jira"), timeout=self.timeout)
    response.raise_for_status()
    resources = response.json()
    if not resources:
        raise RuntimeError("No Jira cloud site is available for this account.")
    first = resources[0]
    return str(first.get("id") or ""), str(first.get("name") or first.get("url") or "Jira")


def _jira_projects(self: ConnectedAppsService) -> tuple[dict[str, Any], ...]:
    cloud_id, _ = _jira_cloud(self)
    response = httpx.get(f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project/search", headers=_bearer(self, "jira"), params={"maxResults": "100"}, timeout=self.timeout)
    response.raise_for_status()
    rows = response.json().get("values", [])
    for row in rows:
        row["_cloud_id"] = cloud_id
    return tuple(rows)


def _jira_issues(self: ConnectedAppsService, project_key: str) -> tuple[dict[str, Any], ...]:
    cloud_id, _ = _jira_cloud(self)
    response = httpx.get(f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/search/jql", headers=_bearer(self, "jira"), params={"jql": f"project = {project_key} ORDER BY updated DESC", "maxResults": "100", "fields": "summary,status,assignee,priority,labels,updated,duedate,issuetype"}, timeout=self.timeout)
    response.raise_for_status()
    rows = response.json().get("issues", [])
    for row in rows:
        row["_cloud_id"] = cloud_id
    return tuple(rows)


def _jira_detail(self: ConnectedAppsService, issue_key: str) -> dict[str, Any]:
    cloud_id, _ = _jira_cloud(self)
    response = httpx.get(f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{issue_key}", headers=_bearer(self, "jira"), params={"fields": "*all"}, timeout=self.timeout)
    response.raise_for_status()
    row = response.json()
    row["_cloud_id"] = cloud_id
    return row


def _plain_rich_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_plain_rich_text(x) for x in value)
    if isinstance(value, dict):
        if "plain_text" in value:
            return str(value.get("plain_text") or "")
        if value.get("type") == "text":
            return str((value.get("text") or {}).get("content") or "")
        if "content" in value:
            return _plain_rich_text(value.get("content"))
        return " ".join(_plain_rich_text(v) for v in value.values())
    return ""


def _item_to_text(self: ConnectedAppsService, provider: str, item: dict[str, Any]) -> str:
    lines = [f"{self.provider_name(provider).upper()} — LOCAL WORKING COPY", ""]
    if provider == "asana":
        lines += [f"Task: {item.get('name') or ''}", f"Completed: {item.get('completed')}", f"Due: {item.get('due_on') or item.get('due_at') or ''}", f"Assignee: {(item.get('assignee') or {}).get('name') or ''}", f"Created by: {(item.get('created_by') or {}).get('name') or ''}", f"URL: {item.get('permalink_url') or ''}", "", "DESCRIPTION", str(item.get('notes') or '')]
        for field in item.get("custom_fields", []) or []:
            lines.append(f"{field.get('name')}: {field.get('display_value') or ''}")
    elif provider == "trello":
        lines += [f"Card: {item.get('name') or ''}", f"Due: {item.get('due') or ''}", f"URL: {item.get('url') or ''}", f"Members: {', '.join(str(x.get('fullName') or x.get('username') or '') for x in item.get('members', []) or [])}", f"Labels: {', '.join(str(x.get('name') or '') for x in item.get('labels', []) or [])}", "", "DESCRIPTION", str(item.get('desc') or '')]
        for checklist in item.get("checklists", []) or []:
            lines += ["", f"CHECKLIST: {checklist.get('name') or ''}"]
            for check in checklist.get("checkItems", []) or []:
                lines.append(f"[{'x' if check.get('state') == 'complete' else ' '}] {check.get('name') or ''}")
    elif provider == "notion":
        lines += [f"Title: {_notion_title(item)}", f"URL: {item.get('url') or ''}", f"Last edited: {item.get('last_edited_time') or ''}", ""]
        for block in item.get("_blocks", []) or []:
            data = block.get(block.get("type"), {}) if isinstance(block, dict) else {}
            text = _plain_rich_text(data.get("rich_text") or data.get("caption") or data)
            if text.strip():
                lines.append(text.strip())
    elif provider == "monday":
        lines += [f"Item: {item.get('name') or ''}", f"Board: {(item.get('board') or {}).get('name') or ''}", f"Group: {(item.get('group') or {}).get('title') or ''}", f"URL: {item.get('url') or ''}", f"Updated: {item.get('updated_at') or ''}", "", "COLUMNS"]
        for col in item.get("column_values", []) or []:
            lines.append(f"{(col.get('column') or {}).get('title') or col.get('id')}: {col.get('text') or ''}")
        for update in item.get("updates", []) or []:
            lines += ["", f"UPDATE — {(update.get('creator') or {}).get('name') or ''} — {update.get('created_at') or ''}", str(update.get('body') or '')]
    elif provider == "jira":
        fields = item.get("fields") or {}
        lines += [f"Issue: {item.get('key') or ''} — {fields.get('summary') or ''}", f"Status: {(fields.get('status') or {}).get('name') or ''}", f"Priority: {(fields.get('priority') or {}).get('name') or ''}", f"Assignee: {(fields.get('assignee') or {}).get('displayName') or ''}", f"Labels: {', '.join(fields.get('labels') or [])}", f"Due: {fields.get('duedate') or ''}", f"Updated: {fields.get('updated') or ''}", "", "DESCRIPTION", _plain_rich_text(fields.get('description'))]
    return "\n".join(lines).strip() + "\n"


_PREV_TEST = ConnectedAppsService.test_connection
_PREV_LIST = ConnectedAppsService.list_root_items


def _test_connection(self: ConnectedAppsService, provider: str) -> ConnectionTestResult:
    if provider == "notion":
        try:
            response = httpx.get("https://api.notion.com/v1/users/me", headers={**_bearer(self, "notion"), "Notion-Version": "2022-06-28"}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            label = str(data.get("name") or self.secret_store.get("connected.notion.workspace_name") or "Notion workspace")
            return ConnectionTestResult(True, provider, label, "Notion is connected read-only.")
        except Exception as exc:
            return ConnectionTestResult(False, provider, detail=self._safe_error(exc))
    if provider == "monday":
        try:
            data = _monday_graphql(self, "query { me { id name email } account { id name } }")
            me = data.get("me") or {}
            account = data.get("account") or {}
            return ConnectionTestResult(True, provider, str(account.get("name") or me.get("name") or me.get("email") or "monday.com"), "monday.com is connected read-only.")
        except Exception as exc:
            return ConnectionTestResult(False, provider, detail=self._safe_error(exc))
    if provider == "jira":
        try:
            _, name = _jira_cloud(self)
            return ConnectionTestResult(True, provider, name, "Jira is connected read-only.")
        except Exception as exc:
            return ConnectionTestResult(False, provider, detail=self._safe_error(exc))
    return _PREV_TEST(self, provider)


def _list_root(self: ConnectedAppsService, provider: str, limit: int = 30) -> tuple[RemoteItem, ...]:
    if provider == "notion":
        return tuple(RemoteItem(provider, str(x.get("id") or ""), _notion_title(x), str(x.get("last_edited_time") or ""), str(x.get("object") or "page"), str(x.get("url") or "")) for x in _notion_items(self)[:limit])
    if provider == "monday":
        return tuple(RemoteItem(provider, str(x.get("id") or ""), str(x.get("name") or "Board"), str((x.get("workspace") or {}).get("name") or ""), "board") for x in _monday_boards(self)[:limit])
    if provider == "jira":
        return tuple(RemoteItem(provider, str(x.get("id") or ""), str(x.get("name") or "Project"), str(x.get("key") or ""), "project") for x in _jira_projects(self)[:limit])
    return _PREV_LIST(self, provider, limit)


def install_project_platform_adapter() -> None:
    if getattr(ConnectedAppsService, "_project_platform_adapter_installed", False):
        return
    ConnectedAppsService.PROVIDERS.update({"notion": "Notion", "monday": "monday.com", "jira": "Jira"})
    ConnectedAppsService.connect_notion_oauth = _connect_notion  # type: ignore[attr-defined]
    ConnectedAppsService.connect_monday_oauth = _connect_monday  # type: ignore[attr-defined]
    ConnectedAppsService.connect_jira_oauth = _connect_jira  # type: ignore[attr-defined]
    ConnectedAppsService.asana_projects = _asana_projects  # type: ignore[attr-defined]
    ConnectedAppsService.asana_tasks = _asana_tasks  # type: ignore[attr-defined]
    ConnectedAppsService.asana_detail = _asana_detail  # type: ignore[attr-defined]
    ConnectedAppsService.trello_boards = _trello_boards  # type: ignore[attr-defined]
    ConnectedAppsService.trello_cards = _trello_cards  # type: ignore[attr-defined]
    ConnectedAppsService.trello_detail = _trello_detail  # type: ignore[attr-defined]
    ConnectedAppsService.notion_items = _notion_items  # type: ignore[attr-defined]
    ConnectedAppsService.notion_detail = _notion_detail  # type: ignore[attr-defined]
    ConnectedAppsService.monday_boards = _monday_boards  # type: ignore[attr-defined]
    ConnectedAppsService.monday_items = _monday_items  # type: ignore[attr-defined]
    ConnectedAppsService.monday_detail = _monday_detail  # type: ignore[attr-defined]
    ConnectedAppsService.jira_projects = _jira_projects  # type: ignore[attr-defined]
    ConnectedAppsService.jira_issues = _jira_issues  # type: ignore[attr-defined]
    ConnectedAppsService.jira_detail = _jira_detail  # type: ignore[attr-defined]
    ConnectedAppsService.project_item_to_text = _item_to_text  # type: ignore[attr-defined]
    ConnectedAppsService.test_connection = _test_connection  # type: ignore[method-assign]
    ConnectedAppsService.list_root_items = _list_root  # type: ignore[method-assign]
    ConnectedAppsService._project_platform_adapter_installed = True  # type: ignore[attr-defined]
