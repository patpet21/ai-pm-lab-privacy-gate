from __future__ import annotations

import os
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

    # app.py launches the branded startup splash in a child Python process via
    # ``python -m ai_pm_lab_privacy_gate.app``. sys.path changes are process-local,
    # so also publish this checkout through PYTHONPATH. The child then imports the
    # exact same FreeV1 sources instead of an editable install from an older venv.
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath_parts = [part for part in existing_pythonpath.split(os.pathsep) if part]
    pythonpath_parts = [part for part in pythonpath_parts if os.path.normcase(part) != os.path.normcase(src_text)]
    os.environ["PYTHONPATH"] = os.pathsep.join([src_text, *pythonpath_parts])

from ai_pm_lab_privacy_gate.app import main


if __name__ == "__main__":
    raise SystemExit(main())
