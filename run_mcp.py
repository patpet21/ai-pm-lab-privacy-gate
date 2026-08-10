import os
import sys


# PyInstaller's Windows GUI bootloader intentionally provides no console
# streams. Some HTTP/logging dependencies still expect writable streams.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
from ai_pm_lab_privacy_gate.infrastructure.mcp.server import main


if __name__ == "__main__":
    main()
