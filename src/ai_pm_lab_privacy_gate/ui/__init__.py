from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_ghost_cleanup import install_protect_ghost_cleanup
from .protect_quick_actions import install_protect_quick_actions
from .layout_polish import install_layout_polish
from .connected_apps_ui import install_connected_apps_ui
from .google_oauth_ui import install_google_oauth_ui
from .brand_palette import apply_brand_palette
from .brand_icons import apply_brand_icons
from .connected_apps_browse_polish import apply_connected_apps_browse_polish
from .protect_source_picker import apply_protect_source_picker
from .protect_workspace_controls import apply_managed_protect_context
from .protect_workspace_branding import apply_managed_protect_branding
from .protect_late_cleanup import apply_protect_late_cleanup
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
from .organization_visual_upgrade import apply_organization_visual_upgrade
from .premium_organization_rebuild import apply_premium_organization_rebuild
from . import premium_organization_rebuild as _premium_organization_rebuild_module
from .mockup_fidelity import apply_mockup_fidelity
from .approved_mockup_override import apply_approved_mockup_override
from .final_visual_polish import apply_final_visual_polish
from .organization_workspace_suite import (
    apply_organization_workspace_suite,
    install_workspace_connector_opt_in,
)
from .organization_workspace_suite_v2 import apply_organization_workspace_suite_v2
from .organization_usability_polish import apply_organization_usability_polish
from .organization_overview_fix import apply_organization_overview_fix
from .organization_overview_consistency import apply_organization_overview_consistency
from .contact_workflows_polish import apply_contact_workflows_polish, apply_popup_visual_polish
from .dialog_visual_system import apply_dialog_visual_system
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
from .account_sidebar_polish import apply_account_sidebar_polish
from .workspace_management_ui import apply_workspace_management_ui
from .settings_executive_redesign import apply_settings_executive_redesign
from .workspace_dropdown_cue import apply_workspace_dropdown_cue
from .workspace_creation_experience import apply_workspace_creation_experience

install_mcp_log_guard()
install_redesign()
install_protect_ghost_cleanup()
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
install_business_foundation()
install_multi_workspace_client()
install_multi_workspace_actions()
install_team_action_recovery()
install_multi_workspace_experience()
install_workspace_connector_opt_in()
install_workspace_action_follow()
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
    apply_organization_visual_upgrade(self)
    _premium_organization_rebuild_module.team_page = getattr(self, "team_page", None)
    apply_premium_organization_rebuild(self)
    apply_account_menu(self)
    apply_mockup_fidelity(self)
    apply_approved_mockup_override(self)
    apply_runtime_fixes(self)
    # Final pass intentionally runs late so legacy controller refreshes cannot
    # reintroduce duplicate Organization chrome or collapse Protect to one pane.
    apply_final_visual_polish(self)
    # Organization remains the team control plane: policy, account permission,
    # membership/device context and approved destinations. It no longer embeds a
    # second document workspace.
    apply_organization_workspace_suite(self)
    apply_organization_workspace_suite_v2(self)
    # Late Organization pass: improve readability, make provider tiles real
    # navigation controls, and add policy/readiness guidance without changing
    # workspace, policy, connector or document-security semantics.
    apply_organization_usability_polish(self)
    # Dedicated late Overview pass: the Overview is rebuilt dynamically by the
    # premium dashboard, so re-apply size and click behavior to the visible stack
    # widget after every render rather than relying on stale child references.
    apply_organization_overview_fix(self)
    # Normalize Overview to the same typography scale as Apps & AI and keep the
    # provider navigation icon-only while preserving its click behavior.
    apply_organization_overview_consistency(self)
    # The existing Protect UI stays the single document workspace. Business /
    # Enterprise members get a compact workspace + connected-account bar there.
    apply_managed_protect_context(self)
    apply_managed_protect_branding(self)
    # Contact / Workflows follows the same premium visual language. Dialog polish
    # is presentation-only and preserves each popup's existing actions/logic.
    apply_contact_workflows_polish(self)
    apply_popup_visual_polish(self)
    # Apply one consistent premium visual system to all dialogs after the legacy
    # popup pass: account-name input, policy editor, workspace permissions,
    # connector dialogs, confirmations, warnings and destructive actions.
    apply_dialog_visual_system(self)
    # Run last: hide detached legacy/parking widgets that can otherwise paint
    # clipped labels/icons at the far-left edge on Windows.
    apply_protect_late_cleanup(self)
    # Account replaces the old LOCAL-FIRST footer and must stay below navigation.
    apply_account_sidebar_polish(self)
    # Final workspace pass: make the active work context visually explicit and
    # expose + Workspace -> Settings for invitation-code enrollment / creation.
    apply_workspace_management_ui(self)
    # Recompose Settings only after Account/Workspace controls exist, reusing the
    # original functional widgets and preparing room for future local file/folder
    # management without changing their behavior.
    apply_settings_executive_redesign(self)
    # Keep the workspace switcher unmistakably interactive with a dedicated,
    # clickable chevron beside the selected workspace name.
    apply_workspace_dropdown_cue(self)
    # Finish the workspace UX after the panel exists: one modern creation dialog,
    # clear seat semantics, friendly errors, and the existing backend actions.
    apply_workspace_creation_experience(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
