from __future__ import annotations

import json
import secrets
import threading
import time

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore

MOBILE_LIBRARY_GRANTS_SECRET = "mobile-library-grants-v1"
_MAX_GRANTS = 500


class MobileLibraryGrantRegistry:
    """Persist explicit per-device grants for protected Library items only.

    Pairing never implies Library access.  A grant binds one protected document to
    one already-paired client.  The grant contains identifiers and audit metadata
    only; protected content remains in protected_library.db and restore mappings are
    never copied into this registry.
    """

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, object]]:
        raw = self.secret_store.get(MOBILE_LIBRARY_GRANTS_SECRET)
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        grants: list[dict[str, object]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            grant_id = item.get("grant_id")
            client_id = item.get("client_id")
            document_id = item.get("document_id")
            if not all(isinstance(value, str) and value for value in (grant_id, client_id, document_id)):
                continue
            grants.append(
                {
                    "grant_id": grant_id,
                    "client_id": client_id,
                    "document_id": document_id,
                    "mode": "protected_copy",
                    "created_at": float(item.get("created_at") or 0.0),
                }
            )
        return grants[-_MAX_GRANTS:]

    def _save(self, grants: list[dict[str, object]]) -> None:
        if not grants:
            self.secret_store.delete(MOBILE_LIBRARY_GRANTS_SECRET)
            return
        self.secret_store.set(
            MOBILE_LIBRARY_GRANTS_SECRET,
            json.dumps(grants[-_MAX_GRANTS:], separators=(",", ":"), sort_keys=True),
        )

    def grant_protected_copy(self, *, client_id: str, document_id: str) -> dict[str, object]:
        client_id = str(client_id).strip()
        document_id = str(document_id).strip()
        if not client_id or not document_id:
            raise ValueError("client_id and document_id are required")
        timestamp = time.time()
        with self._lock:
            grants = [
                item
                for item in self._load()
                if not (
                    item["client_id"] == client_id
                    and item["document_id"] == document_id
                    and item["mode"] == "protected_copy"
                )
            ]
            record: dict[str, object] = {
                "grant_id": secrets.token_urlsafe(18),
                "client_id": client_id,
                "document_id": document_id,
                "mode": "protected_copy",
                "created_at": timestamp,
            }
            grants.append(record)
            self._save(grants)
            return dict(record)

    def list_for_client(self, client_id: str) -> list[dict[str, object]]:
        normalized = str(client_id).strip()
        with self._lock:
            return [dict(item) for item in self._load() if item["client_id"] == normalized]

    def get_for_client(self, client_id: str, grant_id: str) -> dict[str, object] | None:
        normalized_client = str(client_id).strip()
        normalized_grant = str(grant_id).strip()
        with self._lock:
            for item in self._load():
                if item["client_id"] == normalized_client and item["grant_id"] == normalized_grant:
                    return dict(item)
        return None

    def revoke(self, grant_id: str) -> bool:
        normalized = str(grant_id).strip()
        with self._lock:
            grants = self._load()
            retained = [item for item in grants if item["grant_id"] != normalized]
            if len(retained) == len(grants):
                return False
            self._save(retained)
            return True

    def revoke_client(self, client_id: str) -> int:
        normalized = str(client_id).strip()
        with self._lock:
            grants = self._load()
            retained = [item for item in grants if item["client_id"] != normalized]
            removed = len(grants) - len(retained)
            if removed:
                self._save(retained)
            return removed
