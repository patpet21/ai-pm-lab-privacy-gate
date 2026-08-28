from __future__ import annotations

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.library_document_actions_2026 import show_library_ai_menu
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    document_workspace_label,
    policy_status_text,
    scoped_documents,
)
from ai_pm_lab_privacy_gate.ui.mockup_library_organization_2026 import (
    render_organization_library_context,
)
from ai_pm_lab_privacy_gate.ui.mockup_library_personal_2026 import (
    render_personal_library_context,
)


_INSTALLED = False
BLUE = "#2563EB"
INK = "#101828"
TEXT = "#344054"
MUTED = "#667085"
BORDER = "#E4E7EC"
WHITE = "#FFFFFF"
GREEN = "#16A34A"
AMBER = "#D97706"
RED = "#DC2626"
TEAL = "#0891B2"

_SUFFIXES = (
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".pdf",
    ".txt",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
)


def _document_suffix(document) -> str:
    haystack = " ".join(
        str(value or "")
        for value in (
            getattr(document, "title", ""),
            getattr(document, "source_name", ""),
            getattr(document, "source_kind", ""),
        )
    ).lower()
    for suffix in _SUFFIXES:
        if suffix in haystack:
            return suffix
    kind = str(getattr(document, "source_kind", "") or "").lower().strip(".")
    aliases = {
        "word": ".docx",
        "docx": ".docx",
        "doc": ".doc",
        "excel": ".xlsx",
        "xlsx": ".xlsx",
        "xls": ".xls",
        "powerpoint": ".pptx",
        "pptx": ".pptx",
        "ppt": ".ppt",
        "pdf": ".pdf",
        "text": ".txt",
        "txt": ".txt",
        "csv": ".csv",
        "image": ".png",
    }
    return aliases.get(kind, ".txt")


def _native_document_icon(page, document, size: int = 34) -> QPixmap:
    provider = getattr(page, "_library_file_icon_provider_2026", None)
    if provider is None:
        provider = QFileIconProvider()
        page._library_file_icon_provider_2026 = provider
    suffix = _document_suffix(document)
    native = provider.icon(QFileInfo(f"privacygate-library-item{suffix}"))
    if not native.isNull():
        pixmap = native.pixmap(size, size)
        if not pixmap.isNull():
            return pixmap
    fallback = {
        ".pdf": RED,
        ".doc": BLUE,
        ".docx": BLUE,
        ".xls": GREEN,
        ".xlsx": GREEN,
        ".ppt": "#F97316",
        ".pptx": "#F97316",
    }.get(suffix, TEAL)
    return icon("document", color=fallback, size=size).pixmap(size, size)


def _badge(text: str, tone: str = "neutral") -> QLabel:
    palette = {
        "blue": ("#EEF4FF", BLUE, "#D6E4FF"),
        "green": ("#ECFDF3", GREEN, "#BBF7D0"),
        "amber": ("#FFF7ED", AMBER, "#FED7AA"),
        "red": ("#FEF2F2", RED, "#FECACA"),
        "teal": ("#ECFEFF", TEAL, "#A5F3FC"),
        "neutral": ("#F2F4F7", "#475467", BORDER),
    }
    background, foreground, border = palette.get(tone, palette["neutral"])
    label = QLabel(text)
    label.setStyleSheet(
        f"background:{background};color:{foreground};border:1px solid {border};border-radius:7px;"
        "padding:3px 7px;font-size:7px;font-weight:850;"
    )
    return label


def _provider_info(page, document) -> tuple[str, str, str]:
    provider_key = ""
    provider_label = "Local"
    account_label = ""
    source_method = getattr(page, "_source_for_document", None)
    if callable(source_method):
        try:
            provider_key, provider_label = source_method(document)
        except Exception:
            provider_key = ""
            provider_label = "Local"
    account_method = getattr(page, "_account_for_document", None)
    if callable(account_method):
        try:
            _account_key, account_label = account_method(document)
        except Exception:
            account_label = ""
    if account_label == "Legacy / unknown account":
        account_label = "Legacy / unknown account"
    return str(provider_key or ""), str(provider_label or "Local"), str(account_label or "")


