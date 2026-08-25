from __future__ import annotations

from typing import Any

from . import project_platform_adapter
from .service import ConnectedAppsService


def _plain_rich_text_safe(value: Any) -> str:
    """Flatten Notion rich text and Jira Atlassian Document Format safely."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_plain_rich_text_safe(item) for item in value)
    if isinstance(value, dict):
        if "plain_text" in value:
            return str(value.get("plain_text") or "")

        node_type = str(value.get("type") or "")
        if node_type == "text":
            text_value = value.get("text")
            if isinstance(text_value, str):
                return text_value
            if isinstance(text_value, dict):
                return str(text_value.get("content") or "")
            return ""
        if node_type == "hardBreak":
            return "\n"

        if "content" in value:
            return _plain_rich_text_safe(value.get("content"))

        text_value = value.get("text")
        if isinstance(text_value, str):
            return text_value

        return " ".join(_plain_rich_text_safe(item) for item in value.values())
    return ""


def install_jira_adf_fix() -> None:
    if getattr(ConnectedAppsService, "_jira_adf_fix_installed", False):
        return
    project_platform_adapter._plain_rich_text = _plain_rich_text_safe
    ConnectedAppsService._jira_adf_fix_installed = True  # type: ignore[attr-defined]
