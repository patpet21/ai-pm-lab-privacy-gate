from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ai_pm_lab_privacy_gate.domain.plans import Capability, PlanCode, normalize_plan, supports

from .multi_account_registry import MULTI_ACCOUNT_PROVIDERS
from .service import ConnectedAppsService


def _plan(self: ConnectedAppsService) -> PlanCode:
    resolver = getattr(self, "_privacygate_plan_resolver", None)
    if callable(resolver):
        try:
            return normalize_plan(resolver())
        except Exception:
            return PlanCode.BASIC
    return normalize_plan(getattr(self, "_privacygate_entitlement_plan", PlanCode.BASIC))


def _require_additional_account(self: ConnectedAppsService, provider: str) -> None:
    if provider not in MULTI_ACCOUNT_PROVIDERS:
        return
    try:
        count = int(self.account_count(provider))
    except Exception:
        count = 1 if self.is_connected(provider) else 0
    if count >= 1 and not supports(_plan(self), Capability.MULTI_ACCOUNT):
        raise PermissionError(
            f"Adding another {self.provider_name(provider)} account requires PrivacyGate Pro or a Business workspace."
        )


def install_multi_account_entitlement() -> None:
    """Gate second+ connector accounts in the service layer, not only the UI.

    A Basic user can connect one account and can continue using/disconnecting it.
    Pro/Business/Enterprise can add and switch between additional accounts. The
    plan is resolved at call time so switching Personal/company workspace changes
    access immediately. A downgrade never deletes accounts; it simply prevents
    switching to another stored account until an eligible plan is active again.
    """
    if getattr(ConnectedAppsService, "_multi_account_entitlement_installed", False):
        return

    def set_plan_resolver(self: ConnectedAppsService, resolver: Callable[[], object] | None) -> None:
        self._privacygate_plan_resolver = resolver

    previous_save = ConnectedAppsService.save_credentials
    previous_activate = ConnectedAppsService.activate_account

    def save_credentials(self: ConnectedAppsService, provider: str, *, token: str = "", api_key: str = "") -> None:
        provider = provider.strip().lower()
        before = tuple(self.list_connected_accounts(provider)) if provider in MULTI_ACCOUNT_PROVIDERS else ()
        previous_active = next((item.account_id for item in before if item.is_active), "")
        previous_save(self, provider, token=token, api_key=api_key)
        if provider not in MULTI_ACCOUNT_PROVIDERS or supports(_plan(self), Capability.MULTI_ACCOUNT):
            return
        after = tuple(self.list_connected_accounts(provider))
        before_ids = {item.account_id for item in before}
        new_ids = [item.account_id for item in after if item.account_id not in before_ids]
        if before and new_ids:
            for account_id in new_ids:
                try:
                    self.disconnect_account(provider, account_id)
                except Exception:
                    pass
            if previous_active:
                try:
                    previous_activate(self, provider, previous_active)
                except Exception:
                    pass
            raise PermissionError(
                f"Adding another {self.provider_name(provider)} account requires PrivacyGate Pro or a Business workspace."
            )

    def activate_account(
        self: ConnectedAppsService,
        provider: str,
        account_id: str,
        *,
        make_default: bool = False,
    ) -> None:
        provider = provider.strip().lower()
        if provider in MULTI_ACCOUNT_PROVIDERS and not supports(_plan(self), Capability.MULTI_ACCOUNT):
            try:
                count = int(self.account_count(provider))
                current = str(self.active_account_id(provider) or "")
            except Exception:
                count, current = 0, ""
            if count > 1 and str(account_id) != current:
                raise PermissionError(
                    f"Switching between multiple {self.provider_name(provider)} accounts requires PrivacyGate Pro or a Business workspace."
                )
        previous_activate(self, provider, account_id, make_default=make_default)

    ConnectedAppsService.save_credentials = save_credentials  # type: ignore[method-assign]
    ConnectedAppsService.activate_account = activate_account  # type: ignore[method-assign]
    ConnectedAppsService.set_entitlement_plan_resolver = set_plan_resolver  # type: ignore[attr-defined]

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
        original = getattr(ConnectedAppsService, method_name, None)
        if not callable(original):
            continue

        def make_guarded(original_method: Callable[..., Any], provider_key: str):
            def guarded(self: ConnectedAppsService, *args, **kwargs):
                _require_additional_account(self, provider_key)
                return original_method(self, *args, **kwargs)

            return guarded

        setattr(ConnectedAppsService, method_name, make_guarded(original, provider))

    ConnectedAppsService._multi_account_entitlement_installed = True  # type: ignore[attr-defined]
