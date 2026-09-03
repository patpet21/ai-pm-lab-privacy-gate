from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile

FROZEN_DETECTOR_SHA = "a34e5474cc94dc78ef1f640b96ae53f9da37d6ff"
EXPECTED_CASES = 180
EXPECTED_SPANS = 171
EXPECTED_NEGATIVES = 45
RELAXED_OVERLAP = 0.80
OUT_CSV = Path("build/benchmarks/english_blind_v2.csv")
OUT_JSON = Path("build/benchmarks/english_blind_v2_summary.json")

RAW_CASES: list[tuple[str, str, str, list[tuple[str, str]]]] = []


def add(case_id: str, group: str, text: str, expected: list[tuple[str, str]]) -> None:
    RAW_CASES.append((case_id, group, text, expected))


for row in (
    ("ID-001", "Please send the onboarding packet to Amina El-Sayed before close of business.", [("PERSON", "Amina El-Sayed")]),
    ("ID-002", "Primary resident contact: Liam O'Connell", [("PERSON", "Liam O'Connell")]),
    ("ID-003", "Prepared for Grace Chen-Wu", [("PERSON", "Grace Chen-Wu")]),
    ("ID-004", "The authorized signer is Marcus J. Bell.", [("PERSON", "Marcus J. Bell")]),
    ("ID-005", "Applicant name = Priya Nair", [("PERSON", "Priya Nair")]),
    ("ID-006", "Please coordinate access with Theo van Doren.", [("PERSON", "Theo van Doren")]),
    ("ID-007", "Vendor: Crescent Harbor Mechanical LLC", [("ORGANIZATION", "Crescent Harbor Mechanical LLC")]),
    ("ID-008", "Managed by Redstone Property Services Inc.", [("ORGANIZATION", "Redstone Property Services Inc.")]),
    ("ID-009", "Employer = Birchline Analytics Corp.", [("ORGANIZATION", "Birchline Analytics Corp.")]),
    ("ID-010", "The report was prepared by Westfield Engineering Company.", [("ORGANIZATION", "Westfield Engineering Company")]),
    ("ID-011", "Closing counsel: Park & Monroe LLP", [("ORGANIZATION", "Park & Monroe LLP")]),
    ("ID-012", "The inspection site is in Yonkers.", [("LOCATION", "Yonkers")]),
    ("ID-013", "Service territory: Nassau County", [("LOCATION", "Nassau County")]),
    ("ID-014", "The owner relocated to Jersey City.", [("LOCATION", "Jersey City")]),
    ("ID-015", "Forwarding address: 412 West 148th Street Apt 5D", [("STREET_ADDRESS", "412 West 148th Street Apt 5D")]),
    ("ID-016", "Mailing address = 88-12 Queens Boulevard, Suite 604", [("STREET_ADDRESS", "88-12 Queens Boulevard, Suite 604")]),
    ("ID-017", "Property address: 27 Harbor Road Unit 3A", [("STREET_ADDRESS", "27 Harbor Road Unit 3A")]),
    ("ID-018", "Send originals to 1550 Madison Avenue Floor 9.", [("STREET_ADDRESS", "1550 Madison Avenue Floor 9")]),
    ("ID-019", "Email address: operations+lease@northmail.example", [("EMAIL_ADDRESS", "operations+lease@northmail.example")]),
    ("ID-020", "Contact email = priya.nair77@example.org", [("EMAIL_ADDRESS", "priya.nair77@example.org")]),
    ("ID-021", "Mobile: +1 929-555-0146", [("PHONE_NUMBER", "+1 929-555-0146")]),
    ("ID-022", "Reach him at 718-555-0199 ext. 42", [("PHONE_NUMBER", "718-555-0199 ext. 42")]),
    ("ID-023", "Postal code: 10027-5512", [("POSTAL_CODE", "10027-5512")]),
    ("ID-024", "Apartment number: 14C", [("UNIT_NUMBER", "14C")]),
    ("ID-025", "Previous address: 903 Bedford Avenue, Apt 2R", [("STREET_ADDRESS", "903 Bedford Avenue, Apt 2R")]),
):
    add("BLIND2-" + row[0], "identity", row[1], row[2])

