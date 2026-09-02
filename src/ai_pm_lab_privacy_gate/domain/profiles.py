from __future__ import annotations

from dataclasses import dataclass


COMMON_US_ENTITIES = (
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "US_SSN",
    "US_ITIN",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "US_BANK_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "DATE_OF_BIRTH",
    "STREET_ADDRESS",
    "POSTAL_CODE",
)

FINANCIAL_SENSITIVE_ENTITIES = (
    "US_BANK_NUMBER",
    "US_ROUTING_NUMBER",
    "SWIFT_BIC",
    "IBAN_CODE",
    "CRYPTO",
    "CARD_LAST_FOUR",
    "CARD_TRANSACTION_ID",
    "TRANSFER_TRANSACTION_ID",
    "TRANSACTION_ID",
    "STATEMENT_REFERENCE",
    "MONEY_AMOUNT",
    "MERCHANT",
    "COUNTERPARTY",
    "TRANSACTION_REFERENCE",
    "BUSINESS_REGISTRATION_NUMBER",
)

BUSINESS_CONFIDENTIAL_ENTITIES = (
    "ORGANIZATION",
    "URL",
    "BUSINESS_REGISTRATION_NUMBER",
    "INVOICE_NUMBER",
    "PURCHASE_ORDER_ID",
    "CONTRACT_ID",
    "CUSTOMER_ID",
    "EMPLOYEE_ID",
    "CASE_REFERENCE",
)

TECHNICAL_SECRET_ENTITIES = (
    "API_KEY",
    "ACCESS_TOKEN",
    "JWT_TOKEN",
    "OAUTH_SECRET",
    "CLOUD_CREDENTIAL",
    "DATABASE_CREDENTIAL",
    "WEBHOOK_SECRET",
    "PRIVATE_KEY",
    "MAC_ADDRESS",
)

OPERATIONAL_IDENTIFIER_ENTITIES = (
    "US_ROUTING_NUMBER",
    "TENANT_ID",
    "LEASE_ID",
    "NYC_BBL",
    "NYC_BIN",
    "VENDOR_ACCOUNT_ID",
    "WORK_ORDER_ID",
    "PROPOSAL_ID",
    "INSURANCE_POLICY_ID",
    "PREAPPROVAL_ID",
    "MORTGAGE_REFERENCE",
    "US_EIN",
    "PROPERTY_IDENTIFIER",
    "UNIT_NUMBER",
    "PROPERTY_ACCESS_CODE",
    "LOCKBOX_CODE",
    "CONTRACTOR_LICENSE",
    "INSURANCE_CLAIM_ID",
    "UTILITY_ACCOUNT_ID",
    "LOAN_NUMBER",
    "TRANSACTION_ID",
)

