from __future__ import annotations

from presidio_analyzer import RecognizerResult

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.guardrails import (
    filter_english_contextual_results,
    filter_english_ner_results,
)


def _result(entity_type: str, text: str, value: str, score: float = 0.85) -> RecognizerResult:
    start = text.index(value)
    return RecognizerResult(
        entity_type=entity_type,
        start=start,
        end=start + len(value),
        score=score,
    )


def test_public_technical_and_identifier_labels_are_not_private_ner() -> None:
    cases = (
        ("Social Security no. 604-18-2397", "ORGANIZATION", "Social Security"),
        ("Client IP address: 198.51.100.27", "ORGANIZATION", "Client IP"),
        ("GitHub access token = ghp_example1234567890", "ORGANIZATION", "GitHub"),
        ("Authorization: Bearer <access-token>", "ORGANIZATION", "Bearer"),
        ("AWS access key ID values should never be pasted.", "ORGANIZATION", "AWS"),
        ("Device MAC address formatting uses six hexadecimal pairs.", "ORGANIZATION", "MAC"),
        ("U.S. Passport No. 456789123", "LOCATION", "U.S."),
    )
    for text, entity_type, value in cases:
        result = _result(entity_type, text, value)
        assert filter_english_ner_results(text, [result], profile_key="general_business") == []


def test_relative_and_time_only_dates_are_not_sensitive_date_time() -> None:
    for text, value in (
        ("Please send the lease before 4 PM.", "4 PM"),
        ("Rotation is scheduled for next Friday.", "next Friday"),
        ("The process changed this year.", "this year"),
    ):
        result = _result("DATE_TIME", text, value)
        assert filter_english_contextual_results(text, [result]) == []


def test_impossible_context_values_are_rejected() -> None:
    cases = (
        ("The GitHub token policy requires quarterly review.", "INSURANCE_POLICY_ID", "requires"),
        ("The passport renewal process changed.", "US_PASSPORT", "renewal"),
        ("Driver license policy is covered in the handbook.", "US_DRIVER_LICENSE", "policy is covered"),
        ("Customer ID fields are optional.", "CUSTOMER_ID", "fields"),
        ("Tenant ID mapping is handled by migration.", "TENANT_ID", "mapping"),
        ("Wi-Fi password requirements are documented.", "WIFI_CREDENTIAL", "requirements"),
    )
    for text, entity_type, value in cases:
        result = _result(entity_type, text, value, score=0.99)
        assert filter_english_contextual_results(text, [result]) == []


def test_explicit_dob_is_form_wins_over_generic_date_time() -> None:
    text = "Her DOB is 12/09/1985 and her phone is 917-555-0128."
    base = get_profile("general_business")
    profile = type(base)(
        key=base.key,
        name=base.name,
        description=base.description,
        entities=entities_for_scope(base, "maximum"),
        threshold=base.threshold,
    )
    service = PrivacyGateService()
    findings = service.analyze(service.document_from_text(text), profile, language="en")
    found = {(item.entity_type, item.text) for item in findings}
    assert ("DATE_OF_BIRTH", "12/09/1985") in found
    assert ("DATE_TIME", "12/09/1985") not in found
