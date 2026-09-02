from __future__ import annotations

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile


ROADMAP_ENTITIES = {
    "API_KEY",
    "ACCESS_TOKEN",
    "JWT_TOKEN",
    "OAUTH_SECRET",
    "CLOUD_CREDENTIAL",
    "DATABASE_CREDENTIAL",
    "WEBHOOK_SECRET",
    "PRIVATE_KEY",
    "MAC_ADDRESS",
    "CRYPTO",
    "IBAN_CODE",
}


def _maximum_profile():
    base = get_profile("general_business")
    return type(base)(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, "maximum"),
        threshold=base.threshold,
    )


def test_roadmap_entities_are_exposed_by_expected_scopes() -> None:
    base = get_profile("general_business")
    maximum = set(entities_for_scope(base, "maximum"))
    financial = set(entities_for_scope(base, "financial"))
    business = set(entities_for_scope(base, "business"))
    essential = set(entities_for_scope(base, "essential"))

    assert ROADMAP_ENTITIES <= maximum
    assert {"IBAN_CODE", "CRYPTO"} <= financial
    assert not (ROADMAP_ENTITIES - {"IBAN_CODE", "CRYPTO"}) & business
    assert not ROADMAP_ENTITIES & essential


def test_secrets_pack_exact_spans_in_central_engine() -> None:
    text = """OpenAI API key = sk-proj-EXAMPLE1234567890abcdefghijklmnop
GitHub token: ghp_EXAMPLE1234567890abcdefghijklmnopqr
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGFtcGxlIn0.signature123
OAuth client secret = oauth_example_8f93A1b2C3d4E5f6
AWS access key ID: AKIAEXAMPLE12345678
Database URL: postgres://app_user:S3cur3-Pass@example-db.invalid:5432/app
Webhook signing secret: whsec_EXAMPLE_1234567890abcdef
Private key:
-----BEGIN PRIVATE KEY-----
ZXhhbXBsZS1ub3QtYS1yZWFsLWtleQ==
-----END PRIVATE KEY-----
Device MAC address: 00:1A:2B:3C:4D:5E
Bitcoin address: 1BoatSLRHtKNngkdXEeobR76b53LETtpyT
IBAN: GB82WEST12345698765432
Beneficiary IBAN = DE89370400440532013000
IBAN
FR1420041010050500013M02606
"""
    service = PrivacyGateService()
    findings = service.analyze(
        service.document_from_text(text),
        _maximum_profile(),
        language="en",
    )
    found = {(item.entity_type, item.text) for item in findings}

    assert {
        ("API_KEY", "sk-proj-EXAMPLE1234567890abcdefghijklmnop"),
        ("ACCESS_TOKEN", "ghp_EXAMPLE1234567890abcdefghijklmnopqr"),
        ("JWT_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGFtcGxlIn0.signature123"),
        ("OAUTH_SECRET", "oauth_example_8f93A1b2C3d4E5f6"),
        ("CLOUD_CREDENTIAL", "AKIAEXAMPLE12345678"),
        (
            "DATABASE_CREDENTIAL",
            "postgres://app_user:S3cur3-Pass@example-db.invalid:5432/app",
        ),
        ("WEBHOOK_SECRET", "whsec_EXAMPLE_1234567890abcdef"),
        (
            "PRIVATE_KEY",
            "-----BEGIN PRIVATE KEY-----\n"
            "ZXhhbXBsZS1ub3QtYS1yZWFsLWtleQ==\n"
            "-----END PRIVATE KEY-----",
        ),
        ("MAC_ADDRESS", "00:1A:2B:3C:4D:5E"),
        ("CRYPTO", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"),
        ("IBAN_CODE", "GB82WEST12345698765432"),
        ("IBAN_CODE", "DE89370400440532013000"),
        ("IBAN_CODE", "FR1420041010050500013M02606"),
    } <= found


def test_secrets_pack_keeps_placeholder_and_policy_language_clean() -> None:
    texts = (
        "The API key field must never be committed to source control.",
        "Authorization: Bearer <token>",
        "password = <redacted>",
        "-----BEGIN PRIVATE KEY----- is a PEM header string.",
        "The webhook secret rotation policy was updated.",
        "MAC address formatting is documented here.",
        "The IBAN field is optional in this template.",
        "Bitcoin address validation is handled by the wallet library.",
    )
    service = PrivacyGateService()
    profile = _maximum_profile()
    for text in texts:
        findings = service.analyze(
            service.document_from_text(text),
            profile,
            language="en",
        )
        assert not any(item.entity_type in ROADMAP_ENTITIES for item in findings), (
            text,
            [(item.entity_type, item.text) for item in findings],
        )
