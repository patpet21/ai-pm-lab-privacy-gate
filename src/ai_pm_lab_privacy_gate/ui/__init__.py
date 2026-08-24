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
from .page_split import apply_apps_mcp_split

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()
install_layout_polish()
install_connected_apps_ui()
install_google_oauth_ui()
activate_oauth_ready_sources()

from .main_window import MainWindow

_original_main_window_init = MainWindow.__init__


def _main_window_init_with_brand(self, *args, **kwargs) -> None:
    _original_main_window_init(self, *args, **kwargs)
    apply_brand_palette(self)
    apply_brand_icons(self)
    apply_connected_apps_browse_polish(self)
    apply_protect_source_picker(self)
    apply_apps_mcp_split(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
