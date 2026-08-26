from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from .multi_account_registry import MULTI_ACCOUNT_PROVIDERS, MultiAccountRegistry
from .service import ConnectedAppsService


# Values that may legitimately be omitted by a provider when the same account is
# authorized again. They may be restored only when the provider-side identity
# resolves to the exact same PrivacyGate account id.
_SAME_ACCOUNT_PRESERVE_SUFFIXES = (
    "refresh_token",
    "client_id",
    "key",
    "workspace_id",
    "workspace_name",
    "workspace_icon",
    "bot_id",
    "owner",
)


def _registry(service: ConnectedAppsService) -> MultiAccountRegistry:
    registry = getattr(service, "_multi_account_registry", None)
    if registry is None:
        registry = MultiAccountRegistry(service.secret_store)
        service._multi_account_registry = registry
    return registry


def _isolated_connect(provider: str, original: Callable[..., Any]) -> Callable[..., Any]:
    """Prevent the active account compatibility alias leaking into a new OAuth result.

    The existing connector adapters still read/write ``connected.<provider>.*``.
    Multi-account stores each account separately and uses those keys only as the
    active compatibility alias. Before a new authorization starts, clear that
    alias so a provider that omits (for example) a refresh token cannot inherit
    the previous account's credential.

    A failed authorization restores the previous alias. If the user reconnects
    the exact same provider identity, selected long-lived values that the provider
    did not re-issue are restored for that same account only.
    """

    @wraps(original)
    def connect(self: ConnectedAppsService, *args, **kwargs):
        registry = _registry(self)
        registry.migrate_legacy(provider)
        previous_active = registry.active_account_id(provider)
        previous_snapshot = registry.snapshot_legacy(provider)

        # App-level OAuth configuration (for example oauth.google.*) is stored
        # outside this provider alias and intentionally survives this reset.
        registry.clear_legacy(provider)
        try:
            result = original(self, *args, **kwargs)
        except Exception:
            registry.restore_legacy(provider, previous_snapshot)
            raise

        current_active = registry.active_account_id(provider)
        current_token = self.secret_store.get(f"connected.{provider}.token") or ""
        captured_token = (
            self.secret_store.get(
                f"connected.{provider}.account.{current_active}.token"
            )
            or ""
        )
        # An unchanged active id is not sufficient proof that the provider
        # re-authorized the same identity: before identity discovery it still
        # points at the old account. Preserve omitted long-lived values only
        # after the connector captured this exact access token into that account.
        same_account_captured = bool(
            previous_active
            and current_active == previous_active
            and current_token
            and captured_token == current_token
        )
        if same_account_captured:
            for suffix in _SAME_ACCOUNT_PRESERVE_SUFFIXES:
                current_key = f"connected.{provider}.{suffix}"
                if not (self.secret_store.get(current_key) or ""):
                    previous_value = previous_snapshot.get(suffix, "")
                    if previous_value:
                        self.secret_store.set(current_key, previous_value)
            registry.sync_active_from_legacy(provider)

        return result

    return connect


def install_multi_account_safety() -> None:
    """Harden multi-account switching without changing the public connector API."""
    if getattr(ConnectedAppsService, "_multi_account_safety_installed", False):
        return

    # Install after MultiAccountRegistry so these wrappers sit outside the
    # compatibility wrappers and can isolate the alias before OAuth begins.
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
        if provider in MULTI_ACCOUNT_PROVIDERS and callable(method):
            setattr(ConnectedAppsService, method_name, _isolated_connect(provider, method))

    previous_token = ConnectedAppsService._token

    def token(self: ConnectedAppsService, provider: str) -> str:
        if provider != "google_drive":
            return previous_token(self, provider)

        registry = _registry(self)
        registry.ensure_active_alias("google_drive")

        token_value = self.secret_store.get("connected.google_drive.token") or ""
        refresh_token = self.secret_store.get("connected.google_drive.refresh_token") or ""
        expires_raw = self.secret_store.get("connected.google_drive.expires_at") or "0"
        try:
            expires_at = int(expires_raw)
        except ValueError:
            expires_at = 0

        # The older adapter chain can return the access token without reaching
        # Google Drive's proactive refresh path. Force the known-good refresh
        # hook when the selected account is actually expired/near expiry.
        if (
            token_value
            and refresh_token
            and expires_at
            and time.time() >= expires_at - 120
            and callable(getattr(self, "force_google_refresh", None))
        ):
            value = self.force_google_refresh()
            registry.sync_active_from_legacy("google_drive")
            return value

        value = previous_token(self, provider)
        registry.sync_active_from_legacy("google_drive")
        return value

    ConnectedAppsService._token = token  # type: ignore[method-assign]
    ConnectedAppsService._multi_account_safety_installed = True  # type: ignore[attr-defined]
