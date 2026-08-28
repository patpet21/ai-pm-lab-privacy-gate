from __future__ import annotations

"""Local-first original-document finder for Restore.

The finder never indexes or sends document contents to a remote service. It reads
only the existing local Library metadata, local source provenance, local workspace
binding and mapping token names. The selected document is written back into the
existing RestorePage.document_combo so DocumentRestoreService remains the sole
restore engine.
"""

import sqlite3
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.document_workspace_metadata import (
    DocumentWorkspaceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    INK,
    MUTED,
    TEAL,
    TEAL_SOFT,
    WHITE,
)
from ai_pm_lab_privacy_gate.ui.organization_product_experience_2026 import (
    PrivacyGateProductDialog,
)
from ai_pm_lab_privacy_gate.ui.restore_page_v2 import TOKEN_PATTERN


@dataclass(frozen=True, slots=True)
class _FinderRow:
    document: object
    provider: str
    provider_label: str
    account_label: str
    workspace_key: str
    workspace_name: str
    personal: bool | None
    legacy: bool
    token_count: int
    matching_tokens: int
    present_tokens: int

    @property
    def match_ratio(self) -> float:
        if self.present_tokens <= 0:
            return 0.0
        return self.matching_tokens / self.present_tokens

    @property
    def likely_match(self) -> bool:
        return self.present_tokens > 0 and self.matching_tokens == self.present_tokens


