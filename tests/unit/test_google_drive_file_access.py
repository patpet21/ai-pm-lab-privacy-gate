from __future__ import annotations

from types import SimpleNamespace

from ai_pm_lab_privacy_gate.infrastructure.connectors import (
    google_drive_file_access as access,
)


class _Store:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        self.values[key] = str(value)

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class _Service:
    def __init__(self) -> None:
        self.secret_store = _Store()
        self.timeout = 15.0

    def active_account_id(self, _provider: str) -> str:
        # This belongs to the independent Full Drive registry. Selected-file
        # tests intentionally keep it different from drive.file account ids.
        return "full-drive-account-a"

    def google_oauth_client_id(self) -> str:
        return "desktop-client"

    def google_oauth_client_secret(self) -> str:
        return "desktop-secret"


def test_desktop_picker_uses_drive_file_only_and_registers_google_identity(
    monkeypatch,
) -> None:
    service = _Service()
    captured = {}

    def fake_authorize(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return {
            "access_token": "selected-token",
            "refresh_token": "selected-refresh",
            "expires_in": 3600,
            "obtained_at": 9_999_999_000,
            "picked_file_ids": "file-1,file-2",
        }

    monkeypatch.setattr(access, "authorize_desktop", fake_authorize)
    monkeypatch.setattr(
        access,
        "_about_user",
        lambda _service, _token: {
            "permissionId": "permission-a",
            "emailAddress": "alice@example.com",
            "displayName": "Alice",
        },
    )

    assert access.pick_additional_files(service) == ("file-1", "file-2")
    assert captured["client_id"] == "desktop-client"
    assert captured["scopes"] == (access.DRIVE_FILE_SCOPE,)
    assert captured["include_granted_scopes"] is False
    assert captured["login_hint"] == ""
    assert captured["extra_auth_parameters"] == {
        "prompt": "select_account consent",
        "trigger_onepick": "true",
        "allow_multiple": "true",
    }

    accounts = access.list_selected_file_accounts(service)
    assert len(accounts) == 1
    assert accounts[0].label == "alice@example.com"
    assert accounts[0].is_active is True
    assert accounts[0].account_id != "full-drive-account-a"
    assert access.stored_file_ids(service) == ("file-1", "file-2")
    assert (
        service.secret_store.get(
            f"connected.google_drive.drive_file.account.{accounts[0].account_id}.token"
        )
        == "selected-token"
    )


def test_active_selected_account_uses_login_hint_without_forcing_account_chooser(
    monkeypatch,
) -> None:
    service = _Service()
    service.secret_store.set(
        "connected.google_drive.drive_file.accounts",
        '["selected-a"]',
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.active",
        "selected-a",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.email",
        "alice@example.com",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.label",
        "alice@example.com",
    )
    captured = {}

    def fake_authorize(_client_id, **kwargs):
        captured.update(kwargs)
        return {
            "access_token": "selected-token",
            "refresh_token": "selected-refresh",
            "expires_in": 3600,
            "obtained_at": 9_999_999_000,
            "picked_file_ids": "file-3",
        }

    monkeypatch.setattr(access, "authorize_desktop", fake_authorize)
    monkeypatch.setattr(
        access,
        "_about_user",
        lambda _service, _token: {
            "permissionId": "permission-a",
            "emailAddress": "alice@example.com",
            "displayName": "Alice",
        },
    )

    access.pick_additional_files(service)

    assert captured["login_hint"] == "alice@example.com"
    assert captured["extra_auth_parameters"]["prompt"] == "consent"
    assert captured["scopes"] == (access.DRIVE_FILE_SCOPE,)
    assert captured["include_granted_scopes"] is False


def test_explicit_change_account_keeps_account_chooser(monkeypatch) -> None:
    service = _Service()
    service.secret_store.set(
        "connected.google_drive.drive_file.accounts",
        '["selected-a"]',
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.active",
        "selected-a",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.email",
        "alice@example.com",
    )
    captured = {}

    def fake_authorize(_client_id, **kwargs):
        captured.update(kwargs)
        return {
            "access_token": "token-b",
            "refresh_token": "refresh-b",
            "expires_in": 3600,
            "obtained_at": 9_999_999_000,
            "picked_file_ids": "b-1",
        }

    monkeypatch.setattr(access, "authorize_desktop", fake_authorize)
    monkeypatch.setattr(
        access,
        "_about_user",
        lambda _service, _token: {
            "permissionId": "permission-b",
            "emailAddress": "bob@example.com",
        },
    )

    access.pick_additional_files(service, choose_account=True)

    assert captured["login_hint"] == ""
    assert captured["extra_auth_parameters"]["prompt"] == "select_account consent"


def test_two_picker_accounts_keep_tokens_and_file_ids_separate(monkeypatch) -> None:
    service = _Service()
    payloads = iter(
        (
            {
                "access_token": "token-a",
                "refresh_token": "refresh-a",
                "expires_in": 3600,
                "obtained_at": 9_999_999_000,
                "picked_file_ids": "a-1,a-2",
            },
            {
                "access_token": "token-b",
                "refresh_token": "refresh-b",
                "expires_in": 3600,
                "obtained_at": 9_999_999_000,
                "picked_file_ids": "b-1",
            },
        )
    )
    users = {
        "token-a": {
            "permissionId": "permission-a",
            "emailAddress": "alice@example.com",
        },
        "token-b": {
            "permissionId": "permission-b",
            "emailAddress": "bob@example.com",
        },
    }

    monkeypatch.setattr(
        access,
        "authorize_desktop",
        lambda _client_id, **_kwargs: next(payloads),
    )
    monkeypatch.setattr(
        access,
        "_about_user",
        lambda _service, token: users[token],
    )

    access.pick_additional_files(service)
    account_a = access.selected_file_active_account(service)
    assert account_a is not None
    assert account_a.label == "alice@example.com"

    access.pick_additional_files(service, choose_account=True)
    account_b = access.selected_file_active_account(service)
    assert account_b is not None
    assert account_b.label == "bob@example.com"
    assert account_b.account_id != account_a.account_id
    assert len(access.list_selected_file_accounts(service)) == 2
    assert access.stored_file_ids(service) == ("b-1",)
    assert access.selected_file_access_token(service) == "token-b"

    access.activate_selected_file_account(service, account_a.account_id)
    assert access.stored_file_ids(service) == ("a-1", "a-2")
    assert access.selected_file_access_token(service) == "token-a"


def test_authorized_files_queries_only_ids_for_active_selected_account(
    monkeypatch,
) -> None:
    service = _Service()
    service.secret_store.set(
        "connected.google_drive.drive_file.accounts",
        '["selected-a","selected-b"]',
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.active",
        "selected-a",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.token",
        "selected-token",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.expires_at",
        "9999999999",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.file_ids",
        '["file-7"]',
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-b.file_ids",
        '["file-99"]',
    )

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
    assert len(calls) == 1
    assert calls[0][0].endswith("/files/file-7")
    assert calls[0][1]["headers"] == {"Authorization": "Bearer selected-token"}


def test_poc_drive_file_keys_migrate_without_reusing_full_drive_account_id() -> None:
    service = _Service()
    service.secret_store.set(
        "connected.google_drive.drive_file.full-drive-account-a.token",
        "legacy-token",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.full-drive-account-a.expires_at",
        "9999999999",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.full-drive-account-a.file_ids",
        '["legacy-file"]',
    )

    accounts = access.list_selected_file_accounts(service)

    assert len(accounts) == 1
    assert accounts[0].account_id != "full-drive-account-a"
    assert accounts[0].account_id.startswith("legacy-")
    assert access.stored_file_ids(service) == ("legacy-file",)
    assert access.selected_file_access_token(service) == "legacy-token"


def test_disconnect_selected_file_account_keeps_other_selected_account() -> None:
    service = _Service()
    service.secret_store.set(
        "connected.google_drive.drive_file.accounts",
        '["selected-a","selected-b"]',
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.active",
        "selected-a",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-a.token",
        "token-a",
    )
    service.secret_store.set(
        "connected.google_drive.drive_file.account.selected-b.token",
        "token-b",
    )

    access.disconnect_selected_file_account(service, "selected-a")

    records = access.list_selected_file_accounts(service)
    assert [record.account_id for record in records] == ["selected-b"]
    assert records[0].is_active is True
    assert service.secret_store.get(
        "connected.google_drive.drive_file.account.selected-a.token"
    ) is None
    assert service.secret_store.get(
        "connected.google_drive.drive_file.account.selected-b.token"
    ) == "token-b"
