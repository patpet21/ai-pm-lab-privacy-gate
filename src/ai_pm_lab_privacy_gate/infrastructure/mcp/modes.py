from __future__ import annotations

from enum import StrEnum


class ConnectionMode(StrEnum):
    """Explicitly separate local, temporary development, and stable production modes."""

    LOCAL = "local"
    DEV_QUICK = "dev_quick"
    PROD_NAMED = "prod_named"

