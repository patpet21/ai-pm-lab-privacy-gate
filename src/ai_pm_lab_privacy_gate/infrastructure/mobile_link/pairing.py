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
_PAIRING_MAX_ATTEMPTS = 5
_MAX_CLIENTS = 12
_CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


@dataclass(frozen=True, slots=True)
class MobilePairingChallenge:
    code: str
    expires_at: float


class MobilePairingRegistry:
    """Issue one-time pairing codes and persist only hashes of mobile bearer tokens."""

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store
        self._lock = threading.RLock()
        self._challenge_code: str | None = None
        self._challenge_expires_at = 0.0
        self._challenge_attempts = 0

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

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
            records.append(
                {
                    "client_id": client_id,
                    "client_name": str(item.get("client_name") or "Mobile device")[:80],
                    "token_hash": token_hash,
                    "paired_at": float(item.get("paired_at") or 0.0),
                }
            )
        return records[-_MAX_CLIENTS:]

    def _save(self, records: list[dict[str, object]]) -> None:
        if not records:
            self.secret_store.delete(MOBILE_LINK_CLIENTS_SECRET)
            return
        self.secret_store.set(
            MOBILE_LINK_CLIENTS_SECRET,
            json.dumps(records[-_MAX_CLIENTS:], separators=(",", ":"), sort_keys=True),
        )

    def create_challenge(self, *, now: float | None = None) -> MobilePairingChallenge:
        timestamp = time.time() if now is None else float(now)
        code = f"{secrets.randbelow(100_000_000):08d}"
        with self._lock:
            self._challenge_code = code
            self._challenge_expires_at = timestamp + _PAIRING_TTL_SECONDS
            self._challenge_attempts = 0
        return MobilePairingChallenge(code=code, expires_at=self._challenge_expires_at)

    def pair(
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
        timestamp = time.time() if now is None else float(now)
        with self._lock:
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

            token = secrets.token_urlsafe(32)
            records = [item for item in self._load() if item["client_id"] != normalized_id]
            records.append(
                {
                    "client_id": normalized_id,
                    "client_name": str(client_name or "Mobile device")[:80],
                    "token_hash": self._token_hash(token),
                    "paired_at": timestamp,
                }
            )
            self._save(records)
            self._challenge_code = None
            self._challenge_expires_at = 0.0
            self._challenge_attempts = 0
            return token

    def validate(self, token: str | None) -> bool:
        if not token:
            return False
        digest = self._token_hash(token)
        with self._lock:
            records = self._load()
        return any(
            isinstance(item.get("token_hash"), str)
            and hmac.compare_digest(digest, str(item["token_hash"]))
            for item in records
        )

    def revoke_client(self, client_id: str) -> bool:
        normalized_id = str(client_id).strip()
        with self._lock:
            records = self._load()
            retained = [item for item in records if item["client_id"] != normalized_id]
            if len(retained) == len(records):
                return False
            self._save(retained)
            return True

    def list_clients(self) -> list[dict[str, object]]:
        """Public device metadata only; never expose credential hashes to UI."""
        with self._lock:
            return [
                {key: item[key] for key in ("client_id", "client_name", "paired_at")}
                for item in self._load()
            ]