def _source_bucket(page, document) -> str:
    key, label, _account = _provider_info(page, document)
    folded = f"{key} {label}".casefold()
    if "gmail" in folded:
        return "gmail"
    if "google_drive" in folded or "google drive" in folded:
        return "google_drive"
    if key in {"__local_files__", "__local_text__"} or "local" in folded or "pasted" in folded:
        return "local"
    return "other"


def _account_filter_key(page, document) -> tuple[str, str]:
    method = getattr(page, "_account_for_document", None)
    if callable(method):
        try:
            key, label = method(document)
            return str(key or ""), str(label or "")
        except Exception:
            pass
    return "", ""


class _LibraryDocumentRow(QFrame):
    def __init__(self, page, row: int, document) -> None:
        super().__init__()
        self.page = page
        self.row = row
        self.document_id = document.document_id
        self.setObjectName("LibraryFinalDocumentRow")
        self.setProperty("selected", False)
        self.setMinimumHeight(104)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame#LibraryFinalDocumentRow{background:#FFFFFF;border:1px solid #EAECF0;border-radius:11px;}"
            "QFrame#LibraryFinalDocumentRow:hover{background:#F8FAFC;border-color:#D0D5DD;}"
            "QFrame#LibraryFinalDocumentRow[selected=\"true\"]{background:#F5F8FF;border:1px solid #9DB9FF;}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(11, 10, 11, 10)
        root.setSpacing(10)

        file_icon = QLabel()
        file_icon.setFixedSize(42, 42)
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setPixmap(_native_document_icon(page, document, 34))
        file_icon.setStyleSheet("background:transparent;border:none;")
        file_icon.setToolTip(f"{_document_suffix(document).lstrip('.').upper()} protected copy")
        root.addWidget(file_icon, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel(document.title)
        title.setToolTip(document.title)
        title.setStyleSheet(f"color:{INK};font-size:10px;font-weight:900;border:none;")
        star = QLabel("★" if document.favorite else "")
        star.setStyleSheet(f"color:{AMBER};font-size:12px;font-weight:900;border:none;")
        title_row.addWidget(title, 1)
        title_row.addWidget(star)
        body.addLayout(title_row)

        _provider_key, provider_label, account_label = _provider_info(page, document)
        source_line = provider_label
        if account_label:
            source_line += f" · {account_label}"
        source = QLabel(source_line)
        source.setToolTip(source_line)
        source.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;")
        body.addWidget(source)

        badges = QHBoxLayout()
        badges.setSpacing(5)
        badges.addWidget(_badge("Protected", "blue"))
        badges.addWidget(_badge(f"{document.findings_count} findings", "teal"))
        if document.has_mapping:
            badges.addWidget(_badge("Restore available", "green"))
        if document.mcp_shared:
            badges.addWidget(_badge("AI / MCP allowed", "green"))
        else:
            badges.addWidget(_badge("AI / MCP blocked", "amber"))

        context = getattr(page, "_library_workspace_context_2026", None)
        workspace_map = getattr(page, "_library_workspace_metadata_map", {})
        workspace_label = (
            document_workspace_label(context, workspace_map.get(document.document_id))
            if context is not None
            else "Local"
        )
        badges.addWidget(
            _badge(
                workspace_label,
                "neutral" if workspace_label == "Legacy local" else "blue",
            )
        )
        badges.addStretch(1)
        body.addLayout(badges)

        updated = QLabel(document.updated_at.astimezone().strftime("%d %b %Y · %I:%M %p"))
        updated.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
        body.addWidget(updated)
        root.addLayout(body, 1)

        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.page.table.selectRow(self.row)
        super().mousePressEvent(event)


def _metric_block(title: str) -> tuple[QFrame, tuple[QLabel, QLabel, QLabel]]:
    frame = QFrame(objectName="LibraryMetric2026")
    frame.setStyleSheet(
        f"QFrame#LibraryMetric2026{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;}}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(13, 10, 13, 10)
    layout.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet(f"color:{MUTED};font-size:7.5px;font-weight:850;border:none;")
    value = QLabel("—")
    value.setStyleSheet(f"color:{INK};font-size:19px;font-weight:950;border:none;")
    note = QLabel("")
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{MUTED};font-size:7px;border:none;")
    layout.addWidget(heading)
    layout.addWidget(value)
    layout.addWidget(note)
    return frame, (heading, value, note)


def _combo_style() -> str:
    return (
        "QComboBox{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
        "padding:7px 10px;font-size:8.5px;font-weight:750;min-height:22px;}"
        "QComboBox:hover{border-color:#98A2B3;}QComboBox:focus{border-color:#2563EB;}"
    )


def _build_final_library_ui(page: LibraryPage) -> None:
    if bool(getattr(page, "_privacygate_library_final_ui_2026", False)):
        return
    page._privacygate_library_final_ui_2026 = True
    page._library_category_2026 = "all"
    page._library_final_rows = {}

    root = page.layout()
    if root is None:
        return

    # Hide only the legacy presentation furniture. The underlying widgets remain
    # alive because their signals/callbacks are still the authoritative controller.
    old_title = root.itemAt(0).widget() if root.count() > 0 else None
    old_subtitle = root.itemAt(1).widget() if root.count() > 1 else None
    if old_title is not None:
        old_title.hide()
    if old_subtitle is not None:
        old_subtitle.hide()
    source_bar = getattr(page, "_source_folder_bar", None)
    if source_bar is not None:
        source_bar.hide()
    for combo_name in ("_source_folder_combo", "_source_account_combo"):
        combo = getattr(page, combo_name, None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

    header = QFrame(objectName="LibraryHero2026")
    header.setStyleSheet("QFrame#LibraryHero2026{background:transparent;border:none;}")
    header_row = QHBoxLayout(header)
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(12)
    titles = QVBoxLayout()
    titles.setSpacing(3)
    page._library_final_title = QLabel("Local Library")
    page._library_final_title.setStyleSheet(
        f"color:{INK};font-size:24px;font-weight:950;border:none;"
    )
    page._library_final_subtitle = QLabel()
    page._library_final_subtitle.setWordWrap(True)
    page._library_final_subtitle.setStyleSheet(f"color:{MUTED};font-size:8.5px;border:none;")
    titles.addWidget(page._library_final_title)
    titles.addWidget(page._library_final_subtitle)
    page._library_final_context_badge = QLabel("PERSONAL")
    header_row.addLayout(titles, 1)
    header_row.addWidget(page._library_final_context_badge, 0, Qt.AlignmentFlag.AlignTop)
    root.insertWidget(0, header)

    metrics_frame = QFrame()
    metrics_frame.setStyleSheet("QFrame{background:transparent;border:none;}")
    metrics_row = QHBoxLayout(metrics_frame)
    metrics_row.setContentsMargins(0, 0, 0, 0)
    metrics_row.setSpacing(9)
    page._library_metric_widgets = []
    for title in ("Documents", "Restorable", "AI / MCP access", "Workspace"):
        frame, widgets = _metric_block(title)
        metrics_row.addWidget(frame, 1)
        page._library_metric_widgets.append(widgets)
    root.insertWidget(1, metrics_frame)

    tabs = QFrame(objectName="LibraryTabs2026")
    tabs.setStyleSheet(
        f"QFrame#LibraryTabs2026{{background:#FFFFFF;border:1px solid {BORDER};border-radius:11px;}}"
    )
    tabs_row = QHBoxLayout(tabs)
    tabs_row.setContentsMargins(6, 6, 6, 6)
    tabs_row.setSpacing(4)
    page._library_category_buttons = {}
    group = QButtonGroup(page)
    group.setExclusive(True)
    page._library_category_group_2026 = group
    for key, label in (
        ("all", "All"),
        ("protected", "Protected"),
        ("restorable", "Restorable"),
        ("favorites", "Favorites"),
        ("trash", "Trash"),
    ):
        button = QPushButton(label)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(31)
        button.setStyleSheet(
            "QPushButton{background:transparent;color:#667085;border:none;border-radius:8px;"
            "padding:6px 13px;font-size:8.5px;font-weight:800;}"
            "QPushButton:hover{background:#F2F4F7;color:#101828;}"
            "QPushButton:checked{background:#EEF4FF;color:#2563EB;font-weight:900;}"
        )
        button.clicked.connect(
            lambda _checked=False, category=key: _set_category(page, category)
        )
        group.addButton(button)
        page._library_category_buttons[key] = button
        tabs_row.addWidget(button)
    tabs_row.addStretch(1)
    page._library_category_buttons["all"].setChecked(True)
    root.insertWidget(2, tabs)

    filters = QFrame(objectName="LibraryFilters2026")
    filters.setStyleSheet(
        f"QFrame#LibraryFilters2026{{background:#FFFFFF;border:1px solid {BORDER};border-radius:11px;}}"
    )
    filters_row = QHBoxLayout(filters)
    filters_row.setContentsMargins(10, 8, 10, 8)
    filters_row.setSpacing(8)

    page._library_source_filter_2026 = QComboBox()
    page._library_account_filter_2026 = QComboBox()
    page._library_label_filter_2026 = QComboBox()
    page._library_type_filter_2026 = QComboBox()
    for combo in (
        page._library_source_filter_2026,
        page._library_account_filter_2026,
        page._library_label_filter_2026,
        page._library_type_filter_2026,
    ):
        combo.setStyleSheet(_combo_style())
        combo.setMinimumWidth(145)
        combo.currentIndexChanged.connect(
            lambda _index, target=page: target._apply_library_final_filters()
        )
        filters_row.addWidget(combo)

    reset = QPushButton("Reset filters")
    reset.setMinimumHeight(36)
    reset.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:9px;"
        "padding:7px 11px;font-size:8px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
    )
    reset.clicked.connect(lambda _checked=False: _reset_filters(page))
    page._library_reset_filters_2026 = reset
    filters_row.addWidget(reset)
    filters_row.addStretch(1)
    root.insertWidget(3, filters)

    page.favorites_only.hide()
    page.show_trash.hide()
    page.search.setPlaceholderText("Search protected documents, sources, profiles or labels")
    page.search.setMinimumHeight(42)
    page.search.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#101828;border:1px solid #D0D5DD;border-radius:10px;"
        "padding:9px 13px;font-size:9px;}QLineEdit:focus{border:1px solid #2563EB;}"
    )

    page.copy_button.setText("Copy protected text")
    page.export_button.setText("Download safe copy")
    page.edit_button.setText("Edit metadata")
    page.restore_button.setText("Restore")
    page.delete_button.setText("Move to trash")

    preview_card = page.preview.parentWidget()
    preview_layout = preview_card.layout() if preview_card is not None else None
    if preview_layout is not None:
        context_bar = QFrame(objectName="LibraryDocumentContext2026")
        context_bar.setStyleSheet(
            f"QFrame#LibraryDocumentContext2026{{background:#F8FAFC;border:1px solid {BORDER};border-radius:9px;}}"
        )
        context_layout = QHBoxLayout(context_bar)
        context_layout.setContentsMargins(10, 7, 10, 7)
        context_layout.setSpacing(8)
        context_icon = QLabel()
        context_icon.setPixmap(icon("protect", color=BLUE, size=16).pixmap(16, 16))
        page._library_detail_context_2026 = QLabel("Protected locally")
        page._library_detail_context_2026.setWordWrap(True)
        page._library_detail_context_2026.setStyleSheet(
            f"color:{TEXT};font-size:7.5px;font-weight:750;border:none;"
        )
        context_layout.addWidget(context_icon)
        context_layout.addWidget(page._library_detail_context_2026, 1)
        preview_layout.insertWidget(1, context_bar)

        action_layout = None
        for index in range(preview_layout.count() - 1, -1, -1):
            candidate = preview_layout.itemAt(index).layout()
            if candidate is not None:
                action_layout = candidate
                break
        if action_layout is not None:
            use_ai = QPushButton("Use with AI  ▾")
            use_ai.setMinimumHeight(36)
            use_ai.setCursor(Qt.CursorShape.PointingHandCursor)
            use_ai.setStyleSheet(
                "QPushButton{background:#2563EB;color:#FFFFFF;border:1px solid #2563EB;border-radius:8px;"
                "padding:7px 11px;font-weight:900;}QPushButton:hover{background:#1D4ED8;}"
                "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;color:#FFFFFF;}"
            )
            use_ai.clicked.connect(
                lambda _checked=False, button=use_ai: show_library_ai_menu(page, button)
            )
            # Insert immediately before the first stretch/right-side Restore controls.
            insertion = max(0, action_layout.count() - 3)
            action_layout.insertWidget(insertion, use_ai)
            page._library_use_ai_button_2026 = use_ai


def _set_category(page: LibraryPage, category: str) -> None:
    page._library_category_2026 = category
    trash = category == "trash"
    page.show_trash.blockSignals(True)
    page.show_trash.setChecked(trash)
    page.show_trash.blockSignals(False)
    page.favorites_only.blockSignals(True)
    page.favorites_only.setChecked(False)
    page.favorites_only.blockSignals(False)
    page.refresh()


def _reset_filters(page: LibraryPage) -> None:
    for combo in (
        getattr(page, "_library_source_filter_2026", None),
        getattr(page, "_library_account_filter_2026", None),
        getattr(page, "_library_label_filter_2026", None),
        getattr(page, "_library_type_filter_2026", None),
    ):
        if combo is not None:
            combo.setCurrentIndex(0)
    page._apply_library_final_filters()


def _sync_combo(combo: QComboBox, entries: list[tuple[str, str]]) -> None:
    previous = str(combo.currentData() or "")
    combo.blockSignals(True)
    combo.clear()
    for key, label in entries:
        combo.addItem(label, key)
    target = combo.findData(previous)
    combo.setCurrentIndex(target if target >= 0 else 0)
    combo.blockSignals(False)


def _sync_final_filter_options(page: LibraryPage, documents) -> None:
    sources_present = {_source_bucket(page, document) for document in documents}
    source_entries = [("", "All sources")]
    for key, label in (
        ("local", "Local"),
        ("gmail", "Gmail"),
        ("google_drive", "Google Drive"),
        ("other", "Other"),
    ):
        if key in sources_present:
            source_entries.append((key, label))
    _sync_combo(page._library_source_filter_2026, source_entries)

    accounts: dict[str, str] = {}
    for document in documents:
        key, label = _account_filter_key(page, document)
        if key and label:
            accounts.setdefault(key, label)
    _sync_combo(
        page._library_account_filter_2026,
        [("", "All accounts")] + sorted(accounts.items(), key=lambda item: item[1].casefold()),
    )

    labels = sorted(
        {label for document in documents for label in document.labels if str(label).strip()},
        key=str.casefold,
    )
    _sync_combo(
        page._library_label_filter_2026,
        [("", "All labels")] + [(label, label) for label in labels],
    )

    suffixes = sorted({_document_suffix(document) for document in documents})
    _sync_combo(
        page._library_type_filter_2026,
        [("", "All file types")]
        + [(suffix, suffix.lstrip(".").upper()) for suffix in suffixes],
    )


def _document_matches_filters(page: LibraryPage, document) -> bool:
    category = str(getattr(page, "_library_category_2026", "all") or "all")
    if category == "restorable" and not document.has_mapping:
        return False
    if category == "favorites" and not document.favorite:
        return False

    source = str(page._library_source_filter_2026.currentData() or "")
    if source and _source_bucket(page, document) != source:
        return False

    account = str(page._library_account_filter_2026.currentData() or "")
    if account:
        key, _label = _account_filter_key(page, document)
        if key != account:
            return False

    label = str(page._library_label_filter_2026.currentData() or "")
    if label and label not in document.labels:
        return False

    suffix = str(page._library_type_filter_2026.currentData() or "")
    if suffix and _document_suffix(document) != suffix:
        return False
    return True


def _render_rows(page: LibraryPage) -> None:
    page._library_final_rows = {}
    for row, document in enumerate(page._documents):
        item = page.table.item(row, 2)
        if item is None:
            continue
        widget = _LibraryDocumentRow(page, row, document)
        page.table.setRowHeight(row, 112)
        page.table.setCellWidget(row, 2, widget)
        page._library_final_rows[document.document_id] = widget


def _update_row_selection(page: LibraryPage) -> None:
    document = page._current()
    selected_id = document.document_id if document is not None else ""
    for document_id, widget in getattr(page, "_library_final_rows", {}).items():
        widget.set_selected(document_id == selected_id)


def _update_detail(page: LibraryPage) -> None:
    if not bool(getattr(page, "_privacygate_library_final_ui_2026", False)):
        return
    document = page._current()
    use_ai = getattr(page, "_library_use_ai_button_2026", None)
    if document is None:
        if use_ai is not None:
            use_ai.setEnabled(False)
        _update_row_selection(page)
        return

    provider_key, provider_label, account_label = _provider_info(page, document)
    metadata = getattr(page, "_source_metadata_map", {}).get(document.document_id)
    item_title = str(getattr(metadata, "item_title", "") or "").strip() if metadata else ""
    labels = ", ".join(document.labels) if document.labels else "No labels"
    trail = provider_label
    if account_label:
        trail += f" · {account_label}"
    if item_title and item_title.casefold() != document.title.casefold():
        trail += f" · {item_title}"
    trail += f" · {document.updated_at.astimezone().strftime('%d %b %Y')} · {labels}"
    page.meta.setText(trail)
    page.meta.setToolTip(trail)

    detail_icon = getattr(page, "_detail_provider_logo", None)
    if detail_icon is not None:
        detail_icon.setPixmap(_native_document_icon(page, document, 30))
        detail_icon.setToolTip(f"{_document_suffix(document).lstrip('.').upper()} protected copy")
    page._detail_provider_key = provider_key

    context = getattr(page, "_library_workspace_context_2026", None)
    workspace_map = getattr(page, "_library_workspace_metadata_map", {})
    workspace = (
        document_workspace_label(context, workspace_map.get(document.document_id))
        if context is not None
        else "Local"
    )
    if context is not None and context.managed:
        ownership = f"Managed by {context.name} · {policy_status_text(context)}"
    elif workspace == "Legacy local":
        ownership = "Legacy local · not assigned to an Organization"
    else:
        ownership = "Personal workspace"
    restore = "Restore available" if document.has_mapping else "No reversible mapping"
    ai = "AI / MCP access allowed" if document.mcp_shared else "AI / MCP access blocked"
    page._library_detail_context_2026.setText(
        f"{ownership} · Protected locally · {restore} · {ai}"
    )
    if use_ai is not None:
        use_ai.setEnabled(document.deleted_at is None)
    _update_row_selection(page)


def _apply_final_filters(page: LibraryPage) -> None:
    if not bool(getattr(page, "_privacygate_library_final_ui_2026", False)):
        return
    scoped_ids = {
        document.document_id
        for document in getattr(page, "_library_scoped_documents_2026", ())
    }
    first_visible = -1
    visible = 0
    for row, document in enumerate(page._documents):
        hidden = document.document_id not in scoped_ids or not _document_matches_filters(page, document)
        page.table.setRowHidden(row, hidden)
        if not hidden:
            visible += 1
            if first_visible < 0:
                first_visible = row

    heading = getattr(page, "_documents_heading", None)
    if heading is not None:
        heading.setText(f"Documents ({visible})")

    if first_visible >= 0:
        current_row = page.table.currentRow()
        if current_row < 0 or page.table.isRowHidden(current_row):
            page.table.selectRow(first_visible)
    else:
        page.table.clearSelection()
        page.preview.clear()
        context = getattr(page, "_library_workspace_context_2026", None)
        category = str(getattr(page, "_library_category_2026", "all") or "all")
        if category == "trash":
            page.preview_title.setText("Trash is empty")
            page.meta.setText("No deleted protected documents match this workspace and filter view.")
        elif context is not None and context.managed:
            page.preview_title.setText(f"No documents in {context.name}")
            page.meta.setText(
                "Only protected documents explicitly saved in this Organization workspace appear here. Personal and legacy items are not mixed in."
            )
        else:
            page.preview_title.setText("No protected documents in this view")
            page.meta.setText("Try another filter or create a protected copy from Protect.")
        page._set_actions(False)
        use_ai = getattr(page, "_library_use_ai_button_2026", None)
        if use_ai is not None:
            use_ai.setEnabled(False)
    _update_detail(page)


def _finalize_library_refresh(page: LibraryPage) -> None:
    if not bool(getattr(page, "_privacygate_library_final_ui_2026", False)):
        return

    # Current rows honor the existing controller's search/trash query. Workspace
    # scoping is an additional local-only view filter over the SAME repository.
    context, current_map, scoped = scoped_documents(page, tuple(page._documents))

    # Header metrics describe the active Library, not merely the current search.
    # Deleted items stay out of these metrics and appear only on the Trash tab.
    try:
        active_documents = tuple(page.library.list_documents())
        _metric_context, active_map, metric_documents = scoped_documents(page, active_documents)
    except Exception:
        active_map = {}
        metric_documents = scoped

    merged_map = dict(active_map)
    merged_map.update(current_map)
    page._library_workspace_context_2026 = context
    page._library_workspace_metadata_map = merged_map
    page._library_scoped_documents_2026 = scoped

    button = getattr(page, "_library_category_buttons", {}).get(
        str(getattr(page, "_library_category_2026", "all") or "all")
    )
    if button is not None and not button.isChecked():
        button.setChecked(True)

    if context.personal:
        render_personal_library_context(page, context, metric_documents)
    else:
        render_organization_library_context(page, context, metric_documents)

    _sync_final_filter_options(page, scoped)
    _render_rows(page)
    _apply_final_filters(page)


def install_mockup_library_final_2026() -> None:
    """Layer the 2026 Library experience over the proven LibraryPage controller."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = LibraryPage.__init__
    previous_refresh = LibraryPage.refresh
    previous_selection_changed = LibraryPage._selection_changed

    def init(self: LibraryPage, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _build_final_library_ui(self)
        self.refresh()

    def refresh(self: LibraryPage, *args) -> None:
        previous_refresh(self, *args)
        _finalize_library_refresh(self)

    def selection_changed(self: LibraryPage) -> None:
        previous_selection_changed(self)
        _update_detail(self)

    LibraryPage.__init__ = init
    LibraryPage.refresh = refresh
    LibraryPage._selection_changed = selection_changed
    LibraryPage._apply_library_final_filters = _apply_final_filters  # type: ignore[attr-defined]