for row in (
    ("GOV-001", "SSN: 428-51-9036", [("US_SSN", "428-51-9036")]),
    ("GOV-002", "Social Security number = 571-22-6840", [("US_SSN", "571-22-6840")]),
    ("GOV-003", "Employee SSN # 219-63-7745", [("US_SSN", "219-63-7745")]),
    ("GOV-004", "ITIN: 934-72-6158", [("US_ITIN", "934-72-6158")]),
    ("GOV-005", "Individual taxpayer ID 912-84-3306", [("US_ITIN", "912-84-3306")]),
    ("GOV-006", "Passport number: X90817263", [("US_PASSPORT", "X90817263")]),
    ("GOV-007", "U.S. passport no. 583920174", [("US_PASSPORT", "583920174")]),
    ("GOV-008", "Passport No # C44190827", [("US_PASSPORT", "C44190827")]),
    ("GOV-009", "Driver license no. D-482-771-09", [("US_DRIVER_LICENSE", "D-482-771-09")]),
    ("GOV-010", "DL = K9027714", [("US_DRIVER_LICENSE", "K9027714")]),
    ("GOV-011", "Driver's licence: M 771 442 18", [("US_DRIVER_LICENSE", "M 771 442 18")]),
    ("GOV-012", "DOB: 04/17/1988", [("DATE_OF_BIRTH", "04/17/1988")]),
    ("GOV-013", "Date of birth = 1980-02-29", [("DATE_OF_BIRTH", "1980-02-29")]),
    ("GOV-014", "Birth date: November 21, 1976", [("DATE_OF_BIRTH", "November 21, 1976")]),
    ("GOV-015", "Applicant DOB is 7/3/1992", [("DATE_OF_BIRTH", "7/3/1992")]),
    ("GOV-016", "Employer identification number: 38-7712049", [("US_EIN", "38-7712049")]),
    ("GOV-017", "Federal tax ID = 71-5509821", [("US_EIN", "71-5509821")]),
    ("GOV-018", "Source IP: 203.0.113.84", [("IP_ADDRESS", "203.0.113.84")]),
    ("GOV-019", "Remote IP address = 192.0.2.143", [("IP_ADDRESS", "192.0.2.143")]),
    ("GOV-020", "Vehicle license plate: K82-MRT", [("VEHICLE_LICENSE_PLATE", "K82-MRT")]),
):
    add("BLIND2-" + row[0], "government", row[1], row[2])

