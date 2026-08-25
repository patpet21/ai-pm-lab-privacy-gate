from .service import ConnectedAppsService, ConnectionTestResult, RemoteItem
from .google_oauth_adapter import install_google_oauth_adapter
from .multi_oauth_adapter import install_multi_oauth_adapter
from .search_adapter import install_search_adapter
from .clickup_adapter import install_clickup_adapter
from .project_platform_adapter import install_project_platform_adapter
from .asana_auto_oauth import install_asana_auto_oauth
from .notion_auto_oauth import install_notion_auto_oauth

install_google_oauth_adapter()
install_multi_oauth_adapter()
install_search_adapter()
install_clickup_adapter()
install_project_platform_adapter()
install_asana_auto_oauth()
install_notion_auto_oauth()

__all__ = ["ConnectedAppsService", "ConnectionTestResult", "RemoteItem"]
