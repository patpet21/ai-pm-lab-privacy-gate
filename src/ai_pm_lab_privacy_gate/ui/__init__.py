from ai_pm_lab_privacy_gate.application import portable_backup_runtime as _portable_backup_runtime

from .mcp_log_guard import install_mcp_log_guard
from .layout_polish import install_layout_polish
from .connected_apps_ui import install_connected_apps_ui
from .google_oauth_ui import install_google_oauth_ui
from .brand_palette import apply_brand_palette
from .brand_icons import apply_brand_icons
from .connected_apps_browse_polish import apply_connected_apps_browse_polish
from .protect_runtime import install_protect_runtime, apply_protect_runtime
from .global_loading_runtime import apply_global_loading_runtime
from .protect_micro_ux import apply_protect_micro_ux
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
from .document_workspace_context_runtime import install_document_workspace_context_runtime
from .privacy_preflight import install_privacy_preflight
from .business_foundation import install_business_foundation, apply_business_main_window
from .team_action_recovery import install_team_action_recovery
from .organization_product_experience_2026 import install_organization_product_experience_2026
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
from .organization_apps_safe_routing import apply_organization_apps_safe_routing
from .contact_workflows_polish import apply_contact_workflows_polish, apply_popup_visual_polish
from .contact_executive_2026 import apply_contact_executive_2026
from .dialog_visual_system import apply_dialog_visual_system
from .library_source_folders import install_library_source_folders
from .library_visual_upgrade import install_library_visual_upgrade
from .mockup_library_suite_2026 import (
    install_mockup_library_suite_2026,
    apply_mockup_library_suite_2026,
)
from .library_interaction_runtime_2026 import apply_library_interaction_runtime_2026
from .library_control_center_2026 import (
    install_library_control_center_2026,
    apply_library_control_center_2026,
)
from .library_control_center_bridges_2026 import install_library_control_center_bridges_2026
from .library_control_center_polish_2026 import apply_library_control_center_polish_2026
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
from .governance_center_2026 import apply_governance_center_2026
from .mockup_redesign_shell_2026 import apply_mockup_redesign_shell_2026
from .mockup_organization_overview_2026 import apply_mockup_organization_overview_2026
from .mockup_global_visual_system_2026 import apply_mockup_global_visual_system_2026
from .mockup_navigation_2026 import apply_mockup_navigation_2026
from .mockup_mcp_automation_studio_2026 import apply_mockup_mcp_automation_studio_2026
from .mockup_automation_product_studio_2026 import apply_mockup_automation_product_studio_2026
from .mockup_shell_refinement_2026 import apply_mockup_shell_refinement_2026
from .mockup_interaction_polish_2026 import apply_mockup_interaction_polish_2026
from .mockup_personal_workspace_2026 import apply_mockup_personal_workspace_2026
from .mockup_personal_workspace_polish_2026 import apply_mockup_personal_workspace_polish_2026
from .mockup_personal_workspace_final_2026 import apply_mockup_personal_workspace_final_2026
from .mockup_organization_overview_safety_2026 import apply_mockup_organization_overview_safe_2026
from .mockup_protect_final_2026 import apply_mockup_protect_final_2026
from .mockup_protect_refinement_suite_2026 import apply_mockup_protect_refinement_suite_2026
from .mockup_protect_preview_toolbar_2026 import apply_mockup_protect_preview_toolbar_2026
from .mockup_restore_suite_2026 import apply_mockup_restore_suite_2026
from .restore_document_finder_2026 import apply_restore_document_finder_2026
from .restore_document_finder_mount_fix_2026 import apply_restore_document_finder_mount_fix_2026
from .restore_safe_visual_polish_2026 import apply_restore_safe_visual_polish_2026

install_mcp_log_guard()
install_protect_runtime()
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
install_document_workspace_context_runtime()
install_privacy_preflight()
install_business_foundation()
install_multi_workspace_client()
install_multi_workspace_actions()
install_team_action_recovery()
install_organization_product_experience_2026()
install_multi_workspace_experience()
install_workspace_connector_opt_in()
install_workspace_action_follow()
install_managed_protect_experience()
install_library_source_folders()
install_library_visual_upgrade()
install_mockup_library_suite_2026()
install_library_control_center_2026()
install_library_control_center_bridges_2026()

from .main_window import MainWindow

_original_main_window_init = MainWindow.__init__


