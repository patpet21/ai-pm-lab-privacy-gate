from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.storage.governance_repository import (
    DocumentGovernanceRepository,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.ui import mockup_library_final_2026 as _final_library
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.library_page import LibraryPage
from ai_pm_lab_privacy_gate.ui.library_workspace_runtime_2026 import (
    document_workspace_label,
    policy_status_text,
    resolve_library_workspace,
)


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

_INSTALLED = False
_FILTER_PATCHED = False
_REPOSITORY_PATCHED = False


class LibraryDocumentEventStore:
    """Metadata-only per-document timeline stored in the existing local Library DB.

    No document content, titles, original values, restore mappings, file paths,
    search terms, previews or connector tokens are stored here.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS library_document_events (
                    event_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    workspace_key TEXT NOT NULL DEFAULT 'personal',
                    detail TEXT NOT NULL DEFAULT '',
                    policy_version INTEGER NOT NULL DEFAULT 0,
                    ai_destination TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_library_document_events_doc_time "
                "ON library_document_events(document_id, occurred_at DESC)"
            )

    @staticmethod
    def _safe(value: object, limit: int = 160) -> str:
        return str(value or "").replace("\n", " ").strip()[:limit]

    def record(
        self,
        document_id: str,
        event_type: str,
        *,
        workspace_key: str = "personal",
        detail: str = "",
        policy_version: int = 0,
        ai_destination: str = "",
    ) -> None:
        if not document_id:
            return
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO library_document_events(
                        event_id, document_id, occurred_at, event_type,
                        workspace_key, detail, policy_version, ai_destination
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        self._safe(document_id, 96),
                        datetime.now(timezone.utc).isoformat(),
                        self._safe(event_type, 80),
                        self._safe(workspace_key or "personal", 160),
                        self._safe(detail, 200),
                        max(0, int(policy_version or 0)),
                        self._safe(ai_destination, 80),
                    ),
                )
        except sqlite3.IntegrityError:
            # The document may have been permanently deleted between the UI event
            # and this metadata-only write. Deletion remains authoritative.
            return

    def recent(self, document_id: str, limit: int = 10) -> tuple[dict[str, object], ...]:
        safe_limit = max(1, min(int(limit), 50))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT occurred_at, event_type, workspace_key, detail,
                       policy_version, ai_destination
                FROM library_document_events
                WHERE document_id = ?
                ORDER BY occurred_at DESC
                LIMIT ?
                """,
                (str(document_id), safe_limit),
            ).fetchall()
        return tuple(dict(row) for row in rows)


def _repository_event_context(repository: LibraryRepository) -> tuple[str, int]:
    provider = getattr(repository, "_privacygate_governance_context_provider", None)
    if callable(provider):
        try:
            snapshot = provider() or {}
            return (
                str(snapshot.get("key") or "personal"),
                max(0, int(snapshot.get("policy_version") or 0)),
            )
        except Exception:
            pass
    return "personal", 0


def _record_repository_event(
    repository: LibraryRepository,
    document_id: str,
    event_type: str,
    detail: str,
) -> None:
    workspace_key, policy_version = _repository_event_context(repository)
    LibraryDocumentEventStore(repository.db_path).record(
        document_id,
        event_type,
        workspace_key=workspace_key,
        detail=detail,
        policy_version=policy_version,
    )


