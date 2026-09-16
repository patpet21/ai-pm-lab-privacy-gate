from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import SecretStore

MOBILE_LINK_PRIVATE_KEY_SECRET = "mobile-link-private-key-v1"
MOBILE_LINK_CERTIFICATE_SECRET = "mobile-link-certificate-v1"


@dataclass(frozen=True, slots=True)
class MobileLinkCertificate:
    certificate_pem: str
    private_key_pem: str
    certificate_sha256: str


class MobileLinkCertificateStore:
    """Persist the self-signed Mobile Link identity in the platform secret store."""

    def __init__(self, secret_store: SecretStore) -> None:
        self.secret_store = secret_store

    def load_or_create(self) -> MobileLinkCertificate:
        certificate_pem = self.secret_store.get(MOBILE_LINK_CERTIFICATE_SECRET)
        private_key_pem = self.secret_store.get(MOBILE_LINK_PRIVATE_KEY_SECRET)
        if certificate_pem and private_key_pem:
            return self._identity(certificate_pem, private_key_pem)

        private_key = ec.generate_private_key(ec.SECP256R1())
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "PrivacyGate Mobile Link")]
        )
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("privacygate.local"), x509.DNSName("localhost")]
                ),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
        private_key_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("ascii")
        self.secret_store.set(MOBILE_LINK_CERTIFICATE_SECRET, certificate_pem)
        self.secret_store.set(MOBILE_LINK_PRIVATE_KEY_SECRET, private_key_pem)
        return self._identity(certificate_pem, private_key_pem)

    @staticmethod
    def _identity(certificate_pem: str, private_key_pem: str) -> MobileLinkCertificate:
        certificate = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
        fingerprint = hashlib.sha256(
            certificate.public_bytes(serialization.Encoding.DER)
        ).hexdigest()
        return MobileLinkCertificate(
            certificate_pem=certificate_pem,
            private_key_pem=private_key_pem,
            certificate_sha256=fingerprint,
        )
