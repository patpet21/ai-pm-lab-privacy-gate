from __future__ import annotations

import pytest

from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_pairing import (
    BROWSER_PAIRING_SECRET,
    BrowserPairingRegistry,
)
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


ORIGIN = "chrome-extension://privacygate-test"
OTHER_ORIGIN = "chrome-extension://privacygate-other"


def test_pairing_code_is_one_time_and_credential_is_origin_bound() -> None:
    secrets = MemorySecretStore()
    registry = BrowserPairingRegistry(secrets)
    challenge = registry.create_challenge(now=100.0)

    assert len(challenge.code) == 8
    assert challenge.code.isdigit()

    token = registry.pair(ORIGIN, challenge.code, now=101.0)
    assert len(token) >= 24
    assert registry.validate(ORIGIN, token) is True
    assert registry.validate(OTHER_ORIGIN, token) is False
    assert token not in (secrets.get(BROWSER_PAIRING_SECRET) or "")

    with pytest.raises(ValueError, match="expired or unavailable"):
        registry.pair(ORIGIN, challenge.code, now=102.0)


def test_pairing_code_expires() -> None:
    registry = BrowserPairingRegistry(MemorySecretStore())
    challenge = registry.create_challenge(now=100.0)
    with pytest.raises(ValueError, match="expired or unavailable"):
        registry.pair(ORIGIN, challenge.code, now=401.0)


def test_pairing_code_invalidates_after_repeated_wrong_attempts() -> None:
    registry = BrowserPairingRegistry(MemorySecretStore())
    registry.create_challenge(now=100.0)

    for _ in range(5):
        with pytest.raises(ValueError, match="invalid"):
            registry.pair(ORIGIN, "00000000", now=101.0)

    with pytest.raises(ValueError, match="too many attempts"):
        registry.pair(ORIGIN, "00000000", now=101.0)


def test_revoke_removes_persisted_browser_access() -> None:
    secrets = MemorySecretStore()
    registry = BrowserPairingRegistry(secrets)
    challenge = registry.create_challenge(now=100.0)
    token = registry.pair(ORIGIN, challenge.code, now=101.0)
    assert registry.status().paired_count == 1

    registry.revoke()

    assert registry.status().paired_count == 0
    assert registry.validate(ORIGIN, token) is False
    assert secrets.get(BROWSER_PAIRING_SECRET) is None
