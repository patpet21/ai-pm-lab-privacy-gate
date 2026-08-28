"""Local Automation runtime persistence.

Only workflow configuration and metadata-only run records belong here. Original
or protected business content must stay in the existing Protect/Library stores.
"""

from .automation_store import AutomationStore

__all__ = ["AutomationStore"]
