from __future__ import annotations

from types import SimpleNamespace

from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.mcp.production_guard import (
    PRODUCTION_MCP_LOOPBACK_PORT,
    install_production_mcp_port_guard,
)
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.infrastructure.mcp.tunnels import NamedTunnelProvider


class _Configuration:
    hostname = "mcp.example.test"
    oauth_issuer = "https://issuer.example.test"
    oauth_jwks_url = "https://issuer.example.test/jwks"

    def validate(self) -> None:
        return None


class _ProvisioningStore:
    def load(self):
        return _Configuration()


class _PreferencesThatMustNotBeRead:
    def load(self):
        raise AssertionError("Production Named Tunnel must not read general MCP port preferences")


def test_production_named_tunnel_uses_fixed_loopback_origin() -> None:
    install_production_mcp_port_guard()

    manager = RemoteMcpManager.__new__(RemoteMcpManager)
    manager.provisioning_store = _ProvisioningStore()
    manager.preferences = _PreferencesThatMustNotBeRead()
    manager.identity_store = SimpleNamespace(
        secrets=SimpleNamespace(get=lambda _name: "test-user-id")
    )
    manager._log_handle = None

    port, path, provider, auth_args = manager._runtime(ConnectionMode.PROD_NAMED)

    assert port == PRODUCTION_MCP_LOOPBACK_PORT == 8766
    assert path == "/mcp"
    assert isinstance(provider, NamedTunnelProvider)
    assert "--expected-subject" in auth_args
    assert "test-user-id" in auth_args
