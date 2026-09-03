from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDRAILS = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/english/guardrails.py"
REAL_ESTATE = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/real_estate.py"
SENSITIVE = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/real_estate_sensitive_pack.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected anchor not found in {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_after_once(path: Path, anchor: str, insertion: str) -> None:
    text = path.read_text(encoding="utf-8")
    if insertion.strip() in text:
        return
    if anchor not in text:
        raise SystemExit(f"Expected insertion anchor not found in {path}: {anchor[:160]!r}")
    path.write_text(text.replace(anchor, anchor + insertion, 1), encoding="utf-8")


def main() -> int:
    # Preserve legitimate narrative entities when a colon belongs to a later field
    # on the same sentence. A field-label span must be short and local.
    replace_once(
        GUARDRAILS,
        '''    colon = line.find(":")\n    if colon >= 0 and end <= left + colon:\n        label = _normalize(line[:colon])\n        if any(re.search(rf"\\b{re.escape(marker)}\\b", label) for marker in _FIELD_LABEL_MARKERS):\n            return True\n''',
        '''    colon = line.find(":")\n    if colon >= 0 and end <= left + colon:\n        raw_label = line[:colon]\n        label = _normalize(raw_label)\n        if (\n            len(raw_label) <= 64\n            and not re.search(r"[.;!?]", raw_label)\n            and any(re.search(rf"\\b{re.escape(marker)}\\b", label) for marker in _FIELD_LABEL_MARKERS)\n        ):\n            return True\n''',
    )

    passport_anchor = '''    ContextRule(\n        "US_PASSPORT",\n        rf"passport(?:\\s+(?:number|no\\.?))?(?=\\s|:|#){_LABEL_SEPARATOR}(?P<value>[A-Z0-9]{{6,12}})\\b",\n    ),\n'''
    passport_multiline = '''    ContextRule(\n        "US_PASSPORT",\n        r"passport(?:[ \\t]+(?:number|no\\.?))?[ \\t]*(?::|#)?[ \\t]*\\r?\\n[ \\t]*(?P<value>(?=[A-Z0-9]{0,11}\\d)[A-Z0-9]{6,12})\\b",\n    ),\n'''
    insert_after_once(REAL_ESTATE, passport_anchor, passport_multiline)

    unit_anchor = '''    ContextRule(\n        "UNIT_NUMBER",\n        rf"(?:apartment|apt\\.?|unit)\\b{_LABEL_SEPARATOR}(?P<value>[A-Z0-9][A-Z0-9-]{{0,9}})\\b",\n        score=0.91,\n    ),\n'''
    unit_multiline = '''    ContextRule(\n        "UNIT_NUMBER",\n        r"(?:apartment|apt\\.?|unit)(?:[ \\t]+number)?[ \\t]*(?::|#|=)?[ \\t]*\\r?\\n[ \\t]*(?P<value>(?=[A-Z0-9-]*\\d)[A-Z0-9][A-Z0-9-]{0,9})\\b",\n        score=0.91,\n    ),\n'''
    insert_after_once(REAL_ESTATE, unit_anchor, unit_multiline)

    coi_anchor = '    ContextRule("COI_REFERENCE", rf"(?:certificate\\s+of\\s+insurance|coi)(?:\\s+(?:id|reference|ref\\.?|number|no\\.?))?{_SEP}(?P<value>(?=[A-Z0-9./-]*\\d){_ID})\\b", score=0.965),\n'
    coi_multiline = '    ContextRule("COI_REFERENCE", rf"(?:certificate[ \\t]+of[ \\t]+insurance|coi)(?:[ \\t]+(?:id|reference|ref\\.?|number|no\\.?))?[ \\t]*(?::|#|=)?[ \\t]*\\r?\\n[ \\t]*(?P<value>(?=[A-Z0-9./-]*\\d){_ID})\\b", score=0.965),\n'
    insert_after_once(SENSITIVE, coi_anchor, coi_multiline)

    print("Applied English document-pack Pass A refinement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
