from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_WINDOW = ROOT / "src" / "ai_pm_lab_privacy_gate" / "ui" / "main_window.py"
APP = ROOT / "src" / "ai_pm_lab_privacy_gate" / "app.py"

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
