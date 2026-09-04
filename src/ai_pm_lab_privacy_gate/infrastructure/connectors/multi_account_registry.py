from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .google_tls import google_ssl_context

from .service import ConnectedAppsService


MULTI_ACCOUNT_PROVIDERS = (
    "google_drive",
    "gmail",
    "clickup",
    "asana",
    "trello",
    "notion",
    "monday",
    "jira",
)

_ACCOUNT_SUFFIXES = (
    "token",
    "refresh_token",
    "client_id",
    "expires_at",
    "key",
    "workspace_id",
    "workspace_name",
    "workspace_icon",
    "bot_id",
    "owner",
)

_META_SUFFIXES = ("label", "subtitle", "identity", "created_at")


@dataclass(frozen=True)
class ConnectedAccount:
    account_id: str
    label: str
    subtitle: str = ""
    is_active: bool = False
    is_default: bool = False


class MultiAccountRegistry:
    """Encrypted local account index layered over the existing provider keys.

    Provider adapters can keep using ``connected.<provider>.*`` as a compatibility
    alias for the selected account. Every account is persisted separately under
    ``connected.<provider>.account.<id>.*`` in the existing SecretStore
    (DPAPI on Windows / Keychain on macOS).
    """

    def __init__(self, secret_store) -> None:
        self.store = secret_store

    @staticmethod
    def account_id_for_identity(provider: str, identity: str) -> str:
        seed = f"{provider}:{identity.strip().lower()}".encode("utf-8")
        return hashlib.sha256(seed).hexdigest()[:16]

    def _legacy(self, provider: str, suffix: str) -> str:
        return f"connected.{provider}.{suffix}"

    def _account(self, provider: str, account_id: str, suffix: str) -> str:
        return f"connected.{provider}.account.{account_id}.{suffix}"

    def _index(self, provider: str) -> str:
        return f"connected.{provider}.accounts"

    def _active(self, provider: str) -> str:
        return f"connected.{provider}.active"

    def _default(self, provider: str) -> str:
        return f"connected.{provider}.default"

    def _load_ids(self, provider: str) -> list[str]:
        raw = self.store.get(self._index(provider)) or ""
        if not raw:
            return []
        try:
            values = json.loads(raw)
        except Exception:
            return []
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for value in values:
            account_id = str(value or "").strip()
            if account_id and account_id not in result:
                result.append(account_id)
        return result

    def _save_ids(self, provider: str, ids: list[str]) -> None:
        if ids:
            self.store.set(self._index(provider), json.dumps(ids, separators=(",", ":")))
        else:
            self.store.delete(self._index(provider))

    def _has_legacy(self, provider: str) -> bool:
        token = self.store.get(self._legacy(provider, "token")) or ""
        if provider == "trello":
            return bool(token and (self.store.get(self._legacy(provider, "key")) or ""))
        return bool(token)

    def snapshot_legacy(self, provider: str) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for suffix in _ACCOUNT_SUFFIXES:
            value = self.store.get(self._legacy(provider, suffix))
            if value not in (None, ""):
                snapshot[suffix] = str(value)
        return snapshot

    def restore_legacy(self, provider: str, snapshot: dict[str, str]) -> None:
        self.clear_legacy(provider)
        for suffix, value in snapshot.items():
            self.store.set(self._legacy(provider, suffix), value)

    def clear_legacy(self, provider: str) -> None:
        for suffix in _ACCOUNT_SUFFIXES:
            self.store.delete(self._legacy(provider, suffix))

    def _copy_legacy_to_account(self, provider: str, account_id: str) -> None:
        for suffix in _ACCOUNT_SUFFIXES:
            value = self.store.get(self._legacy(provider, suffix))
            key = self._account(provider, account_id, suffix)
            if value in (None, ""):
                self.store.delete(key)
            else:
                self.store.set(key, str(value))

    def _copy_account_to_legacy(self, provider: str, account_id: str) -> None:
        self.clear_legacy(provider)
        for suffix in _ACCOUNT_SUFFIXES:
            value = self.store.get(self._account(provider, account_id, suffix))
            if value not in (None, ""):
                self.store.set(self._legacy(provider, suffix), str(value))

    def migrate_legacy(self, provider: str) -> None:
        ids = self._load_ids(provider)
        if ids:
            active = self.store.get(self._active(provider)) or ""
            default = self.store.get(self._default(provider)) or ""
            if default not in ids:
                default = ids[0]
                self.store.set(self._default(provider), default)
            if active not in ids:
                active = default
                self.store.set(self._active(provider), active)
            return

        if not self._has_legacy(provider):
            return

        label = (
            self.store.get(self._legacy(provider, "workspace_name"))
            or f"{ConnectedAppsService.provider_name(provider)} account"
        )
        identity_hint = (
            self.store.get(self._legacy(provider, "workspace_id"))
            or self.store.get(self._legacy(provider, "bot_id"))
            or self.store.get(self._legacy(provider, "owner"))
            or "legacy"
        )
        account_id = self.account_id_for_identity(provider, str(identity_hint))
        self._copy_legacy_to_account(provider, account_id)
        self.store.set(self._account(provider, account_id, "label"), str(label))
        self.store.set(self._account(provider, account_id, "identity"), str(identity_hint))
        self.store.set(self._account(provider, account_id, "created_at"), str(int(time.time())))
        self._save_ids(provider, [account_id])
        self.store.set(self._active(provider), account_id)
        self.store.set(self._default(provider), account_id)

    def initialize_provider(self, provider: str) -> None:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        if not ids:
            return
        default = self.store.get(self._default(provider)) or ids[0]
        if default not in ids:
            default = ids[0]
            self.store.set(self._default(provider), default)
        self.activate(provider, default, make_default=False)

    def list_accounts(self, provider: str) -> tuple[ConnectedAccount, ...]:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        active = self.store.get(self._active(provider)) or ""
        default = self.store.get(self._default(provider)) or ""
        result: list[ConnectedAccount] = []
        for account_id in ids:
            label = self.store.get(self._account(provider, account_id, "label")) or (
                f"{ConnectedAppsService.provider_name(provider)} account"
            )
            subtitle = self.store.get(self._account(provider, account_id, "subtitle")) or ""
            result.append(
                ConnectedAccount(
                    account_id=account_id,
                    label=str(label),
                    subtitle=str(subtitle),
                    is_active=account_id == active,
                    is_default=account_id == default,
                )
            )
        return tuple(result)

    def account_count(self, provider: str) -> int:
        self.migrate_legacy(provider)
        return len(self._load_ids(provider))

    def active_account_id(self, provider: str) -> str:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        if not ids:
            return ""
        active = self.store.get(self._active(provider)) or ""
        if active not in ids:
            active = self.store.get(self._default(provider)) or ids[0]
            if active not in ids:
                active = ids[0]
            self.store.set(self._active(provider), active)
        return active

    def default_account_id(self, provider: str) -> str:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        if not ids:
            return ""
        default = self.store.get(self._default(provider)) or ""
        if default not in ids:
            default = ids[0]
            self.store.set(self._default(provider), default)
        return default

    def activate(self, provider: str, account_id: str, *, make_default: bool = False) -> None:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        if account_id not in ids:
            raise ValueError("Connected account was not found")
        self._copy_account_to_legacy(provider, account_id)
        self.store.set(self._active(provider), account_id)
        if make_default:
            self.store.set(self._default(provider), account_id)

    def ensure_active_alias(self, provider: str) -> None:
        account_id = self.active_account_id(provider)
        if account_id:
            self._copy_account_to_legacy(provider, account_id)

    def sync_active_from_legacy(self, provider: str) -> None:
        account_id = self.active_account_id(provider)
        if account_id and self._has_legacy(provider):
            self._copy_legacy_to_account(provider, account_id)

    def capture_legacy(
        self,
        provider: str,
        *,
        identity: str,
        label: str,
        subtitle: str = "",
    ) -> str:
        if not self._has_legacy(provider):
            raise RuntimeError(f"{ConnectedAppsService.provider_name(provider)} did not save connection credentials")

        identity = identity.strip()
        if not identity:
            token = self.store.get(self._legacy(provider, "token")) or ""
            identity = "token-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]
        account_id = self.account_id_for_identity(provider, identity)

        ids = self._load_ids(provider)
        if account_id not in ids:
            ids.append(account_id)
        self._copy_legacy_to_account(provider, account_id)
        self.store.set(
            self._account(provider, account_id, "label"),
            label.strip() or f"{ConnectedAppsService.provider_name(provider)} account",
        )
        if subtitle.strip():
            self.store.set(self._account(provider, account_id, "subtitle"), subtitle.strip())
        else:
            self.store.delete(self._account(provider, account_id, "subtitle"))
        self.store.set(self._account(provider, account_id, "identity"), identity)
        if not self.store.get(self._account(provider, account_id, "created_at")):
            self.store.set(self._account(provider, account_id, "created_at"), str(int(time.time())))
        self._save_ids(provider, ids)
        self.store.set(self._active(provider), account_id)
        if not self.store.get(self._default(provider)):
            self.store.set(self._default(provider), account_id)
        return account_id

    def update_account_metadata(
        self,
        provider: str,
        account_id: str,
        *,
        label: str,
        subtitle: str = "",
        identity: str = "",
    ) -> None:
        if account_id not in self._load_ids(provider):
            return
        if label.strip():
            self.store.set(self._account(provider, account_id, "label"), label.strip())
        if subtitle.strip():
            self.store.set(self._account(provider, account_id, "subtitle"), subtitle.strip())
        else:
            self.store.delete(self._account(provider, account_id, "subtitle"))
        if identity.strip():
            self.store.set(self._account(provider, account_id, "identity"), identity.strip())

    def rekey_account(self, provider: str, old_id: str, new_id: str) -> str:
        ids = self._load_ids(provider)
        if old_id not in ids or not new_id or old_id == new_id:
            return old_id

        for suffix in (*_ACCOUNT_SUFFIXES, *_META_SUFFIXES):
            value = self.store.get(self._account(provider, old_id, suffix))
            if value not in (None, ""):
                self.store.set(self._account(provider, new_id, suffix), str(value))

        new_ids: list[str] = []
        for account_id in ids:
            replacement = new_id if account_id == old_id else account_id
            if replacement not in new_ids:
                new_ids.append(replacement)
        self._save_ids(provider, new_ids)

        if self.store.get(self._active(provider)) == old_id:
            self.store.set(self._active(provider), new_id)
        if self.store.get(self._default(provider)) == old_id:
            self.store.set(self._default(provider), new_id)

        for suffix in (*_ACCOUNT_SUFFIXES, *_META_SUFFIXES):
            self.store.delete(self._account(provider, old_id, suffix))
        return new_id

    def disconnect_account(self, provider: str, account_id: str) -> None:
        self.migrate_legacy(provider)
        ids = self._load_ids(provider)
        if account_id not in ids:
            return

        for suffix in (*_ACCOUNT_SUFFIXES, *_META_SUFFIXES):
            self.store.delete(self._account(provider, account_id, suffix))
        ids = [value for value in ids if value != account_id]
        self._save_ids(provider, ids)

        if not ids:
            self.store.delete(self._active(provider))
            self.store.delete(self._default(provider))
            self.clear_legacy(provider)
            return

        default = self.store.get(self._default(provider)) or ""
        if default not in ids:
            default = ids[0]
            self.store.set(self._default(provider), default)

        active = self.store.get(self._active(provider)) or ""
        if active not in ids:
            active = default
        self.activate(provider, active, make_default=False)

    def disconnect_all(self, provider: str) -> None:
        self.migrate_legacy(provider)
        for account_id in self._load_ids(provider):
            for suffix in (*_ACCOUNT_SUFFIXES, *_META_SUFFIXES):
                self.store.delete(self._account(provider, account_id, suffix))
        self.store.delete(self._index(provider))
        self.store.delete(self._active(provider))
        self.store.delete(self._default(provider))
        self.clear_legacy(provider)


