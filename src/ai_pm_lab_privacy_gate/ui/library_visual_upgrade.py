from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.provider_logos import PROVIDER_DOMAINS, ProviderLogoLoader


_INSTALLED = False
NAVY = "#062B4F"
NAVY_SOFT = "#17384E"
PETROL = "#0B7180"
MUTED = "#61798A"
BORDER = "#D7E2EA"
SOFT = "#F8FBFC"

_PROVIDER_FALLBACK = {
    "google_drive": "cloud",
    "gmail": "contact",
    "clickup": "workflow",
    "asana": "workflow",
    "trello": "workflow",
    "notion": "document",
    "monday": "workflow",
    "jira": "workflow",
}

_PROVIDER_ACCENT = {
    "google_drive": "#0F9D58",
    "gmail": "#EA4335",
    "clickup": "#7B68EE",
    "asana": "#F06A6A",
    "trello": "#0C66E4",
    "notion": "#111111",
    "monday": "#6161FF",
    "jira": "#0C66E4",
}


class _DocumentCard(QFrame):
    def __init__(self, page: LibraryPage, row: int, document, provider_key: str, provider_label: str, account_label: str) -> None:
        super().__init__()
        self.page = page
        self.row = row
        self.document_id = document.document_id
        self.provider_key = provider_key
        self.setObjectName("LibraryDocumentCard")
        self.setProperty("selected", False)
        self.setMinimumHeight(116)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame#LibraryDocumentCard{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
            "QFrame#LibraryDocumentCard[selected=\"true\"]{background:#F3FAFB;border:1px solid #0B8D98;}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(11, 10, 11, 10)
        root.setSpacing(10)

        tile = QLabel(objectName="LibraryProviderLogo")
        tile.setFixedSize(42, 42)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setStyleSheet(
            "QLabel#LibraryProviderLogo{background:#F7FAFC;border:1px solid #DCE5EB;border-radius:9px;}"
        )
        root.addWidget(tile, alignment=Qt.AlignmentFlag.AlignTop)
        self.provider_logo = tile

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel(document.title)
        title.setToolTip(document.title)
        title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        star = QLabel("★" if document.favorite else "☆")
        star.setToolTip("Favorite" if document.favorite else "Not favorite")
        star.setStyleSheet(
            f"color:{PETROL if document.favorite else '#8397A6'};font-size:15px;font-weight:900;"
        )
        title_row.addWidget(title, 1)
        title_row.addWidget(star)
        body.addLayout(title_row)

        source_text = provider_label
        if account_label:
            source_text += f"  •  {account_label}"
        source = QLabel(source_text)
        source.setToolTip(source_text)
        source.setStyleSheet(f"color:{MUTED};font-size:9px;")
        body.addWidget(source)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(_badge(f"{document.findings_count} findings", "#EAF5F6", "#0B7180"))
        badges.addWidget(_badge(document.replacement_mode.replace("_", " ").title(), "#EEF4FA", "#2E678D"))
        if document.mcp_shared:
            badges.addWidget(_badge("AI shared", "#EAF7EF", "#23824B"))
        else:
            badges.addWidget(_badge("AI blocked", "#FFF4DF", "#A56A00"))
        badges.addStretch(1)
        body.addLayout(badges)

        updated = QLabel(document.updated_at.astimezone().strftime("%d %b %Y, %I:%M %p"))
        updated.setStyleSheet("color:#536F82;font-size:9px;")
        body.addWidget(updated)
        root.addLayout(body, 1)

        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        _apply_provider_logo(page, provider_key, tile, 23)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.page.table.selectRow(self.row)
        super().mousePressEvent(event)



def _badge(text: str, background: str, foreground: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{background};color:{foreground};border:0;border-radius:7px;"
        "padding:3px 7px;font-size:8px;font-weight:850;"
    )
    return label



