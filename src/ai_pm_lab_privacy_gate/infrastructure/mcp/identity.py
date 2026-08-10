from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import default_data_dir


IDENTITY_FILE = "connection_identity.json"
SETTINGS_FILE = "connection_settings.json"


@dataclass(frozen=True)
class ConnectionIdentity:
    customer_id: str
    device_id: str
    access_secret: str
    display_name: str
    created_at: str

    @property
    def mcp_path(self) -> str:
        return f"/{self.access_secret}/mcp"

    @property
    def short_id(self) -> str:
        return self.customer_id[:8].upper()


class ConnectionIdentityStore:
    """Persist an opaque per-install identity outside the application folder."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / IDENTITY_FILE
        self.settings_path = self.data_dir / SETTINGS_FILE

    def load_or_create(self) -> ConnectionIdentity:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ConnectionIdentity(**payload)
        identity = ConnectionIdentity(
            customer_id=uuid.uuid4().hex,
            device_id=uuid.uuid4().hex,
            access_secret=secrets.token_urlsafe(32),
            display_name="This PC",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write(identity)
        return identity

    def rename(self, display_name: str) -> ConnectionIdentity:
        current = self.load_or_create()
        updated = ConnectionIdentity(
            customer_id=current.customer_id,
            device_id=current.device_id,
            access_secret=current.access_secret,
            display_name=display_name.strip() or "This PC",
            created_at=current.created_at,
        )
        self._write(updated)
        return updated

    def rotate_access_secret(self) -> ConnectionIdentity:
        current = self.load_or_create()
        updated = ConnectionIdentity(
            customer_id=current.customer_id,
            device_id=current.device_id,
            access_secret=secrets.token_urlsafe(32),
            display_name=current.display_name,
            created_at=current.created_at,
        )
        self._write(updated)
        return updated

    def is_remote_enabled(self) -> bool:
        if not self.settings_path.exists():
            return False
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return bool(payload.get("remote_enabled", False))
        except (OSError, ValueError, TypeError):
            return False

    def set_remote_enabled(self, enabled: bool) -> None:
        temporary = self.settings_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"remote_enabled": bool(enabled)}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.settings_path)

    def _write(self, identity: ConnectionIdentity) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(identity), indent=2), encoding="utf-8")
        temporary.replace(self.path)
