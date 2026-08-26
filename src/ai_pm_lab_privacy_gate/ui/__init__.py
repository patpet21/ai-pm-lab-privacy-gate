from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_quick_actions import install_protect_quick_actions
from .layout_polish import install_layout_polish
from .connected_apps_ui import install_connected_apps_ui
from .google_oauth_ui import install_google_oauth_ui
from .brand_palette import apply_brand_palette
from .brand_icons import apply_brand_icons
from .connected_apps_browse_polish import apply_connected_apps_browse_polish
from .protect_source_picker import apply_protect_source_picker
from .source_catalog_activation import activate_oauth_ready_sources
from .gmail_browser_route import install_gmail_browser_route
from .clickup_browser_route import install_clickup_browser_route
from .project_platform_routes import install_project_platform_routes
from .apps_catalog_upgrade import install_apps_catalog_upgrade
from .apps_disconnect_layout import install_apps_disconnect_layout
from .apps_multi_account import install_apps_multi_account
from .account_aware_routing import install_account_aware_routing
from .automatic_temp_cleanup import install_automatic_temp_cleanup
from .source_metadata import install_source_metadata
from .library_save_dialog import install_library_save_dialog
from .privacy_preflight import install_privacy_preflight
from .business_foundation import install_business_foundation, apply_business_main_window
from .team_action_recovery import install_team_action_recovery
from .organization_polish import apply_organization_polish
from .library_source_folders import install_library_source_folders
from .library_visual_upgrade import install_library_visual_upgrade
from .page_split import apply_apps_mcp_split
from .runtime_fixes import apply_runtime_fixes
from ai_pm_lab_privacy_gate.infrastructure.policy.multi_workspace_runtime import install_multi_workspace_client
from ai_pm_lab_privacy_gate.infrastructure.policy.multi_workspace_actions import install_multi_workspace_actions
from .multi_workspace_experience import install_multi_workspace_experience
from .workspace_action_follow import install_workspace_action_follow
from .managed_protect_experience import install_managed_protect_experience
from .workspace_sidebar import apply_workspace_sidebar
from .account_menu import apply_account_menu

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()
install_layout_polish()
install_connected_apps_ui()
install_google_oauth_ui()
activate_oauth_ready_sources()
install_apps_catalog_upgrade()
install_apps_disconnect_layout()
install_apps_multi_account()
install_gmail_browser_route()
install_clickup_browser_route()
install_project_platform_routes()
install_account_aware_routing()
install_automatic_temp_cleanup()
install_source_metadata()
install_library_save_dialog()
install_privacy_preflight()
# Business/Enterprise enforcement stays layered over the existing Protect flow.
# Basic/Pro without an active organization policy keep today's Protect UI.
install_business_foundation()
# Account -> Personal + multiple organization workspaces. Existing connector
# token storage remains unchanged; only local workspace bindings are added.
install_multi_workspace_client()
install_multi_workspace_actions()
install_team_action_recovery()
install_multi_workspace_experience()
# Joining/creating an organization activates that exact new workspace instead of
# snapping back to a previously selected organization on refresh.
install_workspace_action_follow()
# Managed workspaces receive the premium Protect context and Original / Anonymized
# file selector. Personal Protect is intentionally left visually unchanged.
install_managed_protect_experience()
install_library_source_folders()
install_library_visual_upgrade()

from .main_window import MainWindow

_original_main_window_init = MainWindow.__init__


def _main_window_init_with_brand(self, *args, **kwargs) -> None:
    _original_main_window_init(self, *args, **kwargs)
    apply_brand_palette(self)
    apply_brand_icons(self)
    apply_connected_apps_browse_polish(self)
    apply_protect_source_picker(self)
    apply_apps_mcp_split(self)
    apply_business_main_window(self)
    apply_organization_polish(self)
    apply_workspace_sidebar(self)
    # Account is applied after workspace/organization navigation so its shortcuts
    # point to the final pages and its card always remains at the bottom.
    apply_account_menu(self)
    apply_runtime_fixes(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