def _main_window_init_with_brand(self, *args, **kwargs) -> None:
    _original_main_window_init(self, *args, **kwargs)
    apply_brand_palette(self)
    apply_brand_icons(self)
    apply_connected_apps_browse_polish(self)
    apply_protect_runtime(self, "source")
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
    apply_protect_runtime(self, "managed")
    apply_contact_workflows_polish(self)
    apply_contact_executive_2026(self)
    apply_popup_visual_polish(self)
    apply_dialog_visual_system(self)
    apply_protect_runtime(self, "layout")
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
    apply_protect_runtime(self, "visibility")
    apply_governance_center_2026(self)
    apply_protect_runtime(self, "final")
    apply_global_loading_runtime(self)
    apply_protect_micro_ux(self)
    apply_organization_apps_safe_routing(self)
    apply_mockup_redesign_shell_2026(self)
    apply_mockup_organization_overview_2026(self)
    apply_mockup_global_visual_system_2026(self)
    apply_mockup_navigation_2026(self)
    apply_mockup_mcp_automation_studio_2026(self)
    apply_mockup_shell_refinement_2026(self)
    apply_mockup_interaction_polish_2026(self)
    apply_mockup_personal_workspace_2026(self)
    apply_mockup_personal_workspace_polish_2026(self)

    # Last Personal Workspace layer: native OS file-type artwork, compact clickable
    # provider-logo dock and quick document actions. All actions delegate to the
    # existing Library/Restore/MCP controllers rather than duplicating semantics.
    apply_mockup_personal_workspace_final_2026(self)

    # Final Organization Overview built on the reusable 2026 design foundation.
    # It summarizes real TeamState, policy, device and metadata-only activity data,
    # while all membership/policy/device mutations remain in the existing TeamPage.
    apply_mockup_organization_overview_safe_2026(self)

    # Final Protect presentation layer. It deliberately reuses the proven
    # Original/Protected document panels, text editor, preview widgets and all
    # existing Scan/Review/Save/Download/AI callbacks; only their visual hierarchy
    # is aligned with the approved 2026 mockups.
    apply_mockup_protect_final_2026(self)

    # Post-mockup refinement suite: compact workspace context, reusable guidance,
    # color-coherent review and encrypted local-only manual sensitive rules.
    apply_mockup_protect_refinement_suite_2026(self)

    # Compact the final Protect workspace without recreating controls: High-fidelity
    # joins the VIEW actions and the existing Advanced panel occupies the recovered
    # row immediately below the source/view toolbar.
    apply_mockup_protect_preview_toolbar_2026(self)

    # Restore follows the same migration rule as Protect: the proven local
    # DocumentRestoreService/Library mapping/preview/download controllers remain
    # authoritative, while the 2026 presentation and local text-edit experience
    # are layered on last.
    apply_mockup_restore_suite_2026(self)

    # Workspace-aware original-document finder. It searches local Library/source/
    # workspace metadata and mapping token names, then delegates the chosen ID back
    # to RestorePage's existing document combo and DocumentRestoreService.
    apply_restore_document_finder_2026(self)

    # Keep the last visible Restore command bar owned by the proven controls.
    # The experimental product-polish controller remains disabled because it caused
    # a Qt mouse-event regression. The safe layer below only decorates existing
    # controls and Finder items; it does not reparent or reconnect them.
    apply_restore_document_finder_mount_fix_2026(self)
    apply_restore_safe_visual_polish_2026(self)

    # Final Library presentation/runtime layer. LibraryRepository and all existing
    # LibraryPage callbacks stay authoritative; this only scopes the same local data
    # to Personal vs active Organization and never auto-assigns legacy documents.
    apply_mockup_library_suite_2026(self)

    # Last Library interaction layer: real connected accounts and provider artwork,
    # visible workspace-switch loading, and one-click local restore from Library.
    apply_library_interaction_runtime_2026(self)

    # Document Control Center: Smart Collections, multi-document actions,
    # metadata-only per-document activity, and Organization policy context.
    apply_library_control_center_2026(self)
    apply_library_control_center_polish_2026(self)

    # Product-first Automation Studio: real-product hierarchy, privacy boundary,
    # guided builder, templates, run history, approvals and a discreet PM-led
    # AI/automation advisory surface for client discovery.
    apply_mockup_automation_product_studio_2026(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]