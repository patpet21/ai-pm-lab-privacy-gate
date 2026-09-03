from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    ROOT
    / "src"
    / "ai_pm_lab_privacy_gate"
    / "infrastructure"
    / "pii"
    / "recognizers"
    / "real_estate_sensitive_pack.py"
)

OLD = r'_AMOUNT = r"(?:[-+]?\s*(?:USD\s*|[$€£]\s*)?\d[\d,]*(?:\.\d{1,2})?\s*(?:[KMB]|USD|EUR|GBP)?|\(\s*[$€£]?\s*\d[\d,]*(?:\.\d{1,2})?\s*\))"'
NEW = r'_AMOUNT = r"(?:[-+]?\s*(?:USD[ \t]*|[$€£][ \t]*)?\d[\d,]*(?:\.\d{1,2})?(?:[ \t]*(?:[KMB]|USD|EUR|GBP))?|\([ \t]*[$€£]?[ \t]*\d[\d,]*(?:\.\d{1,2})?[ \t]*\))"'


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("English Blind v2 Pass A amount boundary fix already applied.")
        return
    if OLD not in text:
        raise RuntimeError(f"Expected amount-pattern anchor not found in {TARGET}")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied English Blind v2 Pass A amount boundary fix.")


if __name__ == "__main__":
    main()
