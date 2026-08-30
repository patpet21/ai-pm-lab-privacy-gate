from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore


BROWSER_PAIRING_SECRET = "browser-pairing-registry-v1"
_PAIRING_TTL_SECONDS = 300
_PAIRING_MAX_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class BrowserPairingChallenge:
    code: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class BrowserPairingStatus:
    paired_count: int
    origins: tuple[str, ...]


class BrowserPairingRegistry:
    """Issue and validate scoped browser credentials without exposing the main API token."""

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store
        self._lock = threading.RLock()
        self._challenge_code: str | None = None
        self._challenge_expires_at = 0.0
        self._challenge_attempts = 0

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict[str, object]]:
        raw = self.secret_store.get(BROWSER_PAIRING_SECRET)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        records: dict[str, dict[str, object]] = {}
        for origin, record in parsed.items():
            if isinstance(origin, str) and isinstance(record, dict):
                records[origin] = dict(record)
        return records

    def _save(self, records: dict[str, dict[str, object]]) -> None:
        if not records:
            self.secret_store.delete(BROWSER_PAIRING_SECRET)
            return
        self.secret_store.set(
            BROWSER_PAIRING_SECRET,
            json.dumps(records, separators=(",", ":"), sort_keys=True),
        )

    def create_challenge(self, *, now: float | None = None) -> BrowserPairingChallenge:
        timestamp = time.time() if now is None else float(now)
        code = f"{secrets.randbelow(100_000_000):08d}"
        with self._lock:
            self._challenge_code = code
            self._challenge_expires_at = timestamp + _PAIRING_TTL_SECONDS
            self._challenge_attempts = 0
        return BrowserPairingChallenge(code=code, expires_at=timestamp + _PAIRING_TTL_SECONDS)

    def pair(
        self,
        origin: str,
        code: str,
        *,
        client_name: str = "Chromium",
        now: float | None = None,
    ) -> str:
        normalized_origin = origin.rstrip("/")
        if not normalized_origin.startswith("chrome-extension://"):
            raise ValueError("browser extension origin required")
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

            browser_token = secrets.token_urlsafe(32)
            records = self._load()
            records[normalized_origin] = {
                "token_hash": self._token_hash(browser_token),
                "client_name": str(client_name or "Chromium")[:80],
                "paired_at": timestamp,
            }
            self._save(records)
            self._challenge_code = None
            self._challenge_expires_at = 0.0
            self._challenge_attempts = 0
            return browser_token

    def validate(self, origin: str, token: str | None) -> bool:
        if not token:
            return False
        normalized_origin = origin.rstrip("/")
        if not normalized_origin.startswith("chrome-extension://"):
            return False
        with self._lock:
            record = self._load().get(normalized_origin)
        if not record:
            return False
        expected = record.get("token_hash")
        if not isinstance(expected, str):
            return False
        return hmac.compare_digest(self._token_hash(token), expected)

    def status(self) -> BrowserPairingStatus:
        with self._lock:
            origins = tuple(sorted(self._load()))
        return BrowserPairingStatus(paired_count=len(origins), origins=origins)

    def revoke(self, origin: str | None = None) -> None:
        with self._lock:
            if origin is None:
                self._save({})
                return
            records = self._load()
            records.pop(origin.rstrip("/"), None)
            self._save(records)
