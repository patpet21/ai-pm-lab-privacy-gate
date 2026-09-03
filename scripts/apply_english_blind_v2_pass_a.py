from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected patch anchor not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _insert_before_once(path: Path, marker: str, insertion: str) -> None:
    text = path.read_text(encoding="utf-8")
    if insertion.strip() in text:
        return
    if marker not in text:
        raise RuntimeError(f"Expected insertion marker not found in {path}")
    path.write_text(text.replace(marker, insertion + marker, 1), encoding="utf-8")


def main() -> None:
    recognizers = ROOT / "src" / "ai_pm_lab_privacy_gate" / "infrastructure" / "pii" / "recognizers"
    english = recognizers / "english"

    # 1) Realistic secret aliases/forms, still requiring a strong label and a
    # structured secret value. Existing narrow rules remain unchanged.
    secrets = english / "secrets_pack.py"
    secret_marker = '    ContextRule(\n        "MAC_ADDRESS",'
    secret_rules = '''    # Blind-v2 Pass A: realistic aliases with strong labels and structured values.\n    ContextRule(\n        "API_KEY",\n        rf"openai[ \\t]+key{_SEP}(?P<value>sk-(?:proj-)?[A-Za-z0-9_-]{{20,}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "API_KEY",\n        rf"service[ \\t]+api[ \\t]+key{_SEP}(?P<value>api_[A-Za-z0-9_-]{{16,}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "ACCESS_TOKEN",\n        rf"access[ \\t]+token{_SEP}(?P<value>pat_(?:live|test)_[A-Za-z0-9_-]{{16,}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "JWT_TOKEN",\n        rf"(?:bearer[ \\t]+token|jwt){_SEP}(?P<value>[A-Za-z0-9_-]{{8,}}\\.[A-Za-z0-9_-]{{8,}}\\.[A-Za-z0-9_-]{{8,}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "OAUTH_SECRET",\n        rf"client[ \\t]+secret{_SEP}(?P<value>clientSecret_[A-Za-z0-9_-]{{12,}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "CLOUD_CREDENTIAL",\n        rf"cloud[ \\t]+access[ \\t]+key{_SEP}(?P<value>(?:AKIA|ASIA)[A-Z0-9]{{15,16}})\\b",\n        score=1.0,\n    ),\n    ContextRule(\n        "DATABASE_CREDENTIAL",\n        rf"mongo[ \\t]+connection{_SEP}(?P<value>mongodb(?:\\+srv)?:\\/\\/[^\\s:@/]+:[^\\s@/]+@[^\\s]+)",\n        score=1.0,\n    ),\n    ContextRule(\n        "WEBHOOK_SECRET",\n        rf"(?:webhook[ \\t]+secret|signing[ \\t]+secret){_SEP}(?P<value>whsec_[A-Za-z0-9_-]{{12,}})\\b",\n        score=1.0,\n    ),\n'''
    _insert_before_once(secrets, secret_marker, secret_rules)

    # 2) Explicit business labels commonly use '=' in tables/forms. Add it to
    # the existing contextual separators instead of creating fixture-specific rules.
    sensitive = recognizers / "real_estate_sensitive_pack.py"
    _replace_once(
        sensitive,
        '_SEP = r"\\s*(?::|#|number\\b|no\\.?\\b|ref\\.?\\b)?\\s*"',
        '_SEP = r"\\s*(?::|=|#|number\\b|no\\.?\\b|ref\\.?\\b)?\\s*"',
    )
    real_estate = recognizers / "real_estate.py"
    _replace_once(
        real_estate,
        '_LABEL_SEPARATOR = r"\\s*(?::|#|number\\b|no\\.?\\b)?\\s*"',
        '_LABEL_SEPARATOR = r"\\s*(?::|=|#|number\\b|no\\.?\\b)?\\s*"',
    )

    # Project budget is an enabled specific category but had no safe explicit
    # label rule. Add one to the precision-first safe-recall pack.
    safe_recall = english / "safe_recall.py"
    project_budget_marker = '    ContextRule(\n        "RENT_AMOUNT",'
    project_budget_rule = '''    ContextRule(\n        "PROJECT_BUDGET_AMOUNT",\n        rf"(?:project|renovation|capital)[ \\t]+budget(?:[ \\t]+amount)?\\b{_SEP}(?P<value>{_AMOUNT})",\n        score=0.998,\n    ),\n'''
    _insert_before_once(safe_recall, project_budget_marker, project_budget_rule)

    # 3) Generic schema/procedure words must never become ID/reference values.
    # 4) Technical identifier labels/currency codes must not become PERSON/ORG/LOC.
    engine = ROOT / "src" / "ai_pm_lab_privacy_gate" / "infrastructure" / "pii" / "presidio_engine.py"
    _replace_once(
        engine,
        '    "hpd complaint",\n    "housing court",',
        '    "hpd complaint",\n    "beneficiary bic",\n    "eur",\n    "gbp",\n    "itin",\n    "jwt",\n    "nyc bbl",\n    "password",\n    "usd",\n    "housing court",',
    )

    false_values_block = '''_EN_CONTEXT_VALUE_FALSE_VALUES = {\n    "INSURANCE_POLICY_ID": {"follows", "next"},\n    "INVOICE_NUMBER": {"issued", "processing", "total"},\n    "MAINTENANCE_TICKET_ID": {"management"},\n    "PASSWORD_CREDENTIAL": {"requirement", "requirements"},\n    "VEHICLE_LICENSE_PLATE": {"is ready for"},\n}\n'''
    false_values_new = false_values_block + '''_EN_SCHEMA_FALSE_VALUES = {\n    "column",\n    "columns",\n    "field",\n    "fields",\n    "format",\n    "formatting",\n    "mapping",\n    "requirement",\n    "requirements",\n    "review",\n    "workflow",\n}\n_EN_SCHEMA_VALUE_ENTITIES = {\n    "CONTRACTOR_LICENSE",\n    "INSURANCE_POLICY_ID",\n    "MAINTENANCE_TICKET_ID",\n    "PROPERTY_IDENTIFIER",\n}\n'''
    _replace_once(engine, false_values_block, false_values_new)

    _replace_once(
        engine,
        '    "PHONE_NUMBER": {"US_SSN"},',
        '    "URL": {"DATABASE_CREDENTIAL", "JWT_TOKEN"},\n    "PHONE_NUMBER": {"US_SSN"},',
    )

    filter_anchor = '''            invalid_values = _EN_CONTEXT_VALUE_FALSE_VALUES.get(entity_type)\n            if invalid_values and normalized in invalid_values:\n                continue\n\n'''
    filter_new = filter_anchor + '''            if (\n                normalized in _EN_SCHEMA_FALSE_VALUES\n                and (\n                    entity_type.endswith(("_ID", "_REFERENCE"))\n                    or entity_type in _EN_SCHEMA_VALUE_ENTITIES\n                )\n                and not re.search(r"\\d", value)\n            ):\n                continue\n\n'''
    _replace_once(engine, filter_anchor, filter_new)

    print("Applied English Blind v2 Pass A production patch.")


if __name__ == "__main__":
    main()
