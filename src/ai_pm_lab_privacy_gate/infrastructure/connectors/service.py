from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import httpx

from .google_tls import google_ssl_context

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    provider: str
    account_label: str = ""
    detail: str = ""


@dataclass(frozen=True)
class RemoteItem:
    provider: str
    item_id: str
    title: str
    subtitle: str = ""
    kind: str = "item"
    url: str = ""


class ConnectedAppsService:
    """Read-only connected-app access with secrets stored locally.

    This layer deliberately retrieves business data only. It does not send
    retrieved content to an AI provider. Privacy/de-identification is a separate
    local step performed by PrivacyGate before any AI-facing workflow.
    """

    PROVIDERS = {
        "google_drive": "Google Drive",
        "clickup": "ClickUp",
        "asana": "Asana",
        "trello": "Trello",
    }

    def __init__(self, data_dir: str | Path, secret_store: SecretStore | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.secret_store = secret_store or platform_secret_store(self.data_dir)
        self.timeout = httpx.Timeout(15.0, connect=10.0)

    @classmethod
    def provider_name(cls, provider: str) -> str:
        return cls.PROVIDERS.get(provider, provider)

    def is_connected(self, provider: str) -> bool:
        if provider == "trello":
            return bool(self.secret_store.get("connected.trello.key") and self.secret_store.get("connected.trello.token"))
        return bool(self.secret_store.get(f"connected.{provider}.token"))

    def save_credentials(self, provider: str, *, token: str = "", api_key: str = "") -> None:
        provider = provider.strip().lower()
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        if provider == "trello":
            if not api_key.strip() or not token.strip():
                raise ValueError("Trello requires both API key and token")
            self.secret_store.set("connected.trello.key", api_key.strip())
            self.secret_store.set("connected.trello.token", token.strip())
            return
        if not token.strip():
            raise ValueError(f"{self.provider_name(provider)} requires an access token")
        self.secret_store.set(f"connected.{provider}.token", token.strip())

    def disconnect(self, provider: str) -> None:
        if provider == "trello":
            self.secret_store.delete("connected.trello.key")
            self.secret_store.delete("connected.trello.token")
            return
        self.secret_store.delete(f"connected.{provider}.token")

    def test_connection(self, provider: str) -> ConnectionTestResult:
        try:
            if provider == "google_drive":
                token = self._token(provider)
                response = httpx.get(
                    "https://www.googleapis.com/drive/v3/about",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"fields": "user(displayName,emailAddress)"},
                    timeout=self.timeout,
                    verify=google_ssl_context(),
                )
                response.raise_for_status()
                user = response.json().get("user", {})
                label = user.get("displayName") or user.get("emailAddress") or "Google account"
                return ConnectionTestResult(True, provider, label, "Google Drive is connected read-only.")

            if provider == "clickup":
                token = self._token(provider)
                response = httpx.get(
                    "https://api.clickup.com/api/v2/user",
                    headers={"Authorization": token},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                user = response.json().get("user", {})
                label = user.get("username") or user.get("email") or "ClickUp account"
                return ConnectionTestResult(True, provider, label, "ClickUp is connected read-only.")

            if provider == "asana":
                token = self._token(provider)
                response = httpx.get(
                    "https://app.asana.com/api/1.0/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                user = response.json().get("data", {})
                label = user.get("name") or user.get("email") or "Asana account"
                return ConnectionTestResult(True, provider, label, "Asana is connected read-only.")

            if provider == "trello":
                key = self.secret_store.get("connected.trello.key") or ""
                token = self.secret_store.get("connected.trello.token") or ""
                response = httpx.get(
                    "https://api.trello.com/1/members/me",
                    params={"key": key, "token": token, "fields": "fullName,username"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                user = response.json()
                label = user.get("fullName") or user.get("username") or "Trello account"
                return ConnectionTestResult(True, provider, label, "Trello is connected read-only.")

            return ConnectionTestResult(False, provider, detail="Unsupported provider")
        except Exception as exc:
            return ConnectionTestResult(False, provider, detail=self._safe_error(exc))

    def list_root_items(self, provider: str, limit: int = 30) -> tuple[RemoteItem, ...]:
        limit = max(1, min(int(limit), 100))
        if provider == "google_drive":
            token = self._token(provider)
            response = httpx.get(
                "https://www.googleapis.com/drive/v3/files",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "pageSize": str(limit),
                    "orderBy": "modifiedTime desc",
                    "q": "trashed = false",
                    "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
                },
                timeout=self.timeout,
                verify=google_ssl_context(),
            )
            response.raise_for_status()
            return tuple(
                RemoteItem(
                    provider,
                    item.get("id", ""),
                    item.get("name", "Untitled"),
                    item.get("modifiedTime", ""),
                    item.get("mimeType", "file"),
                    item.get("webViewLink", ""),
                )
                for item in response.json().get("files", [])
            )

        if provider == "clickup":
            token = self._token(provider)
            response = httpx.get(
                "https://api.clickup.com/api/v2/team",
                headers={"Authorization": token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            teams = response.json().get("teams", [])[:limit]
            return tuple(
                RemoteItem(provider, str(team.get("id", "")), team.get("name", "Workspace"), "Workspace", "workspace")
                for team in teams
            )

        if provider == "asana":
            token = self._token(provider)
            response = httpx.get(
                "https://app.asana.com/api/1.0/workspaces",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": str(limit), "opt_fields": "name"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return tuple(
                RemoteItem(provider, str(item.get("gid", "")), item.get("name", "Workspace"), "Workspace", "workspace")
                for item in response.json().get("data", [])
            )

        if provider == "trello":
            key = self.secret_store.get("connected.trello.key") or ""
            token = self.secret_store.get("connected.trello.token") or ""
            response = httpx.get(
                "https://api.trello.com/1/members/me/boards",
                params={
                    "key": key,
                    "token": token,
                    "fields": "name,url,dateLastActivity,closed",
                    "filter": "open",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return tuple(
                RemoteItem(
                    provider,
                    str(item.get("id", "")),
                    item.get("name", "Board"),
                    item.get("dateLastActivity", ""),
                    "board",
                    item.get("url", ""),
                )
                for item in response.json()[:limit]
            )

        raise ValueError(f"Unsupported provider: {provider}")

    def _token(self, provider: str) -> str:
        token = self.secret_store.get(f"connected.{provider}.token")
        if not token:
            raise RuntimeError(f"{self.provider_name(provider)} is not connected")
        return token

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            detail = ""
            try:
                payload = exc.response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    detail = str(error.get("message") or "").strip()
                    errors = error.get("errors") or []
                    if not detail and errors and isinstance(errors[0], dict):
                        detail = str(errors[0].get("message") or errors[0].get("reason") or "").strip()
                elif isinstance(error, str):
                    detail = error.strip()
                if not detail and isinstance(payload, dict):
                    detail = str(payload.get("error_description") or payload.get("message") or "").strip()
            except Exception:
                detail = ""
            if code in {401, 403}:
                if detail:
                    return f"Authorization failed (HTTP {code}): {detail}"
                return "Authorization failed. Reconnect this account or check its permissions."
            if code == 429:
                return "The provider rate limit was reached. Try again shortly."
            if detail:
                return f"Provider returned HTTP {code}: {detail}"
            return f"Provider returned HTTP {code}."
        if isinstance(exc, httpx.TimeoutException):
            return "The provider did not respond before the connection timed out."
        return str(exc) or exc.__class__.__name__