def install_library_control_center_2026() -> None:
    """Install additive metadata hooks before MainWindow creates its pages."""
    global _INSTALLED, _REPOSITORY_PATCHED
    if _INSTALLED:
        return
    _INSTALLED = True

    if not _REPOSITORY_PATCHED:
        _REPOSITORY_PATCHED = True

        previous_save = LibraryRepository.save
        previous_update_metadata = LibraryRepository.update_metadata
        previous_set_favorite = LibraryRepository.set_favorite
        previous_set_mcp_shared = LibraryRepository.set_mcp_shared
        previous_move_to_trash = LibraryRepository.move_to_trash
        previous_restore_from_trash = LibraryRepository.restore_from_trash

        def save(self: LibraryRepository, *args, **kwargs):
            document = previous_save(self, *args, **kwargs)
            _record_repository_event(
                self,
                document.document_id,
                "protected_saved",
                "Protected copy saved to the local Library",
            )
            return document

        def update_metadata(self: LibraryRepository, document_id: str, **kwargs):
            document = previous_update_metadata(self, document_id, **kwargs)
            _record_repository_event(
                self,
                document_id,
                "metadata_updated",
                "Local Library metadata updated",
            )
            return document

        def set_favorite(self: LibraryRepository, document_id: str, favorite: bool):
            document = previous_set_favorite(self, document_id, favorite)
            _record_repository_event(
                self,
                document_id,
                "favorite_added" if favorite else "favorite_removed",
                "Favorite state updated locally",
            )
            return document

        def set_mcp_shared(self: LibraryRepository, document_id: str, shared: bool):
            document = previous_set_mcp_shared(self, document_id, shared)
            _record_repository_event(
                self,
                document_id,
                "ai_access_allowed" if shared else "ai_access_blocked",
                "Protected-copy AI / MCP access preference updated",
            )
            return document

        def move_to_trash(self: LibraryRepository, document_id: str) -> None:
            _record_repository_event(
                self,
                document_id,
                "moved_to_trash",
                "Protected copy moved to recoverable local trash",
            )
            previous_move_to_trash(self, document_id)

        def restore_from_trash(self: LibraryRepository, document_id: str) -> None:
            previous_restore_from_trash(self, document_id)
            _record_repository_event(
                self,
                document_id,
                "restored_from_trash",
                "Protected copy restored from local trash",
            )

        LibraryRepository.save = save
        LibraryRepository.update_metadata = update_metadata
        LibraryRepository.set_favorite = set_favorite
        LibraryRepository.set_mcp_shared = set_mcp_shared
        LibraryRepository.move_to_trash = move_to_trash
        LibraryRepository.restore_from_trash = restore_from_trash

    previous_refresh = LibraryPage.refresh
    previous_selection_changed = LibraryPage._selection_changed

    def refresh(self: LibraryPage, *args) -> None:
        previous_refresh(self, *args)
        if not bool(getattr(self, "_library_control_center_2026", False)):
            return
        _after_refresh(self)

    def selection_changed(self: LibraryPage) -> None:
        previous_selection_changed(self)
        if bool(getattr(self, "_library_control_center_2026", False)):
            _update_control_center_detail(self)

    LibraryPage.refresh = refresh
    LibraryPage._selection_changed = selection_changed


def _button_qss(*, active: bool = False, danger: bool = False) -> str:
    if danger:
        return (
            "QPushButton{background:#FFF5F5;color:#B42318;border:1px solid #FECACA;"
            "border-radius:8px;padding:6px 10px;font-size:8px;font-weight:850;}"
            "QPushButton:hover{background:#FEF2F2;}"
        )
    if active:
        return (
            f"QPushButton{{background:#EEF4FF;color:{BLUE};border:1px solid #D6E4FF;"
            "border-radius:8px;padding:6px 10px;font-size:8px;font-weight:900;}"
            "QPushButton:hover{background:#E6EEFF;}"
        )
    return (
        "QPushButton{background:#FFFFFF;color:#344054;border:1px solid #D0D5DD;"
        "border-radius:8px;padding:6px 10px;font-size:8px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;border-color:#98A2B3;}"
    )


def _smart_button(text: str, key: str, page: LibraryPage) -> QPushButton:
    button = QPushButton(text)
    button.setCheckable(True)
    button.setMinimumHeight(30)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#475467;border:1px solid #D0D5DD;"
        "border-radius:8px;padding:5px 10px;font-size:7.8px;font-weight:800;}"
        "QPushButton:hover{background:#F8FAFC;color:#101828;}"
        "QPushButton:checked{background:#EEF4FF;color:#2563EB;border-color:#D6E4FF;font-weight:900;}"
    )
    button.clicked.connect(
        lambda checked=False, collection=key: _set_smart_collection(page, collection if checked else "")
    )
    return button


