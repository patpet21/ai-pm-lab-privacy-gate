from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/real_estate.py"

OLD = '_PERSON_NAME = rf"(?-i:{_PERSON_TOKEN}(?:\\s+(?:{_PERSON_TOKEN}|[A-Z]\\.)){{1,3}})"'
NEW = '_PERSON_NAME = rf"(?-i:{_PERSON_TOKEN}(?:[ \\t]+(?:{_PERSON_TOKEN}|[A-Z]\\.)){{1,3}})"'


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("English document-pack Pass A PERSON line-boundary fix already applied.")
        return 0
    if OLD not in text:
        raise SystemExit("Expected _PERSON_NAME anchor not found; refusing to patch.")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied English document-pack Pass A PERSON line-boundary fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
