from __future__ import annotations

from presidio_analyzer import RecognizerResult

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


def _maximum_profile():
    base = get_profile("general_business")
    return type(base)(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, "maximum"),
        threshold=base.threshold,
    )


def _result(entity_type: str, text: str, value: str, score: float = 0.98) -> RecognizerResult:
    start = text.index(value)
    return RecognizerResult(
        entity_type=entity_type,
        start=start,
        end=start + len(value),
        score=score,
    )


def test_blind_v2_secret_aliases_are_detected_with_exact_spans() -> None:
    text = """OpenAI key = sk-proj-Qw12Er34Ty56Ui78Op90As12Df34
Service API key: api_9F8e7D6c5B4a3A2z1Y0x
Access token = pat_live_Z91xY82wV73uT64sR55q
Bearer token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3NzEifQ.sigA12B34C
JWT = eyJ0eXAiOiJKV1QifQ.eyJyb2xlIjoiYWRtaW4ifQ.signature77
Client secret: clientSecret_44Aa55Bb66Cc
Cloud access key = AKIAZXCVBNMASDFGHJKL
Mongo connection = mongodb://svc:DeltaPass99@mongo.example.invalid:27017/app
Signing secret = whsec_Zx98Cv76Bn54Mm32
Webhook secret: whsec_55Aa66Bb77Cc
"""
    expected = {
        ("API_KEY", "sk-proj-Qw12Er34Ty56Ui78Op90As12Df34"),
        ("API_KEY", "api_9F8e7D6c5B4a3A2z1Y0x"),
        ("ACCESS_TOKEN", "pat_live_Z91xY82wV73uT64sR55q"),
        ("JWT_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3NzEifQ.sigA12B34C"),
        ("JWT_TOKEN", "eyJ0eXAiOiJKV1QifQ.eyJyb2xlIjoiYWRtaW4ifQ.signature77"),
        ("OAUTH_SECRET", "clientSecret_44Aa55Bb66Cc"),
        ("CLOUD_CREDENTIAL", "AKIAZXCVBNMASDFGHJKL"),
        (
            "DATABASE_CREDENTIAL",
            "mongodb://svc:DeltaPass99@mongo.example.invalid:27017/app",
        ),
        ("WEBHOOK_SECRET", "whsec_Zx98Cv76Bn54Mm32"),
        ("WEBHOOK_SECRET", "whsec_55Aa66Bb77Cc"),
    }
    service = PrivacyGateService()
    findings = service.analyze(
        service.document_from_text(text),
        _maximum_profile(),
        language="en",
    )
    found = {(item.entity_type, item.text) for item in findings}
    assert expected <= found


def test_secret_aliases_do_not_fire_on_policy_language() -> None:
    texts = (
        "The OpenAI key rotation policy was updated.",
        "The service API key field is documented.",
        "Access token requirements are reviewed quarterly.",
        "JWT format is described in the integration guide.",
        "The client secret rotation procedure changed.",
        "Cloud access key naming conventions are documented.",
        "Mongo connection settings are managed by operations.",
        "Signing secret requirements include periodic rotation.",
    )
    service = PrivacyGateService()
    profile = _maximum_profile()
    protected_types = {
        "API_KEY",
        "ACCESS_TOKEN",
        "JWT_TOKEN",
        "OAUTH_SECRET",
        "CLOUD_CREDENTIAL",
        "DATABASE_CREDENTIAL",
        "WEBHOOK_SECRET",
    }
    for text in texts:
        findings = service.analyze(service.document_from_text(text), profile, language="en")
        assert not any(item.entity_type in protected_types for item in findings), (
            text,
            [(item.entity_type, item.text) for item in findings],
        )


def test_business_equals_separator_supports_explicit_sensitive_labels() -> None:
    text = """ACH authorization reference = ACH-940551
Cash to close = $126,480.75
Project budget = $245,000
"""
    service = PrivacyGateService()
    findings = service.analyze(
        service.document_from_text(text),
        _maximum_profile(),
        language="en",
    )
    found = {(item.entity_type, item.text) for item in findings}
    assert ("ACH_AUTHORIZATION_ID", "ACH-940551") in found
    assert ("CASH_TO_CLOSE", "$126,480.75") in found
    assert ("PROJECT_BUDGET_AMOUNT", "$245,000") in found


def test_schema_words_are_rejected_as_identifier_values() -> None:
    cases = (
        ("The purchase order workflow was updated.", "PURCHASE_ORDER_ID", "workflow"),
        ("Contract ID fields are generated after signing.", "CONTRACT_ID", "fields"),
        ("Customer ID mapping is maintained by migration.", "CUSTOMER_ID", "mapping"),
        ("Lease number formatting changed.", "LEASE_ID", "formatting"),
        ("Contractor license requirements are listed.", "CONTRACTOR_LICENSE", "requirements"),
        ("Transaction ID columns are hidden.", "TRANSACTION_ID", "columns"),
        ("The policy review is scheduled.", "INSURANCE_POLICY_ID", "review"),
        ("The maintenance ticket field is generated.", "MAINTENANCE_TICKET_ID", "field"),
        ("The property identifier field is populated.", "PROPERTY_IDENTIFIER", "field"),
    )
    for text, entity_type, value in cases:
        result = _result(entity_type, text, value)
        assert PresidioPrivacyEngine._filter_context_value_false_positives(text, [result]) == []


def test_public_identifier_and_currency_labels_are_not_private_ner() -> None:
    cases = (
        ("Beneficiary BIC = DEUTDEFF500", "PERSON", "Beneficiary BIC"),
        ("NYC BBL = 1008420036", "ORGANIZATION", "NYC BBL"),
        ("The ITIN format is documented.", "ORGANIZATION", "ITIN"),
        ("JWT = eyJ0eXAiOiJKV1QifQ.payload.signature", "ORGANIZATION", "JWT"),
        ("Password requirements include a minimum length.", "ORGANIZATION", "Password"),
        ("Wire amount: EUR 35,900", "ORGANIZATION", "EUR"),
    )
    for text, entity_type, value in cases:
        result = _result(entity_type, text, value, score=0.85)
        assert PresidioPrivacyEngine._filter_context_value_false_positives(text, [result]) == []
