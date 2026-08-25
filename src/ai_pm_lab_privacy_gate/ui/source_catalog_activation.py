from __future__ import annotations

from ai_pm_lab_privacy_gate.ui import protect_source_picker


def activate_oauth_ready_sources() -> None:
    live = {"google_drive", "gmail", "clickup", "asana", "trello", "notion", "monday", "jira"}
    updated = []
    for provider in protect_source_picker._PROVIDER_CATALOG:
        key, title, description, icon_key, availability = provider
        updated.append((key, title, description, icon_key, "live" if key in live else availability))
    protect_source_picker._PROVIDER_CATALOG = tuple(updated)
