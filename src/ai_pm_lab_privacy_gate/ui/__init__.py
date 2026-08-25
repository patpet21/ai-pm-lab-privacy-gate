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
from .library_source_folders import install_library_source_folders
from .library_visual_upgrade import install_library_visual_upgrade
from .page_split import apply_apps_mcp_split
from .runtime_fixes import apply_runtime_fixes

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
# Install after every provider-specific browser route so all final entry points
# consistently ask which connected account should supply the data.
install_account_aware_routing()
# Privacy-only working-file lifecycle. This does not change MCP state, sharing,
# remote connections, Library contents, Restore mappings or connector tokens.
install_automatic_temp_cleanup()
install_source_metadata()
# Replace only the generic title prompt with a branded local-first save dialog.
# The underlying Library save, connector provenance and restore mapping behavior
# remain unchanged.
install_library_save_dialog()
# Manual AI handoff gate for ChatGPT/GPT, Claude and other AI tools. The handoff
# runs the local second scan, saves to Library, copies only protected content and
# never auto-submits anything to an AI service.
install_privacy_preflight()
# Business/Enterprise is layered on top of the existing Protect, Preflight and
# Apps flows. Basic remains today's behavior; managed policy enforcement is
# centralized in PolicyEngine instead of being scattered through screens.
install_business_foundation()
# If an organization was attached server-side while the app was already open,
# recover from the stale Individual view instead of showing a duplicate-workspace
# error. The existing organization is synced immediately after the action worker.
install_team_action_recovery()
install_library_source_folders()
# Visual-only Library upgrade. It wraps the existing table/actions instead of
# replacing their storage, Restore, MCP or connector behavior.
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
    # Apply after Apps/MCP page splitting so Team & Plans can wrap the final
    # navigation router and refresh the final AppsHubPage implementation.
    apply_business_main_window(self)
    apply_runtime_fixes(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
