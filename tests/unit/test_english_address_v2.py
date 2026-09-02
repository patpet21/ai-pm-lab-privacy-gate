from __future__ import annotations

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.english.address_v2 import (
    PATTERN_RECOGNIZERS,
)


def _values(text: str) -> set[str]:
    values: set[str] = set()
    for recognizer in PATTERN_RECOGNIZERS:
        for result in recognizer.analyze(text, entities=["STREET_ADDRESS"]):
            values.add(text[result.start : result.end])
    return values


def test_address_v2_keeps_unit_floor_building_hash_and_directional_tails() -> None:
    cases = {
        "Prior address: 245 West 74th St., Apt 5B": "245 West 74th St., Apt 5B",
        "Job site: 9012 Queens Blvd., Floor 3": "9012 Queens Blvd., Floor 3",
        "Billing address: 44-05 Vernon Boulevard #2C": "44-05 Vernon Boulevard #2C",
        "Registered office: 1200 Market St., Bldg 2": "1200 Market St., Bldg 2",
        "Address: 1010 Pennsylvania Avenue NW": "1010 Pennsylvania Avenue NW",
    }
    for text, expected in cases.items():
        assert expected in _values(text)


def test_address_v2_accepts_fractional_and_alphanumeric_house_numbers() -> None:
    assert _values("Residence: 63½ Bedford Street") == {"63½ Bedford Street"}
    assert _values("Property at 12A King Street is under contract.") == {"12A King Street"}


def test_address_v2_preserves_existing_structured_city_state_zip_forms() -> None:
    assert _values(
        "Tenant address: 77-12 31st Avenue, Apt 4A, Jackson Heights, NY 11370."
    ) == {"77-12 31st Avenue, Apt 4A, Jackson Heights, NY 11370"}
    assert _values(
        "Company: 350 Fifth Avenue, Suite 4800, New York, NY 10118."
    ) == {"350 Fifth Avenue, Suite 4800, New York, NY 10118"}
    assert _values(
        "Payment memo: Rent - 245 West 74th Street Apt 8B - New York."
    ) == {"245 West 74th Street Apt 8B"}


def test_address_v2_supports_numeric_po_boxes_and_rural_routes() -> None:
    assert _values("Mailing address: P.O. Box 1842") == {"P.O. Box 1842"}
    assert _values("Forwarding address: PO Box 77B") == {"PO Box 77B"}
    assert _values("Service address: RR 2 Box 145") == {"RR 2 Box 145"}
    assert _values("Rural Route 4 Box 91") == {"Rural Route 4 Box 91"}


def test_address_v2_does_not_promote_address_vocabulary_without_an_address() -> None:
    negatives = (
        "PO Box formatting is described in the style guide.",
        "Floor 7 will be renovated next quarter.",
        "Suite testing passed in the development environment.",
        "Building 2 is ready for inspection.",
        "Route 12A is under review.",
        "The street address field is optional in this template.",
    )
    for text in negatives:
        assert _values(text) == set()
