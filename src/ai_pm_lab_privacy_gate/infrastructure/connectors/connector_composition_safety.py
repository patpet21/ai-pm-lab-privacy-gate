from __future__ import annotations

from . import multi_oauth_adapter
from .service import ConnectedAppsService



def install_connector_composition_safety() -> None:
    """Preserve provider-specific handlers after all connector adapters compose.

    Some adapter modules are imported before their ``install_*`` functions run.
    If they capture ``ConnectedAppsService.test_connection`` or
    ``list_root_items`` at import time, that captured method can predate the
    Gmail adapter. Installing this final wrapper after the provider adapters
    guarantees that Gmail keeps its dedicated read-only test/list behavior while
    every other provider delegates to the fully composed chain.
    """
    if getattr(ConnectedAppsService, "_connector_composition_safety_installed", False):
        return

    previous_test = ConnectedAppsService.test_connection
    previous_list = ConnectedAppsService.list_root_items

    def test_connection(self: ConnectedAppsService, provider: str):
        if provider == "gmail":
            return multi_oauth_adapter._test_connection(self, provider)
        return previous_test(self, provider)

    def list_root_items(self: ConnectedAppsService, provider: str, limit: int = 30):
        if provider == "gmail":
            return multi_oauth_adapter._list_root_items(self, provider, limit)
        return previous_list(self, provider, limit)

    ConnectedAppsService.test_connection = test_connection  # type: ignore[method-assign]
    ConnectedAppsService.list_root_items = list_root_items  # type: ignore[method-assign]
    ConnectedAppsService._connector_composition_safety_installed = True  # type: ignore[attr-defined]
