from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore


TUNNEL_TOKEN_SECRET = "mcp.production_tunnel_token"
HOSTNAME_PATTERN = re.compile(r"mcp-pg-[a-z0-9-]+\.propertydex\.xyz")
PRODUCTION_OAUTH_ISSUER = "https://miihsvfvklwvwvvgeboh.supabase.co/auth/v1"
PRODUCTION_OAUTH_JWKS_URL = f"{PRODUCTION_OAUTH_ISSUER}/.well-known/jwks.json"


class ProvisioningState(StrEnum):
    NOT_PROVISIONED = "not_provisioned"
    PENDING = "pending"
    READY = "ready"
    REVOKED = "revoked"


@dataclass(frozen=True)
class NamedTunnelConfiguration:
    installation_id: str
    tunnel_id: str
    hostname: str
    oauth_issuer: str
    oauth_jwks_url: str
    credential_version: int
    state: str = ProvisioningState.READY.value

    @property
    def mcp_url(self) -> str:
        return f"https://{self.hostname}/mcp"

    def validate(self) -> None:
        if not HOSTNAME_PATTERN.fullmatch(self.hostname):
            raise ValueError("Provisioning returned an unexpected production hostname")
        if self.oauth_issuer != PRODUCTION_OAUTH_ISSUER:
            raise ValueError("Production MCP must use the approved Supabase OAuth issuer")
        if self.oauth_jwks_url != PRODUCTION_OAUTH_JWKS_URL:
            raise ValueError("Production MCP must use the approved Supabase JWKS endpoint")

    def normalized(self) -> "NamedTunnelConfiguration":
        """Migrate pre-release metadata away from the retired control-plane OAuth issuer."""
        if (
            self.oauth_issuer == PRODUCTION_OAUTH_ISSUER
            and self.oauth_jwks_url == PRODUCTION_OAUTH_JWKS_URL
        ):
            return self
        return NamedTunnelConfiguration(
            installation_id=self.installation_id,
            tunnel_id=self.tunnel_id,
            hostname=self.hostname,
            oauth_issuer=PRODUCTION_OAUTH_ISSUER,
            oauth_jwks_url=PRODUCTION_OAUTH_JWKS_URL,
            credential_version=self.credential_version,
            state=self.state,
        )


class ProvisioningClient(Protocol):
    def enroll(self, installation_id: str, device_public_key: str) -> tuple[NamedTunnelConfiguration, str]: ...

    def rotate_tunnel_token(self, installation_id: str) -> tuple[int, str]: ...

    def revoke(self, installation_id: str) -> None: ...


class ProvisioningStore:
    """Store metadata in JSON and the tunnel runtime credential in the OS secret store."""

    def __init__(self, data_dir: str | Path, secrets: SecretStore) -> None:
        self.path = Path(data_dir) / "production_connection.json"
        self.secrets = secrets

    def load(self) -> NamedTunnelConfiguration | None:
        if not self.path.exists():
            return None
        configuration = NamedTunnelConfiguration(
            **json.loads(self.path.read_text(encoding="utf-8"))
        ).normalized()
        configuration.validate()
        serialized = json.dumps(asdict(configuration), indent=2)
        if self.path.read_text(encoding="utf-8").strip() != serialized.strip():
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(serialized, encoding="utf-8")
            temporary.replace(self.path)
        return configuration

    def save(self, configuration: NamedTunnelConfiguration, tunnel_token: str) -> None:
        configuration.validate()
        self.secrets.set(TUNNEL_TOKEN_SECRET, tunnel_token)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(configuration), indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def tunnel_token(self) -> str | None:
        return self.secrets.get(TUNNEL_TOKEN_SECRET)

    def clear_runtime_credential(self) -> None:
        self.secrets.delete(TUNNEL_TOKEN_SECRET)

    def remove(self) -> None:
        self.clear_runtime_credential()
        self.path.unlink(missing_ok=True)
