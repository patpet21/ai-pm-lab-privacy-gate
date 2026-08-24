from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_quick_actions import install_protect_quick_actions
from .layout_polish import install_layout_polish
from .brand_palette import apply_brand_palette
from .brand_icons import apply_brand_icons

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()
install_layout_polish()

from .main_window import MainWindow

_original_main_window_init = MainWindow.__init__


def _main_window_init_with_brand(self, *args, **kwargs) -> None:
    _original_main_window_init(self, *args, **kwargs)
    # Final visual pass only: palette + icons. No layout or application behavior changes.
    apply_brand_palette(self)
    apply_brand_icons(self)


MainWindow.__init__ = _main_window_init_with_brand

__all__ = ["MainWindow"]
