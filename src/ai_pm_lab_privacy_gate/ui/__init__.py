from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_quick_actions import install_protect_quick_actions
from .layout_polish import install_layout_polish
from .iconography import apply_iconography

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()
install_layout_polish()

from .main_window import MainWindow

_original_main_window_init = MainWindow.__init__


def _main_window_init_with_iconography(self, *args, **kwargs) -> None:
    _original_main_window_init(self, *args, **kwargs)
    apply_iconography(self)


MainWindow.__init__ = _main_window_init_with_iconography

__all__ = ["MainWindow"]
