from .mcp_log_guard import install_mcp_log_guard
from .redesign import install_redesign

install_mcp_log_guard()
install_redesign()

from .main_window import MainWindow

__all__ = ["MainWindow"]
