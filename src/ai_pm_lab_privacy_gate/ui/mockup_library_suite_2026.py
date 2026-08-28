from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    policy_status_text,
    scoped_documents,
)
from ai_pm_lab_privacy_gate.ui import mockup_library_final_2026 as _final_library
from ai_pm_lab_privacy_gate.ui.mockup_library_final_2026 import (
    _provider_info,
    install_mockup_library_final_2026,
)


_INSTALLED = False
_LOCAL_SOURCE_KEYS = {"__local_files__", "__local_text__"}


def _app_catalog() -> OrderedDict[str, tuple[str, str]]:
    """Read the live Apps catalog instead of maintaining a second provider list.

    ``apps_catalog_upgrade`` mutates ``apps_hub.APPS`` as connectors become real,
    so resolving it at refresh time means Library automatically follows future
    plugin additions without another hard-coded Gmail/Drive-only list.
    """

    result: OrderedDict[str, tuple[str, str]] = OrderedDict()
    try:
        from ai_pm_lab_privacy_gate.ui import apps_hub

        for app in tuple(apps_hub.APPS):
            if len(app) < 4:
                continue
            key = str(app[0] or "").strip()
            title = str(app[1] or key).strip()
            icon_key = str(app[3] or "workflow").strip() or "workflow"
            if key:
                result[key] = (title, icon_key)
    except Exception:
        pass
    return result


def _connected_source_catalog(page: LibraryPage, documents) -> OrderedDict[str, tuple[str, str]]:
    """Return real connected plugins plus sources represented by local documents."""

    catalog = _app_catalog()
    connected: OrderedDict[str, tuple[str, str]] = OrderedDict()

    # AppsHub is the product-level catalog and its _connected() method delegates
    # to the real connector service. This catches every connector currently
    # installed by PrivacyGate, including catalog upgrades added after this file.
    try:
        apps_page = getattr(page.window(), "apps_hub_page", None)
        checker = getattr(apps_page, "_connected", None)
        if callable(checker):
            for key, (title, icon_key) in catalog.items():
                try:
                    if bool(checker(key)):
                        connected[key] = (title, icon_key)
                except Exception:
                    continue
    except Exception:
        pass

    # Compatibility fallback for connectors exposed through the older Library
    # source service. It is deliberately additive and still checks real state.
    legacy_connected = getattr(page, "_connected_sources", None)
    if callable(legacy_connected):
        try:
            for key, title in legacy_connected().items():
                provider = str(key or "").strip()
                if not provider or provider.startswith("__"):
                    continue
                known_title, known_icon = catalog.get(provider, (str(title or provider), "workflow"))
                connected.setdefault(provider, (known_title, known_icon))
        except Exception:
            pass

    # A disconnected historical source must remain filterable if protected local
    # documents from that source still exist. This does not imply it is connected.
    for document in documents:
        provider, provider_label, _account = _provider_info(page, document)
        normalized = _dynamic_source_bucket(page, document)
        if normalized in {"local", "other"}:
            continue
        title, icon_key = catalog.get(normalized, (provider_label or normalized, "workflow"))
        connected.setdefault(normalized, (title, icon_key))

    return connected


def _catalog_provider_from_label(label: str) -> str:
    folded = str(label or "").strip().casefold()
    if not folded:
        return ""
    for key, (title, _icon_key) in _app_catalog().items():
        if folded in {key.casefold(), title.casefold()}:
            return key
    return ""


def _dynamic_source_bucket(page: LibraryPage, document) -> str:
    """Use the real provider key rather than collapsing every plugin into Other."""

    key, label, _account = _provider_info(page, document)
    key = str(key or "").strip()
    label = str(label or "").strip()
    folded = f"{key} {label}".casefold()

    if key in _LOCAL_SOURCE_KEYS or "local" in folded or "pasted" in folded:
        return "local"
    if key and not key.startswith("__"):
        return key

    # Old documents may carry a legacy provider key. Match their human-readable
    # provider label back to the current catalog when possible.
    matched = _catalog_provider_from_label(label)
    if matched:
        return matched
    if key.startswith("__legacy_provider__:"):
        legacy = key.split(":", 1)[1].strip()
        matched = _catalog_provider_from_label(legacy)
        if matched:
            return matched
    return "other"


