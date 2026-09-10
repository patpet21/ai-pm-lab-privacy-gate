from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "src" / "ai_pm_lab_privacy_gate" / "ui"
MAIN_WINDOW = UI / "main_window.py"
APP = ROOT / "src" / "ai_pm_lab_privacy_gate" / "app.py"
MOCKUP_NAVIGATION = UI / "mockup_navigation_2026.py"
UI_INIT = UI / "__init__.py"
LAZY_RUNTIME = UI / "lazy_runtime_compat_2026.py"

LAZY_PAGE_MODULES = {
    "ai_pm_lab_privacy_gate.ui.library_page",
    "ai_pm_lab_privacy_gate.ui.restore_page",
    "ai_pm_lab_privacy_gate.ui.connections_page",
    "ai_pm_lab_privacy_gate.ui.settings_page",
    "ai_pm_lab_privacy_gate.ui.contact_page",
}


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_secondary_pages_are_not_imported_at_main_window_module_load() -> None:
    imports = _top_level_imports(MAIN_WINDOW)
    assert LAZY_PAGE_MODULES.isdisjoint(imports)


def test_app_does_not_force_settings_page_during_startup() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "window.settings_page" not in source
    assert "window.set_local_api_manager(local_api)" in source


def test_lazy_page_factory_exists_for_secondary_pages() -> None:
    source = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "def _ensure_page(" in source
    for module in LAZY_PAGE_MODULES:
        assert f"from {module} import " in source


def test_redesign_navigation_materializes_lazy_pages_on_first_click() -> None:
    source = MOCKUP_NAVIGATION.read_text(encoding="utf-8")
    assert '"library_page": 1' in source
    assert '"restore_page": 2' in source
    assert '"local_automation_page": 3' in source
    assert '"cloud_automation_page": 4' in source
    assert '"settings_page": 5' in source
    assert 'ensure_page = getattr(self.main_window, "_ensure_page", None)' in source
    assert "page = ensure_page(lazy_index)" in source
    assert "controller._open_page = MethodType(open_page, controller)" in source


def test_lazy_runtime_supports_dynamic_personal_overview_without_stealing_startup() -> None:
    source = LAZY_RUNTIME.read_text(encoding="utf-8")
    assert "except IndexError:" in source
    assert "stack.setCurrentIndex(int(index))" in source
    assert 'target is personal' in source
    assert '"_privacygate_startup_ready"' in source


def test_lazy_runtime_uses_existing_real_lifetime_loading_controller() -> None:
    source = LAZY_RUNTIME.read_text(encoding="utf-8")
    assert 'controller.begin(operation_key' in source
    assert "QApplication.processEvents()" in source
    assert "_attach_page_loading(main_window, page)" in source
    assert "_patch_restore_loading" in source
    assert "_patch_library_backup_loading" in source
    assert "_patch_contact_loading" in source
    assert "QTimer.singleShot(0" in source


def test_lazy_settings_are_fully_composed_before_first_display() -> None:
    source = UI_INIT.read_text(encoding="utf-8")
    settings_start = source.index('if index == 5 and getattr(main_window, "settings_page", None) is not None:')
    settings_end = source.index('if index == 6 and getattr(main_window, "contact_page", None) is not None:')
    block = source[settings_start:settings_end]
    assert "apply_workspace_management_ui(main_window)" in block
    assert "apply_settings_service_pages_2026_runtime(main_window)" in block
    assert "configure(settings)" in block
    assert "apply_approved_settings_mockup_2026(main_window)" in block


def test_protect_empty_state_opens_connected_sources_by_default() -> None:
    source = LAZY_RUNTIME.read_text(encoding="utf-8")
    assert 'choose.setText("Choose a source")' in source
    assert 'picker = getattr(page, "_protect_source_connected", None)' in source
    assert "picker.click()" in source


def test_cloud_mcp_final_layer_is_deferred_with_its_lazy_page() -> None:
    source = UI_INIT.read_text(encoding="utf-8")
    assert 'if index == 4 and getattr(main_window, "cloud_automation_page", None) is not None:' in source
    assert "apply_mockup_mcp_automation_studio_2026(main_window)" in source
    assert "apply_connected_apps_browse_polish(main_window)" in source


def test_personal_apps_are_visible_but_materialized_only_on_first_click() -> None:
    navigation = MOCKUP_NAVIGATION.read_text(encoding="utf-8")
    ui_init = UI_INIT.read_text(encoding="utf-8")
    assert '"Apps", "cloud", lambda: self._open_page("apps_hub_page")' in navigation
    assert "def _ensure_apps_page(main_window):" in navigation
    assert 'attribute == "apps_hub_page"' in navigation
    assert "AppsHubPage(main_window, service)" in navigation
    assert 'controller.begin(\n            loading_key,\n            "Opening Apps"' in navigation
    assert "from .page_split import apply_apps_mcp_split" not in ui_init
    assert "apply_apps_mcp_split(self)" not in ui_init


def test_personal_workflows_use_privacy_first_surface_after_lazy_materialization() -> None:
    source = UI_INIT.read_text(encoding="utf-8")
    start = source.index('if index == 3 and getattr(main_window, "local_automation_page", None) is not None:')
    end = source.index('if index == 4 and getattr(main_window, "cloud_automation_page", None) is not None:')
    block = source[start:end]
    assert "mockup_ai_workflows_2026 as workflows" in block
    assert "workflows.apply_mockup_ai_workflows_2026(main_window)" in block
    assert "mockup_automation_product_studio_2026" not in block
    assert "workflows._open_existing_page = open_existing_page" in block


def test_activity_opens_feature_suite_even_when_settings_are_still_lazy() -> None:
    source = MOCKUP_NAVIGATION.read_text(encoding="utf-8")
    assert "def _open_activity(controller) -> None:" in source
    assert "ensure_page(5)" in source
    assert "ActivityDialog" in source
    assert '"Activity", "history", lambda: _open_activity(self)' in source


def test_workflow_mockup_is_not_marked_complete_during_startup() -> None:
    source = MOCKUP_NAVIGATION.read_text(encoding="utf-8")
    assert "apply_mockup_ai_workflows_2026(main_window)" not in source
    assert "QTimer.singleShot(0, lambda: apply_mockup_ai_workflows_2026(main_window))" not in source
