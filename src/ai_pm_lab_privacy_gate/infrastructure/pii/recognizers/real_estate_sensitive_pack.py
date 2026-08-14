from __future__ import annotations

from presidio_analyzer import RecognizerRegistry

from ai_pm_lab_privacy_gate.infrastructure.pii.recognizers.real_estate import (
    ContextRule,
    ContextValueRecognizer,
)


_SEP = r"\s*(?::|#|number\b|no\.?\b|ref\.?\b)?\s*"
_ID = r"[A-Z0-9][A-Z0-9./-]{2,39}"
_AMOUNT = r"(?:[-+]?\s*(?:USD\s*|[$€£]\s*)?\d[\d,]*(?:\.\d{1,2})?\s*(?:[KMB]|USD|EUR|GBP)?|\(\s*[$€£]?\s*\d[\d,]*(?:\.\d{1,2})?\s*\))"
_DATE = r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Z][a-z]{2,8}\s+\d{1,2}(?:,?\s+\d{4})?(?:\s*-\s*\d{1,2})?)"
_RATE_OR_AMOUNT = rf"(?:\d{{1,3}}(?:\.\d+)?\s*%|\d{{1,3}}\s*/\s*\d{{1,3}}\s+split|one\s+month(?:'s)?\s+rent|{_AMOUNT})"


# Expansion helpers for credentials, financing, screening and project records.
_PERCENT = r"(?:\d{1,3}(?:\.\d{1,3})?\s*%)"
_RATIO = r"(?:\d{1,3}(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*[:/]\s*\d+(?:\.\d+)?)"
_SECRET = r"(?=\S{4,128})(?=.*[A-Za-z0-9])[^\s,;]{4,128}"
_SHORT_SECRET = r"(?=[A-Z0-9#*._-]*\d)[A-Z0-9#*._-]{3,32}"
_SECRET_END = r"(?=$|[\s,;.)\]\}])"
_USERNAME = r"[A-Z0-9._@+-]{3,100}"
_PLATE = r"[A-Z0-9][A-Z0-9 -]{1,10}[A-Z0-9]"
_SCORE = r"(?:[3-8]\d{2})"


