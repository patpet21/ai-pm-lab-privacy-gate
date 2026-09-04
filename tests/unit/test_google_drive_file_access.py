from __future__ import annotations

from types import SimpleNamespace

from ai_pm_lab_privacy_gate.infrastructure.connectors import google_drive_file_access as access


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        self.values[key] = str(value)


class _Service:
    def __init__(self) -> None:
        self.secret_store = _Store()
        self.timeout = 15.0

    def active_account_id(self, _provider: str) -> str:
        return "account-a"

    def google_oauth_client_id(self) -> str:
        return "desktop-client"

    def google_oauth_client_secret(self) -> str:
        return "desktop-secret"


def test_desktop_picker_uses_drive_file_only_and_keeps_selected_ids(monkeypatch) -> None:
    service = _Service()
    captured = {}

    def fake_authorize(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return {
            "access_token": "selected-token",
            "refresh_token": "selected-refresh",
            "expires_in": 3600,
            "obtained_at": 100,
            "picked_file_ids": "file-1,file-2",
        }

    monkeypatch.setattr(access, "authorize_desktop", fake_authorize)

    assert access.pick_additional_files(service) == ("file-1", "file-2")
    assert captured["scopes"] == (access.DRIVE_FILE_SCOPE,)
    assert captured["include_granted_scopes"] is False
    assert captured["extra_auth_parameters"] == {
        "prompt": "consent",
        "trigger_onepick": "true",
        "allow_multiple": "true",
    }
    assert access.stored_file_ids(service) == ("file-1", "file-2")
    assert service.secret_store.get("connected.google_drive.drive_file.account-a.token") == "selected-token"


def test_authorized_files_queries_only_ids_previously_selected(monkeypatch) -> None:
    service = _Service()
    service.secret_store.set("connected.google_drive.drive_file.account-a.token", "selected-token")
    service.secret_store.set("connected.google_drive.drive_file.account-a.expires_at", "9999999999")
    service.secret_store.set("connected.google_drive.drive_file.account-a.file_ids", '["file-7"]')
    calls = []

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "file-7",
                "name": "Lease.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-09-04T12:00:00Z",
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response()

    monkeypatch.setattr(access.httpx, "get", fake_get)
    monkeypatch.setattr(access, "google_ssl_context", lambda: SimpleNamespace())

    rows = access.authorized_files(service)

    assert [row.item_id for row in rows] == ["file-7"]
    assert calls[0][0].endswith("/files/file-7")
    assert calls[0][1]["headers"] == {"Authorization": "Bearer selected-token"}
