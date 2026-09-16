from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.mobile_link.certificate import MobileLinkCertificateStore
from ai_pm_lab_privacy_gate.infrastructure.mobile_link.pairing import MobilePairingRegistry
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore


def test_mobile_pairing_token_is_hashed_and_single_use() -> None:
    secrets = MemorySecretStore()
    registry = MobilePairingRegistry(secrets)
    challenge = registry.create_challenge(now=100.0)

    token = registry.pair("android-test-0001", challenge.code, client_name="Samsung", now=101.0)

    assert registry.validate(token)
    assert all(token not in value for value in secrets.values.values())
    try:
        registry.pair("android-test-0002", challenge.code, now=102.0)
    except ValueError as error:
        assert "expired or unavailable" in str(error)
    else:
        raise AssertionError("pairing challenge must be single-use")


def test_mobile_link_certificate_identity_is_stable() -> None:
    secrets = MemorySecretStore()
    store = MobileLinkCertificateStore(secrets)

    first = store.load_or_create()
    second = store.load_or_create()

    assert first.certificate_pem == second.certificate_pem
    assert first.private_key_pem == second.private_key_pem
    assert first.certificate_sha256 == second.certificate_sha256
    assert len(first.certificate_sha256) == 64


def test_mobile_link_manager_bundle_is_opt_in_and_tls_pinned() -> None:
    from pathlib import Path

    from ai_pm_lab_privacy_gate.infrastructure.mobile_link.manager import MobileLinkManager

    class FakeServer:
        server_port = 8767

        def serve_forever(self, poll_interval: float = 0.25) -> None:
            return

        def shutdown(self) -> None:
            return

        def server_close(self) -> None:
            return

    captured = {}

    def server_factory(**kwargs):
        captured.update(kwargs)
        return FakeServer()

    manager = MobileLinkManager(
        object(),
        Path('.'),
        secret_store=MemorySecretStore(),
        server_factory=server_factory,
    )
    assert manager.status.state == 'disabled'

    bundle = manager.create_pairing_bundle()

    assert manager.status.state == 'online'
    assert captured['host'] == '0.0.0.0'
    assert bundle.endpoints
    assert all(endpoint.startswith('https://') for endpoint in bundle.endpoints)
    assert len(bundle.pairing_code) == 8
    assert 'BEGIN CERTIFICATE' in bundle.certificate_pem
    assert len(bundle.certificate_sha256) == 64
    manager.stop()