REAL_ESTATE_SENSITIVE_ENTITIES = (
    "SECURITY_CODE",
    "UTILITY_METER_ID",
    "HOUSING_ASSISTANCE_ID",
    "LEASE_OCCUPANCY_DATE",
    "RENT_AMOUNT",
    "TENANT_BALANCE",
    "SECURITY_DEPOSIT_AMOUNT",
    "OWNER_DISTRIBUTION",
    "OPERATING_BALANCE",
    "RESERVE_BALANCE",
    "NOI_AMOUNT",
    "CAPEX_BUDGET_AMOUNT",
    "REMAINING_CAPITAL_BUDGET",
    "CONTINGENCY_AMOUNT",
    "CONTRACTOR_BID_AMOUNT",
    "CHANGE_ORDER_AMOUNT",
    "INVOICE_AMOUNT",
    "PURCHASE_ORDER_VALUE",
    "OFFER_PRICE",
    "PURCHASE_PRICE",
    "EARNEST_MONEY_AMOUNT",
    "BROKER_COMMISSION",
    "CLOSING_CREDIT",
    "ESCROW_AMOUNT",
    "MANAGEMENT_FEE",
    "CASE_REFERENCE",
    "MAINTENANCE_TICKET_ID",
    "PROJECT_JOB_CODE",
    "KEY_ACCESS_INSTRUCTION",
    "HOUSING_LEGAL_CASE_ID",
    "NYC_DOB_JOB_ID",
    "NYC_HPD_RECORD_ID",
    "INSPECTION_ACCESS_WINDOW",
    "VACANCY_OCCUPANCY_DATE",
    "APPROVAL_AUTH_CODE",
    "CARD_SECURITY_CODE",
    "PAYMENT_TOKEN",
    "ACH_AUTHORIZATION_ID",
    "WIRE_CONFIRMATION_ID",
    "WIFI_CREDENTIAL",
    "PASSWORD_CREDENTIAL",
    "PORTAL_USERNAME",
    "AUTH_SESSION_ID",
    "DEVICE_FINGERPRINT",
    "MFA_RECOVERY_CODE",
    "SAFE_COMBINATION",
    "APPLICATION_ID",
    "SCREENING_REFERENCE",
    "CREDIT_SCORE",
    "TENANT_INCOME_AMOUNT",
    "HOUSING_ASSISTANCE_AMOUNT",
    "VEHICLE_LICENSE_PLATE",
    "RENT_CONCESSION_AMOUNT",
    "PAYMENT_PLAN_AMOUNT",
    "LATE_FEE_AMOUNT",
    "PROPERTY_TAX_AMOUNT",
    "INSURANCE_PREMIUM_AMOUNT",
    "LOAN_AMOUNT",
    "LOAN_BALANCE",
    "DEBT_SERVICE_AMOUNT",
    "INTEREST_RATE",
    "LTV_RATIO",
    "PREAPPROVAL_AMOUNT",
    "CASH_TO_CLOSE",
    "CLOSING_COST_AMOUNT",
    "BUYER_BUDGET_AMOUNT",
    "SELLER_NET_PROCEEDS",
    "NEGOTIATION_LIMIT_AMOUNT",
    "INTERNAL_VALUATION_AMOUNT",
    "PROJECT_BUDGET_AMOUNT",
    "RETAINAGE_AMOUNT",
    "PAY_APPLICATION_AMOUNT",
    "SUBCONTRACT_AMOUNT",
    "LABOR_RATE",
    "MATERIAL_ALLOWANCE_AMOUNT",
    "PERMIT_ID",
    "LIEN_WAIVER_ID",
    "COI_REFERENCE",
    "INSURANCE_CLAIM_AMOUNT",
    "INSURANCE_DEDUCTIBLE_AMOUNT",
    "TITLE_FILE_ID",
    "LISTING_AGREEMENT_ID",
    "ACCOUNTS_PAYABLE_AMOUNT",
    "COMMITTED_COST_AMOUNT",
)


