from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui import mockup_library_final_2026 as _final_library
from ai_pm_lab_privacy_gate.ui import mockup_library_suite_2026 as _library_suite


_ACCOUNT_SEPARATOR = "\x1e"
_PROVIDER_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def _provider_title(provider: str) -> str:
    catalog = _library_suite._app_catalog()
    title, _icon_key = catalog.get(provider, (provider.replace("_", " ").title(), "contact"))
    return str(title or provider)


def _provider_fallback_icon(provider: str) -> str:
    catalog = _library_suite._app_catalog()
    _title, icon_key = catalog.get(provider, ("", "contact"))
    return str(icon_key or "contact")


def _workspace_store(page):
    try:
        team_page = getattr(page.window(), "team_page", None)
    except Exception:
        team_page = None
    return getattr(team_page, "_privacygate_workspace_store", None) if team_page is not None else None


def _account_is_available(page, provider: str, account_key: str) -> bool:
    if not account_key.startswith("id:"):
        return True
    store = _workspace_store(page)
    if store is None:
        return True
    try:
        context = store.load()
        return bool(
            store.is_account_available(
                provider,
                account_key[3:],
                context.active_key,
            )
        )
    except Exception:
        return True


def _account_selector(provider: str, label: str) -> str:
    return f"{provider}{_ACCOUNT_SEPARATOR}{label.strip().casefold()}"


def _split_account_selector(value: object) -> tuple[str, str]:
    text = str(value or "")
    if _ACCOUNT_SEPARATOR not in text:
        return "", ""
    provider, label = text.split(_ACCOUNT_SEPARATOR, 1)
    return provider, label


def _account_logo_received(page, provider: str, pixmap) -> None:
    if pixmap is None or pixmap.isNull():
        return
    try:
        page._library_provider_pixmaps[provider] = pixmap
    except Exception:
        pass

    combo = getattr(page, "_library_account_filter_2026", None)
    if combo is None:
        return
    try:
        for index in range(combo.count()):
            if str(combo.itemData(index, _PROVIDER_ROLE) or "") == provider:
                combo.setItemIcon(index, QIcon(pixmap))
    except RuntimeError:
        return


def _account_provider_icon(page, provider: str) -> QIcon:
    cached = getattr(page, "_library_provider_pixmaps", {})
    pixmap = cached.get(provider) if isinstance(cached, dict) else None
    if pixmap is not None and not pixmap.isNull():
        return QIcon(pixmap)

    loader = getattr(page, "_library_logo_loader", None)
    requested = getattr(page, "_library_account_logo_requested_2026", set())
    if loader is not None and provider and provider not in requested:
        requested.add(provider)
        page._library_account_logo_requested_2026 = requested
        loader.load(
            provider,
            lambda loaded, key=provider: _account_logo_received(page, key, loaded),
        )

    return icon(_provider_fallback_icon(provider), color="#475467", size=18)


def _connected_accounts_for_provider(page, provider: str) -> OrderedDict[str, str]:
    method = getattr(page, "_connected_accounts", None)
    if not callable(method):
        return OrderedDict()
    try:
        accounts = method(provider)
    except Exception:
        return OrderedDict()

    result: OrderedDict[str, str] = OrderedDict()
    for key, label in accounts.items():
        account_key = str(key or "").strip()
        account_label = str(label or "").strip()
        if not account_key or not account_label:
            continue
        if not _account_is_available(page, provider, account_key):
            continue
        result[account_key] = account_label
    return result


def _account_rows(page, documents) -> list[tuple[str, str, str]]:
    """Build deduplicated provider/account rows from live connectors + local history."""

    selected_source = str(page._library_source_filter_2026.currentData() or "")
    if selected_source == "local":
        return []

    providers: OrderedDict[str, str] = OrderedDict()
    if selected_source and selected_source != "other":
        providers[selected_source] = _provider_title(selected_source)
    elif not selected_source:
        for provider, (title, _fallback) in _library_suite._connected_source_catalog(
            page, documents
        ).items():
            if provider not in {"local", "other"}:
                providers[provider] = title

    # Key by provider + visible identity. This intentionally collapses duplicate
    # OAuth records that resolve to the same real account label/email.
    rows: OrderedDict[tuple[str, str], tuple[str, str, str]] = OrderedDict()

    for provider in providers:
        for _account_key, account_label in _connected_accounts_for_provider(
            page, provider
        ).items():
            normalized = account_label.casefold()
            rows.setdefault(
                (provider, normalized),
                (provider, account_label, _account_selector(provider, account_label)),
            )

    # Historical/disconnected accounts remain filterable when scoped Library
    # documents still exist. They do not become "connected" merely by appearing.
    for document in documents:
        provider = _library_suite._dynamic_source_bucket(page, document)
        if provider == "local":
            continue
        if selected_source and provider != selected_source:
            continue
        _account_key, account_label = _final_library._account_filter_key(page, document)
        account_label = str(account_label or "").strip()
        if not account_label:
            continue
        normalized = account_label.casefold()
        rows.setdefault(
            (provider, normalized),
            (provider, account_label, _account_selector(provider, account_label)),
        )

    return list(rows.values())


