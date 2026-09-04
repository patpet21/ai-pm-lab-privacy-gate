from __future__ import annotations

import json

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


def test_multiple_clients_can_pair_with_same_extension_origin() -> None:
    secrets = MemorySecretStore()
    registry = BrowserPairingRegistry(secrets)

    first = registry.create_challenge(now=100.0)
    token_avg = registry.pair(ORIGIN, first.code, client_name="AVG Secure Browser", now=101.0)

    second = registry.create_challenge(now=200.0)
    token_chrome = registry.pair(ORIGIN, second.code, client_name="Google Chrome", now=201.0)

    assert token_avg != token_chrome
    assert registry.validate(ORIGIN, token_avg) is True
    assert registry.validate(ORIGIN, token_chrome) is True
    assert registry.status().paired_count == 2
    assert registry.status().origins == (ORIGIN,)


def test_revoke_token_disconnects_only_the_requesting_browser() -> None:
    secrets = MemorySecretStore()
    registry = BrowserPairingRegistry(secrets)

    first = registry.create_challenge(now=100.0)
    token_edge = registry.pair(ORIGIN, first.code, client_name="Microsoft Edge", now=101.0)
    second = registry.create_challenge(now=200.0)
    token_chrome = registry.pair(ORIGIN, second.code, client_name="Google Chrome", now=201.0)

    assert registry.revoke_token(ORIGIN, token_edge) is True
    assert registry.validate(ORIGIN, token_edge) is False
    assert registry.validate(ORIGIN, token_chrome) is True
    assert registry.status().paired_count == 1
    assert registry.revoke_token(ORIGIN, token_edge) is False


def test_legacy_single_token_record_is_preserved_when_new_client_pairs() -> None:
    secrets = MemorySecretStore()
    registry = BrowserPairingRegistry(secrets)
    legacy_token = "legacy-browser-token-value-1234567890"
    secrets.set(
        BROWSER_PAIRING_SECRET,
        json.dumps(
            {
                ORIGIN: {
                    "token_hash": registry._token_hash(legacy_token),
                    "client_name": "Legacy Chromium",
                    "paired_at": 50.0,
                }
            }
        ),
    )

    assert registry.validate(ORIGIN, legacy_token) is True

    challenge = registry.create_challenge(now=100.0)
    new_token = registry.pair(ORIGIN, challenge.code, client_name="Google Chrome", now=101.0)

    assert registry.validate(ORIGIN, legacy_token) is True
    assert registry.validate(ORIGIN, new_token) is True
    assert registry.status().paired_count == 2


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
