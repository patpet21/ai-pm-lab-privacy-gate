from __future__ import annotations

import os
import time

import httpx

from .extended_oauth import connect_jira
from .provider_oauth import ProviderOAuthError
from .service import ConnectedAppsService


JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"


def _refresh_jira_payload(refresh_token: str) -> dict:
    client_id = os.environ.get("PRIVACY_GATE_JIRA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PRIVACY_GATE_JIRA_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ProviderOAuthError("Jira OAuth client ID/secret is not configured.")
    response = httpx.post(
        JIRA_TOKEN_URL,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=25.0,
    )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("error_description") or payload.get("error") or "")
        except Exception:
            pass
        raise ProviderOAuthError(
            f"Jira token refresh failed (HTTP {response.status_code})" + (f" — {detail}" if detail else "")
        )
    payload = response.json()
    if not payload.get("access_token"):
        raise ProviderOAuthError("Jira refresh did not return an access token.")
    payload["obtained_at"] = int(time.time())
    return payload


def _store_payload(self: ConnectedAppsService, payload: dict) -> None:
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Jira did not return an access token")
    self.secret_store.set("connected.jira.token", token)
    refresh = str(payload.get("refresh_token") or "")
    if refresh:
        # Atlassian uses rotating refresh tokens. Always replace the previous
        # token when a new one is returned.
        self.secret_store.set("connected.jira.refresh_token", refresh)
    expires_in = int(payload.get("expires_in") or 0)
    if expires_in:
        obtained_at = int(payload.get("obtained_at") or time.time())
        self.secret_store.set("connected.jira.expires_at", str(obtained_at + expires_in))


def install_jira_refresh_adapter() -> None:
    """Add expiry tracking and Atlassian rotating-refresh-token support."""
    if getattr(ConnectedAppsService, "_jira_refresh_adapter_installed", False):
        return

    previous_token = ConnectedAppsService._token

    def connect(self: ConnectedAppsService) -> None:
        _store_payload(self, connect_jira())

    def token(self: ConnectedAppsService, provider: str) -> str:
        if provider != "jira":
            return previous_token(self, provider)

        access_token = self.secret_store.get("connected.jira.token") or ""
        if not access_token:
            raise RuntimeError("Jira is not connected")

        refresh_token = self.secret_store.get("connected.jira.refresh_token") or ""
        expires_raw = self.secret_store.get("connected.jira.expires_at") or "0"
        try:
            expires_at = int(expires_raw)
        except ValueError:
            expires_at = 0

        if expires_at and time.time() < expires_at - 120:
            return access_token
        if not refresh_token:
            return access_token

        # Existing Jira connections created before expiry tracking are refreshed
        # once on first use. This establishes a known expiry and safely rotates
        # the provider refresh token.
        payload = _refresh_jira_payload(refresh_token)
        _store_payload(self, payload)
        return str(payload.get("access_token") or access_token)

    ConnectedAppsService.connect_jira_oauth = connect  # type: ignore[attr-defined]
    ConnectedAppsService._token = token  # type: ignore[method-assign]
    ConnectedAppsService._jira_refresh_adapter_installed = True  # type: ignore[attr-defined]