def _sync_account_combo(page, documents) -> None:
    combo = page._library_account_filter_2026
    previous = str(combo.currentData() or "")
    rows = _account_rows(page, documents)
    selected_source = str(page._library_source_filter_2026.currentData() or "")

    combo.blockSignals(True)
    combo.clear()
    combo.setIconSize(QSize(18, 18))
    combo.addItem(icon("contact", color="#475467", size=18), "All accounts", "")
    combo.setItemData(0, "", _PROVIDER_ROLE)

    for provider, account_label, selector in rows:
        display = account_label
        if not selected_source:
            display = f"{_provider_title(provider)} · {account_label}"
        combo.addItem(_account_provider_icon(page, provider), display, selector)
        combo.setItemData(combo.count() - 1, provider, _PROVIDER_ROLE)

    target = combo.findData(previous)
    combo.setCurrentIndex(target if target >= 0 else 0)
    combo.setEnabled(bool(rows))
    combo.blockSignals(False)


def _sync_filter_options(page, documents) -> None:
    """Dynamic sources + workspace-aware real accounts + existing metadata filters."""

    _library_suite._sync_source_combo(page, documents)
    _sync_account_combo(page, documents)

    labels = sorted(
        {label for document in documents for label in document.labels if str(label).strip()},
        key=str.casefold,
    )
    _final_library._sync_combo(
        page._library_label_filter_2026,
        [("", "All labels")] + [(label, label) for label in labels],
    )

    suffixes = sorted({_final_library._document_suffix(document) for document in documents})
    _final_library._sync_combo(
        page._library_type_filter_2026,
        [("", "All file types")]
        + [(suffix, suffix.lstrip(".").upper()) for suffix in suffixes],
    )


def _document_matches_filters(page, document) -> bool:
    category = str(getattr(page, "_library_category_2026", "all") or "all")
    if category == "restorable" and not document.has_mapping:
        return False
    if category == "favorites" and not document.favorite:
        return False

    source = str(page._library_source_filter_2026.currentData() or "")
    document_provider = _library_suite._dynamic_source_bucket(page, document)
    if source and document_provider != source:
        return False

    account_selector = page._library_account_filter_2026.currentData()
    account_provider, account_label = _split_account_selector(account_selector)
    if account_provider or account_label:
        _key, document_account_label = _final_library._account_filter_key(page, document)
        if document_provider != account_provider:
            return False
        if str(document_account_label or "").strip().casefold() != account_label:
            return False

    label = str(page._library_label_filter_2026.currentData() or "")
    if label and label not in document.labels:
        return False

    suffix = str(page._library_type_filter_2026.currentData() or "")
    if suffix and _final_library._document_suffix(document) != suffix:
        return False
    return True


def _install_account_filter_runtime(page) -> None:
    if bool(getattr(page, "_library_account_runtime_2026", False)):
        return
    page._library_account_runtime_2026 = True

    # These functions are looked up dynamically by the final Library refresh/filter
    # controller, so replacing the module globals keeps the proven table/controller
    # implementation and only changes source/account option semantics.
    _final_library._sync_final_filter_options = _sync_filter_options
    _final_library._document_matches_filters = _document_matches_filters

    source_combo = getattr(page, "_library_source_filter_2026", None)
    if source_combo is not None:
        def source_changed(_index: int) -> None:
            documents = tuple(getattr(page, "_library_scoped_documents_2026", ()) or ())
            _sync_account_combo(page, documents)
            page._apply_library_final_filters()

        source_combo.currentIndexChanged.connect(source_changed)

    page.refresh()