def _source_icon_received(page: LibraryPage, provider: str, pixmap) -> None:
    if pixmap is None or pixmap.isNull():
        return
    try:
        page._library_provider_pixmaps[provider] = pixmap
    except Exception:
        pass
    combo = getattr(page, "_library_source_filter_2026", None)
    if combo is None:
        return
    try:
        index = combo.findData(provider)
        if index >= 0:
            combo.setItemIcon(index, QIcon(pixmap))
    except RuntimeError:
        return


def _source_entry_icon(page: LibraryPage, provider: str, fallback_icon: str) -> QIcon:
    cached = getattr(page, "_library_provider_pixmaps", {})
    pixmap = cached.get(provider) if isinstance(cached, dict) else None
    if pixmap is not None and not pixmap.isNull():
        return QIcon(pixmap)

    loader = getattr(page, "_library_logo_loader", None)
    requested = getattr(page, "_library_source_logo_requested_2026", set())
    if loader is not None and provider and provider not in requested:
        requested.add(provider)
        page._library_source_logo_requested_2026 = requested
        loader.load(
            provider,
            lambda loaded, key=provider: _source_icon_received(page, key, loaded),
        )
    return icon(fallback_icon or "workflow", color="#475467", size=18)


def _sync_source_combo(page: LibraryPage, documents) -> None:
    combo = page._library_source_filter_2026
    previous = str(combo.currentData() or "")
    sources_present = {_dynamic_source_bucket(page, document) for document in documents}
    providers = _connected_source_catalog(page, documents)

    combo.blockSignals(True)
    combo.clear()
    combo.setIconSize(QSize(18, 18))
    combo.addItem(icon("library", color="#475467", size=18), "All sources", "")

    if "local" in sources_present:
        combo.addItem(icon("document", color="#475467", size=18), "Local", "local")

    for provider, (title, fallback_icon) in providers.items():
        combo.addItem(_source_entry_icon(page, provider, fallback_icon), title, provider)

    if "other" in sources_present:
        combo.addItem(icon("workflow", color="#475467", size=18), "Other", "other")

    target = combo.findData(previous)
    combo.setCurrentIndex(target if target >= 0 else 0)
    combo.blockSignals(False)


def _dynamic_sync_final_filter_options(page: LibraryPage, documents) -> None:
    """Keep existing Account/Label/File Type semantics; make Sources dynamic."""

    _sync_source_combo(page, documents)

    accounts: dict[str, str] = {}
    for document in documents:
        key, label = _final_library._account_filter_key(page, document)
        if key and label:
            accounts.setdefault(key, label)
    _final_library._sync_combo(
        page._library_account_filter_2026,
        [("", "All accounts")] + sorted(accounts.items(), key=lambda item: item[1].casefold()),
    )

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


