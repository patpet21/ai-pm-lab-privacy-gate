from ai_pm_lab_privacy_gate.application import portable_backup_runtime as _portable_backup_runtime

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
from .document_pipeline_v2_ui import apply_document_pipeline_v2_ui
from .protect_session_upgrade import apply_protect_session_upgrade
from .protect_session_runtime_fix import apply_protect_session_runtime_fix
from .gmail_package_browser import apply_gmail_package_browser
from .gmail_package_runtime_fix import apply_gmail_package_runtime_fix
from .gmail_component_session import apply_gmail_component_session
from .gmail_component_preview_polish import apply_gmail_component_preview_polish
from .protect_workspace_controls import apply_managed_protect_context
from .protect_workspace_branding import apply_managed_protect_branding
from .protect_late_cleanup import apply_protect_late_cleanup
from .protect_usability_polish import apply_protect_usability_polish
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
from .contact_executive_2026 import apply_contact_executive_2026
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
from .account_menu_popup_2026 import apply_account_menu_popup_2026
from .workspace_management_ui import apply_workspace_management_ui
from .settings_executive_redesign import apply_settings_executive_redesign
from .settings_service_hub_2026 import apply_settings_service_hub_2026
from .workspace_dropdown_cue import apply_workspace_dropdown_cue
from .workspace_creation_experience import apply_workspace_creation_experience
from .workspace_refresh_control import apply_workspace_refresh_control
from .workspace_creation_feedback import apply_workspace_creation_feedback
from .settings_service_pages_runtime import apply_settings_service_pages_2026_runtime
from .feature_suite_2026 import apply_feature_suite_2026
from .feature_suite_runtime import apply_feature_suite_runtime
from .governance_hardening_2026 import apply_governance_hardening_2026
from .governance_release_polish_2026 import apply_governance_release_polish_2026
from .protect_workflow_visibility_fix import apply_protect_workflow_visibility_fix
from .governance_center_2026 import apply_governance_center_2026

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
    apply_final_visual_polish(self)
    apply_organization_workspace_suite(self)
    apply_organization_workspace_suite_v2(self)
    apply_organization_usability_polish(self)
    apply_organization_overview_fix(self)
    apply_organization_overview_consistency(self)
    apply_managed_protect_context(self)
    apply_managed_protect_branding(self)
    apply_contact_workflows_polish(self)
    apply_contact_executive_2026(self)
    apply_popup_visual_polish(self)
    apply_dialog_visual_system(self)
    apply_protect_late_cleanup(self)
    apply_account_sidebar_polish(self)
    apply_account_menu_popup_2026(self)
    apply_workspace_management_ui(self)
    apply_settings_executive_redesign(self)
    apply_settings_service_hub_2026(self)
    apply_workspace_dropdown_cue(self)
    apply_workspace_creation_experience(self)
    apply_workspace_refresh_control(self)
    apply_workspace_creation_feedback(self)
    apply_settings_service_pages_2026_runtime(self)
    apply_feature_suite_2026(self)
    apply_feature_suite_runtime(self)
    apply_governance_hardening_2026(self)
    apply_governance_release_polish_2026(self)
    apply_protect_workflow_visibility_fix(self)
    apply_governance_center_2026(self)
    apply_protect_usability_polish(self)
    # Final functional pass: keep every supported file source on one local
    # import/protect/export path and add the TXT companion export.
    apply_document_pipeline_v2_ui(self)
    # Last Protect pass: preserve all previous behavior while enabling a
    # document + pasted-text session, clearer source review, PPTX drag/drop,
    # visible fidelity status, and clearer Drive navigation.
    apply_protect_session_upgrade(self)
    apply_protect_session_runtime_fix(self)
    # Gmail package picker still owns remote selection/materialization.
    apply_gmail_package_browser(self)
    apply_gmail_package_runtime_fix(self)
    # Final Gmail Protect pass: preserve body + every selected attachment as
    # independent native sources with explicit source buttons and previews.
    apply_gmail_component_session(self)
    apply_gmail_component_preview_polish(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
