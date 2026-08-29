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
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.financial import (
    build_financial_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.fiscal import (
    build_fiscal_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.identity_documents import (
    build_identity_document_recognizers,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.italian.vehicles import (
    build_vehicle_recognizers,
)


ITALIAN_ENTITY_TYPES = (
    "IT_FISCAL_CODE",
    "IT_VAT_NUMBER",
    "IBAN_CODE",
    "EMAIL_ADDRESS",
    "IT_PEC_ADDRESS",
    "PHONE_NUMBER",
    "STREET_ADDRESS",
    "IT_POSTAL_CODE",
    "IT_PROVINCE",
    "IT_ID_CARD",
    "IT_PASSPORT",
    "IT_DRIVER_LICENSE",
    "IT_VEHICLE_PLATE",
    "IT_CADASTRAL_MUNICIPAL_CODE",
    "IT_CADASTRAL_SECTION",
    "IT_CADASTRAL_SHEET",
    "IT_CADASTRAL_PARCEL",
    "IT_CADASTRAL_SUBALTERN",
    "IT_REA_NUMBER",
    "IT_BUSINESS_REGISTER_NUMBER",
)


def install_italian_recognizers(registry) -> None:  # noqa: ANN001
    """Install deterministic recognizers that are safe to run without an NLP model."""
    recognizers = (
        *build_fiscal_recognizers(),
        *build_financial_recognizers(),
        *build_contact_recognizers(),
        *build_address_recognizers(),
        *build_identity_document_recognizers(),
        *build_vehicle_recognizers(),
        *build_cadastral_recognizers(),
        *build_business_recognizers(),
    )
    for recognizer in recognizers:
        registry.add_recognizer(recognizer)
