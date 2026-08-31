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
    ProtectionScope("maximum", "Maximum Protection", "Scans every supported sensitive category, including dates, URLs and business data."),
    ProtectionScope("custom", "Custom Review", "Scans every category, then lets you choose exactly what to protect."),
)


_PROFILES = (
    PrivacyProfile(
        key="property_management",
        name="Property Management",
        description="Tenant, owner, vendor and property records. Includes dates and account identifiers.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="realtor_brokerage",
        name="Realtor / Brokerage",
        description="Client, transaction and brokerage documents. Includes dates and web addresses.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="projects_renovations",
        name="Projects & Renovations",
        description="Owner, contractor, subcontractor and project records. Includes dates and URLs.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="general_business",
        name="General Business",
        description="Identity, contact, financial, contract, customer and operational business data.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="construction",
        name="Construction",
        description="Owner, contractor, vendor, project, permit, insurance and financial identifiers.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="legal",
        name="Legal",
        description="General legal privacy profile for people, cases, contracts, addresses and financial identifiers.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="healthcare_general",
        name="Healthcare — General Privacy",
        description="General identity/contact privacy for healthcare documents; not a substitute for a specialized clinical/HIPAA recognizer pack.",
        entities=COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + ("DATE_TIME",),
    ),
)


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
    raise KeyError(f"Unknown protection scope: {scope_key}")


def entities_for_scope(profile: PrivacyProfile, scope_key: str) -> tuple[str, ...]:
    """Return a stable entity set for a universal protection level."""
    if scope_key == "essential":
        allowed = set(COMMON_US_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key == "financial":
        allowed = set(COMMON_US_ENTITIES + FINANCIAL_SENSITIVE_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key == "business":
        allowed = set(COMMON_US_ENTITIES + OPERATIONAL_IDENTIFIER_ENTITIES + BUSINESS_CONFIDENTIAL_ENTITIES + REAL_ESTATE_SENSITIVE_ENTITIES)
    elif scope_key in {"maximum", "custom"}:
        allowed = set(profile.entities)
    else:
        raise KeyError(f"Unknown protection scope: {scope_key}")
    return tuple(dict.fromkeys(entity for entity in profile.entities if entity in allowed))