# These are deliberately label/context-driven. Standalone words such as CAPEX,
# reserve, inspection or commission are not treated as sensitive values.
CONTEXT_RULES = (
    ContextRule("SECURITY_CODE", rf"(?:alarm|disarm|security(?:\s+panel)?|panic|arm)\s+(?:code|pin)\b{_SEP}(?P<value>(?=[A-Z0-9#*-]*\d)[A-Z0-9#*-]{{3,16}})\b"),
    ContextRule("UTILITY_METER_ID", rf"(?:electric|gas|water|utility)?\s*meter\s*(?:id|sn|serial|number|no\.?|#){_SEP}(?P<value>{_ID})\b"),
    ContextRule("HOUSING_ASSISTANCE_ID", rf"(?:section\s*8\s+voucher|housing\s+assistance|rental\s+assistance|subsidy|program\s+client|hra(?:\s+case)?)\s*(?:id|case|number|no\.?|ref\.?)?\b{_SEP}(?P<value>{_ID})\b"),
    ContextRule("LEASE_OCCUPANCY_DATE", rf"(?:lease\s+(?:start|end|expiration|expires|renewal|commencement)|move[- ]?in|move[- ]?out|occupancy\s+date|renewal\s+date)\b{_SEP}(?P<value>{_DATE})\b", score=0.94),
    ContextRule("RENT_AMOUNT", rf"(?:monthly|legal|preferential|contract|asking)?\s*rent(?:\s+amount)?\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("TENANT_BALANCE", rf"(?:(?:tenant|resident)\s+balance|rent\s+arrears|arrears|past\s+due|delinquency|outstanding)\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("SECURITY_DEPOSIT_AMOUNT", rf"(?:security|tenant|additional)?\s*deposit(?:\s+held|\s+balance)?\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("OWNER_DISTRIBUTION", rf"(?:owner\s+(?:distribution|draw|proceeds)|net\s+remittance|payable\s+to\s+owner)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("OPERATING_BALANCE", rf"(?:operating\s+(?:balance|cash)|ending\s+operating\s+cash|bank\s+balance|cash\s+available)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("RESERVE_BALANCE", rf"(?:(?:replacement|operating|cap\s*ex|tax|insurance|project)\s+reserve|reserve\s+balance)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("NOI_AMOUNT", rf"(?:projected\s+|trailing\s+|annual\s+|t-?12\s+)?(?:noi|net\s+operating\s+income)(?:\s+\d{{4}})?\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("CAPEX_BUDGET_AMOUNT", rf"(?:approved\s+)?(?:cap\s*ex|capital\s+(?:expenditures?|improvements?))(?:\s+budget|\s+reserve)?(?:\s+\d{{4}})?\b(?:\s*[^\w$€£]{{0,3}}\s*){_SEP}(?P<value>(?!20\d{{2}}\b){_AMOUNT})"),
    ContextRule("REMAINING_CAPITAL_BUDGET", rf"(?:remaining\s+(?:capital\s+)?budget|budget\s+remaining|uncommitted\s+cap\s*ex|available\s+capital)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("CONTINGENCY_AMOUNT", rf"(?:(?:construction|project|renovation)\s+)?contingency(?:\s+(?:allowance|reserve))?(?:\s*=)?\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("CONTRACTOR_BID_AMOUNT", rf"(?:proposal\s+total|contractor\s+bid|bid\s+amount|estimated\s+cost|quoted\s+price|lump\s+sum)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("CHANGE_ORDER_AMOUNT", rf"(?:change\s+order|proposed\s+change|pco|co-\d+)[^\r\n:$€£]{{0,30}}(?:\s*:\s*|\s+(?:add|deduct|credit)\s+)(?P<value>{_AMOUNT})"),
    ContextRule("INVOICE_AMOUNT", rf"(?:invoice\s+total|amount\s+due|current\s+billing|total\s+due|balance\s+due|retainage\s+payable)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("PURCHASE_ORDER_VALUE", rf"(?:po\s+(?:value|amount|total)|purchase\s+order\s+total|authorized\s+po\s+amount)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("OFFER_PRICE", rf"(?:offer\s+price|buyer\s+(?:offer|counter)|counteroffer|best\s+(?:and|&)\s+final|bid\s+price|acquisition\s+offer)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("PURCHASE_PRICE", rf"(?:purchase|contract|sale|acquisition|agreed|closing)\s+price\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("EARNEST_MONEY_AMOUNT", rf"(?:earnest\s+money|emd|contract\s+deposit|good[- ]faith\s+deposit|down\s+payment)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("BROKER_COMMISSION", rf"(?:broker\s+commission|commission|broker\s+fee|listing\s+side|buyer\s+side|co-?broke|referral\s+fee|split)\b{_SEP}(?P<value>{_RATE_OR_AMOUNT})"),
    ContextRule("CLOSING_CREDIT", rf"(?:(?:seller|closing|repair)\s+(?:credit|concession)|credit\s+at\s+closing)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("ESCROW_AMOUNT", rf"(?:escrow\s+(?:holdback|balance)|repair\s+escrow|tax\s+escrow|funds\s+held\s+in\s+escrow)\b{_SEP}(?P<value>{_AMOUNT})"),
    ContextRule("MANAGEMENT_FEE", rf"(?:(?:property|construction|asset)\s+management\s+fee|management\s+fee|pm\s+fee|leasing\s+fee|cm\s+fee)\b{_SEP}(?P<value>{_RATE_OR_AMOUNT})"),
    ContextRule("MAINTENANCE_TICKET_ID", rf"(?:maintenance\s+ticket|maintenance\s+request|service\s+request|ticket|case)\s*(?:id|number|no\.?|#)?\b{_SEP}(?P<value>{_ID})\b", score=0.94),
    ContextRule("PROJECT_JOB_CODE", rf"(?:project\s+(?:code|id)|job\s+(?:id|number|no\.?|#)|cap\s*ex\s+project|renovation\s+code)\b{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b"),
    ContextRule("KEY_ACCESS_INSTRUCTION", r"(?:spare\s+)?(?:key|fob|lockbox|access\s+card)\s+(?:is\s+)?(?P<value>(?:taped|stored|located|hidden|kept|inside|under|behind|in|at|beside|above|below)\b[^\r\n.;]{3,100})", score=0.96),
    ContextRule("HOUSING_LEGAL_CASE_ID", rf"(?:housing\s+court\s+index|eviction\s+case|legal\s+matter|lt\s+index|docket)\b{_SEP}(?P<value>{_ID})\b"),
    ContextRule("NYC_DOB_JOB_ID", rf"(?:dob(?:\s+now)?\s+(?:job|filing)|filing\s+(?:id|number|no\.?))\b{_SEP}(?P<value>{_ID})\b", score=0.91),
    ContextRule("NYC_HPD_RECORD_ID", rf"(?:hpd\s+(?:complaint|registration)|violation)\s*(?:id|number|no\.?|#)?\b{_SEP}(?P<value>{_ID})\b", score=0.91),
    ContextRule("INSPECTION_ACCESS_WINDOW", rf"(?:access\s+window|unit\s+inspection|inspection\s+time|showing\s+time|contractor\s+access|appointment)\b{_SEP}(?P<value>[^\r\n.;]{{3,60}}(?:AM|PM))", score=0.92),
    ContextRule("VACANCY_OCCUPANCY_DATE", rf"(?:vacant\s+as\s+of|vacancy\s+date|possession\s+date|unit\s+empty\s+from|turnover\s+date|vacant\s+from|will\s+be\s+(?:vacant|empty))\b{_SEP}(?P<value>{_DATE})", score=0.92),
    ContextRule("APPROVAL_AUTH_CODE", rf"(?:approval\s+code|authorization\s+(?:ref\.?|code)|auth\s+code|exception\s+id|release\s+code)\b{_SEP}(?P<value>{_ID})\b"),

    # ---- Privacy Gate Real Estate expansion v2: high-value sensitive data ----
    # Variants observed in property-management statements and synthetic test packets.
    ContextRule("RENT_AMOUNT", rf"(?:scheduled\s+rent|gross\s+(?:residential\s+)?rent|rent\s+collected(?:\s+to\s+date)?|collected\s+rent|market\s+rent|proposed\s+rent)\b{_SEP}(?P<value>{_AMOUNT})", score=0.975),
    ContextRule("TENANT_BALANCE", rf"(?:delinquency|arrears|past\s+due)(?:\s+(?:total|totals|amount|balance|due))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("SECURITY_DEPOSIT_AMOUNT", rf"(?:security|tenant|additional)?\s*deposits?(?:\s+(?:held|balance|total|amount))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("RESERVE_BALANCE", rf"(?:minimum\s+)?(?:operating|replacement|cap\s*ex|project|tax|insurance)?\s*reserve\s+(?:target|minimum|requirement|balance|available)\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("ACCOUNTS_PAYABLE_AMOUNT", rf"(?:accounts\s+payable(?:\s+(?:due|balance|total|outstanding))?|a/?p\s+(?:due|balance|total|outstanding))\b{_SEP}(?P<value>{_AMOUNT})", score=0.975),
    ContextRule("COMMITTED_COST_AMOUNT", rf"(?:approved\s+)?(?:maintenance|capital|project|vendor)?\s*commitments?(?:\s+(?:amount|total|outstanding))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("WIFI_CREDENTIAL", rf"(?:wi[- ]?fi|wireless|wlan)(?:\s*\([^\r\n)]{{1,40}}\))?\s+(?P<value>[A-Z0-9._-]{{3,64}})\s*/\s*(?=(?:password|passphrase|pwd)\b)", score=0.995),
    ContextRule("PORTAL_USERNAME", rf"(?:camera(?:/nvr)?|nvr|building\s+portal|management\s+portal)\s+(?:administrator|admin|user|username|login)\b{_SEP}(?P<value>{_USERNAME})\b", score=0.975),
    ContextRule("TENANT_INCOME_AMOUNT", rf"(?im)^\s*[A-Z][A-Za-z0-9&.'’ -]{{2,80}}\s*/\s*(?P<value>{_AMOUNT})\s+(?=(?:[A-Z][A-Za-z&.'’ -]{{1,60}}\s+)?(?:Bank|Credit\s+Union|Federal|Community|N\.A\.|ABA|Acct\.?|Account)\b)", score=0.94),

    # Payment/card authentication.
    ContextRule("CARD_SECURITY_CODE", rf"(?:cvv2?|cvc2?|cid|card\s+security\s+code|card\s+verification\s+(?:value|code))\b{_SEP}(?P<value>\d{{3,4}})\b", score=0.999),
    ContextRule("PAYMENT_TOKEN", rf"(?:payment|card|gateway|processor|billing)\s+(?:token|token\s+id|tokenized\s+(?:card\s+)?ref(?:erence)?)\b{_SEP}(?P<value>[A-Z0-9][A-Z0-9._/-]{{5,80}})\b", score=0.998),
    ContextRule("ACH_AUTHORIZATION_ID", rf"(?:ach\s+(?:authorization|authorisation|auth|mandate|debit\s+authorization)|debit\s+mandate)(?:\s+(?:id|reference|ref\.?|number|no\.?))?\b{_SEP}(?P<value>(?=[A-Z0-9._/-]*\d)[A-Z0-9][A-Z0-9._/-]{{4,80}})\b", score=0.998),
    ContextRule("WIRE_CONFIRMATION_ID", rf"(?:wire\s+(?:confirmation|reference|trace)|fedwire\s+(?:reference|trace)|imad|omad)(?:\s+(?:id|number|no\.?))?\b{_SEP}(?P<value>(?=[A-Z0-9._/-]*\d)[A-Z0-9][A-Z0-9._/-]{{5,80}})\b", score=0.996),

    # Passwords, sessions and device/authentication artifacts.
    ContextRule("WIFI_CREDENTIAL", rf"(?:wi[- ]?fi|wireless|wlan)(?:\s*\([^\r\n)]{{1,40}}\))?[^\r\n]{{0,50}}?\b(?:password|passphrase|passcode|pwd)\b{_SEP}(?P<value>{_SECRET}){_SECRET_END}", score=0.999),
    ContextRule("PASSWORD_CREDENTIAL", rf"(?:temporary\s+|temp\s+|admin(?:istrator)?\s+|portal\s+|login\s+|account\s+|system\s+|camera(?:/nvr)?\s+|nvr\s+)?(?:password|passphrase|pwd)\b{_SEP}(?P<value>{_SECRET}){_SECRET_END}", score=0.998),
    ContextRule("PORTAL_USERNAME", rf"(?:portal|login|account|admin(?:istrator)?|camera(?:/nvr)?|nvr)\s+(?:username|user\s*id|login)\b{_SEP}(?P<value>{_USERNAME})\b", score=0.97),
    ContextRule("AUTH_SESSION_ID", rf"(?:verification|identity\s+verification|authentication|auth|login)\s+session(?:\s+(?:id|identifier|reference|ref\.?))?\b{_SEP}(?P<value>(?=[A-Z0-9._/-]*\d)[A-Z0-9][A-Z0-9._/-]{{5,100}})\b", score=0.998),
    ContextRule("DEVICE_FINGERPRINT", rf"(?:device\s+fingerprint|browser\s+fingerprint|device\s+id|device\s+identifier)\b{_SEP}(?P<value>(?=[A-Z0-9._:/-]*\d)[A-Z0-9][A-Z0-9._:/-]{{5,100}})\b", score=0.996),
    ContextRule("MFA_RECOVERY_CODE", rf"(?:(?:mfa|2fa|two[- ]factor)\s+(?:recovery|backup)\s+code|recovery\s+code)\b{_SEP}(?P<value>{_SHORT_SECRET}){_SECRET_END}", score=0.999),
    ContextRule("SAFE_COMBINATION", rf"(?:safe|vault|key\s+safe)\s+(?:combination|combo|code|pin)\b{_SEP}(?P<value>{_SHORT_SECRET}){_SECRET_END}", score=0.999),

    # Tenant screening / application / household financial data.
    ContextRule("APPLICATION_ID", rf"(?:rental|tenant|resident|lease|housing)?\s*application(?:\s+(?:id|identifier|number|no\.?|reference|ref\.?))\b{_SEP}(?P<value>{_ID})\b", score=0.98),
    ContextRule("SCREENING_REFERENCE", rf"(?:tenant\s+screening|resident\s+screening|background\s+(?:check|screening)|credit\s+screening|screening\s+report)(?:\s+(?:id|reference|ref\.?|number|no\.?))?\b{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b", score=0.985),
    ContextRule("CREDIT_SCORE", rf"(?:fico(?:\s+score)?|credit\s+score|screening\s+credit\s+score)\b{_SEP}(?P<value>{_SCORE})\b", score=0.995),
    ContextRule("TENANT_INCOME_AMOUNT", rf"(?:(?:tenant|resident|applicant|borrower|household)\s+)?(?:annual\s+|gross\s+|monthly\s+)?(?:income|salary|wages|employment\s+income)\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("TENANT_INCOME_AMOUNT", rf"(?:employer|employed\s+by)[^\r\n/]{{2,80}}/\s*(?P<value>{_AMOUNT})", score=0.965),
    ContextRule("HOUSING_ASSISTANCE_AMOUNT", rf"(?:section\s*8|voucher|housing\s+assistance|rental\s+assistance|subsidy)(?:\s+(?:amount|payment|share|portion|benefit))\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("VEHICLE_LICENSE_PLATE", rf"(?:vehicle\s+)?(?:license\s+plate|plate(?:\s+(?:number|no\.?))?|tag\s+number)\b{_SEP}(?P<value>{_PLATE})\b", score=0.97),

    # Lease economics and owner/property cash position.
    ContextRule("RENT_CONCESSION_AMOUNT", rf"(?:rent\s+concession|lease\s+concession|free\s+rent\s+value|concession\s+amount|rent\s+credit)\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("PAYMENT_PLAN_AMOUNT", rf"(?:payment\s+plan|repayment\s+plan|arrears\s+plan|installment\s+plan)(?:\s+(?:amount|payment|installment))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("LATE_FEE_AMOUNT", rf"(?:late\s+fee|late\s+charge|returned\s+(?:ach|check)\s+fee|nsf\s+fee)\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("PROPERTY_TAX_AMOUNT", rf"(?:property|real\s+estate)\s+tax(?:es)?(?:\s+(?:due|amount|balance|annual))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("INSURANCE_PREMIUM_AMOUNT", rf"(?:property|liability|umbrella|hazard|building)?\s*insurance\s+premium(?:\s+(?:amount|annual|monthly))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.975),

    # Mortgage, financing and transaction economics.
    ContextRule("LOAN_AMOUNT", rf"(?:mortgage|loan|financing)\s+(?:amount|proceeds|principal)\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("LOAN_BALANCE", rf"(?:outstanding\s+principal|loan\s+balance|mortgage\s+balance|principal\s+balance|payoff\s+balance)\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("DEBT_SERVICE_AMOUNT", rf"(?:monthly|annual)?\s*(?:debt\s+service|mortgage\s+payment|loan\s+payment)\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("INTEREST_RATE", rf"(?:mortgage|loan|note|financing)?\s*(?:interest\s+rate|note\s+rate|coupon\s+rate|apr)\b{_SEP}(?P<value>{_PERCENT})", score=0.985),
    ContextRule("LTV_RATIO", rf"(?:ltv|loan[- ]to[- ]value|combined\s+ltv|cltv)\b{_SEP}(?P<value>{_RATIO})", score=0.975),
    ContextRule("PREAPPROVAL_AMOUNT", rf"(?:pre[- ]?approval|prequalification|pre[- ]?qual)(?:\s+(?:amount|limit|up\s+to))\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("CASH_TO_CLOSE", rf"(?:cash\s+to\s+close|funds\s+to\s+close|buyer\s+cash\s+required)\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("CLOSING_COST_AMOUNT", rf"(?:estimated\s+|buyer\s+|seller\s+)?closing\s+costs?(?:\s+(?:amount|total))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("BUYER_BUDGET_AMOUNT", rf"(?:buyer|client|purchaser)(?:'s)?\s+(?:maximum\s+|max\s+|target\s+)?(?:budget|buying\s+power|price\s+limit)\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("SELLER_NET_PROCEEDS", rf"(?:seller\s+net|net\s+to\s+seller|seller\s+proceeds|estimated\s+net\s+proceeds)\b{_SEP}(?P<value>{_AMOUNT})", score=0.99),
    ContextRule("NEGOTIATION_LIMIT_AMOUNT", rf"(?:walk[- ]away\s+price|minimum\s+acceptable\s+price|seller\s+floor|buyer\s+ceiling|max(?:imum)?\s+offer|negotiation\s+(?:floor|ceiling|limit))\b{_SEP}(?P<value>{_AMOUNT})", score=0.995),
    # Intentionally excludes the generic public label "listing price".
    ContextRule("INTERNAL_VALUATION_AMOUNT", rf"(?:internal\s+(?:valuation|value|estimate)|broker\s+opinion\s+of\s+value|bov|confidential\s+valuation|underwriting\s+value|acquisition\s+value)\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),

    # Renovation / construction / procurement economics and identifiers.
    ContextRule("PROJECT_BUDGET_AMOUNT", rf"(?:(?:project|renovation|construction|turnover|scope)\s+budget|total\s+project\s+budget|approved\s+project\s+budget)\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("RETAINAGE_AMOUNT", rf"(?:retainage|retention)(?:\s+(?:amount|held|balance|payable|due))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("PAY_APPLICATION_AMOUNT", rf"(?:pay\s+application|payment\s+application|application\s+for\s+payment|pay\s+app)(?:\s+(?:amount|current\s+payment|total))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.985),
    ContextRule("SUBCONTRACT_AMOUNT", rf"(?:subcontract|subcontractor\s+contract)(?:\s+(?:amount|value|total|sum))\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("LABOR_RATE", rf"(?:labor|labour|technician|mechanic|electrician|plumber|carpenter|superintendent|foreman)\s+(?:rate|hourly\s+rate|billing\s+rate)\b{_SEP}(?P<value>{_AMOUNT}(?:\s*/\s*(?:hr|hour))?)", score=0.97),
    ContextRule("MATERIAL_ALLOWANCE_AMOUNT", rf"(?:material|fixture|appliance|finish|flooring|cabinet|lighting)\s+allowance(?:\s+(?:amount|budget))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.97),
    ContextRule("PERMIT_ID", rf"(?:(?:building|construction|electrical|plumbing|mechanical|work)\s+)?permit(?:\s+(?:id|number|no\.?|#|reference|ref\.?))?{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b", score=0.96),
    ContextRule("LIEN_WAIVER_ID", rf"(?:lien\s+waiver|lien\s+release|conditional\s+waiver|unconditional\s+waiver)(?:\s+(?:id|reference|ref\.?|number|no\.?))?{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b", score=0.965),
    ContextRule("COI_REFERENCE", rf"(?:certificate\s+of\s+insurance|coi)(?:\s+(?:id|reference|ref\.?|number|no\.?))?{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b", score=0.965),
    ContextRule("INSURANCE_CLAIM_AMOUNT", rf"(?:insurance\s+)?claim(?:\s+(?:amount|reserve|paid|settlement))\b{_SEP}(?P<value>{_AMOUNT})", score=0.98),
    ContextRule("INSURANCE_DEDUCTIBLE_AMOUNT", rf"(?:insurance\s+|policy\s+)?deductible(?:\s+(?:amount))?\b{_SEP}(?P<value>{_AMOUNT})", score=0.975),

    # Brokerage/title file identifiers that are usually internal rather than public MLS data.
    ContextRule("TITLE_FILE_ID", rf"(?:title\s+(?:file|order|case)|title\s+company\s+file)(?:\s+(?:id|number|no\.?|reference|ref\.?))?\b{_SEP}(?P<value>(?=[A-Z0-9./-]*\d){_ID})\b", score=0.97),
    ContextRule("LISTING_AGREEMENT_ID", rf"(?:listing\s+agreement|exclusive\s+listing|buyer\s+agency\s+agreement)(?:\s+(?:id|number|no\.?|reference|ref\.?))\b{_SEP}(?P<value>{_ID})\b", score=0.965),

)


def install_real_estate_sensitive_pack_recognizers(registry: RecognizerRegistry) -> None:
    for rule in CONTEXT_RULES:
        registry.add_recognizer(ContextValueRecognizer(rule))
