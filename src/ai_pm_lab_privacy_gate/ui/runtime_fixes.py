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

    # Team & Plans is injected after the base navigation is constructed. Give it
    # the same explicit navigation style as Apps so the label remains white in
    # normal, hover and selected states instead of inheriting the page text color.
    team_button = next(
        (
            button
            for button in getattr(main_window, "nav_buttons", [])
            if button.text() == "Team & Plans"
        ),
        None,
    )
    if team_button is not None:
        team_button.setStyleSheet(
            "QPushButton{background:transparent;color:#DCE7EF;border:none;border-radius:9px;"
            "padding:12px 14px;text-align:left;font-weight:650;min-height:24px;}"
            "QPushButton:hover{background:#0D3A5C;color:#FFFFFF;}"
            "QPushButton:checked{background:#0B7180;color:#FFFFFF;"
            "border-left:3px solid #D3A13B;}"
        )

    # Gmail routing is installed centrally by gmail_browser_route.py. Do not
    # override it here: doing so previously reopened the legacy flat message list.
