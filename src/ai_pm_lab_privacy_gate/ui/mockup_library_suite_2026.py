from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import scoped_documents
from ai_pm_lab_privacy_gate.ui.mockup_library_final_2026 import (
    _provider_info,
    install_mockup_library_final_2026,
)


_INSTALLED = False


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


def _enrich_detail_context(page: LibraryPage) -> None:
    document = page._current()
    label = getattr(page, "_library_detail_context_2026", None)
    if document is None or label is None:
        return
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

    previous_refresh = LibraryPage.refresh
    previous_selection_changed = LibraryPage._selection_changed

    def refresh(self: LibraryPage, *args) -> None:
        previous_refresh(self, *args)
        if not bool(getattr(self, "_privacygate_library_final_ui_2026", False)):
            return
        _decorate_provider_rows(self)
        _enrich_detail_context(self)
        # The older visual layer created temporary card widgets before the final
        # rows replaced them. Drop those references so asynchronous logo callbacks
        # cannot target a QWidget already removed from the table.
        self._library_card_widgets = {}

    def selection_changed(self: LibraryPage) -> None:
        previous_selection_changed(self)
        _enrich_detail_context(self)

    def select_document(self: LibraryPage, document_id: str) -> None:
        _select_scoped_document(self, document_id)

    LibraryPage.refresh = refresh
    LibraryPage._selection_changed = selection_changed
    LibraryPage.select_document = select_document


def apply_mockup_library_suite_2026(main_window) -> None:
    """Bind workspace changes to the single local Library repository experience."""
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

    page.refresh()
