from __future__ import annotations

from ai_pm_lab_privacy_gate.ui.google_provider_routes import install_google_provider_routes


def install_gmail_browser_route() -> None:
    """Backward-compatible entry point for the shared Google provider routes."""
    install_google_provider_routes()
