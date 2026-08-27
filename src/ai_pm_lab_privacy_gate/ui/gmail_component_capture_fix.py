from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.ui import (
    gmail_browser_route,
    gmail_component_session,
    gmail_package_browser,
)


def _authoritative_manifest(
    body_was_materialized: bool,
    captured_body_text: str,
    captured_attachments: list[tuple[str, Path]],
) -> tuple[dict[str, str], ...]:
    """Build the exact Gmail source manifest from what was materialized."""
    manifest: list[dict[str, str]] = []
    if body_was_materialized:
        manifest.append(
            {
                "key": "gmail_body",
                "label": "Email body",
                "component_kind": "body",
                "text": captured_body_text,
                "path": "",
            }
        )
    for index, (name, path) in enumerate(captured_attachments, start=1):
        manifest.append(
            {
                "key": f"gmail_attachment_{index}",
                "label": name or path.name,
                "component_kind": "attachment",
                "text": "",
                "path": str(path),
            }
        )
    return tuple(manifest)


def _install_manifest(page, manifest: tuple[dict[str, str], ...]) -> None:
    """Install a Gmail package without depending on hidden legacy input state."""
    page._gmail_component_manifest = manifest
    page._gmail_component_sources = {}
    page._gmail_component_results = {}
    page._gmail_package_active = False
    page._protect_session_active = False
    page._protect_session_sources = {}
    page._protect_session_results = {}
    page.current_document = None
    page.current_findings = ()
    page.current_result = None
    page.findings_table.setRowCount(0)
    page.category_list.clear()
    page.preview.clear()
    page._set_result_actions(False)

    old_filter = getattr(page, "_protect_session_filter_bar", None)
    if old_filter is not None:
        old_filter.hide()
    gmail_component_session._refresh_component_strip(page)


def apply_gmail_component_capture_fix(main_window) -> None:
    """Capture the exact Gmail body/attachments selected by the user.

    Gmail used to infer the final Protect package from the hidden ``pdf_path``
    and ``text_input`` widgets after the modal browser closed. That was fragile:
    source-reset listeners and late UI patches could observe those widgets while
    the package was only half-built and drop either the email body or attachment.

    This final route wrapper records the actual materialization calls performed
    by the Gmail picker, then installs the whole Gmail package atomically. Body
    and every selected attachment therefore remain independent native Protect
    sources and can be previewed before Scan.
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
            # Read through a plain Path so the picker can still consume its
            # ManagedReadOncePath normally after we take an in-memory snapshot.
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

        gmail_package_browser.materialize_gmail_message = capture_message
        gmail_package_browser.materialize_gmail_attachment = capture_attachment
        try:
            base_route(window)
        finally:
            gmail_package_browser.materialize_gmail_message = original_message
            gmail_package_browser.materialize_gmail_attachment = original_attachment

        if not body_was_materialized and not captured_attachments:
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

        manifest = _authoritative_manifest(
            body_was_materialized,
            captured_body_text,
            captured_attachments,
        )

        # Source reset listeners are intentionally suspended until every legacy
        # compatibility field and the authoritative manifest agree. Without this
        # transaction, setting text after pdf_path can invalidate the package in
        # the middle of a Body + PDF import.
        page._protect_source_transaction = True
        try:
            page._external_source_metadata = metadata
            page._gmail_package_components = tuple(component_titles)
            page._gmail_component_extra_paths = [
                path for _name, path in captured_attachments
            ]

            if captured_attachments:
                page.pdf_path.setText(str(captured_attachments[0][1]))
                page.input_tabs.setCurrentIndex(1)
            else:
                page.pdf_path.clear()
            if body_was_materialized:
                page.text_input.setPlainText(captured_body_text)
            else:
                page.text_input.clear()

            # Install directly from captured sources. Do not ask Protect to infer
            # a package from pdf_path/text_input a second time.
            _install_manifest(page, manifest)
            page._external_source_metadata = metadata
            page._gmail_package_components = tuple(component_titles)
        finally:
            page._protect_source_transaction = False

        if not manifest:
            return

        preferred_key = "gmail_body" if body_was_materialized else str(
            manifest[0].get("key") or ""
        )
        page._gmail_component_active_key = preferred_key
        selector = getattr(page, "_gmail_component_select", None)
        if preferred_key and callable(selector):
            selector(preferred_key)

        helper = getattr(page, "_protect_session_source_helper", None)
        if helper is not None:
            helper.setText(
                f"Gmail package ready · {len(manifest)} independent source(s) · "
                f"{len(captured_attachments)} attachment(s). Use the source buttons "
                "to preview Email body or each attachment before Scan."
            )

        metric = getattr(page, "_redesign_review_metric", None)
        if metric is not None:
            metric.setText(f"Ready to scan · {len(manifest)} Gmail sources")

    gmail_browser_route.open_gmail_inbox = routed
