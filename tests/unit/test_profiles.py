from ai_pm_lab_privacy_gate.domain.profiles import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_SCOPE_KEY,
    GENERAL_CORE_ENTITIES,
    entities_for_scope,
    get_profile,
    list_profiles,
    list_scopes,
)


def test_professional_profiles_are_available():
    profiles = list_profiles()
    assert [profile.key for profile in profiles] == [
        "general_business",
        "property_management",
        "realtor_brokerage",
        "projects_renovations",
        "construction",
        "legal",
        "healthcare_general",
    ]
    assert profiles[0].key == DEFAULT_PROFILE_KEY
    assert get_profile(DEFAULT_PROFILE_KEY).name == "General — Recommended"
    assert all("US_SSN" in profile.entities for profile in profiles)
    assert all("US_ROUTING_NUMBER" in profile.entities for profile in profiles)
    assert get_profile("property_management").name == "Property Management"
    assert get_profile("construction").name == "Construction"
    assert "not a substitute" in get_profile("healthcare_general").description.lower()


def test_general_recommended_is_a_true_universal_core():
    general = get_profile(DEFAULT_PROFILE_KEY)
    property_management = get_profile("property_management")

    assert general.entities == GENERAL_CORE_ENTITIES
    assert "PERSON" in general.entities
    assert "ORGANIZATION" in general.entities
    assert "EMAIL_ADDRESS" in general.entities
    assert "US_ROUTING_NUMBER" in general.entities
    assert "CONTRACT_ID" in general.entities
    assert "DATE_TIME" in general.entities

    # Vertical-only real-estate identifiers stay out of the universal default.
    assert "TENANT_ID" not in general.entities
    assert "LEASE_ID" not in general.entities
    assert "NYC_BBL" not in general.entities
    assert "UNIT_NUMBER" not in general.entities
    assert "RENT_AMOUNT" not in general.entities

    # Vertical profiles extend, rather than replace, the universal core.
    assert set(general.entities).issubset(property_management.entities)
    assert "TENANT_ID" in property_management.entities
    assert "NYC_BBL" in property_management.entities
    assert "RENT_AMOUNT" in property_management.entities

    assert all(len(profile.entities) == len(set(profile.entities)) for profile in list_profiles())


def test_universal_protection_scopes_are_stable_and_deduplicated():
    profile = get_profile("property_management")
    assert [scope.key for scope in list_scopes()] == [
        "essential",
        "financial",
        "business",
        "maximum",
        "custom",
    ]
    assert DEFAULT_SCOPE_KEY == "maximum"

    financial = entities_for_scope(profile, "financial")
    assert "PERSON" in financial
    assert "MONEY_AMOUNT" in financial
    assert "CARD_TRANSACTION_ID" in financial
    assert "DATE_TIME" not in financial
    assert len(financial) == len(set(financial))

    maximum = entities_for_scope(profile, DEFAULT_SCOPE_KEY)
    assert maximum == profile.entities