class OriginalDocumentFinderDialog(PrivacyGateProductDialog):
    def __init__(self, page, main_window) -> None:
        self.page = page
        self.main_window = main_window
        self._selected_document_id: str | None = None
        self._all_rows: list[_FinderRow] = []
        self._visible_rows: list[_FinderRow] = []
        self._active_descriptor = self._descriptor()
        self._organization_mode = bool(
            self._active_descriptor is not None and not self._active_descriptor.personal
        )
        active_name = (
            str(self._active_descriptor.name)
            if self._organization_mode
            else "Personal Library"
        )
        super().__init__(
            page,
            title=(
                "Find organization original"
                if self._organization_mode
                else "Find original document"
            ),
            subtitle=(
                f"Search reversible documents available locally for {active_name}. "
                "PrivacyGate ranks likely matches from placeholder tokens without sending content anywhere."
            ),
            icon_name="search",
            width=940,
        )
        self.resize(1060, 710)
        self._build_filters()
        self._build_results()
        self.add_notice(
            "Local search only: document text, original values and encrypted restore mappings stay on this PC. Search uses Library metadata and placeholder token names only.",
            privacy=True,
        )
        self.choose_button, _ = self.add_actions(
            primary_text="Use selected original",
            primary_callback=self._accept_selected,
            secondary_text="Cancel",
            primary_enabled=False,
        )
        self._load_rows()
        self._rebuild_filter_options()
        self._apply_filters()

    def _sidebar(self):
        return getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)

    def _context(self):
        sidebar = self._sidebar()
        if sidebar is None:
            return None
        try:
            return sidebar._workspace_context()
        except Exception:
            return None

    def _descriptor(self):
        sidebar = self._sidebar()
        if sidebar is None:
            return None
        try:
            return sidebar._active_descriptor()
        except Exception:
            return None

    def _build_filters(self) -> None:
        shell = QFrame(objectName="RestoreFinderFilters")
        shell.setStyleSheet(
            f"QFrame#RestoreFinderFilters{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;}}"
        )
        root = QVBoxLayout(shell)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search by document name, source, account, label or profile…"
        )
        self.search.setClearButtonEnabled(True)
        self.search.addAction(
            icon("search", color=BLUE, size=15),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.setMinimumHeight(38)
        search_row.addWidget(self.search, 1)

        self.scope = QComboBox()
        self.scope.setMinimumHeight(38)
        self.scope.setMinimumWidth(200)
        self._populate_scope()
        search_row.addWidget(self.scope)
        root.addLayout(search_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(7)
        self.source_filter = QComboBox()
        self.source_filter.setMinimumHeight(34)
        self.source_filter.setMinimumWidth(145)
        self.account_filter = QComboBox()
        self.account_filter.setMinimumHeight(34)
        self.account_filter.setMinimumWidth(165)
        self.label_filter = QComboBox()
        self.label_filter.setMinimumHeight(34)
        self.label_filter.setMinimumWidth(145)
        filter_row.addWidget(QLabel("Source"))
        filter_row.addWidget(self.source_filter)
        filter_row.addWidget(QLabel("Account"))
        filter_row.addWidget(self.account_filter)
        filter_row.addWidget(QLabel("Folder / label"))
        filter_row.addWidget(self.label_filter)
        filter_row.addSpacing(5)
        self.include_legacy = QCheckBox("Include legacy local")
        self.include_legacy.setChecked(True)
        self.include_legacy.setToolTip(
            "Show reversible documents saved before PrivacyGate started tagging Library items with a workspace. They remain local and are not automatically assigned to any organization."
        )
        filter_row.addWidget(self.include_legacy)
        filter_row.addStretch(1)
        self.result_count = QLabel()
        self.result_count.setStyleSheet(
            f"color:{MUTED};font-size:8px;font-weight:800;border:none;background:transparent;"
        )
        filter_row.addWidget(self.result_count)
        root.addLayout(filter_row)

        for label in shell.findChildren(QLabel):
            if label is self.result_count:
                continue
            label.setStyleSheet(
                f"color:{MUTED};font-size:8px;font-weight:850;border:none;background:transparent;"
            )

        self.body.addWidget(shell)
        self.search.textChanged.connect(self._apply_filters)
        self.scope.currentIndexChanged.connect(self._apply_filters)
        self.source_filter.currentIndexChanged.connect(self._source_changed)
        self.account_filter.currentIndexChanged.connect(self._apply_filters)
        self.label_filter.currentIndexChanged.connect(self._apply_filters)
        self.include_legacy.toggled.connect(self._apply_filters)

    def _populate_scope(self) -> None:
        context = self._context()
        active_key = str(getattr(context, "active_key", "personal") or "personal")
        if not self._organization_mode:
            self.scope.addItem("Personal Library", ("workspace", active_key))
            self.scope.addItem("Legacy local only", ("legacy", ""))
            self.scope.addItem("All local reversible", ("all", ""))
            return

        self.scope.addItem(
            f"Current · {self._active_descriptor.name}",
            ("workspace", active_key),
        )
        if context is not None:
            for key, descriptor in context.workspaces.items():
                if descriptor.personal or str(key) == active_key:
                    continue
                self.scope.addItem(
                    f"Organization · {descriptor.name}",
                    ("workspace", str(key)),
                )
        self.scope.addItem("Legacy local only", ("legacy", ""))
        self.scope.addItem("All local reversible", ("all", ""))

    def _build_results(self) -> None:
        info = QHBoxLayout()
        title = QLabel("Reversible documents on this PC")
        title.setStyleSheet(
            f"color:{INK};font-size:11px;font-weight:900;border:none;background:transparent;"
        )
        info.addWidget(title)
        info.addStretch(1)
        hint = QLabel("Best placeholder matches are ranked first")
        hint.setStyleSheet(
            f"color:{TEAL};font-size:8px;font-weight:800;border:none;background:transparent;"
        )
        info.addWidget(hint)
        self.body.addLayout(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Document", "Source", "Account", "Workspace", "Restore match", "Updated"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(330)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#344054;border:1px solid #EAECF0;"
            "border-radius:11px;selection-background-color:#EEF4FF;selection-color:#101828;}"
            "QTableWidget::item{border-bottom:1px solid #F2F4F7;padding:7px 8px;}"
            "QHeaderView::section{background:#F8FAFC;color:#667085;border:none;"
            "border-bottom:1px solid #EAECF0;padding:8px;font-size:8px;font-weight:850;}"
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        self.body.addWidget(self.table, 1)

        self.detail = QLabel("Select a document to inspect its local restore match.")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(
            f"background:{BLUE_SOFT};color:{INK};border:1px solid #D6E4FF;border-radius:9px;"
            "padding:8px 10px;font-size:8px;"
        )
        self.body.addWidget(self.detail)

    def _load_mapping_tokens(self, document_ids: list[str]) -> dict[str, set[str]]:
        if not document_ids:
            return {}
        placeholders = ",".join("?" for _ in document_ids)
        output: dict[str, set[str]] = {document_id: set() for document_id in document_ids}
        connection = None
        try:
            connection = sqlite3.connect(self.page.library.db_path)
            rows = connection.execute(
                f"SELECT document_id, token FROM mappings WHERE document_id IN ({placeholders})",
                tuple(document_ids),
            ).fetchall()
            for document_id, token in rows:
                output.setdefault(str(document_id), set()).add(str(token))
        except Exception:
            return output
        finally:
            if connection is not None:
                connection.close()
        return output

    def _source_for(self, document, metadata) -> tuple[str, str, str]:
        item = metadata.get(document.document_id)
        if item is not None:
            provider = str(item.provider or "local")
            provider_label = str(item.provider_label or item.provider or "Local")
            account_label = str(item.account_label or "")
            return provider, provider_label, account_label
        source = str(document.source_name or document.source_kind or "Local")
        lowered = source.lower()
        parts = [part.strip() for part in source.split(" • ") if part.strip()]
        account_label = parts[1] if len(parts) >= 3 else ""
        if "gmail" in lowered or "mail" in lowered:
            return "gmail", "Gmail", account_label
        if "drive" in lowered or "google" in lowered:
            return "google_drive", "Google Drive", account_label
        if document.source_kind == "text":
            return "paste", "Pasted text", ""
        return "local", "Local file", ""

    def _load_rows(self) -> None:
        documents = [
            item
            for item in self.page.library.list_documents()
            if item.has_mapping and item.replacement_mode == "reversible"
        ]
        ids = [item.document_id for item in documents]
        source_meta = DocumentSourceMetadataRepository(
            self.page.library.db_path
        ).list_for_documents(ids)
        workspace_meta = DocumentWorkspaceMetadataRepository(
            self.page.library.db_path
        ).list_for_documents(ids)
        tokens_by_document = self._load_mapping_tokens(ids)
        present = set(TOKEN_PATTERN.findall(self.page.input_text.toPlainText()))

        rows: list[_FinderRow] = []
        for document in documents:
            provider, provider_label, account_label = self._source_for(document, source_meta)
            workspace = workspace_meta.get(document.document_id)
            tokens = tokens_by_document.get(document.document_id, set())
            matching = len(tokens.intersection(present)) if present else 0
            rows.append(
                _FinderRow(
                    document=document,
                    provider=provider,
                    provider_label=provider_label,
                    account_label=account_label,
                    workspace_key=workspace.workspace_key if workspace else "",
                    workspace_name=workspace.workspace_name if workspace else "Legacy local",
                    personal=workspace.personal if workspace else None,
                    legacy=workspace is None,
                    token_count=len(tokens),
                    matching_tokens=matching,
                    present_tokens=len(present),
                )
            )
        self._all_rows = rows

    def _rebuild_filter_options(self) -> None:
        current_source = self.source_filter.currentData()
        self.source_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItem("All sources", "")
        providers = sorted(
            {(row.provider_label, row.provider) for row in self._all_rows},
            key=lambda item: item[0].lower(),
        )
        for label, value in providers:
            self.source_filter.addItem(label, value)
        source_index = self.source_filter.findData(current_source)
        self.source_filter.setCurrentIndex(max(0, source_index))
        self.source_filter.blockSignals(False)
        self._rebuild_account_options()

        current_label = self.label_filter.currentData()
        self.label_filter.blockSignals(True)
        self.label_filter.clear()
        self.label_filter.addItem("All labels", "")
        labels = sorted(
            {
                str(label)
                for row in self._all_rows
                for label in getattr(row.document, "labels", ())
                if str(label).strip()
            },
            key=str.lower,
        )
        for label in labels:
            self.label_filter.addItem(label, label)
        label_index = self.label_filter.findData(current_label)
        self.label_filter.setCurrentIndex(max(0, label_index))
        self.label_filter.blockSignals(False)

    def _rebuild_account_options(self) -> None:
        source = str(self.source_filter.currentData() or "")
        previous = str(self.account_filter.currentData() or "")
        accounts = sorted(
            {
                row.account_label
                for row in self._all_rows
                if row.account_label and (not source or row.provider == source)
            },
            key=str.lower,
        )
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("All accounts", "")
        for account in accounts:
            self.account_filter.addItem(account, account)
        target = self.account_filter.findData(previous)
        self.account_filter.setCurrentIndex(max(0, target))
        self.account_filter.setEnabled(bool(accounts))
        self.account_filter.blockSignals(False)

    def _source_changed(self, *_args) -> None:
        self._rebuild_account_options()
        self._apply_filters()

    def _scope_accepts(self, row: _FinderRow) -> bool:
        scope = self.scope.currentData()
        kind, value = scope if isinstance(scope, tuple) else ("all", "")
        if kind == "all":
            return True
        if kind == "legacy":
            return row.legacy
        if row.legacy:
            return self.include_legacy.isChecked()
        return row.workspace_key == str(value)

    def _search_accepts(self, row: _FinderRow) -> bool:
        query = self.search.text().strip().lower()
        if not query:
            return True
        document = row.document
        haystack = " ".join(
            [
                str(document.title or ""),
                str(document.source_name or ""),
                str(document.source_kind or ""),
                str(document.profile_key or ""),
                " ".join(str(item) for item in getattr(document, "labels", ())),
                row.provider_label,
                row.account_label,
                row.workspace_name,
            ]
        ).lower()
        return query in haystack

    def _filter_accepts(self, row: _FinderRow) -> bool:
        source = str(self.source_filter.currentData() or "")
        account = str(self.account_filter.currentData() or "")
        label = str(self.label_filter.currentData() or "")
        if source and row.provider != source:
            return False
        if account and row.account_label != account:
            return False
        if label and label not in tuple(str(item) for item in getattr(row.document, "labels", ())):
            return False
        return self._scope_accepts(row) and self._search_accepts(row)

    def _sorted_rows(self) -> list[_FinderRow]:
        rows = [row for row in self._all_rows if self._filter_accepts(row)]
        return sorted(
            rows,
            key=lambda row: (
                0 if row.likely_match else 1,
                -row.matching_tokens,
                -row.match_ratio,
                -row.document.updated_at.timestamp(),
            ),
        )

    def _workspace_display(self, row: _FinderRow) -> str:
        if row.legacy:
            return "Legacy local"
        if row.personal:
            return "Personal"
        return row.workspace_name or "Organization"

    def _match_display(self, row: _FinderRow) -> str:
        if row.present_tokens <= 0:
            return f"{row.token_count} restore keys"
        if row.likely_match:
            return f"Likely match · {row.matching_tokens}/{row.present_tokens}"
        if row.matching_tokens:
            return f"Partial · {row.matching_tokens}/{row.present_tokens}"
        return f"No token match · {row.token_count} keys"

    def _apply_filters(self, *_args) -> None:
        if not hasattr(self, "table"):
            return
        rows = self._sorted_rows()
        self.table.setRowCount(len(rows))
        self._visible_rows = rows
        for index, row in enumerate(rows):
            document = row.document
            values = (
                str(document.title or "Untitled protected document"),
                row.provider_label,
                row.account_label or "—",
                self._workspace_display(row),
                self._match_display(row),
                document.updated_at.strftime("%b %d, %Y"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, document.document_id)
                    item.setToolTip(
                        f"{document.source_name} · {document.findings_count} protected finding(s)"
                    )
                if column == 4:
                    if row.likely_match:
                        item.setForeground(QColor("#15803D"))
                    elif row.present_tokens and row.matching_tokens == 0:
                        item.setForeground(QColor("#B45309"))
                self.table.setItem(index, column, item)
        self.table.resizeRowsToContents()
        self.result_count.setText(f"{len(rows)} document{'s' if len(rows) != 1 else ''}")
        self.choose_button.setEnabled(False)
        self._selected_document_id = None
        if rows and rows[0].likely_match:
            self.table.selectRow(0)

    def _selected_row(self) -> _FinderRow | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self._visible_rows):
            return None
        return self._visible_rows[index]

    def _selection_changed(self) -> None:
        row = self._selected_row()
        self._selected_document_id = row.document.document_id if row is not None else None
        self.choose_button.setEnabled(row is not None)
        if row is None:
            self.detail.setText("Select a document to inspect its local restore match.")
            return
        document = row.document
        labels = ", ".join(str(item) for item in document.labels) or "No labels"
        account = f" · {row.account_label}" if row.account_label else ""
        legacy_note = (
            " · Saved before workspace tagging; not assigned to any organization"
            if row.legacy
            else ""
        )
        self.detail.setText(
            f"{self._match_display(row)} · {row.token_count} local restore key(s) · "
            f"{row.provider_label}{account} · {self._workspace_display(row)} · {labels}{legacy_note}"
        )

    def _accept_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        self._selected_document_id = row.document.document_id
        self.accept()

    @property
    def selected_document_id(self) -> str | None:
        return self._selected_document_id


class RestoreDocumentFinderController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.page = getattr(main_window, "restore_page", None)
        if self.page is None or bool(getattr(self.page, "_restore_document_finder_2026", False)):
            return
        self.page._restore_document_finder_2026 = True
        self._install_command_control()
        self._connect_workspace_changes()
        self._update_selection_copy()

    def _active_descriptor(self):
        sidebar = getattr(self.main_window, "_privacygate_redesign_sidebar_controller", None)
        if sidebar is None:
            return None
        try:
            return sidebar._active_descriptor()
        except Exception:
            return None

    def _install_command_control(self) -> None:
        command = getattr(self.page, "_restore_2026_command_bar", None)
        row = command.layout() if command is not None else None
        if not isinstance(row, QHBoxLayout):
            return

        self.page.document_combo.hide()
        self.page.document_combo.setMaximumWidth(0)
        for label in command.findChildren(QLabel):
            if label.text().strip() == "Original":
                label.hide()
                label.setMaximumWidth(0)

        descriptor = self._active_descriptor()
        org_mode = bool(descriptor is not None and not descriptor.personal)
        self.context_badge = QLabel(
            str(descriptor.name) if org_mode else "Personal Library"
        )
        self.context_badge.setStyleSheet(
            f"background:{TEAL_SOFT if org_mode else BLUE_SOFT};"
            f"color:{TEAL if org_mode else BLUE};border:1px solid {'#A5F3FC' if org_mode else '#D6E4FF'};"
            "border-radius:8px;padding:6px 8px;font-size:7.5px;font-weight:900;"
        )
        self.context_badge.setMaximumWidth(150)

        self.find_button = QPushButton("Find original")
        self.find_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_button.setIcon(icon("search", color=BLUE, size=14))
        self.find_button.setIconSize(QSize(14, 14))
        self.find_button.setMinimumHeight(36)
        self.find_button.setMinimumWidth(118)
        self.find_button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
            "border-radius:9px;padding:7px 10px;font-size:8px;font-weight:850;}"
            "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
        )
        self.find_button.clicked.connect(lambda _checked=False: self.open_finder())

        self.selection = QPushButton("No original selected")
        self.selection.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selection.setMinimumHeight(36)
        self.selection.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.selection.setStyleSheet(
            "QPushButton{background:#F8FAFC;color:#475467;border:1px solid #EAECF0;"
            "border-radius:9px;padding:7px 10px;text-align:left;font-size:8px;font-weight:750;}"
            f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE};border-color:#D6E4FF;}}"
        )
        self.selection.clicked.connect(lambda _checked=False: self.open_finder())

        restore_index = row.indexOf(self.page.restore_button)
        insert_at = restore_index if restore_index >= 0 else row.count()
        row.insertWidget(insert_at, self.context_badge)
        row.insertWidget(insert_at + 1, self.find_button)
        row.insertWidget(insert_at + 2, self.selection, 1)

        self.page.document_combo.currentIndexChanged.connect(
            lambda _index: self._update_selection_copy()
        )
        self.page._restore_document_finder_controller = self

    def _connect_workspace_changes(self) -> None:
        old_combo = getattr(self.main_window, "workspace_sidebar_combo", None)
        if old_combo is not None:
            old_combo.currentIndexChanged.connect(
                lambda _index: self._workspace_changed()
            )

    def _workspace_changed(self) -> None:
        descriptor = self._active_descriptor()
        org_mode = bool(descriptor is not None and not descriptor.personal)
        self.context_badge.setText(
            str(descriptor.name) if org_mode else "Personal Library"
        )
        self.context_badge.setStyleSheet(
            f"background:{TEAL_SOFT if org_mode else BLUE_SOFT};"
            f"color:{TEAL if org_mode else BLUE};border:1px solid {'#A5F3FC' if org_mode else '#D6E4FF'};"
            "border-radius:8px;padding:6px 8px;font-size:7.5px;font-weight:900;"
        )
        if self.page.document_combo.currentIndex() > 0:
            self.page.document_combo.setCurrentIndex(0)
        self._update_selection_copy()

    def open_finder(self) -> None:
        dialog = OriginalDocumentFinderDialog(self.page, self.main_window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        document_id = dialog.selected_document_id
        if not document_id:
            return
        self.page.refresh(document_id)
        index = self.page.document_combo.findData(document_id)
        if index >= 0:
            self.page.document_combo.setCurrentIndex(index)
        self._update_selection_copy()

    def _update_selection_copy(self) -> None:
        document_id = self.page.document_combo.currentData()
        if not document_id:
            self.selection.setText("No original selected · click Find original")
            self.selection.setToolTip("Search the local reversible Library")
            return
        try:
            document = self.page.library.get(str(document_id))
            mappings = self.page.library.get_mappings(str(document_id))
            self.selection.setText(
                f"{document.title}  ·  {len(mappings)} restore key{'s' if len(mappings) != 1 else ''}"
            )
            self.selection.setToolTip(
                f"{document.source_name}\nStored locally · reversible mapping available"
            )
        except Exception:
            self.selection.setText("Original selected")


def apply_restore_document_finder_2026(main_window) -> None:
    if bool(getattr(main_window, "_restore_document_finder_2026", False)):
        return
    main_window._restore_document_finder_2026 = True
    controller = RestoreDocumentFinderController(main_window)
    main_window._restore_document_finder_controller = controller
