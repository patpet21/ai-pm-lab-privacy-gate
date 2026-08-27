from __future__ import annotations

from pathlib import Path

from ai_pm_lab_privacy_gate.domain.protect_package import ProtectPackage, ProtectSource
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
    """Compatibility helper used by tests and the Gmail component UI."""
    sources: list[ProtectSource] = []
    if body_was_materialized and captured_body_text.strip():
        sources.append(
            ProtectSource.text_source(
                key="gmail_body",
                label="Email body",
                text=captured_body_text,
                metadata={"component_kind": "body"},
            )
        )
    for index, (name, path) in enumerate(captured_attachments, start=1):
        sources.append(
            ProtectSource.file_source(
                key=f"gmail_attachment_{index}",
                label=name or path.name,
                path=path,
                metadata={"component_kind": "attachment"},
            )
        )
    return tuple(
        {
            "key": source.key,
            "label": source.label,
            "component_kind": str(source.metadata.get("component_kind") or "attachment"),
            "text": source.text,
            "path": source.path,
        }
        for source in sources
    )


def _package_from_capture(
    *,
    body_was_materialized: bool,
    captured_body_text: str,
    captured_attachments: list[tuple[str, Path]],
    metadata: dict,
) -> ProtectPackage | None:
    sources: list[ProtectSource] = []
    if body_was_materialized and captured_body_text.strip():
        sources.append(
            ProtectSource.text_source(
                key="gmail_body",
                label="Email body",
                text=captured_body_text,
                metadata={"component_kind": "body"},
            )
        )
    for index, (name, path) in enumerate(captured_attachments, start=1):
        sources.append(
            ProtectSource.file_source(
                key=f"gmail_attachment_{index}",
                label=name or path.name,
                path=path,
                metadata={"component_kind": "attachment"},
            )
        )
    if not sources:
        return None

    item_title = str(metadata.get("item_title") or "Gmail message")
    return ProtectPackage(
        origin="gmail",
        label=item_title,
        sources=tuple(sources),
        metadata=dict(metadata),
    )


def _install_package(page, package: ProtectPackage) -> None:
    """Install one connector package as the authoritative Protect state."""
    manifest = tuple(
        {
            "key": source.key,
            "label": source.label,
            "component_kind": str(source.metadata.get("component_kind") or "attachment"),
            "text": source.text,
            "path": source.path,
        }
        for source in package.sources
    )

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
    page._last_residual = ()
    page.findings_table.setRowCount(0)
    page.category_list.clear()
    page.preview.clear()
    page._set_result_actions(False)

    old_filter = getattr(page, "_protect_session_filter_bar", None)
    if old_filter is not None:
        old_filter.hide()

    gmail_component_session._refresh_component_strip(page)

    preferred_key = (
        "gmail_body"
        if any(source.key == "gmail_body" for source in package.sources)
        else package.sources[0].key
    )
    page._gmail_component_active_key = preferred_key
    selector = getattr(page, "_gmail_component_select", None)
    if callable(selector):
        selector(preferred_key)

    helper = getattr(page, "_protect_session_source_helper", None)
    if helper is not None:
        helper.setText(
            f"Gmail package ready · {package.source_count} independent source(s) · "
            f"{package.file_count} attachment(s). Click Email body or any attachment "
            "to preview the original before Scan."
        )

    metric = getattr(page, "_redesign_review_metric", None)
    if metric is not None:
        metric.setText(f"Ready to scan · {package.source_count} Gmail sources")


