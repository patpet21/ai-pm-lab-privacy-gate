from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected anchor not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_once(path: Path, anchor: str, insertion: str) -> None:
    text = path.read_text(encoding="utf-8")
    if insertion.strip() in text:
        return
    if anchor not in text:
        raise SystemExit(f"Expected insertion anchor not found in {path}: {anchor[:120]!r}")
    path.write_text(text.replace(anchor, insertion + anchor, 1), encoding="utf-8")


def main() -> int:
    guardrails = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/english/guardrails.py"
    safe_recall = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/english/safe_recall.py"
    real_estate = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/real_estate.py"
    sensitive = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/real_estate_sensitive_pack.py"
    engine = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/presidio_engine.py"

    # 1) Label separators must never consume the next document line.
    replace_once(
        safe_recall,
        '_SEP = r"\\s*(?::|#|=|[-–—])?\\s*"\n_REQ_SEP = r"\\s*(?::|#|=|[-–—])\\s*"',
        '_SEP = r"[ \\t]*(?::|#|=|[-–—])?[ \\t]*"\n_REQ_SEP = r"[ \\t]*(?::|#|=|[-–—])[ \\t]*"',
    )
    replace_once(
        real_estate,
        '_LABEL_SEPARATOR = r"\\s*(?::|=|#|number\\b|no\\.?\\b)?\\s*"',
        '_LABEL_SEPARATOR = r"[ \\t]*(?::|=|#|number\\b|no\\.?\\b)?[ \\t]*"',
    )
    replace_once(
        sensitive,
        '_SEP = r"\\s*(?::|=|#|number\\b|no\\.?\\b|ref\\.?\\b)?\\s*"',
        '_SEP = r"[ \\t]*(?::|=|#|number\\b|no\\.?\\b|ref\\.?\\b)?[ \\t]*"',
    )
    replace_once(
        sensitive,
        '_ID = r"[A-Z0-9][A-Z0-9./-]{2,39}"',
        '_ID = r"(?=[A-Z0-9./-]*\\d)[A-Z0-9][A-Z0-9./-]{2,39}"',
    )
    replace_once(
        sensitive,
        '_AMOUNT = r"(?:[-+]?\\s*(?:USD[ \\t]*|[$€£][ \\t]*)?\\d[\\d,]*(?:\\.\\d{1,2})?(?:[ \\t]*(?:[KMB]|USD|EUR|GBP))?|\\([ \\t]*[$€£]?[ \\t]*\\d[\\d,]*(?:\\.\\d{1,2})?[ \\t]*\\))"',
        '_AMOUNT = r"(?:[-+]?[ \\t]*(?:USD[ \\t]*|[$€£][ \\t]*)?\\d[\\d,]*(?:\\.\\d{1,2})?(?:[ \\t]*(?:[KMB]|USD|EUR|GBP))?|\\([ \\t]*[$€£]?[ \\t]*\\d[\\d,]*(?:\\.\\d{1,2})?[ \\t]*\\))"',
    )

    # 2) PO must be a complete label, not the prefix of POL-xxxx policy IDs.
    replace_once(
        safe_recall,
        'rf"(?:purchase\\s+order|p\\.?\\s*o\\.?)\\s*(?:number|no\\.?|id)?{_SEP}(?P<value>{_ID})\\b",',
        'rf"(?:purchase[ \\t]+order|p\\.?[ \\t]*o\\.?){_LABEL_END}[ \\t]*(?:number|no\\.?|id)?{_SEP}(?P<value>{_ID})\\b",',
    )

    # 3) Recover people from explicit business-role fields after rejecting bad multiline NER spans.
    old_roles = (
        'rf"(?:tenant|resident|applicant|borrower|buyer|seller|managing\\s+member|emergency\\s+contact|broker\\s+contact|contact\\s+person|requested\\s+by|approved\\s+by|assigned\\s+to|submitted\\s+by|prepared\\s+by)\\b\\s*[:#-]?\\s*(?P<value>{_PERSON_NAME})(?=\\s*(?:[,;|/]|\\r?$|\\b(?:email|phone|tenant\\s+id|resident\\s+id|dob)\\b))",'
    )
    new_roles = (
        'rf"(?:resident\\s+contact|tenant|resident|applicant|borrower|buyer|seller|guarantor|insured|technician|project\\s+manager|authorized\\s+signer|administrator|superintendent|managing\\s+member|emergency\\s+contact|broker\\s+contact|contact\\s+person|requested\\s+by|approved\\s+by|assigned\\s+to|submitted\\s+by|prepared\\s+by)\\b[ \\t]*[:#-]?[ \\t]*(?P<value>{_PERSON_NAME})(?=[ \\t]*(?:[,;|/]|\\r?$|\\b(?:email|phone|tenant\\s+id|resident\\s+id|dob)\\b))",'
    )
    replace_once(real_estate, old_roles, new_roles)

    guard_constants_anchor = '_PROCEDURE_LINE_RE = re.compile(\n'
    guard_constants = '''_DOCUMENT_HEADING_TERMS = {\n    "application",\n    "controls",\n    "coordination",\n    "follow-up",\n    "form",\n    "glossary",\n    "handout",\n    "instructions",\n    "intake",\n    "memo",\n    "note",\n    "reconciliation",\n    "record",\n    "report",\n    "routing",\n    "schedule",\n    "sheet",\n    "snapshot",\n    "summary",\n    "template",\n    "worksheet",\n}\n_FIELD_LABEL_MARKERS = {\n    "access",\n    "account",\n    "address",\n    "amount",\n    "code",\n    "contact",\n    "email",\n    "id",\n    "number",\n    "phone",\n    "proceeds",\n}\n_MULTILINE_NER_NEXT_FIELD_RE = re.compile(\n    r"^(?:applicant|tenant|resident|contact|design|insurance|project|phone|email|vendor|"\n    r"contractor|employee|customer|broker|property|lease|invoice|policy|claim|mobile|"\n    r"mailing|forwarding|service|site|administrator|work|unit|safe|lockbox)\\b",\n    re.IGNORECASE,\n)\n'''
    insert_once(guardrails, guard_constants_anchor, guard_constants)

    structure_anchor = '    if _SCHEMA_LABEL_RE.fullmatch(raw):\n        return True\n'
    structure_insert = '''    letters_only = re.sub(r"[^A-Za-z]+", "", raw)\n    if (\n        letters_only\n        and letters_only.isupper()\n        and any(term in clean for term in _DOCUMENT_HEADING_TERMS)\n        and not _LEGAL_SUFFIX_RE.search(value)\n    ):\n        return True\n\n    colon = line.find(":")\n    if colon >= 0 and end <= left + colon:\n        label = _normalize(line[:colon])\n        if any(re.search(rf"\\b{re.escape(marker)}\\b", label) for marker in _FIELD_LABEL_MARKERS):\n            return True\n\n'''
    insert_once(guardrails, structure_anchor, structure_insert)

    filter_anchor = '        if _is_source_independent_false_positive(\n'
    filter_insert = '''        if _is_statistical_ner_result(result) and "\\n" in value:\n            trailing = value.split("\\n", 1)[1].strip()\n            if _MULTILINE_NER_NEXT_FIELD_RE.match(trailing):\n                continue\n\n'''
    # Insert only inside filter_english_ner_results, using its unique nearby block.
    text = guardrails.read_text(encoding="utf-8")
    marker = '    filtered: list[Any] = []\n    for result in results:\n        value = text[result.start : result.end]\n        entity_type = str(result.entity_type)\n\n'
    desired = marker + filter_insert
    if desired not in text:
        if marker not in text:
            raise SystemExit("Expected filter_english_ner_results anchor not found")
        guardrails.write_text(text.replace(marker, desired, 1), encoding="utf-8")

    # 4) Generic document words are not identifier values; preserve structured values.
    old_schema = '''_EN_SCHEMA_FALSE_VALUES = {\n    "column",\n    "columns",\n    "field",\n    "fields",\n    "format",\n    "formatting",\n    "mapping",\n    "requirement",\n    "requirements",\n    "review",\n    "workflow",\n}\n'''
    new_schema = '''_EN_SCHEMA_FALSE_VALUES = {\n    "amount",\n    "applicant",\n    "can",\n    "column",\n    "columns",\n    "field",\n    "fields",\n    "format",\n    "formatting",\n    "guidance",\n    "intake",\n    "language",\n    "lease",\n    "mapping",\n    "monthly",\n    "reference",\n    "requirement",\n    "requirements",\n    "review",\n    "summary",\n    "template",\n    "vendor",\n    "work",\n    "workflow",\n}\n'''
    replace_once(engine, old_schema, new_schema)
    replace_once(
        engine,
        'entity_type.endswith(("_ID", "_REFERENCE"))',
        'entity_type.endswith(("_ID", "_REFERENCE", "_NUMBER"))',
    )

    vehicle_anchor = '            if entity_type == "UNIT_NUMBER":\n'
    vehicle_insert = '''            if (\n                entity_type == "VEHICLE_LICENSE_PLATE"\n                and not re.search(r"\\d", value)\n                and value != value.upper()\n            ):\n                continue\n\n'''
    insert_once(engine, vehicle_anchor, vehicle_insert)

    print("Applied English realistic document pack Pass A production patch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
