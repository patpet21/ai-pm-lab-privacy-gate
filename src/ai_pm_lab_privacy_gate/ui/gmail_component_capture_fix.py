from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.ui import (
    gmail_browser_route,
    gmail_component_session,
    gmail_package_browser,
)


def apply_gmail_component_capture_fix(main_window) -> None:
    """Capture every Gmail attachment at materialization time.

    The package browser historically kept only the first attachment in the
    hidden document path and converted attachment 2+ to text.  The component
    session then had to infer which files had been selected after the dialog
    closed.  That inference is fragile because late Protect/UI patches may
    clear or replace the hidden document path.

    This final route wrapper captures the actual local file returned for every
    selected Gmail attachment, then rebuilds the Gmail component manifest from
    those real paths.  Body and attachments therefore remain independent native
    Protect sources and are immediately previewable before Scan.
    """
    if getattr(main_window, "_gmail_component_capture_fix", False):
        return
    main_window._gmail_component_capture_fix = True

    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    base_route = gmail_browser_route.open_gmail_inbox

    def routed(window) -> None:
        captured: list[Path] = []
        original_materialize = gmail_package_browser.materialize_gmail_attachment

        def capture_materialized_attachment(service, item, attachment):
            path = Path(original_materialize(service, item, attachment))
            if path not in captured:
                captured.append(path)
            return path

        # Keep the interception scoped to the modal Gmail browser call.  This
        # avoids changing connector behavior elsewhere in the application.
        gmail_package_browser.materialize_gmail_attachment = capture_materialized_attachment
        try:
            base_route(window)
        finally:
            gmail_package_browser.materialize_gmail_attachment = original_materialize

        if not captured:
            # Body-only imports are already handled correctly by the component
            # session.  A cancelled dialog also lands here and must be a no-op.
            return

        metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
        if (
            metadata.get("provider") != "gmail"
            or metadata.get("package_mode") != "gmail_message_package"
        ):
            return

        # Re-adopt from the actual materialized paths.  This deliberately does
        # not depend on pdf_path: that hidden legacy field is exactly what can
        # be cleared by other late-bound Protect UI/runtime patches.
        page._gmail_component_extra_paths = list(captured)
        gmail_component_session._adopt_imported_package(page)

        manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
        if not manifest:
            return

        # Show a real original immediately.  If body was selected it opens the
        # body comparison first; otherwise the first attachment opens in its
        # native PDF/Office preview.  The source pills remain available to jump
        # between every selected component before and after Scan/Protect.
        active = str(getattr(page, "_gmail_component_active_key", "") or "")
        if not active:
            active = str(manifest[0].get("key") or "")
            page._gmail_component_active_key = active
        selector = getattr(page, "_gmail_component_select", None)
        if active and callable(selector):
            selector(active)

        helper = getattr(page, "_protect_session_source_helper", None)
        if helper is not None:
            attachment_count = sum(
                1 for item in manifest if item.get("component_kind") == "attachment"
            )
            helper.setText(
                f"Gmail package ready · {len(manifest)} independent source(s) · "
                f"{attachment_count} attachment(s). Use the source buttons to preview "
                "each original, then Scan all selected sources together."
            )

    gmail_browser_route.open_gmail_inbox = routed
