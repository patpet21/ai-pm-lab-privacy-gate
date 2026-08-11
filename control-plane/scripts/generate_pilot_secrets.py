"""Generate one-time control-plane secrets without printing them.

Output lives under the git-ignored ``private`` directory and must be removed
after the values have been uploaded with ``wrangler secret put``.
"""

from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


root = Path(__file__).resolve().parents[1]
output = root / "private"
output.mkdir(mode=0o700, parents=True, exist_ok=True)

private_key = ec.generate_private_key(ec.SECP256R1())
numbers = private_key.private_numbers()
public = numbers.public_numbers
kid = secrets.token_hex(8)

public_jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": b64url(public.x.to_bytes(32, "big")),
    "y": b64url(public.y.to_bytes(32, "big")),
    "use": "sig",
    "alg": "ES256",
    "kid": kid,
}
private_jwk = {
    **public_jwk,
    "d": b64url(numbers.private_value.to_bytes(32, "big")),
}

(output / "JWT_PRIVATE_JWK.txt").write_text(
    json.dumps(private_jwk, separators=(",", ":")), encoding="utf-8"
)
(output / "JWT_PUBLIC_JWK.txt").write_text(
    json.dumps(public_jwk, separators=(",", ":")), encoding="utf-8"
)
(output / "PILOT_APPROVAL_CODE.txt").write_text(
    secrets.token_urlsafe(24), encoding="utf-8"
)

print("Generated three secrets in control-plane/private (values not displayed).")
