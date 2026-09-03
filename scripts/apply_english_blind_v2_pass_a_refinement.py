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


def main() -> None:
    engine = ROOT / "src" / "ai_pm_lab_privacy_gate" / "infrastructure" / "pii" / "presidio_engine.py"
    safe_recall = ROOT / "src" / "ai_pm_lab_privacy_gate" / "infrastructure" / "pii" / "recognizers" / "english" / "safe_recall.py"

    # A literal placeholder is documentation/template text, not a real password.
    # Keep this narrow to explicit placeholder syntax so normal password values
    # remain protected.
    placeholder_anchor = '''            invalid_values = _EN_CONTEXT_VALUE_FALSE_VALUES.get(entity_type)\n            if invalid_values and normalized in invalid_values:\n                continue\n\n'''
    placeholder_new = placeholder_anchor + '''            if entity_type == "PASSWORD_CREDENTIAL" and re.fullmatch(\n                r"(?:<|\\[)\\s*(?:redacted|placeholder|password|secret|token)\\s*(?:>|\\])",\n                value,\n                re.IGNORECASE,\n            ):\n                continue\n\n'''
    _replace_once(engine, placeholder_anchor, placeholder_new)

    # Plain "capital budget" is intentionally left to the existing more-specific
    # capital/remaining-budget recognizers. This rule owns only explicit project
    # or renovation budget labels (plus "capital project budget").
    _replace_once(
        safe_recall,
        'rf"(?:project|renovation|capital)[ \\t]+budget(?:[ \\t]+amount)?\\b{_SEP}(?P<value>{_AMOUNT})"',
        'rf"(?:project|renovation|capital[ \\t]+project)[ \\t]+budget(?:[ \\t]+amount)?\\b{_SEP}(?P<value>{_AMOUNT})"',
    )

    print("Applied English Blind v2 Pass A refinement.")


if __name__ == "__main__":
    main()