def _provider_info(page: LibraryPage, document) -> tuple[str, str, str]:
    provider_key = ""
    provider_label = "Local file"
    account_label = ""

    source_method = getattr(page, "_source_for_document", None)
    if callable(source_method):
        try:
            provider_key, provider_label = source_method(document)
        except Exception:
            provider_key = ""

    account_method = getattr(page, "_account_for_document", None)
    if callable(account_method):
        try:
            _account_key, account_label = account_method(document)
            if account_label == "Legacy / unknown account":
                account_label = ""
        except Exception:
            account_label = ""

    if provider_key.startswith("__"):
        provider_key = ""
    return provider_key, provider_label or "Local file", account_label



def _fallback_icon(provider_key: str, size: int) -> QIcon:
    key = _PROVIDER_FALLBACK.get(provider_key, "document")
    color = _PROVIDER_ACCENT.get(provider_key, PETROL)
    return icon(key, color=color, size=size)



def _apply_provider_logo(page: LibraryPage, provider_key: str, target: QLabel, size: int) -> None:
    cached = getattr(page, "_library_provider_pixmaps", {}).get(provider_key)
    if isinstance(cached, QPixmap) and not cached.isNull():
        target.setPixmap(cached.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        return

    target.setPixmap(_fallback_icon(provider_key, size).pixmap(size, size))
    if not provider_key or provider_key not in PROVIDER_DOMAINS:
        return

    requested = getattr(page, "_library_logo_requested", set())
    if provider_key in requested:
        return
    requested.add(provider_key)
    page._library_logo_requested = requested

    loader = getattr(page, "_library_logo_loader", None)
    if loader is None:
        return

    def received(pixmap: QPixmap, provider: str = provider_key) -> None:
        if pixmap.isNull():
            return
        page._library_provider_pixmaps[provider] = pixmap
        _refresh_loaded_provider_logo(page, provider)

    loader.load(provider_key, received)



def _refresh_loaded_provider_logo(page: LibraryPage, provider_key: str) -> None:
    pixmap = getattr(page, "_library_provider_pixmaps", {}).get(provider_key)
    if not isinstance(pixmap, QPixmap) or pixmap.isNull():
        return
    for card in getattr(page, "_library_card_widgets", {}).values():
        if getattr(card, "provider_key", "") != provider_key:
            continue
        card.provider_logo.setPixmap(
            pixmap.scaled(23, 23, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
    if getattr(page, "_detail_provider_key", "") == provider_key:
        page._detail_provider_logo.setPixmap(
            pixmap.scaled(27, 27, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
    combo = getattr(page, "_source_folder_combo", None)
    if combo is not None:
        for index in range(combo.count()):
            if str(combo.itemData(index) or "") == provider_key:
                combo.setItemIcon(index, QIcon(pixmap))



def _polish_existing_layout(page: LibraryPage) -> None:
    page._library_logo_loader = ProviderLogoLoader(page.library.data_dir, page)
    page._library_provider_pixmaps: dict[str, QPixmap] = {}
    page._library_logo_requested: set[str] = set()
    page._library_card_widgets: dict[str, _DocumentCard] = {}

    root = page.layout()
    if root is not None:
        root.setSpacing(12)

    navigator = getattr(page, "_source_folder_bar", None)
    if navigator is not None:
        navigator.setStyleSheet(
            "QFrame#LibrarySourceNavigator{background:#FBFDFE;border:1px solid #D5E1E8;border-radius:11px;}"
        )
    reset = getattr(page, "_source_reset_button", None)
    if reset is not None:
        reset.setText("Reset filters")
        reset.setMinimumHeight(38)
        reset.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C8D7E0;border-radius:9px;"
            "padding:7px 13px;font-size:9px;font-weight:850;}"
            "QPushButton:hover{background:#F0F8F9;border-color:#8FBEC4;}"
        )

    for combo in (getattr(page, "_source_folder_combo", None), getattr(page, "_source_account_combo", None)):
        if combo is not None:
            combo.setIconSize(QSize(18, 18))
            combo.setMinimumHeight(40)

    page.search.setMinimumHeight(40)
    page.search.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E1;border-radius:9px;"
        "padding:8px 12px;font-size:10px;}QLineEdit:focus{border-color:#1595A3;}"
    )

    for button in (page.backup_button, page.import_backup_button, page.refresh_button):
        button.setMinimumHeight(38)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E1;border-radius:9px;"
            "padding:7px 12px;font-weight:800;}QPushButton:hover{background:#F2F8F9;border-color:#9BC9CE;}"
        )

    table = page.table
    table.setColumnHidden(0, True)
    table.setColumnHidden(1, True)
    table.setColumnHidden(2, False)
    table.setColumnHidden(3, True)
    table.setColumnHidden(4, True)
    table.setColumnHidden(5, True)
    table.horizontalHeader().hide()
    table.verticalHeader().hide()
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(2, table.horizontalHeader().ResizeMode.Stretch)
    table.setStyleSheet(
        "QTableWidget{background:#FFFFFF;border:0;outline:0;padding:0;}"
        "QTableWidget::item{background:transparent;border:0;padding:0;}"
        "QTableWidget::item:selected{background:transparent;border:0;}"
        "QScrollBar:vertical{background:#F2F6F8;width:9px;border-radius:4px;margin:1px;}"
        "QScrollBar::handle:vertical{background:#B9C9D2;min-height:30px;border-radius:4px;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
    )

    table_card = table.parentWidget()
    if table_card is not None:
        table_card.setMinimumWidth(350)
        table_card.setStyleSheet(
            "QFrame#Card{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
        )
        table_layout = table_card.layout()
        if table_layout is not None:
            heading_row = QHBoxLayout()
            page._documents_heading = QLabel("Documents")
            page._documents_heading.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:900;")
            sort_combo = QComboBox()
            sort_combo.addItem("Newest first")
            sort_combo.setFixedWidth(118)
            sort_combo.setMinimumHeight(30)
            sort_combo.setStyleSheet(
                "QComboBox{background:#FFFFFF;color:#365469;border:0;padding:4px 7px;font-size:9px;font-weight:750;}"
            )
            heading_row.addWidget(page._documents_heading)
            heading_row.addStretch(1)
            heading_row.addWidget(sort_combo)
            table_layout.insertLayout(0, heading_row)
            page._library_sort_combo = sort_combo

    preview_card = page.preview.parentWidget()
    if preview_card is not None:
        preview_card.setMinimumWidth(560)
        preview_card.setStyleSheet(
            "QFrame#Card{background:#FFFFFF;border:1px solid #D7E2EA;border-radius:11px;}"
        )
        preview_layout = preview_card.layout()
        if preview_layout is not None:
            preview_layout.removeWidget(page.preview_title)
            preview_layout.removeWidget(page.meta)

            detail = QFrame(objectName="LibraryDetailHeader")
            detail.setStyleSheet("QFrame#LibraryDetailHeader{background:#FFFFFF;border:0;}")
            detail_row = QHBoxLayout(detail)
            detail_row.setContentsMargins(2, 2, 2, 5)
            detail_row.setSpacing(11)

            tile = QLabel(objectName="LibraryDetailProviderLogo")
            tile.setFixedSize(50, 50)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setStyleSheet(
                "QLabel#LibraryDetailProviderLogo{background:#F4F8FB;border:1px solid #DFE7ED;border-radius:10px;}"
            )
            page._detail_provider_logo = tile
            page._detail_provider_key = ""
            detail_row.addWidget(tile, alignment=Qt.AlignmentFlag.AlignTop)

            titles = QVBoxLayout()
            titles.setContentsMargins(0, 0, 0, 0)
            titles.setSpacing(5)
            page.preview_title.setStyleSheet(f"color:{NAVY};font-size:18px;font-weight:950;")
            page.meta.setStyleSheet(f"color:{MUTED};font-size:9px;")
            titles.addWidget(page.preview_title)
            titles.addWidget(page.meta)
            detail_row.addLayout(titles, 1)

            badges = QHBoxLayout()
            badges.setSpacing(7)
            page._detail_findings_badge = _badge("0 findings", "#EAF5F6", "#0B7180")
            page._detail_mode_badge = _badge("Reversible", "#EEF4FA", "#2E678D")
            page._detail_mcp_badge = _badge("AI blocked", "#FFF4DF", "#A56A00")
            badges.addWidget(page._detail_findings_badge)
            badges.addWidget(page._detail_mode_badge)
            badges.addWidget(page._detail_mcp_badge)
            detail_row.addLayout(badges)
            preview_layout.insertWidget(0, detail)
            page._library_detail_header = detail

            protected_bar = QFrame(objectName="ProtectedContentBar")
            protected_bar.setStyleSheet(
                "QFrame#ProtectedContentBar{background:#FBFDFE;border:1px solid #D7E5EA;border-bottom:0;"
                "border-top-left-radius:9px;border-top-right-radius:9px;}"
            )
            protected_row = QHBoxLayout(protected_bar)
            protected_row.setContentsMargins(10, 7, 10, 7)
            shield = QLabel()
            shield.setPixmap(icon("protect", color=PETROL, size=18).pixmap(18, 18))
            protected_title = QLabel("PROTECTED CONTENT")
            protected_title.setStyleSheet(f"color:{PETROL};font-size:9px;font-weight:950;")
            local_note = QLabel("Local protected copy")
            local_note.setStyleSheet("color:#718696;font-size:8px;")
            protected_row.addWidget(shield)
            protected_row.addWidget(protected_title)
            protected_row.addStretch(1)
            protected_row.addWidget(local_note)
            preview_index = preview_layout.indexOf(page.preview)
            preview_layout.insertWidget(max(1, preview_index), protected_bar)
            page._protected_content_bar = protected_bar

    page.preview.setStyleSheet(
        "QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D7E5EA;border-radius:9px;"
        "padding:10px;font-family:Consolas, 'Courier New', monospace;font-size:10px;selection-background-color:#CDEBED;}"
    )

    secondary = (
        "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E1;border-radius:8px;"
        "padding:7px 10px;font-weight:800;}QPushButton:hover{background:#F1F8F9;border-color:#91C5CA;}"
        "QPushButton:disabled{background:#F5F7F8;color:#9AA8B2;border-color:#E2E8EC;}"
    )
    for button in (page.copy_button, page.export_button, page.edit_button, page.favorite_button, page.mcp_button):
        button.setMinimumHeight(36)
        button.setStyleSheet(secondary)
    page.restore_button.setMinimumHeight(36)
    page.restore_button.setStyleSheet(
        "QPushButton{background:#0B8390;color:#FFFFFF;border:1px solid #0B8390;border-radius:8px;"
        "padding:7px 12px;font-weight:900;}QPushButton:hover{background:#096B76;}"
        "QPushButton:disabled{background:#B7CFD2;color:#F5FAFA;border-color:#B7CFD2;}"
    )
    page.restore_trash_button.setMinimumHeight(36)
    page.delete_button.setMinimumHeight(36)
    page.delete_button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#C62828;border:1px solid #F0B9B9;border-radius:8px;"
        "padding:7px 11px;font-weight:850;}QPushButton:hover{background:#FFF4F4;border-color:#E89494;}"
    )

    splitter = table_card.parentWidget() if table_card is not None else None
    if splitter is not None and hasattr(splitter, "setSizes"):
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([385, 900])
        try:
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
        except Exception:
            pass



def _render_document_cards(page: LibraryPage) -> None:
    if not getattr(page, "_library_visual_ready", False):
        return

    page._library_card_widgets = {}
    for row, document in enumerate(page._documents):
        item = page.table.item(row, 2)
        if item is None:
            continue
        provider_key, provider_label, account_label = _provider_info(page, document)
        card = _DocumentCard(page, row, document, provider_key, provider_label, account_label)
        page.table.setRowHeight(row, 126)
        page.table.setCellWidget(row, 2, card)
        page._library_card_widgets[document.document_id] = card

    _sync_source_combo_icons(page)
    _update_visible_count(page)
    _update_card_selection(page)



def _sync_source_combo_icons(page: LibraryPage) -> None:
    combo = getattr(page, "_source_folder_combo", None)
    if combo is None:
        return
    combo.setIconSize(QSize(18, 18))
    for index in range(combo.count()):
        provider_key = str(combo.itemData(index) or "")
        if not provider_key or provider_key.startswith("__"):
            continue
        cached = page._library_provider_pixmaps.get(provider_key)
        if isinstance(cached, QPixmap) and not cached.isNull():
            combo.setItemIcon(index, QIcon(cached))
        else:
            combo.setItemIcon(index, _fallback_icon(provider_key, 18))
            dummy = QLabel()
            _apply_provider_logo(page, provider_key, dummy, 18)



def _update_visible_count(page: LibraryPage) -> None:
    heading = getattr(page, "_documents_heading", None)
    if heading is None:
        return
    visible = sum(1 for row in range(page.table.rowCount()) if not page.table.isRowHidden(row))
    heading.setText(f"Documents ({visible})")



def _update_card_selection(page: LibraryPage) -> None:
    current = page._current()
    current_id = current.document_id if current is not None else ""
    for document_id, card in getattr(page, "_library_card_widgets", {}).items():
        card.set_selected(document_id == current_id)



def _clear_detail(page: LibraryPage) -> None:
    if not getattr(page, "_library_visual_ready", False):
        return
    page._detail_provider_key = ""
    page._detail_provider_logo.setPixmap(icon("document", color=PETROL, size=27).pixmap(27, 27))
    page._detail_findings_badge.setText("0 findings")
    page._detail_mode_badge.setText("Protected")
    page._detail_mcp_badge.setText("AI blocked")



def _update_detail(page: LibraryPage) -> None:
    if not getattr(page, "_library_visual_ready", False):
        return
    document = page._current()
    if document is None:
        _clear_detail(page)
        _update_card_selection(page)
        return

    provider_key, provider_label, account_label = _provider_info(page, document)
    metadata = getattr(page, "_source_metadata_map", {}).get(document.document_id)
    item_title = str(getattr(metadata, "item_title", "") or "").strip() if metadata is not None else ""

    trail = provider_label
    if account_label:
        trail += f"  ›  {account_label}"
    if item_title and item_title.casefold() != document.title.casefold():
        trail += f"  ›  {item_title}"
    page.meta.setText(trail)
    page.meta.setToolTip(trail)
    page._detail_findings_badge.setText(f"{document.findings_count} findings")
    page._detail_mode_badge.setText(document.replacement_mode.replace("_", " ").title())
    if document.mcp_shared:
        page._detail_mcp_badge.setText("AI shared")
        page._detail_mcp_badge.setStyleSheet(
            "background:#EAF7EF;color:#23824B;border:0;border-radius:7px;padding:3px 7px;font-size:8px;font-weight:850;"
        )
    else:
        page._detail_mcp_badge.setText("AI blocked")
        page._detail_mcp_badge.setStyleSheet(
            "background:#FFF4DF;color:#A56A00;border:0;border-radius:7px;padding:3px 7px;font-size:8px;font-weight:850;"
        )

    page._detail_provider_key = provider_key
    _apply_provider_logo(page, provider_key, page._detail_provider_logo, 27)
    _update_card_selection(page)



def install_library_visual_upgrade() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = LibraryPage.__init__
    previous_refresh = LibraryPage.refresh
    previous_selection_changed = LibraryPage._selection_changed
    previous_filter = getattr(LibraryPage, "_apply_source_folder_filter", None)

    def init(self: LibraryPage, *args, **kwargs) -> None:
        self._library_visual_ready = False
        previous_init(self, *args, **kwargs)
        _polish_existing_layout(self)
        self._library_visual_ready = True
        self.refresh()

    def refresh(self: LibraryPage, *args) -> None:
        previous_refresh(self, *args)
        if not getattr(self, "_library_visual_ready", False):
            return
        _render_document_cards(self)
        _update_detail(self)

    def selection_changed(self: LibraryPage) -> None:
        previous_selection_changed(self)
        if not getattr(self, "_library_visual_ready", False):
            return
        _update_detail(self)

    def apply_filter(self: LibraryPage) -> None:
        if callable(previous_filter):
            previous_filter(self)
        if not getattr(self, "_library_visual_ready", False):
            return
        _update_visible_count(self)
        _update_detail(self)

    LibraryPage.__init__ = init
    LibraryPage.refresh = refresh
    LibraryPage._selection_changed = selection_changed
    if callable(previous_filter):
        LibraryPage._apply_source_folder_filter = apply_filter  # type: ignore[attr-defined]
