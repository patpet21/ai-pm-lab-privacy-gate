import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from ai_pm_lab_privacy_gate.infrastructure.mcp.device_identity import DeviceIdentityKey
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_device_request_signature_is_p256_and_stable() -> None:
    secrets = MemorySecretStore()
    identity = DeviceIdentityKey(secrets)
    body = b'{"code":"ABCD1234"}'
    headers = identity.sign_request("a" * 32, "POST", "/v1/pairings/approve", body)
    jwk = identity.public_jwk()
    public_key = ec.EllipticCurvePublicNumbers(
        int.from_bytes(_decode(jwk["x"]), "big"),
        int.from_bytes(_decode(jwk["y"]), "big"),
        ec.SECP256R1(),
    ).public_key()
    raw = _decode(headers.signature)
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    canonical = (
        f"{headers.timestamp}\n{headers.nonce}\nPOST\n/v1/pairings/approve\n"
        f"{base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')}"
    ).encode()
    public_key.verify(encode_dss_signature(r, s), canonical, ec.ECDSA(hashes.SHA256()))
    assert DeviceIdentityKey(secrets).public_jwk() == jwk
