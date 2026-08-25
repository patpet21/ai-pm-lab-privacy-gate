from __future__ import annotations


def apply_runtime_fixes(main_window) -> None:
    """Small post-construction fixes that preserve existing business logic."""
    protect = getattr(main_window, "protection_page", None)
    if protect is not None:
        # Legacy metrics remain available to internal verification logic but must
        # never render as orphan labels after the Protect redesign.
        for name in (
            "verification_metric",
            "findings_metric",
            "types_metric",
            "pages_metric",
            "source_metric",
        ):
            widget = getattr(protect, name, None)
            if widget is not None:
                widget.hide()
                widget.setMaximumHeight(0)

    # Gmail routing is installed centrally by gmail_browser_route.py. Do not
    # override it here: doing so previously reopened the legacy flat message list.