def _install_workspace_loading(main_window, page) -> None:
    if bool(getattr(main_window, "_privacygate_workspace_loading_2026", False)):
        return
    controller = getattr(main_window, "_unified_loading", None)
    team_page = getattr(main_window, "team_page", None)
    store = getattr(team_page, "_privacygate_workspace_store", None) if team_page else None
    if controller is None or team_page is None or store is None:
        return

    main_window._privacygate_workspace_loading_2026 = True
    try:
        initial = store.load()
        main_window._privacygate_workspace_loading_key_2026 = initial.active_key
    except Exception:
        main_window._privacygate_workspace_loading_key_2026 = ""
    main_window._privacygate_workspace_loading_generation_2026 = 0

    def active_context():
        try:
            context = store.load()
            return context, context.workspaces.get(context.active_key)
        except Exception:
            return None, None

    def finish_when_ready(generation: int) -> None:
        if generation != getattr(
            main_window, "_privacygate_workspace_loading_generation_2026", 0
        ):
            return
        if getattr(team_page, "_active_worker", None) is not None:
            QTimer.singleShot(80, lambda: finish_when_ready(generation))
            return
        try:
            page.refresh()
        finally:
            controller.end("workspace.switch")

    def begin_if_changed(*_args) -> None:
        context, descriptor = active_context()
        if context is None:
            return
        key = str(context.active_key or "")
        previous = str(
            getattr(main_window, "_privacygate_workspace_loading_key_2026", "") or ""
        )
        if not key or key == previous:
            return

        main_window._privacygate_workspace_loading_key_2026 = key
        generation = int(
            getattr(main_window, "_privacygate_workspace_loading_generation_2026", 0)
        ) + 1
        main_window._privacygate_workspace_loading_generation_2026 = generation

        if descriptor is not None and descriptor.personal:
            title = "Switching to Personal"
            message = "Loading your Personal workspace, connected accounts and local Library…"
        else:
            name = getattr(descriptor, "name", None) or "Organization"
            title = f"Switching to {name}"
            message = (
                f"Loading {name}, applying its policy and refreshing connected accounts "
                "and local Library…"
            )

        controller.begin("workspace.switch", title, message)

        # TeamPage's normal busy wrapper may start immediately after state_changed.
        # Re-promote the workspace operation on the next event-loop tick so the
        # user sees the meaningful switch message instead of a generic busy title.
        QTimer.singleShot(
            0,
            lambda: controller.update("workspace.switch", title=title, message=message),
        )
        QTimer.singleShot(120, lambda: finish_when_ready(generation))

    state_changed = getattr(team_page, "state_changed", None)
    if state_changed is not None:
        state_changed.connect(begin_if_changed)

    old_combo = getattr(main_window, "workspace_sidebar_combo", None)
    if old_combo is not None:
        old_combo.currentIndexChanged.connect(begin_if_changed)

    selector = getattr(team_page, "workspace_selector", None)
    if selector is not None:
        selector.currentIndexChanged.connect(begin_if_changed)


def _install_direct_library_restore(main_window, page) -> None:
    if bool(getattr(main_window, "_privacygate_direct_library_restore_2026", False)):
        return
    restore_page = getattr(main_window, "restore_page", None)
    pages = getattr(main_window, "pages", None)
    if restore_page is None or pages is None:
        return

    main_window._privacygate_direct_library_restore_2026 = True

    try:
        page.restore_requested.disconnect()
    except (RuntimeError, TypeError):
        pass

    def restore_from_library(document_id: str) -> None:
        current = page._current()
        if current is None or current.document_id != document_id:
            QMessageBox.warning(
                page,
                "Restore unavailable",
                "Select a visible document in the active workspace before restoring it.",
            )
            return

        try:
            document = page.library.get(document_id)
        except Exception as exc:
            QMessageBox.critical(page, "Restore unavailable", str(exc))
            return

        if document.deleted_at is not None:
            QMessageBox.information(
                page,
                "Restore unavailable",
                "Restore this document from Trash first.",
            )
            return
        if not document.has_mapping or document.replacement_mode != "reversible":
            QMessageBox.information(
                page,
                "No local restore key",
                "This Library item does not have a reversible local mapping.",
            )
            return

        # Library stores the protected text and encrypted mapping locally. For a
        # Library-origin restore we can therefore load that protected copy directly
        # into the existing Restore controller and start the real restore operation.
        restore_page.clear()
        restore_index = int(pages.indexOf(restore_page))
        if restore_index >= 0:
            main_window._show_page(restore_index)

        restore_page.select_document(document_id)
        restore_page._source_path = None
        restore_page._restored_path = None
        restore_page._report = None
        restore_page._syncing_text = True
        restore_page.input_text.setPlainText(document.protected_text)
        restore_page._syncing_text = False
        restore_page.drop_zone.set_filename(None)
        restore_page._highlight_input_tokens()
        restore_page.restore_status.setText(
            "Protected Library copy loaded. Restoring the original values locally…"
        )
        restore_page._update_restore_state()

        # Let the Restore page paint first. _restore() then uses its existing
        # worker, mappings, safety checks and unified loading dialog.
        QTimer.singleShot(0, restore_page._restore)

    page.restore_requested.connect(restore_from_library)


def apply_library_interaction_runtime_2026(main_window) -> None:
    """Finish Library/workspace interactions without replacing storage semantics."""

    page = getattr(main_window, "library_page", None)
    if page is None:
        return

    _install_account_filter_runtime(page)
    _install_workspace_loading(main_window, page)
    _install_direct_library_restore(main_window, page)
