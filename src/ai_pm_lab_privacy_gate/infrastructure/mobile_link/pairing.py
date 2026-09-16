from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore

MOBILE_LINK_CLIENTS_SECRET = "mobile-link-clients-v1"
_PAIRING_TTL_SECONDS = 300
_PAIRING_APPROVAL_TTL_SECONDS = 300
_PAIRING_RESULT_TTL_SECONDS = 120
_PAIRING_MAX_ATTEMPTS = 5
_MAX_CLIENTS = 12
_CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{24,128}$")
_REMOTE_VALUE = re.compile(r"^[A-Za-z0-9_-]{20,256}$")


@dataclass(frozen=True, slots=True)
class MobilePairingChallenge:
    code: str
    expires_at: float


class MobilePairingRegistry:
    """Own trusted mobile credentials and per-device remote E2E material.

    The normal Mobile bearer credential is persisted only as a hash. Remote relay
    room credentials and the independent E2E secret are stored inside SecretStore,
    protected by the current-user OS secret boundary. They are never exposed by
    list_clients() and never leave Desktop except through an authenticated local
    pairing/status response or inside the already-established E2E channel.
    """

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store
        self._lock = threading.RLock()
        self._challenge_code: str | None = None
        self._challenge_expires_at = 0.0
        self._challenge_attempts = 0
        self._pending: dict[str, dict[str, object]] = {}

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _client_name(value: object) -> str:
        name = str(value or "").strip()
        if not name:
            raise ValueError("device name cannot be empty")
        if len(name) > 80:
            raise ValueError("device name cannot exceed 80 characters")
        return name

    @staticmethod
    def _new_remote_material() -> dict[str, str]:
        return {
            "relay_room_id": secrets.token_urlsafe(24),
            "relay_token": secrets.token_urlsafe(32),
            "remote_secret": secrets.token_urlsafe(32),
        }

    @staticmethod
    def _valid_remote_material(item: dict[str, object]) -> bool:
        return all(
            isinstance(item.get(key), str) and _REMOTE_VALUE.fullmatch(str(item[key]))
            for key in ("relay_room_id", "relay_token", "remote_secret")
        )

    def _load(self) -> list[dict[str, object]]:
        raw = self.secret_store.get(MOBILE_LINK_CLIENTS_SECRET)
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        records: list[dict[str, object]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            client_id = item.get("client_id")
            token_hash = item.get("token_hash")
            if not isinstance(client_id, str) or not _CLIENT_ID.fullmatch(client_id):
                continue
            if not isinstance(token_hash, str) or not token_hash:
                continue
            record: dict[str, object] = {
                "client_id": client_id,
                "client_name": str(item.get("client_name") or "Mobile device")[:80],
                "token_hash": token_hash,
                "paired_at": float(item.get("paired_at") or 0.0),
            }
            if self._valid_remote_material(item):
                record.update(
                    {
                        "relay_room_id": str(item["relay_room_id"]),
                        "relay_token": str(item["relay_token"]),
                        "remote_secret": str(item["remote_secret"]),
                    }
                )
            records.append(record)
        return records[-_MAX_CLIENTS:]

    def _save(self, records: list[dict[str, object]]) -> None:
        if not records:
            self.secret_store.delete(MOBILE_LINK_CLIENTS_SECRET)
            return
        self.secret_store.set(
            MOBILE_LINK_CLIENTS_SECRET,
            json.dumps(records[-_MAX_CLIENTS:], separators=(",", ":"), sort_keys=True),
        )

    def _cleanup_pending(self, now: float) -> None:
        expired = [
            request_id
            for request_id, item in self._pending.items()
            if float(item.get("expires_at") or 0.0) <= now
        ]
        for request_id in expired:
            self._pending.pop(request_id, None)

    def create_challenge(self, *, now: float | None = None) -> MobilePairingChallenge:
        timestamp = time.time() if now is None else float(now)
        code = f"{secrets.randbelow(100_000_000):08d}"
        with self._lock:
            self._challenge_code = code
            self._challenge_expires_at = timestamp + _PAIRING_TTL_SECONDS
            self._challenge_attempts = 0
            self._cleanup_pending(timestamp)
        return MobilePairingChallenge(code=code, expires_at=self._challenge_expires_at)

    def request_pairing(
        self,
        client_id: str,
        code: str,
        *,
        client_name: str = "Mobile device",
        now: float | None = None,
    ) -> str:
        normalized_id = str(client_id).strip()
        if not _CLIENT_ID.fullmatch(normalized_id):
            raise ValueError("client_id is invalid")
        normalized_name = self._client_name(client_name or "Mobile device")
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._cleanup_pending(timestamp)
            expected = self._challenge_code
            if expected is None or timestamp > self._challenge_expires_at:
                self._challenge_code = None
                raise ValueError("pairing code expired or unavailable")
            self._challenge_attempts += 1
            if self._challenge_attempts > _PAIRING_MAX_ATTEMPTS:
                self._challenge_code = None
                raise ValueError("pairing code invalidated after too many attempts")
            if not hmac.compare_digest(str(code).strip(), expected):
                raise ValueError("pairing code is invalid")

            self._challenge_code = None
            self._challenge_expires_at = 0.0
            self._challenge_attempts = 0
            for request_id, item in list(self._pending.items()):
                if item.get("client_id") == normalized_id:
                    self._pending.pop(request_id, None)
            request_id = secrets.token_urlsafe(24)
            self._pending[request_id] = {
                "request_id": request_id,
                "client_id": normalized_id,
                "client_name": normalized_name,
                "requested_at": timestamp,
                "expires_at": timestamp + _PAIRING_APPROVAL_TTL_SECONDS,
                "status": "pending",
                "mobile_token": None,
            }
            return request_id

    def approve_request(self, request_id: str, *, now: float | None = None) -> bool:
        normalized = str(request_id).strip()
        if not _REQUEST_ID.fullmatch(normalized):
            return False
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._cleanup_pending(timestamp)
            item = self._pending.get(normalized)
            if item is None or item.get("status") != "pending":
                return False
            token = secrets.token_urlsafe(32)
            remote = self._new_remote_material()
            records = [
                record
                for record in self._load()
                if record["client_id"] != item["client_id"]
            ]
            records.append(
                {
                    "client_id": item["client_id"],
                    "client_name": item["client_name"],
                    "token_hash": self._token_hash(token),
                    "paired_at": timestamp,
                    **remote,
                }
            )
            self._save(records)
            item["status"] = "approved"
            item["mobile_token"] = token
            item.update(remote)
            item["expires_at"] = timestamp + _PAIRING_RESULT_TTL_SECONDS
            return True

    def deny_request(self, request_id: str, *, now: float | None = None) -> bool:
        normalized = str(request_id).strip()
        if not _REQUEST_ID.fullmatch(normalized):
            return False
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._cleanup_pending(timestamp)
            item = self._pending.get(normalized)
            if item is None or item.get("status") != "pending":
                return False
            item["status"] = "denied"
            item["mobile_token"] = None
            item["expires_at"] = timestamp + _PAIRING_RESULT_TTL_SECONDS
            return True

    def consume_pairing_result(
        self,
        request_id: str,
        *,
        now: float | None = None,
    ) -> dict[str, object]:
        normalized = str(request_id).strip()
        if not _REQUEST_ID.fullmatch(normalized):
            raise ValueError("pairing request id is invalid")
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._cleanup_pending(timestamp)
            item = self._pending.get(normalized)
            if item is None:
                return {"status": "expired"}
            status = str(item.get("status") or "expired")
            if status == "pending":
                return {"status": "pending"}
            if status == "denied":
                self._pending.pop(normalized, None)
                return {"status": "denied"}
            if status == "approved":
                token = item.get("mobile_token")
                self._pending.pop(normalized, None)
                if not isinstance(token, str) or not token:
                    return {"status": "expired"}
                result: dict[str, object] = {"status": "approved", "mobile_token": token}
                if self._valid_remote_material(item):
                    result.update(
                        {
                            "relay_room_id": str(item["relay_room_id"]),
                            "relay_token": str(item["relay_token"]),
                            "remote_secret": str(item["remote_secret"]),
                        }
                    )
                return result
            self._pending.pop(normalized, None)
            return {"status": "expired"}

    def validate(self, token: str | None) -> bool:
        return self.client_for_token(token) is not None

    def client_for_token(self, token: str | None) -> dict[str, object] | None:
        if not token:
            return None
        digest = self._token_hash(token)
        with self._lock:
            for item in self._load():
                if hmac.compare_digest(digest, str(item["token_hash"])):
                    return {
                        key: item[key]
                        for key in ("client_id", "client_name", "paired_at")
                    }
        return None

    def ensure_remote_for_client(self, client_id: str) -> dict[str, str] | None:
        normalized = str(client_id).strip()
        if not _CLIENT_ID.fullmatch(normalized):
            return None
        with self._lock:
            records = self._load()
            for item in records:
                if item["client_id"] != normalized:
                    continue
                if not self._valid_remote_material(item):
                    item.update(self._new_remote_material())
                    self._save(records)
                return {
                    "relay_room_id": str(item["relay_room_id"]),
                    "relay_token": str(item["relay_token"]),
                    "remote_secret": str(item["remote_secret"]),
                }
        return None

    def ensure_remote_for_token(self, token: str | None) -> dict[str, str] | None:
        if not token:
            return None
        digest = self._token_hash(token)
        with self._lock:
            records = self._load()
            for item in records:
                if not hmac.compare_digest(digest, str(item["token_hash"])):
                    continue
                if not self._valid_remote_material(item):
                    item.update(self._new_remote_material())
                    self._save(records)
                return {
                    "relay_room_id": str(item["relay_room_id"]),
                    "relay_token": str(item["relay_token"]),
                    "remote_secret": str(item["remote_secret"]),
                }
        return None

    def remote_for_client(self, client_id: str) -> dict[str, str] | None:
        normalized = str(client_id).strip()
        with self._lock:
            for item in self._load():
                if item["client_id"] == normalized and self._valid_remote_material(item):
                    return {
                        "relay_room_id": str(item["relay_room_id"]),
                        "relay_token": str(item["relay_token"]),
                        "remote_secret": str(item["remote_secret"]),
                    }
        return None

    def rename_client(self, client_id: str, client_name: str) -> bool:
        normalized_id = str(client_id).strip()
        normalized_name = self._client_name(client_name)
        with self._lock:
            records = self._load()
            changed = False
            for item in records:
                if item["client_id"] == normalized_id:
                    item["client_name"] = normalized_name
                    changed = True
                    break
            if changed:
                self._save(records)
            return changed

    def rename_for_token(self, token: str | None, client_name: str) -> dict[str, object] | None:
        if not token:
            return None
        digest = self._token_hash(token)
        normalized_name = self._client_name(client_name)
        with self._lock:
            records = self._load()
            for item in records:
                if hmac.compare_digest(digest, str(item["token_hash"])):
                    item["client_name"] = normalized_name
                    self._save(records)
                    return {
                        key: item[key]
                        for key in ("client_id", "client_name", "paired_at")
                    }
        return None

    def revoke_client(self, client_id: str) -> bool:
        normalized_id = str(client_id).strip()
        with self._lock:
            records = self._load()
            retained = [item for item in records if item["client_id"] != normalized_id]
            if len(retained) == len(records):
                return False
            self._save(retained)
            return True

    def revoke_for_token(self, token: str | None) -> str | None:
        record = self.client_for_token(token)
        if record is None:
            return None
        client_id = str(record["client_id"])
        return client_id if self.revoke_client(client_id) else None

    def list_clients(self) -> list[dict[str, object]]:
        """Public device metadata only; never expose credential or E2E secrets."""
        with self._lock:
            return [
                {
                    "client_id": item["client_id"],
                    "client_name": item["client_name"],
                    "paired_at": item["paired_at"],
                    "remote_ready": self._valid_remote_material(item),
                }
                for item in self._load()
            ]

    def list_pending_requests(self, *, now: float | None = None) -> list[dict[str, object]]:
        timestamp = time.time() if now is None else float(now)
        with self._lock:
            self._cleanup_pending(timestamp)
            return [
                {
                    key: item[key]
                    for key in (
                        "request_id",
                        "client_id",
                        "client_name",
                        "requested_at",
                        "expires_at",
                    )
                }
                for item in self._pending.values()
                if item.get("status") == "pending"
            ]
