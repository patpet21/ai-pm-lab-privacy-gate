from .service import ConnectedAppsService, ConnectionTestResult, RemoteItem
from .google_oauth_adapter import install_google_oauth_adapter
from .multi_oauth_adapter import install_multi_oauth_adapter

install_google_oauth_adapter()
install_multi_oauth_adapter()

__all__ = ["ConnectedAppsService", "ConnectionTestResult", "RemoteItem"]
