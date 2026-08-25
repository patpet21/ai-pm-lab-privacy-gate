from .service import ConnectedAppsService, ConnectionTestResult, RemoteItem
from .google_oauth_adapter import install_google_oauth_adapter
from .multi_oauth_adapter import install_multi_oauth_adapter
from .search_adapter import install_search_adapter
from .clickup_adapter import install_clickup_adapter
from .project_platform_adapter import install_project_platform_adapter
from .asana_auto_oauth import install_asana_auto_oauth
from .notion_auto_oauth import install_notion_auto_oauth
from .jira_adf_fix import install_jira_adf_fix
from .jira_refresh_adapter import install_jira_refresh_adapter
from .multi_account_registry import install_multi_account_registry

install_google_oauth_adapter()
install_multi_oauth_adapter()
install_search_adapter()
install_clickup_adapter()
install_project_platform_adapter()
install_asana_auto_oauth()
install_notion_auto_oauth()
install_jira_adf_fix()
install_jira_refresh_adapter()
# Install last: it wraps the final provider token/connect methods so every
# provider keeps independent credentials while legacy adapters use an active
# compatibility alias.
install_multi_account_registry()

__all__ = ["ConnectedAppsService", "ConnectionTestResult", "RemoteItem"]
