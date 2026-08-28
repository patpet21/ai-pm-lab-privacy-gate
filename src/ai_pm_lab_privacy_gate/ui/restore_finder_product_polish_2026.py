from __future__ import annotations

"""Final product pass for Restore's local Original Document Finder.

This layer keeps DocumentRestoreService and RestorePage authoritative. It adds
reactive local placeholder matching, best-match suggestions, richer selection
state and Finder artwork. No document content, mapping value, filename or search
query is sent to Supabase or any PrivacyGate backend.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QFileInfo, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.document_source_metadata import (
    DocumentSourceMetadataRepository,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.document_workspace_metadata import (
    DocumentWorkspaceMetadataRepository,
)
from ai_pm_lab_privacy_gate.ui import restore_document_finder_2026 as _finder_module
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.mockup_design_foundation_2026 import (
    BLUE,
    BLUE_SOFT,
    BORDER,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    WHITE,
)
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader
from ai_pm_lab_privacy_gate.ui.restore_page_v2 import TOKEN_PATTERN


AMBER = "#B45309"
AMBER_SOFT = "#FFFBEB"
GRAY_SOFT = "#F8FAFC"

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
)


@dataclass(frozen=True, slots=True)
class _Candidate:
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
    def likely(self) -> bool:
        return self.present_tokens > 0 and self.matching_tokens == self.present_tokens

    @property
    def partial(self) -> bool:
        return self.present_tokens > 0 and 0 < self.matching_tokens < self.present_tokens


# ---------------------------------------------------------------------------
# Shared local-only matching helpers
# ---------------------------------------------------------------------------
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
    return {
        "word": ".docx",
        "docx": ".docx",
        "excel": ".xlsx",
        "xlsx": ".xlsx",
        "powerpoint": ".pptx",
        "pptx": ".pptx",
        "pdf": ".pdf",
        "text": ".txt",
        "txt": ".txt",
        "csv": ".csv",
    }.get(kind, ".txt")


def _file_type_label(document) -> str:
    suffix = _document_suffix(document).lstrip(".").upper()
    return {"DOCX": "WORD", "XLSX": "EXCEL", "PPTX": "POWERPOINT"}.get(suffix, suffix)


def _native_file_icon(provider: QFileIconProvider, document, size: int = 22) -> QIcon:
    suffix = _document_suffix(document)
    result = provider.icon(QFileInfo(f"privacygate-restore{suffix}"))
    if not result.isNull():
        return result
    return icon("document", color=BLUE, size=size)


def _mapping_tokens(page, ids: list[str]) -> dict[str, set[str]]:
    result = {item: set() for item in ids}
    if not ids:
        return result
    placeholders = ",".join("?" for _ in ids)
    connection = None
    try:
        connection = sqlite3.connect(page.library.db_path)
        rows = connection.execute(
            f"SELECT document_id, token FROM mappings WHERE document_id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
        for document_id, token in rows:
            result.setdefault(str(document_id), set()).add(str(token))
    except Exception:
        return result
    finally:
        if connection is not None:
            connection.close()
    return result


def _source_info(document, metadata) -> tuple[str, str, str]:
    item = metadata.get(document.document_id)
    if item is not None:
        return (
            str(item.provider or "local"),
            str(item.provider_label or item.provider or "Local file"),
            str(item.account_label or ""),
        )
    source = str(document.source_name or document.source_kind or "Local file")
    lowered = source.lower()
    parts = [part.strip() for part in source.split(" • ") if part.strip()]
    account = parts[1] if len(parts) >= 3 else ""
    if "gmail" in lowered or "mail" in lowered:
        return "gmail", "Gmail", account
    if "drive" in lowered or "google" in lowered:
        return "google_drive", "Google Drive", account
    if str(getattr(document, "source_kind", "")) == "text":
        return "paste", "Pasted text", ""
    return "local", "Local file", ""


def _active_workspace(main_window) -> tuple[str, object | None]:
    sidebar = getattr(main_window, "_privacygate_redesign_sidebar_controller", None)
    if sidebar is None:
        return "", None
    try:
        context = sidebar._workspace_context()
        descriptor = sidebar._active_descriptor()
        return str(getattr(context, "active_key", "") or ""), descriptor
    except Exception:
        return "", None


def _load_candidates(page, main_window) -> list[_Candidate]:
    documents = [
        item
        for item in page.library.list_documents()
        if bool(getattr(item, "has_mapping", False))
        and str(getattr(item, "replacement_mode", "")) == "reversible"
    ]
    ids = [item.document_id for item in documents]
    source_meta = DocumentSourceMetadataRepository(page.library.db_path).list_for_documents(ids)
    workspace_meta = DocumentWorkspaceMetadataRepository(page.library.db_path).list_for_documents(ids)
    tokens_by_doc = _mapping_tokens(page, ids)
    present = set(TOKEN_PATTERN.findall(page.input_text.toPlainText()))
    active_key, descriptor = _active_workspace(main_window)
    organization_mode = bool(descriptor is not None and not getattr(descriptor, "personal", True))

    output: list[_Candidate] = []
    for document in documents:
        provider, provider_label, account = _source_info(document, source_meta)
        workspace = workspace_meta.get(document.document_id)
        mapping_tokens = tokens_by_doc.get(document.document_id, set())
        matching = len(mapping_tokens.intersection(present)) if present else 0
        output.append(
            _Candidate(
                document=document,
                provider=provider,
                provider_label=provider_label,
                account_label=account,
                workspace_key=workspace.workspace_key if workspace else "",
                workspace_name=workspace.workspace_name if workspace else "Legacy local",
                personal=workspace.personal if workspace else None,
                legacy=workspace is None,
                token_count=len(mapping_tokens),
                matching_tokens=matching,
                present_tokens=len(present),
            )
        )

    def workspace_rank(row: _Candidate) -> int:
        if row.workspace_key and row.workspace_key == active_key:
            return 0
        if row.legacy:
            return 1
        if organization_mode:
            return 2
        return 3

    output.sort(
        key=lambda row: (
            0 if row.likely else 1 if row.partial else 2,
            -row.matching_tokens,
            workspace_rank(row),
            -getattr(row.document.updated_at, "timestamp", lambda: 0.0)(),
        )
    )
    return output


def _workspace_text(candidate: _Candidate) -> str:
    if candidate.legacy:
        return "Legacy local"
    if candidate.personal:
        return "Personal"
    return candidate.workspace_name or "Organization"


def _match_text(candidate: _Candidate) -> tuple[str, str]:
    if candidate.present_tokens <= 0:
        return "Manual selection", f"{candidate.token_count} restore keys"
    if candidate.likely:
        return "Likely match", f"{candidate.matching_tokens} / {candidate.present_tokens} keys"
    if candidate.partial:
        return "Partial match", f"{candidate.matching_tokens} / {candidate.present_tokens} keys"
    return "No token match", f"0 / {candidate.present_tokens} keys"


# ---------------------------------------------------------------------------
# Rich Finder dialog
# ---------------------------------------------------------------------------
_BaseFinder = _finder_module.OriginalDocumentFinderDialog


class SmartOriginalDocumentFinderDialog(_BaseFinder):
    def __init__(self, page, main_window) -> None:
        self._file_icons = QFileIconProvider()
        self._logo_loader = ProviderLogoLoader(Path(page.library.db_path).parent, self)
        self._best_card: QFrame | None = None
        self._best_title: QLabel | None = None
        self._best_copy: QLabel | None = None
        self._best_button: QPushButton | None = None
        super().__init__(page, main_window)
        self.scope.setCurrentIndex(0)
        self._polish_filters()
        self._install_best_card()
        self._polish_detail()
        self._apply_filters()

    def _polish_filters(self) -> None:
        self.search.setPlaceholderText("Search documents by name, source, account, label, profile or restore-key count…")
        for widget in (self.search, self.scope, self.source_filter, self.account_filter, self.label_filter):
            widget.setMinimumHeight(40 if widget in {self.search, self.scope} else 36)
        self.scope.setToolTip("Scope · choose Personal, the current organization, legacy local documents or all local reversible documents")
        self.source_filter.setToolTip("Source · Local file, Gmail, Google Drive or another source already recorded in your local Library")
        self.account_filter.setToolTip("Account · narrow connected-source documents to the account that supplied them")
        self.label_filter.setToolTip("Folder / label · filter using real local Library labels; no organization folders are invented")

    def _install_best_card(self) -> None:
        card = QFrame(objectName="RestoreBestMatchCard")
        card.setStyleSheet(
            f"QFrame#RestoreBestMatchCard{{background:{GREEN_SOFT};border:1px solid #BBF7D0;border-radius:11px;}}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(icon("check", color=GREEN, size=20).pixmap(20, 20))
        row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        title = QLabel("Best original candidates found")
        title.setStyleSheet(f"color:{INK};font-size:9.5px;font-weight:900;border:none;background:transparent;")
        detail = QLabel()
        detail.setWordWrap(True)
        detail.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;background:transparent;")
        copy.addWidget(title)
        copy.addWidget(detail)
        row.addLayout(copy, 1)
        use = QPushButton("Use best match")
        use.setMinimumHeight(34)
        use.setStyleSheet(
            f"QPushButton{{background:{GREEN};color:#FFFFFF;border:1px solid {GREEN};border-radius:8px;padding:6px 10px;font-size:8px;font-weight:900;}}"
            "QPushButton:hover{background:#15803D;border-color:#15803D;}"
            "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;}"
        )
        use.clicked.connect(lambda _checked=False: self._use_best_match())
        row.addWidget(use)

        filters = self.findChild(QFrame, "RestoreFinderFilters")
        index = self.body.indexOf(filters) if filters is not None else 1
        self.body.insertWidget(max(1, index + 1), card)
        self._best_card = card
        self._best_title = title
        self._best_copy = detail
        self._best_button = use

    def _polish_detail(self) -> None:
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setMinimumHeight(82)
        self.detail.setStyleSheet(
            f"background:{BLUE_SOFT};color:{INK};border:1px solid #D6E4FF;border-radius:10px;"
            "padding:9px 11px;font-size:8px;"
        )

    def _search_accepts(self, row) -> bool:
        query = self.search.text().strip().lower()
        if not query:
            return True
        if super()._search_accepts(row):
            return True
        extra = " ".join(
            (
                str(getattr(row, "token_count", 0)),
                f"{getattr(row, 'matching_tokens', 0)}/{getattr(row, 'present_tokens', 0)}",
                _file_type_label(row.document),
                _document_suffix(row.document).lstrip("."),
            )
        ).lower()
        return query in extra

    def _apply_filters(self, *_args) -> None:
        super()._apply_filters(*_args)
        if not hasattr(self, "table"):
            return
        for table_row, candidate in enumerate(getattr(self, "_visible_rows", ())):
            document_item = self.table.item(table_row, 0)
            source_item = self.table.item(table_row, 1)
            match_item = self.table.item(table_row, 4)
            if document_item is not None:
                document_item.setIcon(_native_file_icon(self._file_icons, candidate.document, 22))
                title = str(candidate.document.title or "Untitled protected document")
                document_item.setText(f"{title}\n{_file_type_label(candidate.document)} · protected · reversible")
                document_item.setToolTip(
                    f"{candidate.document.source_name}\n{candidate.token_count} local restore keys"
                )
            if source_item is not None:
                if candidate.provider in {"local", "paste"}:
                    source_item.setIcon(icon("document", color=BLUE, size=17))
                else:
                    source_item.setIcon(icon("cloud", color=BLUE, size=17))
                    self._logo_loader.load(
                        candidate.provider,
                        lambda pixmap, item=source_item: item.setIcon(QIcon(pixmap)),
                    )
            if match_item is not None:
                if candidate.present_tokens <= 0:
                    match_item.setText(f"Manual selection\n{candidate.token_count} restore keys")
                    match_item.setForeground(QColor("#667085"))
                    match_item.setBackground(QColor(GRAY_SOFT))
                elif candidate.likely_match:
                    match_item.setText(f"✓  Likely match\n{candidate.matching_tokens} / {candidate.present_tokens} keys")
                    match_item.setForeground(QColor("#15803D"))
                    match_item.setBackground(QColor(GREEN_SOFT))
                elif candidate.matching_tokens:
                    match_item.setText(f"●  Partial match\n{candidate.matching_tokens} / {candidate.present_tokens} keys")
                    match_item.setForeground(QColor(AMBER))
                    match_item.setBackground(QColor(AMBER_SOFT))
                else:
                    match_item.setText(f"No token match\n0 / {candidate.present_tokens} keys")
                    match_item.setForeground(QColor("#667085"))
                    match_item.setBackground(QColor(GRAY_SOFT))
            self.table.setRowHeight(table_row, 50)
        self._refresh_best_card()

    def _refresh_best_card(self) -> None:
        if self._best_card is None or self._best_copy is None or self._best_button is None or self._best_title is None:
            return
        rows = list(getattr(self, "_visible_rows", ()))
        present = len(TOKEN_PATTERN.findall(self.page.input_text.toPlainText()))
        matched = [row for row in rows if getattr(row, "matching_tokens", 0) > 0]
        if not present:
            self._best_card.setStyleSheet(
                f"QFrame#RestoreBestMatchCard{{background:{BLUE_SOFT};border:1px solid #D6E4FF;border-radius:11px;}}"
            )
            self._best_title.setText("Upload the AI result for automatic matching")
            self._best_copy.setText("You can still search and choose any reversible document manually.")
            self._best_button.setEnabled(False)
            return
        if not matched:
            self._best_card.setStyleSheet(
                f"QFrame#RestoreBestMatchCard{{background:{AMBER_SOFT};border:1px solid #FDE68A;border-radius:11px;}}"
            )
            self._best_title.setText("No strong restore match found")
            self._best_copy.setText(
                "Try searching by document name, source, account or restore-key count. You can still choose a document manually."
            )
            self._best_button.setEnabled(False)
            return
        self._best_card.setStyleSheet(
            f"QFrame#RestoreBestMatchCard{{background:{GREEN_SOFT};border:1px solid #BBF7D0;border-radius:11px;}}"
        )
        self._best_title.setText("Best original candidates found")
        lines = []
        for row in matched[:2]:
            state = "Likely match" if row.likely_match else "Partial match"
            lines.append(f"{row.document.title} — {state} · {row.matching_tokens}/{row.present_tokens} keys")
        self._best_copy.setText("\n".join(lines))
        self._best_button.setEnabled(True)

    def _use_best_match(self) -> None:
        rows = [row for row in getattr(self, "_visible_rows", ()) if getattr(row, "matching_tokens", 0) > 0]
        if not rows:
            return
        self._selected_document_id = rows[0].document.document_id
        self.accept()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        row = self._selected_row()
        if row is None:
            self.detail.setText("Select a document to inspect its local restore match.")
            return
        match = self._match_display(row)
        labels = ", ".join(str(item) for item in row.document.labels) or "No labels"
        account = row.account_label or "—"
        self.detail.setText(
            "<b>SELECTED DOCUMENT</b><br>"
            f"<b>Title:</b> {row.document.title}<br>"
            f"<b>Source:</b> {row.provider_label} &nbsp; · &nbsp; <b>Account:</b> {account}<br>"
            f"<b>Workspace:</b> {self._workspace_display(row)} &nbsp; · &nbsp; "
            f"<b>Restore keys:</b> {row.token_count} &nbsp; · &nbsp; <b>Match:</b> {match}<br>"
            f"<b>Folder / label:</b> {labels}"
        )


# ---------------------------------------------------------------------------
# Restore-page smart state + auto suggestion
# ---------------------------------------------------------------------------
class RestoreSmartMatchController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.page = getattr(main_window, "restore_page", None)
        self.finder = getattr(main_window, "_restore_document_finder_controller", None)
        if self.page is None or self.finder is None:
            return
        if bool(getattr(self.page, "_restore_smart_match_2026", False)):
            return
        self.page._restore_smart_match_2026 = True
        self._file_icons = QFileIconProvider()
        self._install_state_chip()
        self._install_suggestion_card()
        self._connect()
        self.refresh()

    def _bar(self):
        return getattr(self.page, "_restore_finder_command_bar", None)

    def _install_state_chip(self) -> None:
        bar = self._bar()
        row = bar.layout() if bar is not None else None
        if not isinstance(row, QHBoxLayout):
            self.state = None
            return
        self.state = QLabel()
        self.state.setMaximumWidth(190)
        self.state.setMinimumHeight(34)
        self.state.setWordWrap(True)
        self.state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        restore_index = row.indexOf(self.page.restore_button)
        row.insertWidget(max(0, restore_index), self.state)

        selection = getattr(self.finder, "selection", None)
        if selection is not None:
            selection.setMinimumHeight(48)
            selection.setMaximumHeight(52)
            selection.setStyleSheet(
                "QPushButton{background:#F8FAFC;color:#344054;border:1px solid #D0D5DD;"
                "border-radius:10px;padding:6px 10px;text-align:left;font-size:8px;font-weight:760;}"
                f"QPushButton:hover{{background:{BLUE_SOFT};color:{BLUE};border-color:#D6E4FF;}}"
            )
        self.page.restore_button.setMinimumHeight(48)
        self.page.restore_button.setMaximumHeight(52)

    def _install_suggestion_card(self) -> None:
        bar = self._bar()
        parent = bar.parentWidget() if bar is not None else None
        layout = parent.layout() if parent is not None else None
        if not isinstance(layout, QVBoxLayout):
            self.suggestion = None
            return
        card = QFrame(objectName="RestoreSmartSuggestion")
        card.setStyleSheet(
            f"QFrame#RestoreSmartSuggestion{{background:{GREEN_SOFT};border:1px solid #BBF7D0;border-radius:10px;}}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(9)
        marker = QLabel()
        marker.setPixmap(icon("check", color=GREEN, size=18).pixmap(18, 18))
        row.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(1)
        self.suggestion_title = QLabel("Best original candidates found")
        self.suggestion_title.setStyleSheet(f"color:{INK};font-size:9px;font-weight:900;border:none;background:transparent;")
        self.suggestion_copy = QLabel()
        self.suggestion_copy.setWordWrap(True)
        self.suggestion_copy.setStyleSheet(f"color:{MUTED};font-size:7.5px;border:none;background:transparent;")
        copy.addWidget(self.suggestion_title)
        copy.addWidget(self.suggestion_copy)
        row.addLayout(copy, 1)
        review = QPushButton("Review candidates")
        review.setMinimumHeight(32)
        review.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;border-radius:8px;padding:5px 9px;font-size:7.5px;font-weight:850;}"
        )
        review.clicked.connect(lambda _checked=False: self.finder.open_finder())
        self.use_best = QPushButton("Use best match")
        self.use_best.setMinimumHeight(32)
        self.use_best.setStyleSheet(
            f"QPushButton{{background:{GREEN};color:#FFFFFF;border:1px solid {GREEN};border-radius:8px;padding:5px 9px;font-size:7.5px;font-weight:900;}}"
            "QPushButton:disabled{background:#D0D5DD;border-color:#D0D5DD;}"
        )
        self.use_best.clicked.connect(lambda _checked=False: self._use_best())
        row.addWidget(review)
        row.addWidget(self.use_best)
        index = layout.indexOf(bar)
        layout.insertWidget(max(0, index + 1), card)
        card.hide()
        self.suggestion = card

    def _connect(self) -> None:
        self.page.input_text.textChanged.connect(lambda: QTimer.singleShot(0, self.refresh))
        self.page.document_combo.currentIndexChanged.connect(lambda _index: QTimer.singleShot(0, self.refresh))
        old_combo = getattr(self.main_window, "workspace_sidebar_combo", None)
        if old_combo is not None:
            old_combo.currentIndexChanged.connect(lambda _index: QTimer.singleShot(0, self.refresh))

    def _select(self, document_id: str) -> None:
        self.page.refresh(document_id)
        index = self.page.document_combo.findData(document_id)
        if index >= 0:
            self.page.document_combo.setCurrentIndex(index)
        try:
            self.finder._update_selection_copy()
        except Exception:
            pass
        self.refresh()

    def _use_best(self) -> None:
        rows = [item for item in _load_candidates(self.page, self.main_window) if item.matching_tokens > 0]
        if rows:
            self._select(rows[0].document.document_id)

    def _selected_candidate(self, candidates: list[_Candidate]) -> _Candidate | None:
        document_id = str(self.page.document_combo.currentData() or "")
        return next((row for row in candidates if row.document.document_id == document_id), None)

    def _update_selected_copy(self, candidates: list[_Candidate]) -> None:
        selection = getattr(self.finder, "selection", None)
        if selection is None:
            return
        selected = self._selected_candidate(candidates)
        if selected is None:
            selection.setIcon(icon("search", color=BLUE, size=18))
            selection.setIconSize(QSize(18, 18))
            selection.setText("No original selected\nClick Find original to search the local reversible Library")
            return
        quality, keys = _match_text(selected)
        title = str(selected.document.title or "Original protected document")
        if len(title) > 66:
            title = title[:31] + "…" + title[-31:]
        account = f" · {selected.account_label}" if selected.account_label else ""
        selection.setIcon(_native_file_icon(self._file_icons, selected.document, 20))
        selection.setIconSize(QSize(20, 20))
        selection.setText(
            f"Original selected · {title}\n"
            f"{selected.provider_label}{account} · {_workspace_text(selected)} · {selected.token_count} keys · {quality}"
        )
        selection.setToolTip(
            f"{selected.document.title}\n{selected.provider_label}{account}\n{keys} · {_workspace_text(selected)}"
        )

    def _update_state(self, candidates: list[_Candidate]) -> None:
        text = self.page.input_text.toPlainText()
        has_input = bool(text.strip())
        tokens = TOKEN_PATTERN.findall(text)
        has_tokens = bool(tokens)
        has_document = bool(self.page.document_combo.currentData())
        busy = getattr(self.page, "_active_worker", None) is not None
        ready = has_input and has_tokens and has_document and not busy
        self.page.restore_button.setEnabled(ready)
        if self.state is None:
            return
        if busy:
            label, bg, fg, border = "Working locally…", BLUE_SOFT, BLUE, "#D6E4FF"
        elif not has_input:
            label, bg, fg, border = "Step 1 missing\nUpload AI result", AMBER_SOFT, AMBER, "#FDE68A"
        elif not has_tokens:
            label, bg, fg, border = "AI result loaded\nNo PrivacyGate placeholders", AMBER_SOFT, AMBER, "#FDE68A"
        elif not has_document:
            label, bg, fg, border = "Step 2 missing\nChoose original document", BLUE_SOFT, BLUE, "#D6E4FF"
        else:
            label, bg, fg, border = "Ready to restore\nLocal mapping matched", GREEN_SOFT, GREEN, "#BBF7D0"
        self.state.setText(label)
        self.state.setStyleSheet(
            f"background:{bg};color:{fg};border:1px solid {border};border-radius:8px;padding:5px 7px;font-size:7px;font-weight:900;"
        )

    def _update_suggestion(self, candidates: list[_Candidate]) -> None:
        if self.suggestion is None:
            return
        tokens = TOKEN_PATTERN.findall(self.page.input_text.toPlainText())
        if not tokens or self.page.document_combo.currentData():
            self.suggestion.hide()
            return
        matches = [item for item in candidates if item.matching_tokens > 0]
        self.suggestion.show()
        if not matches:
            self.suggestion.setStyleSheet(
                f"QFrame#RestoreSmartSuggestion{{background:{AMBER_SOFT};border:1px solid #FDE68A;border-radius:10px;}}"
            )
            self.suggestion_title.setText("No strong restore match found")
            self.suggestion_copy.setText(
                "Try Find original and search by filename, source, account or restore-key count. You can still choose a document manually."
            )
            self.use_best.setEnabled(False)
            return
        self.suggestion.setStyleSheet(
            f"QFrame#RestoreSmartSuggestion{{background:{GREEN_SOFT};border:1px solid #BBF7D0;border-radius:10px;}}"
        )
        self.suggestion_title.setText("Best original candidates found")
        lines = []
        for item in matches[:2]:
            quality, keys = _match_text(item)
            lines.append(f"{item.document.title} — {quality} · {keys}")
        self.suggestion_copy.setText("\n".join(lines))
        self.use_best.setEnabled(True)

    def refresh(self) -> None:
        try:
            candidates = _load_candidates(self.page, self.main_window)
            self._update_selected_copy(candidates)
            self._update_state(candidates)
            self._update_suggestion(candidates)
        except Exception:
            # Smart matching must never interrupt the proven Restore path.
            return


def apply_restore_finder_product_polish_2026(main_window) -> None:
    if bool(getattr(main_window, "_restore_finder_product_polish_2026", False)):
        return
    main_window._restore_finder_product_polish_2026 = True

    # Controller.open_finder resolves this module symbol at runtime, so replacing
    # it here upgrades the dialog while keeping selection/delegation semantics.
    _finder_module.OriginalDocumentFinderDialog = SmartOriginalDocumentFinderDialog

    controller = RestoreSmartMatchController(main_window)
    main_window._restore_smart_match_controller = controller
