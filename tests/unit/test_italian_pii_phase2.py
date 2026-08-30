from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.addresses import (
    build_address_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.business import (
    build_business_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.cadastral import (
    build_cadastral_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.contacts import (
    build_contact_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.identity_documents import (
    build_identity_document_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.vehicles import (
    build_vehicle_recognizers,
)


def _values(recognizers, text: str, entity_type: str) -> list[str]:
    values: list[str] = []
    for recognizer in recognizers:
        if entity_type not in recognizer.supported_entities:
            continue
        for result in recognizer.analyze(text, [entity_type]):
            values.append(text[result.start : result.end])
    return values


def test_italian_contacts_detect_email_pec_and_phone() -> None:
    recognizers = build_contact_recognizers()
    text = (
        "Email: mario.rossi@example.it\n"
        "PEC: studio@pec.example.it.\n"
        "Telefono: 06 6982 1234\n"
        "Cellulare: +39 347 1234567"
    )

    assert "mario.rossi@example.it" in _values(recognizers, text, "EMAIL_ADDRESS")
    assert "studio@pec.example.it" in _values(recognizers, text, "IT_PEC_ADDRESS")
    phone_values = _values(recognizers, text, "PHONE_NUMBER")
    assert "06 6982 1234" in phone_values
    assert "+39 347 1234567" in phone_values


def test_phone_recognizer_handles_centralino_split_across_ocr_lines() -> None:
    text = "Centralino: +39 02\n1234 5678."
    assert _values(build_contact_recognizers(), text, "PHONE_NUMBER") == [
        "+39 02\n1234 5678",
        "+39 02\n1234 5678",
    ]


def test_italian_address_fields_require_plausible_context() -> None:
    recognizers = build_address_recognizers()
    text = "Via Giuseppe Garibaldi 12\nCAP: 00184\nProvincia: RM"

    assert "Via Giuseppe Garibaldi 12" in _values(recognizers, text, "STREET_ADDRESS")
    assert _values(recognizers, text, "IT_POSTAL_CODE") == ["00184"]
    assert _values(recognizers, text, "IT_PROVINCE") == ["RM"]

    inline = "Via Alessandro Manzoni 24, 20121 Milano (MI)"
    assert "20121" in _values(recognizers, inline, "IT_POSTAL_CODE")

    unrelated = "Numero pratica 00184"
    assert _values(recognizers, unrelated, "IT_POSTAL_CODE") == []


def test_italian_identity_documents_are_contextual() -> None:
    recognizers = build_identity_document_recognizers()
    text = (
        "Carta d'identità n. CA12345AB\n"
        "Passaporto n. YA1234567\n"
        "Patente di guida n. U1AB234567"
    )

    assert _values(recognizers, text, "IT_ID_CARD") == ["CA12345AB"]
    assert _values(recognizers, text, "IT_PASSPORT") == ["YA1234567"]
    assert _values(recognizers, text, "IT_DRIVER_LICENSE") == ["U1AB234567"]
    assert _values(recognizers, "Codice progetto CA12345AB", "IT_ID_CARD") == []


def test_italian_vehicle_plate_requires_vehicle_context() -> None:
    recognizers = build_vehicle_recognizers()
    assert _values(recognizers, "Targa: AB123CD", "IT_VEHICLE_PLATE") == ["AB123CD"]
    assert _values(
        recognizers,
        "Targa veicolo autorizzato: AB123CD",
        "IT_VEHICLE_PLATE",
    ) == ["AB123CD"]
    assert _values(recognizers, "Ordine AB123CD", "IT_VEHICLE_PLATE") == []


def test_italian_cadastral_fields_are_separate_findings() -> None:
    recognizers = build_cadastral_recognizers()
    text = (
        "Codice catastale: H501\n"
        "Sezione urbana: A\n"
        "Foglio: 123\n"
        "Particella: 456/2\n"
        "Subalterno: 7"
    )

    assert _values(recognizers, text, "IT_CADASTRAL_MUNICIPAL_CODE") == ["H501"]
    assert _values(recognizers, text, "IT_CADASTRAL_SECTION") == ["A"]
    assert _values(recognizers, text, "IT_CADASTRAL_SHEET") == ["123"]
    assert _values(recognizers, text, "IT_CADASTRAL_PARCEL") == ["456/2"]
    assert _values(recognizers, text, "IT_CADASTRAL_SUBALTERN") == ["7"]


def test_cadastral_section_accepts_explicit_catastale_label() -> None:
    assert _values(
        build_cadastral_recognizers(),
        "Sezione catastale\nA",
        "IT_CADASTRAL_SECTION",
    ) == ["A"]


def test_italian_business_identifiers_and_legal_entity() -> None:
    recognizers = build_business_recognizers()
    text = (
        "Società: Aurora Gestioni Immobiliari S.r.l.\n"
        "R.E.A. n. RM-123456\n"
        "Registro Imprese n. RM123456789"
    )

    assert _values(recognizers, text, "ORGANIZATION") == [
        "Aurora Gestioni Immobiliari S.r.l."
    ]
    assert _values(recognizers, text, "IT_REA_NUMBER") == ["RM-123456"]
    assert _values(recognizers, text, "IT_BUSINESS_REGISTER_NUMBER") == ["RM123456789"]
    assert _values(recognizers, "Pratica RM-123456", "IT_REA_NUMBER") == []

    prose = (
        "Mario Rossi incontrerà l’amministratrice Laura Ferri presso gli uffici di "
        "Aurora Gestioni Immobiliari S.r.l. a Milano."
    )
    assert _values(recognizers, prose, "ORGANIZATION") == [
        "Aurora Gestioni Immobiliari S.r.l."
    ]
