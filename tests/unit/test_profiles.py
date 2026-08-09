from ai_pm_lab_privacy_gate.domain.profiles import get_profile, list_profiles


def test_three_profiles_are_available():
    profiles = list_profiles()
    assert [profile.key for profile in profiles] == [
        "property_management",
        "realtor_brokerage",
        "projects_renovations",
    ]
    assert all("US_SSN" in profile.entities for profile in profiles)
    assert get_profile("property_management").name == "Property Management"