def _provider_logo_received(page, document_id: str, provider: str, pixmap) -> None:
    if pixmap is None or pixmap.isNull():
        return
    try:
        page._library_provider_pixmaps[provider] = pixmap
    except Exception:
        pass
    row = getattr(page, "_library_final_rows", {}).get(document_id)
    target = getattr(row, "_library_provider_logo_2026", None) if row is not None else None
    if target is None:
        return
    try:
        target.setPixmap(
            pixmap.scaled(
                15,
                15,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    except RuntimeError:
        # A refresh may have replaced this row while an asynchronous logo request
        # was in flight. The next row uses the cached official artwork.
        return


def _decorate_provider_rows(page: LibraryPage) -> None:
    """Put official provider artwork beside source provenance when available."""
    rows = getattr(page, "_library_final_rows", {})
    loader = getattr(page, "_library_logo_loader", None)
    cached = getattr(page, "_library_provider_pixmaps", {})

    for document in page._documents:
        row = rows.get(document.document_id)
        if row is None or bool(getattr(row, "_library_provider_decorated_2026", False)):
            continue
        row._library_provider_decorated_2026 = True
        root = row.layout()
        body = root.itemAt(1).layout() if root is not None and root.count() > 1 else None
        source_label = body.itemAt(1).widget() if body is not None and body.count() > 1 else None
        if body is None or not isinstance(source_label, QLabel):
            continue

        provider, _provider_label, _account_label = _provider_info(page, document)
        if not provider or provider.startswith("__"):
            continue

        source_wrap = QFrame()
        source_wrap.setStyleSheet("QFrame{background:transparent;border:none;}")
        source_row = QHBoxLayout(source_wrap)
        source_row.setContentsMargins(0, 0, 0, 0)
        source_row.setSpacing(5)
        logo = QLabel()
        logo.setFixedSize(16, 16)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background:transparent;border:none;")
        logo.setToolTip(_provider_label)
        row._library_provider_logo_2026 = logo

        body.removeWidget(source_label)
        source_row.addWidget(logo)
        source_row.addWidget(source_label, 1)
        body.insertWidget(1, source_wrap)

        pixmap = cached.get(provider) if isinstance(cached, dict) else None
        if pixmap is not None and not pixmap.isNull():
            _provider_logo_received(page, document.document_id, provider, pixmap)
        elif loader is not None:
            loader.load(
                provider,
                lambda loaded, doc_id=document.document_id, key=provider: _provider_logo_received(
                    page, doc_id, key, loaded
                ),
            )


def _safe_current(page: LibraryPage, previous_current):
    document = previous_current(page)
    if document is None or not bool(getattr(page, "_privacygate_library_final_ui_2026", False)):
        return document
    if not hasattr(page, "_library_scoped_documents_2026"):
        return document

    row = page.table.currentRow()
    if row < 0 or page.table.isRowHidden(row):
        return None
    try:
        selected_rows = {index.row() for index in page.table.selectionModel().selectedRows()}
        if row not in selected_rows:
            return None
    except Exception:
        return None

    allowed_ids = {
        item.document_id
        for item in getattr(page, "_library_scoped_documents_2026", ())
    }
    if document.document_id not in allowed_ids:
        return None
    return document


def _clear_empty_detail(page: LibraryPage) -> None:
    """Never leave a hidden Personal document painted in an empty Organization view."""

    if page._current() is not None:
        for name in ("_detail_findings_badge", "_detail_mode_badge", "_detail_mcp_badge"):
            widget = getattr(page, name, None)
            if widget is not None:
                widget.show()
        detail_icon = getattr(page, "_detail_provider_logo", None)
        if detail_icon is not None:
            detail_icon.show()
        return

    page.preview.clear()
    page._set_actions(False)
    use_ai = getattr(page, "_library_use_ai_button_2026", None)
    if use_ai is not None:
        use_ai.setEnabled(False)

    # These badges belong to the older detail header retained as a controller
    # surface. Hiding them avoids showing findings/mode/MCP state from a row that
    # is now outside the active workspace.
    for name in ("_detail_findings_badge", "_detail_mode_badge", "_detail_mcp_badge"):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.hide()
    detail_icon = getattr(page, "_detail_provider_logo", None)
    if detail_icon is not None:
        detail_icon.hide()
    page._detail_provider_key = ""

    context = getattr(page, "_library_workspace_context_2026", None)
    context_label = getattr(page, "_library_detail_context_2026", None)
    if context_label is not None:
        if context is not None and context.managed:
            context_label.setText(
                f"Managed by {context.name} · {policy_status_text(context)} · No Organization document selected"
            )
        else:
            context_label.setText("Protected locally · No document selected")


def _enrich_detail_context(page: LibraryPage) -> None:
    document = page._current()
    label = getattr(page, "_library_detail_context_2026", None)
    if document is None or label is None:
        _clear_empty_detail(page)
        return

    for name in ("_detail_findings_badge", "_detail_mode_badge", "_detail_mcp_badge"):
        widget = getattr(page, name, None)
        if widget is not None:
            widget.show()
    detail_icon = getattr(page, "_detail_provider_logo", None)
    if detail_icon is not None:
        detail_icon.show()

    base = str(label.text() or "")
    marker = " · Profile:"
    if marker in base:
        base = base.split(marker, 1)[0]
    profile = document.profile_key.replace("_", " ").title()
    mode = document.replacement_mode.replace("_", " ").title()
    label.setText(f"{base} · Profile: {profile} · Mode: {mode}")


def _select_scoped_document(page: LibraryPage, document_id: str) -> None:
    """Programmatic selection must never reveal another workspace's document."""

    def choose_visible() -> bool:
        for row, document in enumerate(page._documents):
            if document.document_id != document_id:
                continue
            if page.table.isRowHidden(row):
                return False
            page.table.selectRow(row)
            return True
        return False

    page.refresh()
    if choose_visible():
        return

    try:
        target = page.library.get(document_id)
    except Exception:
        return
    _context, _metadata, allowed = scoped_documents(page, (target,))
    if not allowed:
        # Exact Organization scoping is intentional. Personal/legacy content is
        # not surfaced merely because another page knows its local document ID.
        return

    page.search.blockSignals(True)
    page.search.clear()
    page.search.blockSignals(False)
    page._library_category_2026 = "trash" if target.deleted_at is not None else "all"
    page.show_trash.blockSignals(True)
    page.show_trash.setChecked(target.deleted_at is not None)
    page.show_trash.blockSignals(False)
    for combo_name in (
        "_library_source_filter_2026",
        "_library_account_filter_2026",
        "_library_label_filter_2026",
        "_library_type_filter_2026",
    ):
        combo = getattr(page, combo_name, None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
    page.refresh()
    choose_visible()


def install_mockup_library_suite_2026() -> None:
    """Install the final Library wrappers after the proven legacy layers."""
    global _INSTALLED
    if _INSTALLED:
        return
    install_mockup_library_final_2026()
    _INSTALLED = True

    # Patch only the final Library presentation globals. The real LibraryPage
    # repository/controller and Protect/Restore callbacks remain untouched.
    _final_library._source_bucket = _dynamic_source_bucket
    _final_library._sync_final_filter_options = _dynamic_sync_final_filter_options

    previous_current = LibraryPage._current
    previous_refresh = LibraryPage.refresh
    previous_selection_changed = LibraryPage._selection_changed

    def current(self: LibraryPage):
        return _safe_current(self, previous_current)

    def refresh(self: LibraryPage, *args) -> None:
        previous_refresh(self, *args)
        if not bool(getattr(self, "_privacygate_library_final_ui_2026", False)):
            return
        _decorate_provider_rows(self)
        _enrich_detail_context(self)
        _clear_empty_detail(self)
        # The older visual layer created temporary card widgets before the final
        # rows replaced them. Drop those references so asynchronous logo callbacks
        # cannot target a QWidget already removed from the table.
        self._library_card_widgets = {}

    def selection_changed(self: LibraryPage) -> None:
        previous_selection_changed(self)
        _enrich_detail_context(self)
        _clear_empty_detail(self)

    def select_document(self: LibraryPage, document_id: str) -> None:
        _select_scoped_document(self, document_id)

    LibraryPage._current = current
    LibraryPage.refresh = refresh
    LibraryPage._selection_changed = selection_changed
    LibraryPage.select_document = select_document


def apply_mockup_library_suite_2026(main_window) -> None:
    """Bind workspace/app changes to the single local Library repository experience."""
    if bool(getattr(main_window, "_privacygate_mockup_library_suite_2026", False)):
        return
    main_window._privacygate_mockup_library_suite_2026 = True

    page = getattr(main_window, "library_page", None)
    if page is None:
        return

    def refresh_library(*_args) -> None:
        QTimer.singleShot(0, page.refresh)

    team_page = getattr(main_window, "team_page", None)
    state_changed = getattr(team_page, "state_changed", None) if team_page is not None else None
    if state_changed is not None:
        state_changed.connect(refresh_library)

    policy_changed = getattr(team_page, "policy_changed", None) if team_page is not None else None
    if policy_changed is not None:
        policy_changed.connect(refresh_library)

    old_combo = getattr(main_window, "workspace_sidebar_combo", None)
    if old_combo is not None:
        old_combo.currentIndexChanged.connect(refresh_library)

    controller = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    workspace_menu = getattr(controller, "workspace_menu", None) if controller is not None else None
    if workspace_menu is not None:
        workspace_menu.aboutToHide.connect(refresh_library)

    # Navigating back to Library already calls page.refresh() in MainWindow; this
    # initial refresh also picks up any real connectors installed before the suite
    # was mounted.
    page.refresh()
