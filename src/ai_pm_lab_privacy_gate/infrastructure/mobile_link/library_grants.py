from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore

MOBILE_LIBRARY_GRANTS_SECRET = "mobile-library-grants-v1"
_MAX_GRANTS = 500
_ALLOWED_MODES = {"protected_copy", "full_offline_session"}


class MobileLibraryGrantRegistry:
    """Persist explicit credential-scoped Library transfer grants.

    Pairing never implies Library access. A grant binds one document, one trusted
    client credential, and one transfer mode. The registry stores identifiers and
    audit metadata only; document content and restore mappings never live here.

    There is at most one effective grant per client/document pair. A Full offline
    session is an upgrade of Protected copy and supersedes it, preventing duplicate
    entries and accidental downgrade of a restorable mobile copy.
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

        # Collapse any grants created by earlier builds. Prefer Full offline
        # session over Protected copy for the same client/document pair.
        effective: dict[tuple[str, str], dict[str, object]] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            grant_id = item.get("grant_id")
            client_id = item.get("client_id")
            token_hash = item.get("token_hash")
            document_id = item.get("document_id")
            values = (grant_id, client_id, token_hash, document_id)
            if not all(isinstance(value, str) and value for value in values):
                continue
            mode = str(item.get("mode") or "protected_copy")
            if mode not in _ALLOWED_MODES:
                continue
            record: dict[str, object] = {
                "grant_id": grant_id,
                "client_id": client_id,
                "token_hash": token_hash,
                "document_id": document_id,
                "mode": mode,
                "created_at": float(item.get("created_at") or 0.0),
            }
            key = (client_id, document_id)
            current = effective.get(key)
            if current is not None and current["mode"] == "full_offline_session" and mode != "full_offline_session":
                continue
            # Reinsert so the resulting list follows the most recently selected
            # effective grant rather than the first historical occurrence.
            effective.pop(key, None)
            effective[key] = record

        return list(effective.values())[-_MAX_GRANTS:]

    def _save(self, grants: list[dict[str, object]]) -> None:
        if not grants:
            self.secret_store.delete(MOBILE_LIBRARY_GRANTS_SECRET)
            return
        self.secret_store.set(
            MOBILE_LIBRARY_GRANTS_SECRET,
            json.dumps(grants[-_MAX_GRANTS:], separators=(",", ":"), sort_keys=True),
        )

    def grant(
        self,
        *,
        client_id: str,
        token_hash: str,
        document_id: str,
        mode: str,
    ) -> dict[str, object]:
        client_id = str(client_id).strip()
        token_hash = str(token_hash).strip()
        document_id = str(document_id).strip()
        mode = str(mode).strip()
        if mode not in _ALLOWED_MODES:
            raise ValueError("unsupported Library transfer mode")
        if not client_id or not token_hash or not document_id:
            raise ValueError("client_id, token_hash and document_id are required")

        timestamp = time.time()
        with self._lock:
            grants = self._load()
            current = next(
                (
                    item
                    for item in grants
                    if item["client_id"] == client_id
                    and item["document_id"] == document_id
                ),
                None,
            )
            if (
                mode == "protected_copy"
                and current is not None
                and current.get("mode") == "full_offline_session"
            ):
                raise ValueError(
                    "Full offline session is already authorized for this device"
                )

            # Re-authorizing replaces the old grant. Full offline therefore
            # upgrades Protected copy rather than creating a second Mobile item.
            grants = [
                item
                for item in grants
                if not (
                    item["client_id"] == client_id
                    and item["document_id"] == document_id
                )
            ]
            record: dict[str, object] = {
                "grant_id": secrets.token_urlsafe(18),
                "client_id": client_id,
                "token_hash": token_hash,
                "document_id": document_id,
                "mode": mode,
                "created_at": timestamp,
            }
            grants.append(record)
            self._save(grants)
            return dict(record)

    def grant_protected_copy(
        self,
        *,
        client_id: str,
        token_hash: str,
        document_id: str,
    ) -> dict[str, object]:
        return self.grant(
            client_id=client_id,
            token_hash=token_hash,
            document_id=document_id,
            mode="protected_copy",
        )

    def grant_full_offline_session(
        self,
        *,
        client_id: str,
        token_hash: str,
        document_id: str,
    ) -> dict[str, object]:
        return self.grant(
            client_id=client_id,
            token_hash=token_hash,
            document_id=document_id,
            mode="full_offline_session",
        )

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def list_for_token(self, token: str | None) -> list[dict[str, object]]:
        if not token:
            return []
        digest = self._digest(token)
        with self._lock:
            return [
                dict(item)
                for item in self._load()
                if hmac.compare_digest(digest, str(item["token_hash"]))
            ]

    def list_for_client(self, client_id: str) -> list[dict[str, object]]:
        normalized = str(client_id).strip()
        if not normalized:
            return []
        with self._lock:
            return [
                {
                    key: item[key]
                    for key in (
                        "grant_id",
                        "client_id",
                        "document_id",
                        "mode",
                        "created_at",
                    )
                }
                for item in self._load()
                if item["client_id"] == normalized
            ]

    def get_for_token(
        self,
        token: str | None,
        grant_id: str,
    ) -> dict[str, object] | None:
        if not token:
            return None
        digest = self._digest(token)
        normalized_grant = str(grant_id).strip()
        with self._lock:
            for item in self._load():
                if (
                    item["grant_id"] == normalized_grant
                    and hmac.compare_digest(digest, str(item["token_hash"]))
                ):
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
