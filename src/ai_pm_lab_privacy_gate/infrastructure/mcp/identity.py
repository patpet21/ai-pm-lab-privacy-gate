from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.mcp.modes import ConnectionMode
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import default_data_dir


IDENTITY_FILE = "connection_identity.json"
SETTINGS_FILE = "connection_settings.json"
DEV_ACCESS_SECRET = "mcp.dev_access_secret"


@dataclass(frozen=True)
class ConnectionIdentity:
    installation_id: str
    device_id: str
    display_name: str
    created_at: str
    schema_version: int = 2

    @property
    def customer_id(self) -> str:
        """Compatibility alias for pre-0.4 internal callers."""
        return self.installation_id

    @property
    def short_id(self) -> str:
        return self.installation_id[:8].upper()

    @property
    def hostname_label(self) -> str:
        return f"mcp-pg-{self.installation_id}"


class ConnectionIdentityStore:
    """Persist non-identifying public metadata and keep credentials in the OS vault."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / IDENTITY_FILE
        self.settings_path = self.data_dir / SETTINGS_FILE
        self.secrets = secret_store or platform_secret_store(self.data_dir)

    def load_or_create(self) -> ConnectionIdentity:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if "installation_id" in payload:
                return ConnectionIdentity(**payload)
            return self._migrate_legacy(payload)
        identity = ConnectionIdentity(
            installation_id=secrets.token_hex(16),
            device_id=uuid.uuid4().hex,
            display_name="This PC",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write(identity)
        return identity

    def _migrate_legacy(self, payload: dict[str, object]) -> ConnectionIdentity:
        legacy_secret = str(payload.get("access_secret") or "")
        if legacy_secret and not self.secrets.get(DEV_ACCESS_SECRET):
            self.secrets.set(DEV_ACCESS_SECRET, legacy_secret)
        identity = ConnectionIdentity(
            installation_id=str(payload.get("customer_id") or secrets.token_hex(16)),
            device_id=str(payload.get("device_id") or uuid.uuid4().hex),
            display_name=str(payload.get("display_name") or "This PC"),
            created_at=str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()),
        )
        self._write(identity)
        return identity

    def rename(self, display_name: str) -> ConnectionIdentity:
        current = self.load_or_create()
        updated = ConnectionIdentity(
            installation_id=current.installation_id,
            device_id=current.device_id,
            display_name=display_name.strip() or "This PC",
            created_at=current.created_at,
        )
        self._write(updated)
        return updated

    def dev_access_secret(self) -> str:
        value = self.secrets.get(DEV_ACCESS_SECRET)
        if value:
            return value
        value = secrets.token_urlsafe(32)
        self.secrets.set(DEV_ACCESS_SECRET, value)
        return value

    def dev_mcp_path(self) -> str:
        return f"/{self.dev_access_secret()}/mcp"

    def rotate_access_secret(self) -> ConnectionIdentity:
        self.secrets.set(DEV_ACCESS_SECRET, secrets.token_urlsafe(32))
        return self.load_or_create()

    def settings(self) -> dict[str, object]:
        defaults: dict[str, object] = {
            "remote_enabled": False,
            "connection_mode": ConnectionMode.LOCAL.value,
        }
        if not self.settings_path.exists():
            return defaults
        try:
            stored = json.loads(self.settings_path.read_text(encoding="utf-8"))
            defaults.update(stored)
            if stored.get("remote_enabled") and "connection_mode" not in stored:
                defaults["connection_mode"] = ConnectionMode.DEV_QUICK.value
        except (OSError, ValueError, TypeError):
            pass
        return defaults

    def is_remote_enabled(self) -> bool:
        return bool(self.settings().get("remote_enabled", False))

    def connection_mode(self) -> ConnectionMode:
        raw = str(self.settings().get("connection_mode", ConnectionMode.LOCAL.value))
        try:
            return ConnectionMode(raw)
        except ValueError:
            return ConnectionMode.LOCAL

    def set_connection(self, *, enabled: bool, mode: ConnectionMode) -> None:
        payload = self.settings()
        payload.update({"remote_enabled": bool(enabled), "connection_mode": mode.value})
        self._write_settings(payload)

    def set_remote_enabled(self, enabled: bool) -> None:
        mode = self.connection_mode()
        if enabled and mode is ConnectionMode.LOCAL:
            mode = ConnectionMode.DEV_QUICK
        self.set_connection(enabled=enabled, mode=mode)

    def _write_settings(self, payload: dict[str, object]) -> None:
        temporary = self.settings_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.settings_path)

    def _write(self, identity: ConnectionIdentity) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(identity), indent=2), encoding="utf-8")
        temporary.replace(self.path)
