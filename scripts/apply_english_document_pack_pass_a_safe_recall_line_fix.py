from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/ai_pm_lab_privacy_gate/infrastructure/pii/recognizers/english/safe_recall.py"


def replace_once(old: str, new: str) -> None:
    text = TARGET.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected anchor not found in {TARGET}: {old!r}")
    TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    replace_once(
        '_SEP = r"[ \\t]*(?::|#|=|[-–—])?[ \\t]*"',
        '_SEP = r"[ \\t]*(?::|#|=|[-–—])?[ \\t]*(?:\\r?\\n[ \\t]*)?"',
    )
    replace_once(
        '_REQ_SEP = r"[ \\t]*(?::|#|=|[-–—])[ \\t]*"',
        '_REQ_SEP = r"[ \\t]*(?::|#|=|[-–—])[ \\t]*(?:\\r?\\n[ \\t]*)?"',
    )
    print("Applied English document-pack Pass A safe-recall line-break fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
