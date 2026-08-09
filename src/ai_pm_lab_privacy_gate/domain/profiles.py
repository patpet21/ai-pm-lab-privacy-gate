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
)


@dataclass(frozen=True, slots=True)
class PrivacyProfile:
    key: str
    name: str
    description: str
    entities: tuple[str, ...]
    # Favor recall for a privacy gate. The user can deselect false positives
    # before export, while missed PII is harder to recover from.
    threshold: float = 0.35


_PROFILES = (
    PrivacyProfile(
        key="property_management",
        name="Property Management",
        description="Tenant, owner, vendor and property records. Includes dates and account identifiers.",
        entities=COMMON_US_ENTITIES + ("DATE_TIME",),
    ),
    PrivacyProfile(
        key="realtor_brokerage",
        name="Realtor / Brokerage",
        description="Client, transaction and brokerage documents. Includes dates and web addresses.",
        entities=COMMON_US_ENTITIES + ("DATE_TIME", "URL"),
    ),
    PrivacyProfile(
        key="projects_renovations",
        name="Projects & Renovations",
        description="Owner, contractor, subcontractor and project records. Includes dates and URLs.",
        entities=COMMON_US_ENTITIES + ("DATE_TIME", "URL"),
    ),
)


def list_profiles() -> tuple[PrivacyProfile, ...]:
    return _PROFILES


def get_profile(key: str) -> PrivacyProfile:
    for profile in _PROFILES:
        if profile.key == key:
            return profile
    raise KeyError(f"Unknown privacy profile: {key}")
