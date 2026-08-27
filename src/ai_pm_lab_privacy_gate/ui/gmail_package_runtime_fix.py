from __future__ import annotations

from ai_pm_lab_privacy_gate.ui import gmail_browser_route, gmail_package_browser


def apply_gmail_package_runtime_fix(main_window) -> None:
    """Keep Gmail package imports isolated from any previous Protect source state."""
    if getattr(main_window, "_gmail_package_runtime_fix", False):
        return
    main_window._gmail_package_runtime_fix = True

    protect = getattr(main_window, "protection_page", None)
    if protect is None:
        return

    def routed_browser(window) -> None:
        before = getattr(protect, "_external_source_metadata", None)
        gmail_package_browser.open_gmail_package_browser(window)
        after = getattr(protect, "_external_source_metadata", None)
        if after is before or not isinstance(after, dict):
            return
        if after.get("provider") != "gmail" or after.get("package_mode") != "gmail_message_package":
            return

        attachment_count = int(after.get("attachment_count") or 0)
        body_selected = bool(after.get("email_body_selected"))

        # A new Gmail package replaces, rather than silently inherits, source
        # slots from the previous Protect session.
        if attachment_count == 0:
            protect.pdf_path.clear()
        if not body_selected and attachment_count <= 1:
            protect.text_input.clear()

        sync = getattr(protect, "_protect_session_sync_source_status", None)
        if callable(sync):
            sync()

        helper = getattr(protect, "_protect_session_source_helper", None)
        components = tuple(after.get("selected_components") or ())
        if helper is not None and components:
            helper.setText(
                f"Gmail package ready · {len(components)} selected component(s): "
                + " · ".join(str(component) for component in components[:4])
                + (" · …" if len(components) > 4 else "")
                + ". Scan locally to review them together."
            )

    # The Gmail route closures read this module global at click time, so one
    # late assignment updates both Apps > Gmail and Protect > Connected sources.
    gmail_browser_route.open_gmail_inbox = routed_browser
