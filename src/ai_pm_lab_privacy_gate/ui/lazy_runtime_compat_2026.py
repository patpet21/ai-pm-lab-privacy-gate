from __future__ import annotations

"""Compatibility bridge for startup-lazy desktop pages.

The 2026 presentation layers were originally assembled with every core page
already constructed. Startup lazy-loading deliberately changes that assumption.
This module keeps the fast Protect-first startup while reconnecting the existing
navigation and unified-loading runtimes to pages that are materialized later.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


_LAZY_PAGE_LABELS = {
    1: ("Library", "Preparing your protected Library locally…"),
    2: ("Restore", "Preparing local restore tools and document mappings…"),
    3: ("Workflows", "Preparing local workflow tools…"),
    4: ("MCP & AI Direct", "Preparing AI connection controls…"),
    5: ("Settings", "Preparing PrivacyGate settings and local services…"),
    6: ("Support", "Preparing PrivacyGate support and update tools…"),
}


def _compact_loading_dialog(main_window) -> None:
    controller = getattr(main_window, "_unified_loading", None)
    dialog = getattr(controller, "dialog", None) if controller is not None else None
    if dialog is None:
        return
    dialog.setMinimumWidth(390)
    dialog.setMaximumWidth(460)
    layout = dialog.layout()
    if layout is not None:
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(9)
    progress = getattr(dialog, "progress", None)
    if progress is not None:
        progress.setFixedHeight(7)
    note = getattr(dialog, "note", None)
    if note is not None:
        note.setText("This closes automatically when the operation is complete.")


def _attach_page_loading(main_window, page) -> None:
    controller = getattr(main_window, "_unified_loading", None)
    if controller is None or page is None:
        return

    page._unified_loading = controller

    # Re-run the existing idempotent adapters now that the lazy page really
    # exists. No second loading framework is introduced.
    from ai_pm_lab_privacy_gate.ui.global_loading_runtime import (
        _patch_contact_loading,
        _patch_library_backup_loading,
        _patch_restore_loading,
        _patch_standard_busy_pages,
    )

    _patch_restore_loading(main_window, controller)
    _patch_contact_loading(main_window, controller)
    _patch_library_backup_loading(main_window)
    _patch_standard_busy_pages(main_window, controller)


def _finalize_lazy_settings(main_window) -> None:
    settings = getattr(main_window, "settings_page", None)
    if settings is None:
        return

    # The approved Settings hub was historically queued for the next event-loop
    # turn because all Settings services already existed at startup. In lazy mode
    # build it now, after the service stack has been materialized, so the user
    # never sees the half-composed intermediary page.
    from ai_pm_lab_privacy_gate.ui.settings_service_hub_2026 import (
        apply_approved_settings_mockup_2026,
    )

    apply_approved_settings_mockup_2026(main_window)
    stack = getattr(settings, "settings_service_stack", None)
    hub = getattr(settings, "settings_service_hub", None)
    if stack is not None and hub is not None:
        stack.setCurrentWidget(hub)
    try:
        settings.ensurePolished()
        if settings.layout() is not None:
            settings.layout().activate()
    except RuntimeError:
        pass


def _fix_protect_empty_source_action(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    choose = getattr(page, "_protect_empty_choose", None) if page is not None else None
    if choose is None or bool(getattr(choose, "_privacygate_connected_source_action", False)):
        return

    context_bar = getattr(page, "_managed_workspace_context_bar", None)
    subtitle = getattr(page, "_protect_empty_source_subtitle", None)

    def provider_key() -> str:
        if context_bar is None:
            return ""
        combo = getattr(context_bar, "source_combo", None)
        return str(combo.currentData() or "") if combo is not None else ""

    def refresh_copy(*_args) -> None:
        provider = provider_key()
        if provider == "gmail":
            choose.setText("Choose an email")
            if subtitle is not None:
                subtitle.setText(
                    "Choose an email from the connected Gmail account or switch to Paste text."
                )
        elif provider == "google_drive":
            choose.setText("Choose a Drive file")
            if subtitle is not None:
                subtitle.setText(
                    "Choose a file from the connected Google Drive account or switch to Paste text."
                )
        else:
            choose.setText("Choose a source")
            if subtitle is not None:
                subtitle.setText(
                    "Choose from your connected sources. Use Upload or drag & drop for a local file."
                )

    def open_source() -> None:
        page._protect_entry_force_empty = False
        provider = provider_key()
        direct = getattr(page, "_protect_2026_connected_browse_action", None)
        if direct is None and context_bar is not None:
            direct = getattr(context_bar, "browse", None)

        # Preserve the direct Gmail/Drive flow when one of those providers is
        # already selected in the connected-source context.
        if provider in {"gmail", "google_drive"} and direct is not None:
            direct.click()
            return

        # Otherwise open the canonical Connected Sources picker rather than the
        # Windows local-file dialog. Local upload remains a separate action.
        picker = getattr(page, "_protect_source_connected", None)
        if picker is not None:
            picker.click()
            return
        if direct is not None:
            direct.click()
            return
        page.browse_button.click()

    try:
        choose.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    choose.clicked.connect(open_source)

    combo = getattr(context_bar, "source_combo", None) if context_bar is not None else None
    if combo is not None:
        combo.currentIndexChanged.connect(refresh_copy)
    choose._privacygate_connected_source_action = True
    refresh_copy()


def install_lazy_runtime_compat_2026(main_window) -> None:
    """Install post-bootstrap compatibility for lazy core pages."""
    if bool(getattr(main_window, "_privacygate_lazy_runtime_compat_2026", False)):
        return
    main_window._privacygate_lazy_runtime_compat_2026 = True

    _compact_loading_dialog(main_window)
    _fix_protect_empty_source_action(main_window)

    pages = getattr(main_window, "pages", None)
    if pages is not None:
        for index in range(pages.count()):
            _attach_page_loading(main_window, pages.widget(index))

    original_ensure_page = getattr(main_window, "_ensure_page", None)
    if callable(original_ensure_page):
        def ensure_page(index: int):
            instances = getattr(main_window, "_page_instances", {})
            already_loaded = index in instances
            controller = getattr(main_window, "_unified_loading", None)
            operation_key = f"page.load:{index}"
            show_loading = (
                not already_loaded
                and index in _LAZY_PAGE_LABELS
                and index != 6  # Contact may be materialized by the silent update check.
                and controller is not None
                and bool(getattr(main_window, "_privacygate_startup_ready", False))
            )

            if show_loading:
                label, message = _LAZY_PAGE_LABELS[index]
                controller.begin(operation_key, f"Opening {label}", message)
                # Give Qt one paint turn before the QWidget constructor begins.
                QApplication.processEvents()

            try:
                page = original_ensure_page(index)
                _attach_page_loading(main_window, page)
                if index == 5:
                    _finalize_lazy_settings(main_window)
                return page
            except Exception:
                if show_loading:
                    controller.end(operation_key)
                raise
            finally:
                if show_loading:
                    # Keep the popup through the page switch itself; close on the
                    # next event-loop turn, not on an arbitrary duration.
                    QTimer.singleShot(0, lambda key=operation_key, c=controller: c.end(key))

        main_window._ensure_page = ensure_page

    original_show_page = getattr(main_window, "_show_page", None)
    if callable(original_show_page):
        def show_page(index: int):
            try:
                return original_show_page(index)
            except IndexError:
                stack = getattr(main_window, "pages", None)
                if stack is None or not 0 <= int(index) < stack.count():
                    raise

                target = stack.widget(int(index))
                personal = getattr(main_window, "personal_workspace_page", None)
                if (
                    target is personal
                    and not bool(getattr(main_window, "_privacygate_startup_ready", False))
                ):
                    # Keep the new Protect-first startup. The historical personal
                    # dashboard redirect is still available from Overview after
                    # the first paint, but no longer steals the initial landing.
                    return None

                stack.setCurrentIndex(int(index))
                sidebar = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
                sync = getattr(sidebar, "_sync_checked_state", None) if sidebar is not None else None
                if callable(sync):
                    QTimer.singleShot(0, sync)
                return None

        main_window._show_page = show_page
