from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.ui import (
    gmail_browser_route,
    gmail_component_session,
    gmail_package_browser,
)


def apply_gmail_component_capture_fix(main_window) -> None:
    """Capture the exact Gmail body/attachments selected by the user.

    Gmail used to infer the final Protect package from the hidden ``pdf_path``
    and ``text_input`` widgets after the modal browser closed.  That was fragile:
    late UI patches could clear one of those widgets, and attachment 2+ was
    historically flattened into the text lane.  The result was the behavior seen
    in testing: selecting Email body + PDF could arrive in Protect as only one
    source.

    This final route wrapper records the *actual* materialization calls performed
    by the Gmail picker.  The message materializer proves that Email body was
    selected; attachment materializers prove exactly which files were selected.
    After the dialog closes we rebuild the component manifest from that captured
    data, so Protect never has to guess from legacy UI state.
    """
    if getattr(main_window, "_gmail_component_capture_fix", False):
        return
    main_window._gmail_component_capture_fix = True

    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    base_route = gmail_browser_route.open_gmail_inbox

    def routed(window) -> None:
        body_was_materialized = False
        captured_body_text = ""
        captured_attachments: list[tuple[str, Path]] = []

        original_message = gmail_package_browser.materialize_gmail_message
        original_attachment = gmail_package_browser.materialize_gmail_attachment

        def capture_message(service, item):
            nonlocal body_was_materialized, captured_body_text
            path = original_message(service, item)
            body_was_materialized = True
            # ``materialize_gmail_message`` returns a ManagedReadOncePath.  Read
            # through a plain Path copy so we can preserve an in-memory snapshot
            # without consuming/deleting the read-once object before the picker
            # itself reads it.
            try:
                captured_body_text = Path(str(path)).read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                captured_body_text = ""
            return path

        def capture_attachment(service, item, attachment):
            path = Path(original_attachment(service, item, attachment))
            entry = (str(getattr(attachment, "filename", "") or path.name), path)
            if all(existing_path != path for _name, existing_path in captured_attachments):
                captured_attachments.append(entry)
            return path

        # Keep interception scoped to the modal Gmail browser only.
        gmail_package_browser.materialize_gmail_message = capture_message
        gmail_package_browser.materialize_gmail_attachment = capture_attachment
        try:
            base_route(window)
        finally:
            gmail_package_browser.materialize_gmail_message = original_message
            gmail_package_browser.materialize_gmail_attachment = original_attachment

        if not body_was_materialized and not captured_attachments:
            # Cancelled dialog / no import.
            return

        metadata = dict(getattr(page, "_external_source_metadata", {}) or {})
        if (
            metadata.get("provider") != "gmail"
            or metadata.get("package_mode") != "gmail_message_package"
        ):
            return

        component_titles = (["Email body"] if body_was_materialized else []) + [
            name for name, _path in captured_attachments
        ]

        # Rebuild the public source metadata from what was actually materialized,
        # not from the old hidden UI fields.
        metadata.update(
            {
                "selected_components": component_titles,
                "selected_component_count": len(component_titles),
                "email_body_selected": body_was_materialized,
                "attachment_count": len(captured_attachments),
                "primary_attachment": (
                    captured_attachments[0][0] if captured_attachments else ""
                ),
            }
        )
        page._external_source_metadata = metadata
        page._gmail_package_components = tuple(component_titles)

        # Keep legacy widgets synchronized only for compatibility with the rest
        # of Protect.  They are no longer the source of truth for Gmail.
        if captured_attachments:
            page.pdf_path.setText(str(captured_attachments[0][1]))
        else:
            page.pdf_path.clear()
        if body_was_materialized:
            page.text_input.setPlainText(captured_body_text)
        else:
            page.text_input.clear()

        page._gmail_component_extra_paths = [
            path for _name, path in captured_attachments
        ]
        gmail_component_session._adopt_imported_package(page)

        manifest = tuple(getattr(page, "_gmail_component_manifest", ()) or ())
        if not manifest:
            return

        # Open the body first when selected; otherwise open the first attachment.
        preferred_key = "gmail_body" if body_was_materialized else str(
            manifest[0].get("key") or ""
        )
        if preferred_key not in {
            str(item.get("key") or "") for item in manifest
        }:
            preferred_key = str(manifest[0].get("key") or "")
        page._gmail_component_active_key = preferred_key
        selector = getattr(page, "_gmail_component_select", None)
        if preferred_key and callable(selector):
            selector(preferred_key)

        helper = getattr(page, "_protect_session_source_helper", None)
        if helper is not None:
            helper.setText(
                f"Gmail package ready · {len(manifest)} independent source(s) · "
                f"{len(captured_attachments)} attachment(s). Use the source buttons "
                "to preview each original, then Scan all selected sources together."
            )

    gmail_browser_route.open_gmail_inbox = routed
