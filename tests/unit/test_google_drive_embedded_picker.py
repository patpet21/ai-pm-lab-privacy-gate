from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.connectors import google_drive_picker_access
from ai_pm_lab_privacy_gate.infrastructure.connectors.service import ConnectedAppsService
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
from ai_pm_lab_privacy_gate.ui.google_drive_embedded_picker import _picker_html


def test_experiment_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("PRIVACY_GATE_ENABLE_EMBEDDED_DRIVE_PICKER", raising=False)
    assert google_drive_picker_access.embedded_picker_enabled() is False


def test_experiment_can_be_enabled_locally(monkeypatch) -> None:
    monkeypatch.setenv("PRIVACY_GATE_ENABLE_EMBEDDED_DRIVE_PICKER", "1")
    assert google_drive_picker_access.embedded_picker_enabled() is True


def test_picker_uses_official_iframe_contract_and_multiselect() -> None:
    html = _picker_html("secret-token", "browser-key", "123456")
    assert "https://apis.google.com/js/api.js" in html
    assert ".setOrigin(window.location.origin)" in html
    assert "MULTISELECT_ENABLED" in html
    assert ".setMaxItems(20)" in html
    assert ".setSize(1051,650)" in html
    assert "google.picker.PickerBuilder" in html


def test_drive_file_token_is_stored_separately_from_readonly_token(monkeypatch) -> None:
    store = MemorySecretStore()
    store.set("connected.google_drive.token", "readonly-token")
    service = ConnectedAppsService(".", secret_store=store)
    monkeypatch.setattr(service, "active_account_id", lambda _provider: "account-1", raising=False)
    monkeypatch.setattr(service, "list_connected_accounts", lambda _provider: (), raising=False)
    monkeypatch.setattr(service, "google_oauth_client_id", lambda: "123-client", raising=False)
    monkeypatch.setattr(service, "google_oauth_client_secret", lambda: "", raising=False)
    monkeypatch.setattr(
        google_drive_picker_access,
        "authorize_desktop",
        lambda *_args, **_kwargs: {
            "access_token": "drive-file-token",
            "expires_in": 3600,
            "scope": google_drive_picker_access.DRIVE_FILE_SCOPE,
        },
    )

    assert google_drive_picker_access.selected_file_access_token(service) == "drive-file-token"
    assert store.get("connected.google_drive.token") == "readonly-token"
    assert store.get("connected.google_drive.picker.account-1.token") == "drive-file-token"
