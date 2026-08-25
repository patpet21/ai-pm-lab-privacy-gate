from __future__ import annotations

from .multi_account_registry import MULTI_ACCOUNT_PROVIDERS
from .service import ConnectedAppsService


def install_multi_account_label_refresh() -> None:
    """Refresh each account token before resolving its display identity.

    Migrated connections can carry an expired access token even though they also
    have a valid refresh token. The registry intentionally resolves a freshly
    connected account from the raw compatibility alias, so it cannot refresh in
    that code path without risking overwriting the new OAuth result. This small
    post-registry adapter only affects explicit label refreshes from the account
    manager, where activation is already deliberate and safe.
    """
    if getattr(ConnectedAppsService, "_multi_account_label_refresh_installed", False):
        return

    previous = getattr(ConnectedAppsService, "refresh_account_labels", None)
    if not callable(previous):
        return

    def refresh_account_labels(self: ConnectedAppsService, provider: str):
        if provider not in MULTI_ACCOUNT_PROVIDERS:
            return previous(self, provider)

        try:
            records = tuple(self.list_connected_accounts(provider))
            original_active = self.active_account_id(provider)
            for record in records:
                try:
                    self.activate_account(provider, record.account_id)
                    # Goes through the provider's normal refresh logic and the
                    # registry's alias sync, updating only this account.
                    self._token(provider)
                except Exception:
                    continue
            if original_active:
                try:
                    self.activate_account(provider, original_active)
                except Exception:
                    pass
        except Exception:
            pass

        return previous(self, provider)

    ConnectedAppsService.refresh_account_labels = refresh_account_labels  # type: ignore[attr-defined]
    ConnectedAppsService._multi_account_label_refresh_installed = True  # type: ignore[attr-defined]
