from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign
from .protect_quick_actions import install_protect_quick_actions

install_mcp_log_guard()
install_redesign()
install_protect_quick_actions()

from .main_window import MainWindow

__all__ = ["MainWindow"]
