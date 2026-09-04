from __future__ import annotations

import sys
from pathlib import Path


# Always run the package from this checkout first, even when the Python
# interpreter comes from another PrivacyGate virtual environment that has an
# editable install pointing at a different repository.
_repo_root = Path(__file__).resolve().parent
_src = _repo_root / "src"
if _src.exists():
    src_text = str(_src)
    if src_text in sys.path:
        sys.path.remove(src_text)
    sys.path.insert(0, src_text)

from ai_pm_lab_privacy_gate.app import main


if __name__ == "__main__":
    raise SystemExit(main())
