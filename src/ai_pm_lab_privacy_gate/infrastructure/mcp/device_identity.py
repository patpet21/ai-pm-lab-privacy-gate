from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore


DEVICE_PRIVATE_KEY_SECRET = "mcp.device_private_key"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


@dataclass(frozen=True)
class SignedRequestHeaders:
    installation_id: str
    timestamp: str
    nonce: str
    signature: str

    def as_http_headers(self) -> dict[str, str]:
        return {
            "X-PG-Installation": self.installation_id,
            "X-PG-Timestamp": self.timestamp,
            "X-PG-Nonce": self.nonce,
            "X-PG-Signature": self.signature,
        }


class DeviceIdentityKey:
    """A non-exported-by-UI P-256 device key used only for infrastructure requests."""

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store

    def _private_key(self) -> ec.EllipticCurvePrivateKey:
        encoded = self.secret_store.get(DEVICE_PRIVATE_KEY_SECRET)
        if encoded:
            key = serialization.load_pem_private_key(encoded.encode("ascii"), password=None)
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise ValueError("Stored device key has an unexpected type")
            return key
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        self.secret_store.set(DEVICE_PRIVATE_KEY_SECRET, pem)
        return key

    def public_jwk(self) -> dict[str, str]:
        numbers = self._private_key().public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "use": "sig",
            "alg": "ES256",
            "x": _b64url(numbers.x.to_bytes(32, "big")),
            "y": _b64url(numbers.y.to_bytes(32, "big")),
        }

    def public_jwk_json(self) -> str:
        return json.dumps(self.public_jwk(), separators=(",", ":"), sort_keys=True)

    def sign_request(
        self,
        installation_id: str,
        method: str,
        path: str,
        body: bytes,
    ) -> SignedRequestHeaders:
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(18)
        digest = _b64url(hashlib.sha256(body).digest())
        canonical = f"{timestamp}\n{nonce}\n{method.upper()}\n{path}\n{digest}".encode("utf-8")
        der = self._private_key().sign(canonical, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return SignedRequestHeaders(
            installation_id=installation_id,
            timestamp=timestamp,
            nonce=nonce,
            signature=_b64url(raw_signature),
        )