def _build_smart_collections(page: LibraryPage) -> None:
    root = page.layout()
    if root is None or getattr(page, "_library_smart_collections_2026", None) is not None:
        return

    frame = QFrame(objectName="LibrarySmartCollections2026")
    frame.setStyleSheet(
        f"QFrame#LibrarySmartCollections2026{{background:{WHITE};border:1px solid {BORDER};border-radius:11px;}}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(10, 7, 10, 7)
    row.setSpacing(6)

    title = QLabel("SMART COLLECTIONS")
    title.setStyleSheet(
        f"color:{MUTED};font-size:7px;font-weight:950;border:none;padding-right:3px;"
    )
    row.addWidget(title)

    page._library_smart_collection_2026 = ""
    page._library_smart_buttons_2026 = {}
    for key, label in (
        ("recent", "Recent"),
        ("needs_attention", "Needs attention"),
        ("ai_blocked", "AI access blocked"),
        ("legacy", "Legacy local"),
        ("policy_outdated", "Policy review"),
    ):
        button = _smart_button(label, key, page)
        page._library_smart_buttons_2026[key] = button
        row.addWidget(button)

    clear = QPushButton("Clear smart view")
    clear.setMinimumHeight(30)
    clear.setStyleSheet(_button_qss())
    clear.clicked.connect(lambda _checked=False: _set_smart_collection(page, ""))
    row.addWidget(clear)
    row.addStretch(1)

    root.insertWidget(3, frame)
    page._library_smart_collections_2026 = frame


def _build_bulk_bar(page: LibraryPage) -> None:
    root = page.layout()
    if root is None or getattr(page, "_library_bulk_bar_2026", None) is not None:
        return

    page._library_bulk_selected_ids_2026 = set()

    frame = QFrame(objectName="LibraryBulkBar2026")
    frame.setStyleSheet(
        "QFrame#LibraryBulkBar2026{background:#F5F8FF;border:1px solid #D6E4FF;border-radius:11px;}"
    )
    row = QHBoxLayout(frame)
    row.setContentsMargins(10, 7, 10, 7)
    row.setSpacing(6)

    count = QLabel("0 selected")
    count.setStyleSheet(
        f"color:{BLUE};font-size:8px;font-weight:950;border:none;"
    )
    row.addWidget(count)
    row.addSpacing(5)

    favorite = QPushButton("Favorite")
    block = QPushButton("Block AI access")
    allow = QPushButton("Allow AI access")
    labels = QPushButton("Add labels")
    download = QPushButton("Download safe copies")
    trash = QPushButton("Move to trash")
    clear = QPushButton("Clear selection")

    for button in (favorite, block, allow, labels, download, clear):
        button.setMinimumHeight(30)
        button.setStyleSheet(_button_qss())
    trash.setMinimumHeight(30)
    trash.setStyleSheet(_button_qss(danger=True))

    favorite.clicked.connect(lambda _checked=False: _bulk_favorite(page))
    block.clicked.connect(lambda _checked=False: _bulk_ai_access(page, False))
    allow.clicked.connect(lambda _checked=False: _bulk_ai_access(page, True))
    labels.clicked.connect(lambda _checked=False: _bulk_labels(page))
    download.clicked.connect(lambda _checked=False: _bulk_download(page))
    trash.clicked.connect(lambda _checked=False: _bulk_trash(page))
    clear.clicked.connect(lambda _checked=False: _clear_bulk_selection(page))

    for button in (favorite, block, allow, labels, download, trash):
        row.addWidget(button)
    row.addStretch(1)
    row.addWidget(clear)

    root.insertWidget(4, frame)
    frame.hide()

    page._library_bulk_bar_2026 = frame
    page._library_bulk_count_2026 = count


def _detail_value() -> QLabel:
    label = QLabel("—")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setStyleSheet(f"color:{TEXT};font-size:8px;font-weight:750;border:none;")
    return label


def _build_details_activity(page: LibraryPage) -> None:
    if getattr(page, "_library_control_tabs_2026", None) is not None:
        return
    preview_card = page.preview.parentWidget()
    layout = preview_card.layout() if preview_card is not None else None
    if not isinstance(layout, QVBoxLayout):
        return

    tabs = QTabWidget()
    tabs.setMaximumHeight(255)
    tabs.setStyleSheet(
        "QTabWidget::pane{background:#FFFFFF;border:1px solid #E4E7EC;border-radius:10px;top:-1px;}"
        "QTabBar::tab{background:#F8FAFC;color:#667085;border:1px solid #E4E7EC;"
        "padding:6px 11px;font-size:8px;font-weight:800;}"
        "QTabBar::tab:selected{background:#FFFFFF;color:#2563EB;border-bottom-color:#FFFFFF;font-weight:900;}"
    )

    details = QWidget()
    detail_layout = QVBoxLayout(details)
    detail_layout.setContentsMargins(11, 9, 11, 9)
    detail_layout.setSpacing(7)

    compliance = QFrame(objectName="LibraryCompliance2026")
    compliance_row = QHBoxLayout(compliance)
    compliance_row.setContentsMargins(10, 7, 10, 7)
    compliance_icon = QLabel()
    compliance_icon.setFixedSize(18, 18)
    compliance_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    compliance_text = QLabel("Policy context")
    compliance_text.setWordWrap(True)
    compliance_text.setStyleSheet(
        f"color:{TEXT};font-size:7.8px;font-weight:800;border:none;"
    )
    compliance_row.addWidget(compliance_icon, 0, Qt.AlignmentFlag.AlignTop)
    compliance_row.addWidget(compliance_text, 1)
    detail_layout.addWidget(compliance)

    grid = QGridLayout()
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(5)
    page._library_control_detail_values_2026 = {}
    fields = (
        ("source", "Source / account"),
        ("workspace", "Workspace"),
        ("type", "File / protection"),
        ("profile", "Privacy profile"),
        ("findings", "Protected findings"),
        ("dates", "Created / updated"),
        ("restore", "Restore"),
        ("ai", "AI / MCP"),
    )
    for index, (key, caption) in enumerate(fields):
        row_index = index // 2
        column = (index % 2) * 2
        heading = QLabel(caption.upper())
        heading.setStyleSheet(
            f"color:{MUTED};font-size:6.7px;font-weight:950;border:none;"
        )
        value = _detail_value()
        page._library_control_detail_values_2026[key] = value
        grid.addWidget(heading, row_index, column)
        grid.addWidget(value, row_index, column + 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    detail_layout.addLayout(grid)

    activity = QWidget()
    activity_layout = QVBoxLayout(activity)
    activity_layout.setContentsMargins(11, 9, 11, 9)
    activity_layout.setSpacing(5)
    activity_heading = QLabel(
        "Metadata-only timeline · content, original values, file paths and search terms are never stored here."
    )
    activity_heading.setWordWrap(True)
    activity_heading.setStyleSheet(
        f"color:{MUTED};font-size:7px;border:none;"
    )
    activity_text = QLabel("Select a document to view its local activity.")
    activity_text.setWordWrap(True)
    activity_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    activity_text.setAlignment(Qt.AlignmentFlag.AlignTop)
    activity_text.setStyleSheet(
        f"color:{TEXT};font-size:7.8px;border:none;background:#F8FAFC;"
        f"border:1px solid {BORDER};border-radius:8px;padding:8px;"
    )
    activity_layout.addWidget(activity_heading)
    activity_layout.addWidget(activity_text, 1)

    tabs.addTab(details, "Details")
    tabs.addTab(activity, "Activity")
    index = layout.indexOf(page.preview)
    layout.insertWidget(max(1, index), tabs)

    page._library_control_tabs_2026 = tabs
    page._library_compliance_frame_2026 = compliance
    page._library_compliance_icon_2026 = compliance_icon
    page._library_compliance_text_2026 = compliance_text
    page._library_activity_text_2026 = activity_text


def _set_compliance_style(page: LibraryPage, tone: str, text: str) -> None:
    palette = {
        "green": ("#ECFDF3", GREEN, "#BBF7D0", "check"),
        "amber": ("#FFF7ED", AMBER, "#FED7AA", "protect"),
        "red": ("#FEF2F2", RED, "#FECACA", "protect"),
        "blue": ("#EEF4FF", BLUE, "#D6E4FF", "protect"),
        "neutral": ("#F8FAFC", MUTED, BORDER, "info"),
    }
    background, foreground, border, icon_name = palette.get(tone, palette["neutral"])
    frame = getattr(page, "_library_compliance_frame_2026", None)
    label = getattr(page, "_library_compliance_text_2026", None)
    icon_label = getattr(page, "_library_compliance_icon_2026", None)
    if frame is not None:
        frame.setStyleSheet(
            f"QFrame#LibraryCompliance2026{{background:{background};border:1px solid {border};border-radius:9px;}}"
        )
    if label is not None:
        label.setText(text)
        label.setStyleSheet(
            f"color:{foreground};font-size:7.8px;font-weight:850;border:none;"
        )
    if icon_label is not None:
        icon_label.setPixmap(icon(icon_name, color=foreground, size=15).pixmap(15, 15))


def _active_policy_version(page: LibraryPage) -> int:
    context = getattr(page, "_library_workspace_context_2026", None)
    policy = getattr(context, "policy", None) if context is not None else None
    try:
        return max(0, int(getattr(policy, "version", 0) or 0))
    except Exception:
        return 0


def _governance_metadata(page: LibraryPage, document_id: str):
    repository = getattr(page, "_library_governance_repository_2026", None)
    if repository is None:
        return None
    try:
        return repository.get(document_id)
    except Exception:
        return None


def _attention_reasons(page: LibraryPage, document) -> tuple[str, ...]:
    reasons: list[str] = []
    if document.replacement_mode == "reversible" and not document.has_mapping:
        reasons.append("Reversible mode has no local restore mapping")

    context = getattr(page, "_library_workspace_context_2026", None)
    if context is not None and context.managed:
        active_version = _active_policy_version(page)
        metadata = _governance_metadata(page, document.document_id)
        if context.policy is None:
            reasons.append("Organization policy is unavailable")
        elif metadata is None:
            reasons.append("Governance policy context was not captured")
        elif active_version and metadata.policy_version != active_version:
            if metadata.policy_version:
                reasons.append(
                    f"Protected under policy v{metadata.policy_version}; current policy is v{active_version}"
                )
            else:
                reasons.append(f"No recorded policy version; current policy is v{active_version}")
    return tuple(reasons)


def _smart_match(page: LibraryPage, document) -> bool:
    key = str(getattr(page, "_library_smart_collection_2026", "") or "")
    if not key:
        return True
    if key == "recent":
        try:
            return document.updated_at >= datetime.now(timezone.utc) - timedelta(days=7)
        except Exception:
            return False
    if key == "needs_attention":
        return bool(_attention_reasons(page, document))
    if key == "ai_blocked":
        return not bool(document.mcp_shared)
    if key == "legacy":
        metadata = getattr(page, "_library_workspace_metadata_map", {}).get(document.document_id)
        return metadata is None
    if key == "policy_outdated":
        context = getattr(page, "_library_workspace_context_2026", None)
        if context is None or not context.managed:
            return False
        active_version = _active_policy_version(page)
        metadata = _governance_metadata(page, document.document_id)
        return bool(active_version and (metadata is None or metadata.policy_version != active_version))
    return True


def _patch_filter_runtime() -> None:
    global _FILTER_PATCHED
    if _FILTER_PATCHED:
        return
    _FILTER_PATCHED = True
    previous_match = _final_library._document_matches_filters

    def document_matches(page: LibraryPage, document) -> bool:
        return bool(previous_match(page, document) and _smart_match(page, document))

    _final_library._document_matches_filters = document_matches


def _set_smart_collection(page: LibraryPage, key: str) -> None:
    _clear_bulk_selection(page)
    page._library_smart_collection_2026 = key
    buttons = getattr(page, "_library_smart_buttons_2026", {})
    for name, button in buttons.items():
        button.blockSignals(True)
        button.setChecked(bool(key and name == key))
        button.blockSignals(False)
    page._apply_library_final_filters()
    _update_smart_counts(page)
    _update_control_center_detail(page)


def _update_smart_counts(page: LibraryPage) -> None:
    buttons = getattr(page, "_library_smart_buttons_2026", {})
    documents = tuple(getattr(page, "_library_scoped_documents_2026", ()) or ())
    current = str(getattr(page, "_library_smart_collection_2026", "") or "")

    labels = {
        "recent": "Recent",
        "needs_attention": "Needs attention",
        "ai_blocked": "AI access blocked",
        "legacy": "Legacy local",
        "policy_outdated": "Policy review",
    }

    for key, button in buttons.items():
        old = page._library_smart_collection_2026
        page._library_smart_collection_2026 = key
        count = sum(1 for document in documents if _smart_match(page, document))
        page._library_smart_collection_2026 = old
        button.setText(f"{labels[key]}  {count}")

    context = getattr(page, "_library_workspace_context_2026", None)
    personal = bool(context is None or context.personal)
    if "legacy" in buttons:
        buttons["legacy"].setVisible(personal)
    if "policy_outdated" in buttons:
        buttons["policy_outdated"].setVisible(not personal)

    if (personal and current == "policy_outdated") or (not personal and current == "legacy"):
        current = ""
        for button in buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)

    page._library_smart_collection_2026 = current


def _toggle_bulk_document(page: LibraryPage, document_id: str, checked: bool) -> None:
    selected = getattr(page, "_library_bulk_selected_ids_2026", set())
    if checked:
        selected.add(document_id)
    else:
        selected.discard(document_id)
    page._library_bulk_selected_ids_2026 = selected
    _update_bulk_bar(page)


def _decorate_bulk_rows(page: LibraryPage) -> None:
    rows = getattr(page, "_library_final_rows", {})
    selected = getattr(page, "_library_bulk_selected_ids_2026", set())
    scoped_ids = {
        document.document_id
        for document in getattr(page, "_library_scoped_documents_2026", ())
    }
    selected.intersection_update(scoped_ids)
    page._library_bulk_selected_ids_2026 = selected

    for document_id, widget in rows.items():
        if getattr(widget, "_library_bulk_checkbox_2026", None) is not None:
            continue
        check = QCheckBox()
        check.setToolTip("Select this document for bulk actions")
        check.setCursor(Qt.CursorShape.PointingHandCursor)
        check.setChecked(document_id in selected)
        check.setStyleSheet(
            "QCheckBox{background:transparent;border:none;}"
            "QCheckBox::indicator{width:17px;height:17px;}"
        )
        check.toggled.connect(
            lambda checked, doc_id=document_id: _toggle_bulk_document(
                page, doc_id, checked
            )
        )
        layout = widget.layout()
        if layout is not None:
            layout.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
        widget._library_bulk_checkbox_2026 = check

    _update_bulk_bar(page)


def _update_bulk_bar(page: LibraryPage) -> None:
    selected = getattr(page, "_library_bulk_selected_ids_2026", set())
    bar = getattr(page, "_library_bulk_bar_2026", None)
    count = getattr(page, "_library_bulk_count_2026", None)
    if count is not None:
        count.setText(f"{len(selected)} selected")
    if bar is not None:
        bar.setVisible(bool(selected))


def _clear_bulk_selection(page: LibraryPage) -> None:
    page._library_bulk_selected_ids_2026 = set()
    for widget in getattr(page, "_library_final_rows", {}).values():
        check = getattr(widget, "_library_bulk_checkbox_2026", None)
        if check is not None:
            check.blockSignals(True)
            check.setChecked(False)
            check.blockSignals(False)
    _update_bulk_bar(page)


def _selected_bulk_documents(page: LibraryPage):
    selected = set(getattr(page, "_library_bulk_selected_ids_2026", set()))
    scoped = tuple(getattr(page, "_library_scoped_documents_2026", ()) or ())
    return tuple(
        document
        for document in scoped
        if document.document_id in selected and document.deleted_at is None
    )


def _bulk_favorite(page: LibraryPage) -> None:
    documents = _selected_bulk_documents(page)
    if not documents:
        return
    for document in documents:
        page.library.set_favorite(document.document_id, True)
    _clear_bulk_selection(page)
    page.refresh()


def _bulk_ai_access(page: LibraryPage, allow: bool) -> None:
    documents = _selected_bulk_documents(page)
    if not documents:
        return
    context = resolve_library_workspace(page)
    if allow and context.managed and context.policy is None:
        QMessageBox.warning(
            page,
            "Organization policy unavailable",
            "PrivacyGate cannot verify the active Organization policy, so bulk AI / MCP access cannot be enabled right now.",
        )
        return
    if allow:
        answer = QMessageBox.question(
            page,
            "Allow AI / MCP access?",
            f"Allow the protected copies of {len(documents)} selected document(s) to be available to approved AI / MCP workflows?\n\n"
            "Original values and encrypted restore mappings remain local. Organization AI destinations are still enforced by policy.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
    for document in documents:
        page.library.set_mcp_shared(document.document_id, allow)
    _clear_bulk_selection(page)
    page.refresh()


def _bulk_labels(page: LibraryPage) -> None:
    documents = _selected_bulk_documents(page)
    if not documents:
        return
    value, ok = QInputDialog.getText(
        page,
        "Add labels to selected documents",
        "Comma-separated labels to add:",
    )
    if not ok:
        return
    additions = tuple(
        dict.fromkeys(part.strip() for part in value.split(",") if part.strip())
    )
    if not additions:
        return
    for document in documents:
        merged = tuple(dict.fromkeys((*document.labels, *additions)))
        page.library.update_metadata(document.document_id, labels=merged)
    _clear_bulk_selection(page)
    page.refresh()


def _safe_filename(value: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")
    return name[:100] or "protected_document"


def _bulk_download(page: LibraryPage) -> None:
    documents = _selected_bulk_documents(page)
    if not documents:
        return
    directory = QFileDialog.getExistingDirectory(
        page,
        "Download protected text copies",
    )
    if not directory:
        return
    root = Path(directory)
    written = 0
    for document in documents:
        stem = _safe_filename(document.title)
        target = root / f"{stem}_protected.txt"
        counter = 2
        while target.exists():
            target = root / f"{stem}_protected_{counter}.txt"
            counter += 1
        target.write_text(document.protected_text, encoding="utf-8")
        store = getattr(page, "_library_document_events_2026", None)
        if store is not None:
            context = resolve_library_workspace(page)
            store.record(
                document.document_id,
                "safe_copy_downloaded",
                workspace_key=context.key,
                detail="Protected text copy downloaded locally",
                policy_version=_active_policy_version(page),
            )
        written += 1
    QMessageBox.information(
        page,
        "Safe copies downloaded",
        f"{written} protected text cop{'y' if written == 1 else 'ies'} saved locally.",
    )
    _clear_bulk_selection(page)
    _update_control_center_detail(page)


def _bulk_trash(page: LibraryPage) -> None:
    documents = _selected_bulk_documents(page)
    if not documents:
        return
    answer = QMessageBox.question(
        page,
        "Move selected documents to trash?",
        f"Move {len(documents)} protected document(s) and their encrypted restore mappings to recoverable local trash?",
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    for document in documents:
        page.library.move_to_trash(document.document_id)
    _clear_bulk_selection(page)
    page.refresh()


def _format_event_type(value: str) -> str:
    labels = {
        "protected_saved": "Protected & saved",
        "metadata_updated": "Metadata updated",
        "favorite_added": "Added to favorites",
        "favorite_removed": "Removed from favorites",
        "ai_access_allowed": "AI / MCP access allowed",
        "ai_access_blocked": "AI / MCP access blocked",
        "moved_to_trash": "Moved to trash",
        "restored_from_trash": "Restored from trash",
        "restore_requested": "Restore started",
        "restore_completed": "Restore completed",
        "ai_handoff": "Used with AI",
        "protected_text_copied": "Protected text copied",
        "safe_copy_downloaded": "Safe copy downloaded",
    }
    return labels.get(value, value.replace("_", " ").title())


def _update_activity_panel(page: LibraryPage, document) -> None:
    target = getattr(page, "_library_activity_text_2026", None)
    store = getattr(page, "_library_document_events_2026", None)
    if target is None:
        return
    if document is None:
        target.setText("Select a document to view its local activity.")
        return

    events = store.recent(document.document_id, 9) if store is not None else ()
    lines: list[str] = []
    for event in events:
        try:
            stamp = datetime.fromisoformat(str(event.get("occurred_at") or "")).astimezone()
            when = stamp.strftime("%d %b %Y · %I:%M %p")
        except Exception:
            when = "Local event"
        label = _format_event_type(str(event.get("event_type") or "activity"))
        destination = str(event.get("ai_destination") or "").strip()
        policy_version = int(event.get("policy_version") or 0)
        suffix: list[str] = []
        if destination:
            suffix.append(destination)
        if policy_version:
            suffix.append(f"Policy v{policy_version}")
        detail = str(event.get("detail") or "").strip()
        extra = f" · {' · '.join(suffix)}" if suffix else ""
        if detail:
            extra += f"\n    {detail}"
        lines.append(f"{when}  ·  {label}{extra}")

    if not lines:
        when = document.created_at.astimezone().strftime("%d %b %Y · %I:%M %p")
        lines.append(
            f"{when}  ·  Protected Library record created\n"
            "    Historical item: detailed per-document activity was not recorded before this feature was enabled."
        )
    target.setText("\n\n".join(lines))


def _update_compliance(page: LibraryPage, document) -> None:
    context = getattr(page, "_library_workspace_context_2026", None)
    if document is None or context is None:
        _set_compliance_style(page, "neutral", "Select a document to review its policy context.")
        return

    if context.personal:
        metadata = getattr(page, "_library_workspace_metadata_map", {}).get(document.document_id)
        label = document_workspace_label(context, metadata)
        if label == "Legacy local":
            _set_compliance_style(
                page,
                "amber",
                "Personal · Legacy local item · not assigned to an Organization. Local integrity and restore controls still apply.",
            )
        else:
            _set_compliance_style(
                page,
                "blue",
                f"Personal · {context.plan_label} · protected and governed locally on this device.",
            )
        return

    if context.policy is None:
        _set_compliance_style(
            page,
            "amber",
            f"Managed by {context.name} · Policy unavailable · AI handoff fails closed until the Organization policy can be verified.",
        )
        return

    active_version = _active_policy_version(page)
    governance = getattr(page, "_library_governance_repository_2026", None)
    metadata = _governance_metadata(page, document.document_id)
    integrity = None
    if governance is not None:
        try:
            integrity = governance.verify(document.document_id)
        except Exception:
            integrity = None

    if integrity is not None and not integrity.ok:
        _set_compliance_style(
            page,
            "red",
            f"Managed by {context.name} · INTEGRITY FAILED · restore and governed use require review before this document should be used.",
        )
        return

    if metadata is None:
        _set_compliance_style(
            page,
            "amber",
            f"Managed by {context.name} · Policy v{active_version} active · governance capture is missing for this local item.",
        )
        return

    if active_version and metadata.policy_version == active_version:
        integrity_text = (
            "local integrity verified"
            if integrity is not None and integrity.ok
            else "local integrity status available"
        )
        _set_compliance_style(
            page,
            "green",
            f"Managed by {context.name} · Policy v{active_version} context current · {integrity_text}. AI destinations remain enforced at handoff.",
        )
        return

    captured = f"v{metadata.policy_version}" if metadata.policy_version else "no recorded policy version"
    _set_compliance_style(
        page,
        "amber",
        f"Managed by {context.name} · Protected under {captured} · current Policy v{active_version} · policy review recommended before the next AI handoff.",
    )


def _update_control_center_detail(page: LibraryPage) -> None:
    if not bool(getattr(page, "_library_control_center_2026", False)):
        return
    document = page._current()
    values = getattr(page, "_library_control_detail_values_2026", {})
    if document is None:
        for value in values.values():
            value.setText("—")
        _update_activity_panel(page, None)
        _update_compliance(page, None)
        return

    provider_key, provider_label, account_label = _final_library._provider_info(page, document)
    source = provider_label or "Local"
    if account_label:
        source += f" · {account_label}"
    metadata = getattr(page, "_library_workspace_metadata_map", {}).get(document.document_id)
    context = getattr(page, "_library_workspace_context_2026", None)
    workspace = document_workspace_label(context, metadata) if context is not None else "Local"
    suffix = _final_library._document_suffix(document).lstrip(".").upper()
    entities = ", ".join(
        str(value).replace("_", " ").title()
        for value in tuple(document.entity_types or ())[:8]
    ) or "No category metadata"
    if len(tuple(document.entity_types or ())) > 8:
        entities += "…"

    if "source" in values:
        values["source"].setText(source)
    if "workspace" in values:
        values["workspace"].setText(workspace)
    if "type" in values:
        values["type"].setText(
            f"{suffix} · {document.replacement_mode.replace('_', ' ').title()}"
        )
    if "profile" in values:
        values["profile"].setText(document.profile_key.replace("_", " ").title())
    if "findings" in values:
        values["findings"].setText(f"{document.findings_count} · {entities}")
    if "dates" in values:
        values["dates"].setText(
            f"{document.created_at.astimezone().strftime('%d %b %Y')} · updated {document.updated_at.astimezone().strftime('%d %b %Y')}"
        )
    if "restore" in values:
        values["restore"].setText(
            "Available · encrypted local mapping"
            if document.has_mapping
            else "Unavailable · no reversible mapping"
        )
    if "ai" in values:
        values["ai"].setText(
            "Protected copy allowed"
            if document.mcp_shared
            else "Protected copy blocked"
        )

    _update_activity_panel(page, document)
    _update_compliance(page, document)


def _after_refresh(page: LibraryPage) -> None:
    _update_smart_counts(page)
    _decorate_bulk_rows(page)
    _update_control_center_detail(page)


def _install_action_hooks(main_window, page: LibraryPage) -> None:
    store = page._library_document_events_2026

    def current_context():
        context = resolve_library_workspace(page)
        return context.key, _active_policy_version(page)

    def log_current(event_type: str, detail: str) -> None:
        document = page._current()
        if document is None:
            return
        workspace_key, policy_version = current_context()
        store.record(
            document.document_id,
            event_type,
            workspace_key=workspace_key,
            detail=detail,
            policy_version=policy_version,
        )
        QTimer.singleShot(0, lambda: _update_control_center_detail(page))

    page.copy_button.clicked.connect(
        lambda _checked=False: log_current(
            "protected_text_copied",
            "Protected text copied locally",
        )
    )

    page.restore_requested.connect(
        lambda document_id: store.record(
            document_id,
            "restore_requested",
            workspace_key=resolve_library_workspace(page).key,
            detail="Local restore started from Library",
            policy_version=_active_policy_version(page),
        )
    )

    def ai_hook(document, destination) -> None:
        store.record(
            document.document_id,
            "ai_handoff",
            workspace_key=resolve_library_workspace(page).key,
            detail="Privacy Preflight passed; protected text copied for approved AI handoff",
            policy_version=_active_policy_version(page),
            ai_destination=str(getattr(destination, "label", "") or ""),
        )
        _update_control_center_detail(page)

    page._library_ai_activity_hook_2026 = ai_hook

    restore_page = getattr(main_window, "restore_page", None)
    if restore_page is not None and not bool(
        getattr(restore_page, "_library_document_activity_hook_2026", False)
    ):
        restore_page._library_document_activity_hook_2026 = True
        previous_restore_ready = restore_page._restore_ready

        def restore_ready(payload: object) -> None:
            previous_restore_ready(payload)
            try:
                restored_count = int(payload.get("restored_count", 0))
            except Exception:
                restored_count = 0
            document_id = str(restore_page.document_combo.currentData() or "")
            if document_id and restored_count > 0:
                context = resolve_library_workspace(page)
                store.record(
                    document_id,
                    "restore_completed",
                    workspace_key=context.key,
                    detail=f"{restored_count} placeholder occurrence(s) restored locally",
                    policy_version=_active_policy_version(page),
                )
                QTimer.singleShot(0, lambda: _update_control_center_detail(page))

        restore_page._restore_ready = restore_ready


def apply_library_control_center_2026(main_window) -> None:
    """Add Smart Collections, bulk controls, document activity and policy context."""
    page = getattr(main_window, "library_page", None)
    if page is None or bool(getattr(page, "_library_control_center_2026", False)):
        return

    page._library_control_center_2026 = True
    page._library_document_events_2026 = LibraryDocumentEventStore(page.library.db_path)
    page._library_governance_repository_2026 = DocumentGovernanceRepository(page.library)

    _patch_filter_runtime()
    _build_smart_collections(page)
    _build_bulk_bar(page)
    _build_details_activity(page)
    _install_action_hooks(main_window, page)

    team_page = getattr(main_window, "team_page", None)
    for signal_name in ("state_changed", "policy_changed"):
        signal = getattr(team_page, signal_name, None) if team_page is not None else None
        if signal is not None:
            signal.connect(lambda *_args: QTimer.singleShot(0, page.refresh))

    page.refresh()