def apply_gmail_component_capture_fix(main_window) -> None:
    """Install the authoritative Gmail -> Protect multi-source contract.

    Older implementations routed Gmail through several wrappers and then tried
    to reconstruct the user's selection from ``pdf_path`` and ``text_input``.
    That made Body + attachment fragile because those compatibility widgets are
    updated in multiple steps.

    This final route deliberately bypasses those older route wrappers. It calls
    the package picker directly, captures exactly which body/attachments were
    materialized, and installs a first-class ProtectPackage in one transaction.
    The legacy widgets are synchronized only for compatibility; they are no
    longer the source of truth for Gmail.
    """
    if getattr(main_window, "_gmail_component_capture_fix", False):
        return
    main_window._gmail_component_capture_fix = True

    page = getattr(main_window, "protection_page", None)
    if page is None:
        return

    def routed(window) -> None:
        before_metadata_object = getattr(page, "_external_source_metadata", None)
        body_was_materialized = False
        captured_body_text = ""
        captured_attachments: list[tuple[str, Path]] = []

        original_message = gmail_package_browser.materialize_gmail_message
        original_attachment = gmail_package_browser.materialize_gmail_attachment
        original_document_as_text = gmail_package_browser._document_as_text

        def capture_message(service, item):
            nonlocal body_was_materialized, captured_body_text
            path = original_message(service, item)
            body_was_materialized = True
            try:
                # Read through a plain Path so ManagedReadOncePath is not
                # consumed before the Gmail picker performs its own read.
                captured_body_text = Path(str(path)).read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                captured_body_text = ""
            return path

        def capture_attachment(service, item, attachment):
            path = Path(original_attachment(service, item, attachment))
            label = str(getattr(attachment, "filename", "") or path.name)
            if all(existing_path != path for _label, existing_path in captured_attachments):
                captured_attachments.append((label, path))
            return path

        # The old picker used to extract attachment 2+ into Paste text because
        # Protect had only one native document lane. The new package contract
        # keeps every attachment as a native source, so that extraction is both
        # redundant and a source of stale state.
        def skip_legacy_attachment_flattening(_protect, _path: Path) -> str:
            return ""

        # Suspend source-reset listeners for the *entire* picker transaction.
        # This is the key difference from the previous fix, which only suspended
        # them after the picker had already written pdf_path/text_input.
        page._protect_source_transaction = True
        gmail_package_browser.materialize_gmail_message = capture_message
        gmail_package_browser.materialize_gmail_attachment = capture_attachment
        gmail_package_browser._document_as_text = skip_legacy_attachment_flattening
        try:
            # Call the actual picker directly. Do not call the previously wrapped
            # gmail_browser_route here; that would re-enter legacy inference.
            gmail_package_browser.open_gmail_package_browser(window)

            after_metadata = getattr(page, "_external_source_metadata", None)
            if after_metadata is before_metadata_object or not isinstance(after_metadata, dict):
                return
            if (
                after_metadata.get("provider") != "gmail"
                or after_metadata.get("package_mode") != "gmail_message_package"
            ):
                return

            package = _package_from_capture(
                body_was_materialized=body_was_materialized,
                captured_body_text=captured_body_text,
                captured_attachments=captured_attachments,
                metadata=dict(after_metadata),
            )
            if package is None:
                return

            component_titles = [source.label for source in package.sources]
            metadata = dict(after_metadata)
            metadata.update(
                {
                    "selected_components": component_titles,
                    "selected_component_count": package.source_count,
                    "email_body_selected": any(
                        source.key == "gmail_body" for source in package.sources
                    ),
                    "attachment_count": package.file_count,
                    "primary_attachment": next(
                        (
                            source.label
                            for source in package.sources
                            if source.source_type == "file"
                        ),
                        "",
                    ),
                    "protect_package_contract": "v1",
                }
            )
            page._external_source_metadata = metadata
            page._gmail_package_components = tuple(component_titles)
            page._gmail_component_extra_paths = [
                Path(source.path)
                for source in package.sources
                if source.source_type == "file"
            ]

            # Synchronize compatibility widgets only after the complete package
            # is known. Attachment 2+ is never flattened into Paste text.
            primary_file = next(
                (source for source in package.sources if source.source_type == "file"),
                None,
            )
            body_source = next(
                (source for source in package.sources if source.key == "gmail_body"),
                None,
            )
            if primary_file is not None:
                page.pdf_path.setText(primary_file.path)
                page.input_tabs.setCurrentIndex(1)
            else:
                page.pdf_path.clear()
            if body_source is not None:
                page.text_input.setPlainText(body_source.text)
            else:
                page.text_input.clear()
                if primary_file is None:
                    page.input_tabs.setCurrentIndex(0)

            package = ProtectPackage(
                origin=package.origin,
                label=package.label,
                sources=package.sources,
                metadata=metadata,
            )
            page._protect_package = package
            _install_package(page, package)

            sync = getattr(page, "_protect_session_sync_source_status", None)
            if callable(sync):
                sync()

            window.statusBar().showMessage(
                f"Gmail package ready: {package.source_count} independent source(s).",
                7000,
            )
        finally:
            gmail_package_browser.materialize_gmail_message = original_message
            gmail_package_browser.materialize_gmail_attachment = original_attachment
            gmail_package_browser._document_as_text = original_document_as_text
            page._protect_source_transaction = False

    # Final authoritative route. This intentionally replaces the older Gmail
    # wrappers installed earlier during startup.
    gmail_browser_route.open_gmail_inbox = routed
