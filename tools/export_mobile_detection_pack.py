from __future__ import annotations

import argparse
from pathlib import Path

from ai_pm_lab_privacy_gate.domain.detection_pack import (
    detection_pack_json,
    render_flutter_detection_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the canonical PrivacyGate Desktop detection taxonomy."
    )
    parser.add_argument(
        "--format",
        choices=("json", "flutter"),
        default="json",
        help="Portable JSON or generated Flutter/Dart source.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write to this path instead of stdout.",
    )
    args = parser.parse_args()

    content = (
        render_flutter_detection_pack()
        if args.format == "flutter"
        else detection_pack_json(indent=2) + "\n"
    )
    if args.output is None:
        print(content, end="")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
