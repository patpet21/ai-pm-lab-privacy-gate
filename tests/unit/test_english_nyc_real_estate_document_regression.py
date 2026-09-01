from __future__ import annotations

import pytest

from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.presidio_engine import PresidioPrivacyEngine


TEXT = """Residential Lease Agreement - Synthetic Test Document
COMPLETELY FICTITIOUS DATA - FOR PRIVACYGATE TESTING ONLY
This document does not represent real people, companies, bank accounts, or properties. All data was created exclusively to validate the recognition and protection of sensitive information in an English-language NYC real estate context.
1. Parties to the lease
Landlord: Michael Romano, born in Queens, New York on March 14, 1981, residing at 142 West 81st Street, Apt 5C, New York, NY 10024. SSN: 123-45-6789. Phone: +1 (212) 555-0147. Email: michael.romano@example.com.
Tenant: Emily Carter, currently domiciled at 77-12 31st Avenue, Apt 4A, Jackson Heights, NY 11370. SSN: 987-65-4321. Phone: +1 (917) 555-0182. Email: emily.carter@example.com.
2. Property management and administrative references
Company: Hudson Bridge Property Management LLC, 350 Fifth Avenue, Suite 4800, New York, NY 10118. EIN: 12-3456789. NY DOS Entity ID: 7654321. Registration No.: 004821.
Leasing email: leases@hudsonbridgepm.example.com. Operations email: operations@hudsonbridgepm.example.com. Main line: +1 (646) 555-0120.
3. Property and NYC parcel data
The leased unit is located at 245 West 74th Street, Apartment 8B, New York, NY 10023. It is a residential two-bedroom, two-bathroom apartment.
Field Synthetic value
Borough Manhattan
Block 1165
Lot 42
BBL 1011650042
Unit 8B
ZIP Code 10023
County New York
4. Financial coordinates and payments
Dedicated rent account number: 000123456789. ABA routing number: 021000089. Monthly rent amount: USD 4,850.00. Payment memo: Rent - 245 West 74th Street Apt 8B - New York.
5. Identity documents and access credentials
New York State Driver License No.: 123 456 789. U.S. Passport No.: 123456789. Building access credential: NYC-8B-4821. Authorized vehicle plate: KNY-4821.
6. Communications and people involved
For key handover, Michael Romano will meet property manager Sarah Klein at Hudson Bridge Property Management LLC in Manhattan. Engineer Daniel Brooks will perform the move-in inspection, while the Midtown leasing team will handle lease administration.
Appendix A - Categories PrivacyGate should detect
PERSON (people)
ORGANIZATION (companies / organizations)
LOCATION (city / borough / locality)
US_SSN (Social Security Number)
US_EIN / TAX_ID (Employer Identification Number)
BANK_ACCOUNT_NUMBER / ABA_ROUTING_NUMBER
EMAIL_ADDRESS
PHONE_NUMBER
STREET_ADDRESS, ZIP_CODE, state / county
NYC property IDs: borough / block / lot / BBL / unit
US_DRIVER_LICENSE / US_PASSPORT / access credential
Vehicle license plate
NY DOS Entity ID / business registration
Recommended test procedure
Open Protect and select Document language: English.
Upload this DOCX file.
Run Scan & Protect.
Review the findings and compare them with the checklist above.
Keep all findings selected and generate the protected copy.
Verify the local Privacy Check.
Save or download the protected copy and also inspect the TXT companion.
If Reversible placeholders mode is used, finally verify Restore locally.
"""


def _surface(results):
    return {(item.entity_type, TEXT[item.start:item.end]) for item in results}


@pytest.mark.parametrize(
    "false_positive",
    [
        "Landlord",
        "Driver License",
        "EIN",
        "PHONE_NUMBER",
        "English",
        "Privacy Check",
    ],
)
def test_nyc_fixture_does_not_promote_labels_or_checklist_terms_to_people(false_positive: str) -> None:
    engine = PresidioPrivacyEngine()
    profile = get_profile("property_management")
    results = engine.analyze_page(TEXT, language="en", profile=profile)
    people = {value for entity_type, value in _surface(results) if entity_type == "PERSON"}
    assert false_positive not in people


def test_nyc_fixture_keeps_real_people_company_and_core_identifiers() -> None:
    engine = PresidioPrivacyEngine()
    profile = get_profile("property_management")
    results = engine.analyze_page(TEXT, language="en", profile=profile)
    surface = _surface(results)

    for expected in {
        ("PERSON", "Michael Romano"),
        ("PERSON", "Emily Carter"),
        ("PERSON", "Sarah Klein"),
        ("PERSON", "Daniel Brooks"),
        ("ORGANIZATION", "Hudson Bridge Property Management LLC"),
        ("US_SSN", "123-45-6789"),
        ("US_SSN", "987-65-4321"),
        ("EMAIL_ADDRESS", "michael.romano@example.com"),
        ("EMAIL_ADDRESS", "emily.carter@example.com"),
    }:
        assert expected in surface