def _merge_entities(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Merge entity groups without changing their first-seen order."""
    return tuple(dict.fromkeys(entity for group in groups for entity in group))


# Universal core used by the default profile and inherited by vertical profiles.
# Keep vertical-only identifiers (tenant/lease/BBL/unit/etc.) out of this base.
# Technical secrets live in the core so Maximum/Custom can expose them, while
# Essential/Financial/Business remain filtered by their explicit scope allowlists.
GENERAL_CORE_ENTITIES = _merge_entities(
    COMMON_US_ENTITIES,
    FINANCIAL_SENSITIVE_ENTITIES,
    BUSINESS_CONFIDENTIAL_ENTITIES,
    TECHNICAL_SECRET_ENTITIES,
    ("US_EIN", "DATE_TIME"),
)

DEFAULT_PROFILE_KEY = "general_business"
DEFAULT_SCOPE_KEY = "maximum"


@dataclass(frozen=True, slots=True)
class PrivacyProfile:
    key: str
    name: str
    description: str
    entities: tuple[str, ...]
    threshold: float = 0.35


@dataclass(frozen=True, slots=True)
class ProtectionScope:
    key: str
    name: str
    description: str


_SCOPES = (
    ProtectionScope("essential", "Essential PII", "Identity, contact, government IDs, addresses and payment credentials."),
    ProtectionScope("financial", "PII + Financial", "Adds accounts, transaction IDs, card endings, amounts, merchants and references."),
    ProtectionScope("business", "PII + Business Confidential", "Adds company, property, contract, project and operational identifiers."),
    ProtectionScope("maximum", "Maximum Protection", "Scans every sensitive category available in PrivacyGate, across the core and installed profile packs."),
    ProtectionScope("custom", "Custom Review", "Scans every category enabled by the selected profile, then lets you choose exactly what to protect."),
)


_PROFILES = (
    PrivacyProfile(
        key="general_business",
        name="General — Recommended",
        description="Recommended default for most documents: identity, contact, financial, organization, contract, customer and general business data.",
        entities=GENERAL_CORE_ENTITIES,
    ),
    PrivacyProfile(
        key="property_management",
        name="Property Management",
        description="General protection plus tenant, owner, vendor, property, lease, building-access and real-estate financial data.",
        entities=_merge_entities(
            GENERAL_CORE_ENTITIES,
            OPERATIONAL_IDENTIFIER_ENTITIES,
            REAL_ESTATE_SENSITIVE_ENTITIES,
        ),
    ),
    PrivacyProfile(
        key="realtor_brokerage",
        name="Realtor / Brokerage",
        description="General protection plus client, transaction, brokerage, property, offer and closing-sensitive data.",
        entities=_merge_entities(
            GENERAL_CORE_ENTITIES,
            OPERATIONAL_IDENTIFIER_ENTITIES,
            REAL_ESTATE_SENSITIVE_ENTITIES,
        ),
    ),
    PrivacyProfile(
        key="projects_renovations",
        name="Projects & Renovations",
        description="General protection plus owner, contractor, subcontractor, project, budget, permit and site-access data.",
        entities=_merge_entities(
            GENERAL_CORE_ENTITIES,
            OPERATIONAL_IDENTIFIER_ENTITIES,
            REAL_ESTATE_SENSITIVE_ENTITIES,
        ),
    ),
    PrivacyProfile(
        key="construction",
        name="Construction",
        description="General protection plus owner, contractor, vendor, project, permit, insurance and construction-financial identifiers.",
        entities=_merge_entities(
            GENERAL_CORE_ENTITIES,
            OPERATIONAL_IDENTIFIER_ENTITIES,
            REAL_ESTATE_SENSITIVE_ENTITIES,
        ),
    ),
    PrivacyProfile(
        key="legal",
        name="Legal",
        description="General protection plus case, contract and operational identifiers commonly present in legal documents.",
        entities=_merge_entities(
            GENERAL_CORE_ENTITIES,
            OPERATIONAL_IDENTIFIER_ENTITIES,
        ),
    ),
    PrivacyProfile(
        key="healthcare_general",
        name="Healthcare — General Privacy",
        description="General identity/contact/business privacy for healthcare documents; not a substitute for a specialized clinical/HIPAA recognizer pack.",
        entities=GENERAL_CORE_ENTITIES,
    ),
)


def _all_profile_entities() -> tuple[str, ...]:
    """Return the deduplicated union of every currently installed profile pack."""
    return _merge_entities(*(profile.entities for profile in _PROFILES))


def list_profiles() -> tuple[PrivacyProfile, ...]:
    return _PROFILES


def get_profile(key: str) -> PrivacyProfile:
    for profile in _PROFILES:
        if profile.key == key:
            return profile
    raise KeyError(f"Unknown privacy profile: {key}")


def list_scopes() -> tuple[ProtectionScope, ...]:
    return _SCOPES


def get_scope(key: str) -> ProtectionScope:
    for scope in _SCOPES:
        if scope.key == key:
            return scope
    raise KeyError(f"Unknown protection scope: {key}")


def entities_for_scope(profile: PrivacyProfile, scope_key: str) -> tuple[str, ...]:
    """Return a stable entity set for a universal protection level."""
    if scope_key == "essential":
        allowed = set(COMMON_US_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key == "financial":
        allowed = set(COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key == "business":
        allowed = set(COMMON_US_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key == "maximum":
        # Maximum is the product-wide safety net: scan every category PrivacyGate
        # currently knows, regardless of which profile supplied that recognizer.
        return _all_profile_entities()
    elif scope_key == "custom":
        allowed = set(profile.entities)
    else:
        raise KeyError(f"Unknown protection scope: {scope_key}")
    return tuple(dict.fromkeys(entity for entity in profile.entities if entity in allowed))
