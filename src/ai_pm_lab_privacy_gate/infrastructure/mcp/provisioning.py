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
        if not self.oauth_issuer.startswith("https://"):
            raise ValueError("OAuth issuer must use HTTPS")
        if not self.oauth_jwks_url.startswith("https://"):
            raise ValueError("OAuth JWKS endpoint must use HTTPS")


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
        )
        configuration.validate()
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