for row in (
    ("FIN-001", "Savings account number: 883400771255", [("US_BANK_NUMBER", "883400771255")]),
    ("FIN-002", "Acct. # 001928374650", [("US_BANK_NUMBER", "001928374650")]),
    ("FIN-003", "Routing number: 026009593", [("US_ROUTING_NUMBER", "026009593")]),
    ("FIN-004", "ABA routing = 021000021", [("US_ROUTING_NUMBER", "021000021")]),
    ("FIN-005", "SWIFT/BIC: CHASUS33", [("SWIFT_BIC", "CHASUS33")]),
    ("FIN-006", "Beneficiary BIC = DEUTDEFF500", [("SWIFT_BIC", "DEUTDEFF500")]),
    ("FIN-007", "Mastercard 5555 5555 5555 4444", [("CREDIT_CARD", "5555 5555 5555 4444")]),
    ("FIN-008", "Card number: 4111-1111-1111-1111", [("CREDIT_CARD", "4111-1111-1111-1111")]),
    ("FIN-009", "Card ending in 7304", [("CARD_LAST_FOUR", "7304")]),
    ("FIN-010", "Wire amount = $63,440.25", [("MONEY_AMOUNT", "$63,440.25")]),
    ("FIN-011", "Refund amount: EUR 1,275.50", [("MONEY_AMOUNT", "EUR 1,275.50")]),
    ("FIN-012", "Payment amount USD 8,900", [("MONEY_AMOUNT", "USD 8,900")]),
    ("FIN-013", "IBAN: FR7630006000011234567890189", [("IBAN_CODE", "FR7630006000011234567890189")]),
    ("FIN-014", "Beneficiary IBAN = ES9121000418450200051332", [("IBAN_CODE", "ES9121000418450200051332")]),
    ("FIN-015", "Merchant: Harborview Pharmacy", [("MERCHANT", "Harborview Pharmacy")]),
    ("FIN-016", "Merchant name = Copper Kettle Cafe", [("MERCHANT", "Copper Kettle Cafe")]),
    ("FIN-017", "Sent funds to Jordan Pierce; memo: move-in deposit", [("COUNTERPARTY", "Jordan Pierce"), ("TRANSACTION_REFERENCE", "move-in deposit")]),
    ("FIN-018", "Transaction ID = TXN-774920-AZ", [("TRANSACTION_ID", "TXN-774920-AZ")]),
    ("FIN-019", "Statement reference: a82d6614-1f47-4bb3-bc11-82916f7aa701", [("STATEMENT_REFERENCE", "a82d6614-1f47-4bb3-bc11-82916f7aa701")]),
    ("FIN-020", "Wire confirmation ID: WIRE-2026-771205", [("WIRE_CONFIRMATION_ID", "WIRE-2026-771205")]),
    ("FIN-021", "ACH authorization reference = ACH-940551", [("ACH_AUTHORIZATION_ID", "ACH-940551")]),
    ("FIN-022", "Payment token: tok_live_82HdK44Lm90", [("PAYMENT_TOKEN", "tok_live_82HdK44Lm90")]),
    ("FIN-023", "Loan amount: $780,000", [("LOAN_AMOUNT", "$780,000")]),
    ("FIN-024", "Cash to close = $126,480.75", [("CASH_TO_CLOSE", "$126,480.75")]),
    ("FIN-025", "Outstanding loan balance: $612,944.03", [("LOAN_BALANCE", "$612,944.03")]),
):
    add("BLIND2-" + row[0], "financial", row[1], row[2])

for row in (
    ("BIZ-001", "Invoice number: INV-26-44018", [("INVOICE_NUMBER", "INV-26-44018")]),
    ("BIZ-002", "Invoice No = 88441-QT", [("INVOICE_NUMBER", "88441-QT")]),
    ("BIZ-003", "Purchase order number: PO-77128-B", [("PURCHASE_ORDER_ID", "PO-77128-B")]),
    ("BIZ-004", "PO ID = 90417-XY", [("PURCHASE_ORDER_ID", "90417-XY")]),
    ("BIZ-005", "Contract ID: CTR-2026-118", [("CONTRACT_ID", "CTR-2026-118")]),
    ("BIZ-006", "Contract reference = AGR-771902", [("CONTRACT_ID", "AGR-771902")]),
    ("BIZ-007", "Customer ID: CUST-902881", [("CUSTOMER_ID", "CUST-902881")]),
    ("BIZ-008", "Customer identifier = CL-551902", [("CUSTOMER_ID", "CL-551902")]),
    ("BIZ-009", "Employee ID: EMP-66172", [("EMPLOYEE_ID", "EMP-66172")]),
    ("BIZ-010", "Tenant ID = TEN-73188", [("TENANT_ID", "TEN-73188")]),
    ("BIZ-011", "Resident account: RES-440291", [("TENANT_ID", "RES-440291")]),
    ("BIZ-012", "Lease number: LSE-2026-5501", [("LEASE_ID", "LSE-2026-5501")]),
    ("BIZ-013", "Lease ID = L-990174", [("LEASE_ID", "L-990174")]),
    ("BIZ-014", "NYC BBL = 1008420036", [("NYC_BBL", "1008420036")]),
    ("BIZ-015", "NYC BIN: 1019927", [("NYC_BIN", "1019927")]),
    ("BIZ-016", "Monthly rent: $5,180.00", [("RENT_AMOUNT", "$5,180.00")]),
    ("BIZ-017", "Preferential rent = $3,945", [("RENT_AMOUNT", "$3,945")]),
    ("BIZ-018", "Security deposit held: $7,890", [("SECURITY_DEPOSIT_AMOUNT", "$7,890")]),
    ("BIZ-019", "Purchase price = $1,875,000", [("PURCHASE_PRICE", "$1,875,000")]),
    ("BIZ-020", "Broker commission: 3.75%", [("BROKER_COMMISSION", "3.75%")]),
    ("BIZ-021", "Contractor license number: HIC-2098417", [("CONTRACTOR_LICENSE", "HIC-2098417")]),
    ("BIZ-022", "Safe combination = 22-71-06", [("SAFE_COMBINATION", "22-71-06")]),
    ("BIZ-023", "Wi-Fi password: CedarLoft!84", [("WIFI_CREDENTIAL", "CedarLoft!84")]),
    ("BIZ-024", "Work order number: WO-2026-9918", [("WORK_ORDER_ID", "WO-2026-9918")]),
    ("BIZ-025", "Maintenance ticket ID: MT-771509", [("MAINTENANCE_TICKET_ID", "MT-771509")]),
    ("BIZ-026", "Property identifier: PROP-884102", [("PROPERTY_IDENTIFIER", "PROP-884102")]),
    ("BIZ-027", "Lockbox code: 7049#", [("LOCKBOX_CODE", "7049#")]),
    ("BIZ-028", "Building permit number: DOB-26-71884", [("PERMIT_ID", "DOB-26-71884")]),
    ("BIZ-029", "Project budget = $245,000", [("PROJECT_BUDGET_AMOUNT", "$245,000")]),
    ("BIZ-030", "Insurance claim reference: CLM-550918", [("INSURANCE_CLAIM_ID", "CLM-550918")]),
):
    add("BLIND2-" + row[0], "business_real_estate", row[1], row[2])