def _registry(self: ConnectedAppsService) -> MultiAccountRegistry:
    registry = getattr(self, "_multi_account_registry", None)
    if registry is None:
        registry = MultiAccountRegistry(self.secret_store)
        self._multi_account_registry = registry
    return registry


def _fallback_identity(self: ConnectedAppsService, provider: str) -> tuple[str, str, str]:
    store = self.secret_store
    workspace_id = store.get(f"connected.{provider}.workspace_id") or ""
    workspace_name = store.get(f"connected.{provider}.workspace_name") or ""
    bot_id = store.get(f"connected.{provider}.bot_id") or ""
    owner = store.get(f"connected.{provider}.owner") or ""
    token = store.get(f"connected.{provider}.token") or ""
    identity = str(workspace_id or bot_id or owner)
    if not identity:
        identity = "token-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]
    label = str(workspace_name or self.provider_name(provider) + " account")
    return identity, label, ""


def _resolve_current_identity(self: ConnectedAppsService, provider: str) -> tuple[str, str, str]:
    """Resolve a stable provider-side identity for the active compatibility alias."""
    try:
        token = self.secret_store.get(f"connected.{provider}.token") or ""
        if not token:
            return _fallback_identity(self, provider)

        if provider == "google_drive":
            response = httpx.get(
                "https://www.googleapis.com/drive/v3/about",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "user(displayName,emailAddress,permissionId)"},
                timeout=self.timeout,
                verify=google_ssl_context(),
            )
            response.raise_for_status()
            user = response.json().get("user") or {}
            identity = str(user.get("emailAddress") or user.get("permissionId") or "")
            label = str(user.get("emailAddress") or user.get("displayName") or "Google Drive account")
            return identity, label, str(user.get("displayName") or "")

        if provider == "gmail":
            response = httpx.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            email = str(response.json().get("emailAddress") or "")
            return email, email or "Gmail account", ""

        if provider == "clickup":
            response = httpx.get(
                "https://api.clickup.com/api/v2/user",
                headers={"Authorization": token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            user = response.json().get("user") or {}
            identity = str(user.get("id") or user.get("email") or user.get("username") or "")
            label = str(user.get("email") or user.get("username") or "ClickUp account")
            return identity, label, str(user.get("username") or "")

        if provider == "asana":
            response = httpx.get(
                "https://app.asana.com/api/1.0/users/me",
                headers={"Authorization": f"Bearer {token}"},
                params={"opt_fields": "name,email"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            user = response.json().get("data") or {}
            identity = str(user.get("gid") or user.get("email") or user.get("name") or "")
            label = str(user.get("email") or user.get("name") or "Asana account")
            return identity, label, str(user.get("name") or "")

        if provider == "trello":
            key = self.secret_store.get("connected.trello.key") or ""
            response = httpx.get(
                "https://api.trello.com/1/members/me",
                params={"key": key, "token": token, "fields": "id,fullName,username"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            user = response.json()
            identity = str(user.get("id") or user.get("username") or "")
            label = str(user.get("username") or user.get("fullName") or "Trello account")
            return identity, label, str(user.get("fullName") or "")

        if provider == "notion":
            response = httpx.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": "2022-06-28",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            user = response.json()
            workspace_id = self.secret_store.get("connected.notion.workspace_id") or ""
            workspace_name = self.secret_store.get("connected.notion.workspace_name") or ""
            user_id = str(user.get("id") or "")
            identity = ":".join(part for part in (str(workspace_id), user_id) if part)
            label = str(workspace_name or user.get("name") or "Notion workspace")
            return identity, label, str(user.get("name") or "")

        if provider == "jira":
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resources = httpx.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers=headers,
                timeout=self.timeout,
            )
            resources.raise_for_status()
            rows = resources.json()
            if rows:
                resource = rows[0]
                cloud_id = str(resource.get("id") or "")
                site = str(resource.get("name") or resource.get("url") or "Jira")
                myself = httpx.get(
                    f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself",
                    headers=headers,
                    timeout=self.timeout,
                )
                myself.raise_for_status()
                user = myself.json()
                account_id = str(user.get("accountId") or user.get("displayName") or "")
                label = str(user.get("displayName") or site)
                return f"{cloud_id}:{account_id}", label, site

        if provider == "monday":
            response = httpx.post(
                "https://api.monday.com/v2",
                headers={"Authorization": token, "Content-Type": "application/json"},
                json={"query": "query { me { id name email } account { id name } }"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("errors"):
                data = payload.get("data") or {}
                user = data.get("me") or {}
                account = data.get("account") or {}
                identity = f"{account.get('id') or ''}:{user.get('id') or ''}".strip(":")
                label = str(user.get("email") or user.get("name") or account.get("name") or "monday.com")
                return identity, label, str(account.get("name") or "")
    except Exception:
        pass

    return _fallback_identity(self, provider)


def install_multi_account_registry() -> None:
    if getattr(ConnectedAppsService, "_multi_account_registry_installed", False):
        return

    previous_init = ConnectedAppsService.__init__
    previous_token = ConnectedAppsService._token
    previous_is_connected = ConnectedAppsService.is_connected
    previous_disconnect = ConnectedAppsService.disconnect
    previous_save_credentials = ConnectedAppsService.save_credentials
    previous_force_google_refresh = getattr(ConnectedAppsService, "force_google_refresh", None)

    connect_methods: dict[str, tuple[str, Callable[..., Any]]] = {}
    for provider, method_name in (
        ("google_drive", "connect_google_oauth"),
        ("gmail", "connect_gmail_oauth"),
        ("clickup", "connect_clickup_oauth"),
        ("asana", "connect_asana_oauth"),
        ("trello", "connect_trello_oauth"),
        ("notion", "connect_notion_oauth"),
        ("monday", "connect_monday_oauth"),
        ("jira", "connect_jira_oauth"),
    ):
        method = getattr(ConnectedAppsService, method_name, None)
        if callable(method):
            connect_methods[provider] = (method_name, method)

    def init(self: ConnectedAppsService, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        registry = _registry(self)
        for provider in MULTI_ACCOUNT_PROVIDERS:
            try:
                registry.initialize_provider(provider)
            except Exception:
                continue

    def is_connected(self: ConnectedAppsService, provider: str) -> bool:
        if provider not in MULTI_ACCOUNT_PROVIDERS:
            return previous_is_connected(self, provider)
        return _registry(self).account_count(provider) > 0

    def token(self: ConnectedAppsService, provider: str) -> str:
        if provider not in MULTI_ACCOUNT_PROVIDERS:
            return previous_token(self, provider)
        registry = _registry(self)
        registry.ensure_active_alias(provider)
        value = previous_token(self, provider)
        registry.sync_active_from_legacy(provider)
        return value

    def disconnect(self: ConnectedAppsService, provider: str) -> None:
        if provider not in MULTI_ACCOUNT_PROVIDERS:
            previous_disconnect(self, provider)
            return
        _registry(self).disconnect_all(provider)

    def save_credentials(self: ConnectedAppsService, provider: str, *, token: str = "", api_key: str = "") -> None:
        previous_save_credentials(self, provider, token=token, api_key=api_key)
        if provider in MULTI_ACCOUNT_PROVIDERS:
            identity, label, subtitle = _resolve_current_identity(self, provider)
            _registry(self).capture_legacy(provider, identity=identity, label=label, subtitle=subtitle)

    def list_connected_accounts(self: ConnectedAppsService, provider: str) -> tuple[ConnectedAccount, ...]:
        return _registry(self).list_accounts(provider)

    def account_count(self: ConnectedAppsService, provider: str) -> int:
        return _registry(self).account_count(provider)

    def active_account_id(self: ConnectedAppsService, provider: str) -> str:
        return _registry(self).active_account_id(provider)

    def activate_account(
        self: ConnectedAppsService,
        provider: str,
        account_id: str,
        *,
        make_default: bool = False,
    ) -> None:
        _registry(self).activate(provider, account_id, make_default=make_default)

    def disconnect_account(self: ConnectedAppsService, provider: str, account_id: str) -> None:
        _registry(self).disconnect_account(provider, account_id)

    def refresh_account_labels(self: ConnectedAppsService, provider: str) -> tuple[ConnectedAccount, ...]:
        registry = _registry(self)
        records = list(registry.list_accounts(provider))
        if not records:
            return ()
        original_active = registry.active_account_id(provider)
        for record in records:
            try:
                registry.activate(provider, record.account_id)
                identity, label, subtitle = _resolve_current_identity(self, provider)
                stable_id = registry.account_id_for_identity(provider, identity) if identity else record.account_id
                current_id = registry.rekey_account(provider, record.account_id, stable_id)
                registry.update_account_metadata(
                    provider,
                    current_id,
                    label=label,
                    subtitle=subtitle,
                    identity=identity,
                )
            except Exception:
                continue
        ids = {record.account_id for record in registry.list_accounts(provider)}
        if original_active in ids:
            registry.activate(provider, original_active)
        else:
            default = registry.default_account_id(provider)
            if default:
                registry.activate(provider, default)
        return registry.list_accounts(provider)

    def make_connect(provider: str, original: Callable[..., Any]) -> Callable[..., Any]:
        def connect(self: ConnectedAppsService, *args, **kwargs):
            registry = _registry(self)
            registry.migrate_legacy(provider)
            previous_snapshot = registry.snapshot_legacy(provider)
            try:
                result = original(self, *args, **kwargs)
            except Exception:
                registry.restore_legacy(provider, previous_snapshot)
                raise
            identity, label, subtitle = _resolve_current_identity(self, provider)
            registry.capture_legacy(provider, identity=identity, label=label, subtitle=subtitle)
            return result

        return connect

    ConnectedAppsService.__init__ = init  # type: ignore[method-assign]
    ConnectedAppsService.is_connected = is_connected  # type: ignore[method-assign]
    ConnectedAppsService._token = token  # type: ignore[method-assign]
    ConnectedAppsService.disconnect = disconnect  # type: ignore[method-assign]
    ConnectedAppsService.save_credentials = save_credentials  # type: ignore[method-assign]
    ConnectedAppsService.list_connected_accounts = list_connected_accounts  # type: ignore[attr-defined]
    ConnectedAppsService.account_count = account_count  # type: ignore[attr-defined]
    ConnectedAppsService.active_account_id = active_account_id  # type: ignore[attr-defined]
    ConnectedAppsService.activate_account = activate_account  # type: ignore[attr-defined]
    ConnectedAppsService.disconnect_account = disconnect_account  # type: ignore[attr-defined]
    ConnectedAppsService.refresh_account_labels = refresh_account_labels  # type: ignore[attr-defined]

    for provider, (method_name, original) in connect_methods.items():
        setattr(ConnectedAppsService, method_name, make_connect(provider, original))

    if callable(previous_force_google_refresh):
        def force_google_refresh(self: ConnectedAppsService) -> str:
            _registry(self).ensure_active_alias("google_drive")
            refreshed = previous_force_google_refresh(self)
            _registry(self).sync_active_from_legacy("google_drive")
            return refreshed

        ConnectedAppsService.force_google_refresh = force_google_refresh  # type: ignore[attr-defined]

    ConnectedAppsService._multi_account_registry_installed = True  # type: ignore[attr-defined]
