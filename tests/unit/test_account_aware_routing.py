from ai_pm_lab_privacy_gate.infrastructure.connectors.multi_account_registry import MultiAccountRegistry
from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.ui import account_aware_routing


def _service_with_accounts(provider: str, identities: tuple[str, ...]):
    store = MemorySecretStore()
    service = ConnectedAppsService(".", secret_store=store)
    registry = MultiAccountRegistry(store)
    ids = []
    for index, identity in enumerate(identities, start=1):
        store.set(f"connected.{provider}.token", f"token-{index}")
        ids.append(registry.capture_legacy(provider, identity=identity, label=identity))
    return service, registry, ids


def test_single_account_is_activated_without_prompt(monkeypatch):
    service, registry, ids = _service_with_accounts("gmail", ("one@example.com",))

    def should_not_prompt(*_args, **_kwargs):
        raise AssertionError("single account should not show an account picker")

    monkeypatch.setattr(account_aware_routing.QInputDialog, "getItem", should_not_prompt)

    assert account_aware_routing.choose_provider_account(None, service, "gmail", "Gmail") is True
    assert registry.active_account_id("gmail") == ids[0]


def test_multiple_accounts_activate_exact_user_selection(monkeypatch):
    service, registry, ids = _service_with_accounts(
        "gmail",
        ("one@example.com", "two@example.com", "three@example.com"),
    )
    registry.activate("gmail", ids[0], make_default=True)

    def choose_third(_parent, _title, _label, items, _current, _editable):
        assert len(items) == 3
        return items[2], True

    monkeypatch.setattr(account_aware_routing.QInputDialog, "getItem", choose_third)

    assert account_aware_routing.choose_provider_account(None, service, "gmail", "Gmail") is True
    assert registry.active_account_id("gmail") == ids[2]
    assert registry.default_account_id("gmail") == ids[0]


def test_cancel_keeps_current_account(monkeypatch):
    service, registry, ids = _service_with_accounts("asana", ("user-1", "user-2"))
    registry.activate("asana", ids[0])

    monkeypatch.setattr(
        account_aware_routing.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("", False),
    )

    assert account_aware_routing.choose_provider_account(None, service, "asana", "Asana") is False
    assert registry.active_account_id("asana") == ids[0]
