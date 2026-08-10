from ai_pm_lab_privacy_gate.domain.profiles import (
    entities_for_scope,
    get_profile,
    list_profiles,
    list_scopes,
)


def test_three_profiles_are_available():
    profiles = list_profiles()
    assert [profile.key for profile in profiles] == [
        "property_management",
        "realtor_brokerage",
        "projects_renovations",
    ]
    assert all("US_SSN" in profile.entities for profile in profiles)
    assert all("US_ROUTING_NUMBER" in profile.entities for profile in profiles)
    assert all("TENANT_ID" in profile.entities for profile in profiles)
    assert all("WORK_ORDER_ID" in profile.entities for profile in profiles)
    assert get_profile("property_management").name == "Property Management"


def test_universal_protection_scopes_are_stable_and_deduplicated():
    profile = get_profile("property_management")
    assert [scope.key for scope in list_scopes()] == [
        "essential",
        "financial",
        "business",
        "maximum",
        "custom",
    ]
    financial = entities_for_scope(profile, "financial")
    assert "PERSON" in financial
    assert "MONEY_AMOUNT" in financial
    assert "CARD_TRANSACTION_ID" in financial
    assert "DATE_TIME" not in financial
    assert len(financial) == len(set(financial))
