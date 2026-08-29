from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.auth.supabase_account import (
    SUPABASE_TOKEN_AUDIENCE,
    USER_ID_SECRET,
)
from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.mcp.remote import RemoteMcpManager
from ai_pm_lab_privacy_gate.infrastructure.mcp.tunnels import NamedTunnelProvider


PRODUCTION_MCP_LOOPBACK_PORT = 8766


def install_production_mcp_port_guard() -> None:
    """Keep the stable production MCP origin independent from UI port preferences.

    The provisioned named Cloudflare tunnel is configured for loopback port 8766.
    Development quick tunnels may still use the existing configurable/automatic port
    path, but production must never read ``manual_port`` from general Settings.
    """
    if bool(getattr(RemoteMcpManager, "_privacygate_production_port_guard", False)):
        return

    original_runtime = RemoteMcpManager._runtime

    def guarded_runtime(self, mode: ConnectionMode):
        if mode is not ConnectionMode.PROD_NAMED:
            return original_runtime(self, mode)

        configuration = self.provisioning_store.load()
        if configuration is None:
            raise RuntimeError("This installation has not been provisioned for a stable connection.")
        configuration.validate()
        account_user_id = self.identity_store.secrets.get(USER_ID_SECRET)
        if not account_user_id:
            raise RuntimeError("Sign in to your Privacy Gate account before starting remote MCP.")

        auth_args = [
            "--auth-mode",
            "jwt",
            "--resource",
            f"https://{configuration.hostname}/mcp",
            "--issuer",
            configuration.oauth_issuer,
            "--jwks-url",
            configuration.oauth_jwks_url,
            "--token-audience",
            SUPABASE_TOKEN_AUDIENCE,
            "--expected-subject",
            account_user_id,
        ]
        return (
            PRODUCTION_MCP_LOOPBACK_PORT,
            "/mcp",
            NamedTunnelProvider(configuration, self.provisioning_store, self._log_handle),
            auth_args,
        )

    RemoteMcpManager._runtime = guarded_runtime
    RemoteMcpManager._privacygate_production_port_guard = True
