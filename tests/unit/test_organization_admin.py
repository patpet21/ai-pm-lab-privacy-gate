from __future__ import annotations

from dataclasses import dataclass

from ai_pm_lab_privacy_gate.ui.organization_admin import (
    set_device_status,
    set_member_role,
    set_member_status,
)


@dataclass
class Session:
    access_token: str = "token"


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, dict[str, object]]] = []

    def _request(self, method, path, session, *, json=None, **_kwargs):
        self.calls.append((method, path, session, dict(json or {})))
        return None


def test_set_member_role_uses_admin_rpc() -> None:
    client = FakeClient()
    session = Session()

    set_member_role(client, session, "org-1", "user-1", "manager")

    assert client.calls == [
        (
            "POST",
            "/rest/v1/rpc/privacy_gate_set_member_role",
            session,
            {
                "p_organization_id": "org-1",
                "p_user_id": "user-1",
                "p_role": "manager",
            },
        )
    ]


def test_set_member_status_uses_admin_rpc() -> None:
    client = FakeClient()
    session = Session()

    set_member_status(client, session, "org-1", "user-1", "disabled")

    assert client.calls[0][1] == "/rest/v1/rpc/privacy_gate_set_member_status"
    assert client.calls[0][3]["p_status"] == "disabled"


def test_set_device_status_uses_installation_hash() -> None:
    client = FakeClient()
    session = Session()

    set_device_status(client, session, "org-1", "hash-1", "revoked")

    assert client.calls[0][1] == "/rest/v1/rpc/privacy_gate_set_device_status"
    assert client.calls[0][3] == {
        "p_organization_id": "org-1",
        "p_installation_hash": "hash-1",
        "p_status": "revoked",
    }
