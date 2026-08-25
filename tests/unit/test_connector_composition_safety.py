from ai_pm_lab_privacy_gate.infrastructure.connectors import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.connectors import multi_oauth_adapter
from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectionTestResult, RemoteItem
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore



def _service() -> ConnectedAppsService:
    return ConnectedAppsService(".", secret_store=MemorySecretStore())



def test_final_composition_keeps_gmail_connection_test(monkeypatch):
    service = _service()

    expected = ConnectionTestResult(True, "gmail", "second@example.com", "Gmail works")
    monkeypatch.setattr(
        multi_oauth_adapter,
        "_test_connection",
        lambda _service, provider: expected if provider == "gmail" else None,
    )

    assert service.test_connection("gmail") == expected



def test_final_composition_keeps_gmail_root_listing(monkeypatch):
    service = _service()
    expected = (RemoteItem("gmail", "m1", "Hello", kind="email"),)

    monkeypatch.setattr(
        multi_oauth_adapter,
        "_list_root_items",
        lambda _service, provider, limit=30: expected if provider == "gmail" else (),
    )

    assert service.list_root_items("gmail", 30) == expected