for row in (
    ("SEC-001", "API key: sk-live-Ab91Cd82Ef73Gh64Ij55Kl46Mn37", [("API_KEY", "sk-live-Ab91Cd82Ef73Gh64Ij55Kl46Mn37")]),
    ("SEC-002", "OpenAI key = sk-proj-Qw12Er34Ty56Ui78Op90As12Df34", [("API_KEY", "sk-proj-Qw12Er34Ty56Ui78Op90As12Df34")]),
    ("SEC-003", "Service API key: api_9F8e7D6c5B4a3A2z1Y0x", [("API_KEY", "api_9F8e7D6c5B4a3A2z1Y0x")]),
    ("SEC-004", "GitHub token: ghp_1a2B3c4D5e6F7g8H9i0J1k2L3m4N5o6P7q8R", [("ACCESS_TOKEN", "ghp_1a2B3c4D5e6F7g8H9i0J1k2L3m4N5o6P7q8R")]),
    ("SEC-005", "Access token = pat_live_Z91xY82wV73uT64sR55q", [("ACCESS_TOKEN", "pat_live_Z91xY82wV73uT64sR55q")]),
    ("SEC-006", "Bearer token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3NzEifQ.sigA12B34C", [("JWT_TOKEN", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3NzEifQ.sigA12B34C")]),
    ("SEC-007", "JWT = eyJ0eXAiOiJKV1QifQ.eyJyb2xlIjoiYWRtaW4ifQ.signature77", [("JWT_TOKEN", "eyJ0eXAiOiJKV1QifQ.eyJyb2xlIjoiYWRtaW4ifQ.signature77")]),
    ("SEC-008", "OAuth client secret = oauth_9Za8Yb7Xc6Wd5Ve4", [("OAUTH_SECRET", "oauth_9Za8Yb7Xc6Wd5Ve4")]),
    ("SEC-009", "Client secret: clientSecret_44Aa55Bb66Cc", [("OAUTH_SECRET", "clientSecret_44Aa55Bb66Cc")]),
    ("SEC-010", "AWS access key ID: AKIAQWERTYUIOPASDFGH", [("CLOUD_CREDENTIAL", "AKIAQWERTYUIOPASDFGH")]),
    ("SEC-011", "Cloud access key = AKIAZXCVBNMASDFGHJKL", [("CLOUD_CREDENTIAL", "AKIAZXCVBNMASDFGHJKL")]),
    ("SEC-012", "Database URL: postgres://appuser:StoneRiver77@db.example.invalid:5432/ledger", [("DATABASE_CREDENTIAL", "postgres://appuser:StoneRiver77@db.example.invalid:5432/ledger")]),
    ("SEC-013", "Mongo connection = mongodb://svc:DeltaPass99@mongo.example.invalid:27017/app", [("DATABASE_CREDENTIAL", "mongodb://svc:DeltaPass99@mongo.example.invalid:27017/app")]),
    ("SEC-014", "Webhook secret: whsec_7gH6fD5sA4qW3eR2tY1u", [("WEBHOOK_SECRET", "whsec_7gH6fD5sA4qW3eR2tY1u")]),
    ("SEC-015", "Signing secret = whsec_Zx98Cv76Bn54Mm32", [("WEBHOOK_SECRET", "whsec_Zx98Cv76Bn54Mm32")]),
    ("SEC-016", "MAC address: 3C:52:82:AA:19:7F", [("MAC_ADDRESS", "3C:52:82:AA:19:7F")]),
    ("SEC-017", "Device MAC = 08-00-27-12-34-56", [("MAC_ADDRESS", "08-00-27-12-34-56")]),
    ("SEC-018", "Bitcoin wallet: 1BoatSLRHtKNngkdXEeobR76b53LETtpyT", [("CRYPTO", "1BoatSLRHtKNngkdXEeobR76b53LETtpyT")]),
    ("SEC-019", "Private key:\n-----BEGIN PRIVATE KEY-----\nU29tZUZha2VCYXNlNjREYXRhMTIzNDU2Nzg5MA==\n-----END PRIVATE KEY-----", [("PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nU29tZUZha2VCYXNlNjREYXRhMTIzNDU2Nzg5MA==\n-----END PRIVATE KEY-----")]),
    ("SEC-020", "Signing material:\n-----BEGIN RSA PRIVATE KEY-----\nQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=\n-----END RSA PRIVATE KEY-----", [("PRIVATE_KEY", "-----BEGIN RSA PRIVATE KEY-----\nQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=\n-----END RSA PRIVATE KEY-----")]),
):
    add("BLIND2-" + row[0], "secrets", row[1], row[2])

for row in (
    ("MIX-001", "Tenant: Nadia Brooks\nDOB: 09/28/1987\nEmail: nadia.brooks@example.com\nPhone: 347-555-0118", [("PERSON", "Nadia Brooks"), ("DATE_OF_BIRTH", "09/28/1987"), ("EMAIL_ADDRESS", "nadia.brooks@example.com"), ("PHONE_NUMBER", "347-555-0118")]),
    ("MIX-002", "Vendor: Ironwood Restoration LLC\nInvoice number: INV-77128\nInvoice total: $14,620.80", [("ORGANIZATION", "Ironwood Restoration LLC"), ("INVOICE_NUMBER", "INV-77128"), ("INVOICE_AMOUNT", "$14,620.80")]),
    ("MIX-003", "Resident: Omar Haddad\nTenant ID: TEN-55109\nLease ID: LSE-88104\nLegal rent: $4,120", [("PERSON", "Omar Haddad"), ("TENANT_ID", "TEN-55109"), ("LEASE_ID", "LSE-88104"), ("RENT_AMOUNT", "$4,120")]),
    ("MIX-004", "Beneficiary IBAN: IT60X0542811101000000123456\nSWIFT/BIC: BPPIITRRXXX\nWire amount: EUR 35,900", [("IBAN_CODE", "IT60X0542811101000000123456"), ("SWIFT_BIC", "BPPIITRRXXX"), ("MONEY_AMOUNT", "EUR 35,900")]),
    ("MIX-005", "API key: sk-live-Zx12Cv34Bn56Mm78Qq90\nWebhook secret: whsec_55Aa66Bb77Cc\nMAC: 54:27:1E:44:AA:09", [("API_KEY", "sk-live-Zx12Cv34Bn56Mm78Qq90"), ("WEBHOOK_SECRET", "whsec_55Aa66Bb77Cc"), ("MAC_ADDRESS", "54:27:1E:44:AA:09")]),
    ("MIX-006", "Applicant Priya Shah can be reached at 646-555-0133 or priya.shah@example.net. DOB is 1989-05-14.", [("PERSON", "Priya Shah"), ("PHONE_NUMBER", "646-555-0133"), ("EMAIL_ADDRESS", "priya.shah@example.net"), ("DATE_OF_BIRTH", "1989-05-14")]),
    ("MIX-007", "Property address: 640 Riverside Drive Apt 11F\nTenant ID: TEN-88291\nSecurity deposit: $8,400", [("STREET_ADDRESS", "640 Riverside Drive Apt 11F"), ("TENANT_ID", "TEN-88291"), ("SECURITY_DEPOSIT_AMOUNT", "$8,400")]),
    ("MIX-008", "Contractor: Apex Electrical Services Inc.\nLicense no. HIC-771920\nPurchase order ID: PO-44018", [("ORGANIZATION", "Apex Electrical Services Inc."), ("CONTRACTOR_LICENSE", "HIC-771920"), ("PURCHASE_ORDER_ID", "PO-44018")]),
    ("MIX-009", "Borrower: Ethan Cole\nSSN: 364-91-5507\nLoan amount: $925,000\nCash to close: $184,220", [("PERSON", "Ethan Cole"), ("US_SSN", "364-91-5507"), ("LOAN_AMOUNT", "$925,000"), ("CASH_TO_CLOSE", "$184,220")]),
    ("MIX-010", "Customer ID CUST-77192 paid merchant Harbor Bread Co. under transaction TXN-8841-Z.", [("CUSTOMER_ID", "CUST-77192"), ("MERCHANT", "Harbor Bread Co."), ("TRANSACTION_ID", "TXN-8841-Z")]),
    ("MIX-011", "Owner: Sofia Marin\nMailing address: 31 Beacon Street Apt 6E\nPostal code: 11215", [("PERSON", "Sofia Marin"), ("STREET_ADDRESS", "31 Beacon Street Apt 6E"), ("POSTAL_CODE", "11215")]),
    ("MIX-012", "Wi-Fi password: MapleHouse#29\nLockbox code: 8114*\nSafe combination: 31-08-66", [("WIFI_CREDENTIAL", "MapleHouse#29"), ("LOCKBOX_CODE", "8114*"), ("SAFE_COMBINATION", "31-08-66")]),
    ("MIX-013", "Passport number: P77190218\nDriver license no. R-440-882-17\nDOB: January 8, 1983", [("US_PASSPORT", "P77190218"), ("US_DRIVER_LICENSE", "R-440-882-17"), ("DATE_OF_BIRTH", "January 8, 1983")]),
    ("MIX-014", "Bank account: 991200440188\nRouting number: 021300077\nCard ending in 5518", [("US_BANK_NUMBER", "991200440188"), ("US_ROUTING_NUMBER", "021300077"), ("CARD_LAST_FOUR", "5518")]),
    ("MIX-015", "Managed by Oakline Property Group LLC at 205 East 63rd Street Suite 12. Contact: Maya Patel, 917-555-0171.", [("ORGANIZATION", "Oakline Property Group LLC"), ("STREET_ADDRESS", "205 East 63rd Street Suite 12"), ("PERSON", "Maya Patel"), ("PHONE_NUMBER", "917-555-0171")]),
):
    add("BLIND2-" + row[0], "mixed", row[1], row[2])

NEGATIVES = (
    "API key rotation is documented in the security handbook.",
    "The access token policy requires approval from two reviewers.",
    "Authorization: Bearer <token-goes-here>",
    "OAuth client secret fields are disabled in this template.",
    "AWS access key ID values must not be included in support tickets.",
    "Database URL configuration is explained in the deployment guide.",
    "Webhook signing secret rotation occurs automatically.",
    "MAC address formatting uses six hexadecimal pairs.",
    "The Bitcoin address field is blank.",
    "-----BEGIN PRIVATE KEY----- is shown only as a documentation heading.",
    "Passport renewal appointments are handled by the government office.",
    "The driver license policy is under legal review.",
    "Date of birth is required on the application form.",
    "The SSN field accepts digits and hyphens.",
    "The ITIN format is described in the instructions.",
    "Federal tax ID fields are optional for this workflow.",
    "The street address field is blank.",
    "Postal code formatting is validated before submission.",
    "Invoice processing begins after manager approval.",
    "The purchase order workflow was updated.",
    "Contract ID fields are generated after signing.",
    "Customer ID mapping is maintained by the migration job.",
    "Tenant ID fields are optional in the import template.",
    "Lease number formatting changed in the new system.",
    "The rent policy was revised after annual review.",
    "Security deposit rules vary by jurisdiction.",
    "Broker commission policy follows the executed agreement.",
    "Contractor license requirements are listed on the city website.",
    "The safe combination procedure is stored in the operations manual.",
    "Wi-Fi password requirements are documented separately.",
    "Password requirements include a minimum length.",
    "Routing number fields should contain nine digits.",
    "The bank account field is masked in screenshots.",
    "IBAN validation runs before submission.",
    "SWIFT/BIC formatting is checked automatically.",
    "Merchant services training is scheduled for staff.",
    "Transaction ID columns are hidden from the printed report.",
    "The card number field should never be copied into chat.",
    "Card ending digits are displayed only on receipts.",
    "The meeting starts at 4 PM in the conference room.",
    "The policy review is scheduled for next Friday.",
    "The handbook was updated this year.",
    "The maintenance ticket field is generated by the portal.",
    "The lockbox code policy requires manager approval.",
    "The property identifier field is populated after import.",
)
for i, text in enumerate(NEGATIVES, 1):
    add(f"BLIND2-NEG-{i:03d}", "negative", text, [])


def build_cases() -> list[dict]:
    cases: list[dict] = []
    for case_id, group, text, annotations in RAW_CASES:
        expected = []
        for entity_type, value in annotations:
            if text.count(value) != 1:
                raise RuntimeError(f"{case_id}: expected value must occur exactly once: {value!r}")
            start = text.index(value)
            expected.append({"entity_type": entity_type, "value": value, "page_number": 1, "start": start, "end": start + len(value)})
        cases.append({"id": case_id, "group": group, "text": text, "expected": expected})
    return cases


def metric(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def mtext(d: dict) -> str:
    return f"P={d['precision']:.3f} R={d['recall']:.3f} F1={d['f1']:.3f} (TP={d['tp']} FP={d['fp']} FN={d['fn']})"


def overlap(a: dict, b: dict) -> float:
    if a["page_number"] != b["page_number"]:
        return 0.0
    inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    if not inter:
        return 0.0
    return inter / max(1, a["end"] - a["start"])


def gitsha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--details", action="store_true", help="print every non-perfect case")
    args = parser.parse_args()

    cases = build_cases()
    spans = sum(len(c["expected"]) for c in cases)
    negatives = sum(not c["expected"] for c in cases)
    if len(cases) != EXPECTED_CASES or spans != EXPECTED_SPANS or negatives != EXPECTED_NEGATIVES:
        raise RuntimeError(f"Frozen Blind v2 corpus changed: cases={len(cases)} spans={spans} negatives={negatives}")

    base = get_profile("general_business")
    profile = replace(base, entities=entities_for_scope(base, "maximum"))
    service = PrivacyGateService()

    total = defaultdict(int)
    groups: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    entities: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows = []
    category_hits = 0

    for case in cases:
        findings = service.analyze(service.document_from_text(case["text"]), profile, language="en")
        pred = [{"entity_type": f.entity_type, "value": f.text, "page_number": f.page_number, "start": f.start, "end": f.end, "score": round(float(f.score), 4)} for f in findings]
        expected = case["expected"]
        ek = {(e["page_number"], e["start"], e["end"], e["entity_type"]) for e in expected}
        pk = {(p["page_number"], p["start"], p["end"], p["entity_type"]) for p in pred}
        tp = len(ek & pk)
        misses = [e for e in expected if (e["page_number"], e["start"], e["end"], e["entity_type"]) not in pk]
        extras = [p for p in pred if (p["page_number"], p["start"], p["end"], p["entity_type"]) not in ek]
        fp, fn = len(extras), len(misses)
        perfect = int(fp == 0 and fn == 0)
        negative = int(not expected)
        clean = int(negative and not pred)

        total["cases"] += 1; total["expected"] += len(expected); total["tp"] += tp; total["fp"] += fp; total["fn"] += fn; total["perfect"] += perfect; total["negative"] += negative; total["negative_clean"] += clean
        g = groups[case["group"]]
        g["cases"] += 1; g["expected"] += len(expected); g["tp"] += tp; g["fp"] += fp; g["fn"] += fn; g["perfect"] += perfect; g["negative"] += negative; g["negative_clean"] += clean

        for e in expected:
            name = e["entity_type"]; entities[name]["expected"] += 1
            key = (e["page_number"], e["start"], e["end"], name)
            if key in pk: entities[name]["tp"] += 1
            else: entities[name]["fn"] += 1
            if any(p["entity_type"] == name and overlap(e, p) >= RELAXED_OVERLAP for p in pred): category_hits += 1
        for p in extras: entities[p["entity_type"]]["fp"] += 1

        rows.append({"case_id": case["id"], "group": case["group"], "tp": tp, "fp": fp, "fn": fn, "perfect": perfect, "negative_clean": clean if negative else "", "text": case["text"], "expected": json.dumps(expected, ensure_ascii=False), "predictions": json.dumps(pred, ensure_ascii=False), "misses": json.dumps(misses, ensure_ascii=False), "extras": json.dumps(extras, ensure_ascii=False)})

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    strict = metric(total["tp"], total["fp"], total["fn"])
    overlap_recall = category_hits / total["expected"] if total["expected"] else 1.0
    summary = {"git_sha": gitsha(), "frozen_detector_sha": FROZEN_DETECTOR_SHA, "cases": total["cases"], "expected_spans": total["expected"], "negative_cases": total["negative"], "strict": strict, "correct_category_overlap_recall": overlap_recall, "perfect_cases": total["perfect"], "negative_clean": total["negative_clean"], "by_group": {}, "by_entity": {}}
    for name, bucket in sorted(groups.items()):
        summary["by_group"][name] = {"cases": bucket["cases"], "expected": bucket["expected"], **metric(bucket["tp"], bucket["fp"], bucket["fn"]), "perfect": bucket["perfect"], "negative": bucket["negative"], "negative_clean": bucket["negative_clean"]}
    for name, bucket in sorted(entities.items()):
        summary["by_entity"][name] = {"expected": bucket["expected"], **metric(bucket["tp"], bucket["fp"], bucket["fn"])}
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("PrivacyGate English blind validation v2")
    print(f"Frozen detector SHA: {FROZEN_DETECTOR_SHA}")
    print(f"Run git SHA: {summary['git_sha']}")
    print(f"Cases: {total['cases']}")
    print(f"Expected spans: {total['expected']}")
    print(f"Negative/adversarial cases: {total['negative']}")
    print(f"Strict exact: {mtext(strict)}")
    print(f"Correct-category overlap recall: {overlap_recall:.3f}")
    print(f"Perfect cases: {total['perfect']}/{total['cases']}")
    print(f"Negative clean: {total['negative_clean']}/{total['negative']} ({total['negative_clean']/total['negative']:.3f})")
    print(f"CSV: {OUT_CSV}")
    print(f"Summary: {OUT_JSON}")
    print("\nBy group:")
    for name, d in summary["by_group"].items():
        suffix = f" negative-clean={d['negative_clean']}/{d['negative']}" if d["negative"] else ""
        print(f"  {name:22s} cases={d['cases']:3d} {mtext(d)}{suffix}")
    probs = [(name, d) for name, d in summary["by_entity"].items() if d["fp"] or d["fn"]]
    if probs:
        print("\nEntities with misses or false positives:")
        for name, d in probs: print(f"  {name:32s} {mtext(d)}")
    else:
        print("\nNo entity-level misses or false positives.")

    if args.details:
        print("\nCase-level details:")
        for row in rows:
            if row["fp"] or row["fn"]:
                print(f"\n[{row['case_id']}] group={row['group']} fp={row['fp']} fn={row['fn']}")
                print("TEXT:", row["text"])
                print("EXPECTED:", row["expected"])
                print("PREDICTED:", row["predictions"])
                print("EXTRAS:", row["extras"])
                print("MISSES:", row["misses"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
