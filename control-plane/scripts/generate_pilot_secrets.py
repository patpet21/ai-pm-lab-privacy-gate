"""Generate one-time control-plane secrets without printing them.

Output lives under the git-ignored ``private`` directory and must be removed
after the values have been uploaded with ``wrangler secret put``.
"""

from __future__ import annotations

import secrets
from pathlib import Path


root = Path(__file__).resolve().parents[1]
output = root / "private"
output.mkdir(mode=0o700, parents=True, exist_ok=True)

(output / "PROVISIONING_FINGERPRINT_SALT.txt").write_text(
    secrets.token_urlsafe(48), encoding="utf-8"
)

print("Generated the provisioning fingerprint salt in control-plane/private.")
