from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_quick_actions import install_protect_quick_actions
from .layout_polish import install_layout_polish

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()
install_layout_polish()

from .main_window import MainWindow

__all__ = ["MainWindow"]
