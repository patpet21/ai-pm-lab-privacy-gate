from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.connectors import google_oauth


def test_production_google_client_id_is_available_without_environment(monkeypatch) -> None:
    monkeypatch.delenv("PRIVACY_GATE_GOOGLE_CLIENT_ID", raising=False)

    assert google_oauth.configured_client_id() == (
        "1072973463893-ur5674ii2n1m5jab4tsa1mguaggijfpk.apps.googleusercontent.com"
    )


def test_google_client_id_environment_override_still_wins(monkeypatch) -> None:
    monkeypatch.setenv("PRIVACY_GATE_GOOGLE_CLIENT_ID", "override-client")

    assert google_oauth.configured_client_id() == "override-client"


def test_google_client_secret_is_not_embedded(monkeypatch) -> None:
    monkeypatch.delenv("PRIVACY_GATE_GOOGLE_CLIENT_SECRET", raising=False)

    assert google_oauth.configured_client_secret() == ""


def test_default_google_drive_scope_is_selected_files_only() -> None:
    assert google_oauth.DRIVE_SCOPES == (
        "https://www.googleapis.com/auth/drive.file",
    )
