from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _friendly_connection_error, _retry_network, _run_busy


THEMES = {
    "asana": {"title": "Asana", "accent": "#F06A6A", "accent2": "#FCBD01", "soft": "#FFF1F0", "source": "Projects", "item": "Tasks"},
    "trello": {"title": "Trello", "accent": "#0C66E4", "accent2": "#579DFF", "soft": "#E9F2FF", "source": "Boards", "item": "Cards"},
    "notion": {"title": "Notion", "accent": "#111111", "accent2": "#6B6B6B", "soft": "#F2F2F2", "source": "Workspace", "item": "Pages & databases"},
    "monday": {"title": "monday.com", "accent": "#6161FF", "accent2": "#00C875", "soft": "#EFEFFF", "source": "Boards", "item": "Items"},
    "jira": {"title": "Jira", "accent": "#0C66E4", "accent2": "#22A06B", "soft": "#E9F2FF", "source": "Projects", "item": "Issues"},
}


def _title_for(provider: str, item: dict[str, Any]) -> str:
    if provider == "asana":
        return str(item.get("name") or "Untitled task")
    if provider == "trello":
        return str(item.get("name") or "Untitled card")
    if provider == "notion":
        props = item.get("properties") or {}
        for value in props.values():
            if value.get("type") == "title":
                text = "".join(str(x.get("plain_text") or "") for x in value.get("title", []) or [])
                return text.strip() or "Untitled page"
        bits = item.get("title", []) or []
        text = "".join(str(x.get("plain_text") or "") for x in bits)
        return text.strip() or "Untitled page"
    if provider == "monday":
        return str(item.get("name") or "Untitled item")
    if provider == "jira":
        fields = item.get("fields") or {}
        return f"{item.get('key') or ''}  {fields.get('summary') or ''}".strip()
    return "Item"


def _meta_for(provider: str, item: dict[str, Any]) -> str:
    if provider == "asana":
        assignee = (item.get("assignee") or {}).get("name") or "Unassigned"
        due = item.get("due_on") or item.get("due_at") or "No due date"
        return f"{assignee}   •   {due}"
    if provider == "trello":
        labels = ", ".join(str(x.get("name") or x.get("color") or "") for x in item.get("labels", []) or [])
        return "   •   ".join(x for x in (str(item.get("list_name") or ""), labels, str(item.get("due") or "")) if x)
    if provider == "notion":
        return f"{str(item.get('object') or 'page').title()}   •   {item.get('last_edited_time') or ''}"
    if provider == "monday":
        values = [str(x.get("text") or "") for x in item.get("column_values", []) or [] if str(x.get("text") or "").strip()]
        return "   •   ".join(values[:3])
    if provider == "jira":
        fields = item.get("fields") or {}
        return "   •   ".join(x for x in (
            str((fields.get("status") or {}).get("name") or ""),
            str((fields.get("priority") or {}).get("name") or ""),
            str((fields.get("assignee") or {}).get("displayName") or ""),
        ) if x)
    return ""


def open_project_platform_browser(main_window, provider: str) -> None:
    theme = THEMES[provider]
    service = getattr(main_window.cloud_automation_page, "_connected_apps_service", None)
    if service is None:
        QMessageBox.warning(main_window, theme["title"], "Connected Apps service is unavailable.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle(f"{theme['title']} — connected source")
    dialog.resize(1120, 735)
    dialog.setMinimumSize(900, 600)
    dialog.setStyleSheet("QDialog{background:#F7F8FA;}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(18, 16, 18, 16)
    root.setSpacing(11)

    hero = QFrame()
    hero.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DDE3EA;border-radius:15px;}")
    hero_row = QHBoxLayout(hero)
    hero_row.setContentsMargins(16, 13, 16, 13)
    badge = QLabel(theme["title"][0].upper())
    badge.setFixedSize(42, 42)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(f"background:{theme['accent']};color:#FFFFFF;border-radius:11px;font-size:18px;font-weight:950;")
    hero_row.addWidget(badge)
    titles = QVBoxLayout()
    heading = QLabel(f"{theme['title']} workspace")
    heading.setStyleSheet("color:#172B4D;font-size:22px;font-weight:950;")
    subtitle = QLabel(f"Browse {theme['source'].lower()} and {theme['item'].lower()}, preview content locally, then move only the selected item into Protect.")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#5E6C84;font-size:10px;")
    titles.addWidget(heading)
    titles.addWidget(subtitle)
    hero_row.addLayout(titles, 1)
    ro = QLabel("READ ONLY")
    ro.setStyleSheet(f"background:{theme['soft']};color:{theme['accent']};border:1px solid {theme['accent2']};border-radius:9px;padding:6px 9px;font-size:8px;font-weight:950;")
    hero_row.addWidget(ro)
    root.addWidget(hero)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)

    left = QFrame()
    left.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DDE3EA;border-radius:13px;}")
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(12, 12, 12, 12)
    left_title = QLabel(theme["source"].upper())
    left_title.setStyleSheet(f"color:{theme['accent']};font-size:9px;font-weight:950;letter-spacing:.5px;")
    left_layout.addWidget(left_title)
    sources = QListWidget()
    sources.setStyleSheet(f"QListWidget{{background:#FFFFFF;border:0;color:#243757;outline:0;font-size:11px;}}QListWidget::item{{padding:9px 7px;border-radius:8px;}}QListWidget::item:hover{{background:{theme['soft']};}}QListWidget::item:selected{{background:{theme['soft']};color:{theme['accent']};font-weight:850;}}")
    left_layout.addWidget(sources, 1)
    splitter.addWidget(left)

    right = QFrame()
    right.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #DDE3EA;border-radius:13px;}")
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(13, 12, 13, 12)
    top = QHBoxLayout()
    breadcrumb = QLabel(f"Select {theme['source'].lower()}")
    breadcrumb.setStyleSheet("color:#172B4D;font-size:13px;font-weight:900;")
    top.addWidget(breadcrumb, 1)
    search = QLineEdit()
    search.setPlaceholderText(f"Filter {theme['item'].lower()}, people, status or tags…")
    search.setClearButtonEnabled(True)
    search.setMinimumWidth(300)
    search.setStyleSheet(f"QLineEdit{{background:#FAFBFC;color:#172B4D;border:1px solid #D6DCE5;border-radius:9px;padding:8px 10px;font-size:10px;}}QLineEdit:focus{{border-color:{theme['accent']};background:#FFFFFF;}}")
    top.addWidget(search)
    right_layout.addLayout(top)

    items = QListWidget()
    items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    items.setStyleSheet(f"QListWidget{{background:#FFFFFF;border:1px solid #E2E6EC;border-radius:10px;color:#172B4D;outline:0;font-size:11px;padding:5px;}}QListWidget::item{{padding:10px;border-bottom:1px solid #EEF1F5;border-radius:7px;}}QListWidget::item:hover{{background:{theme['soft']};}}QListWidget::item:selected{{background:{theme['soft']};color:{theme['accent']};font-weight:850;}}")
    right_layout.addWidget(items, 3)

    preview_label = QLabel("LOCAL PREVIEW")
    preview_label.setStyleSheet(f"color:{theme['accent2']};font-size:9px;font-weight:950;letter-spacing:.5px;")
    right_layout.addWidget(preview_label)
    preview = QTextEdit()
    preview.setReadOnly(True)
    preview.setMaximumHeight(210)
    preview.setPlaceholderText("Select an item to preview the exact local working copy PrivacyGate will scan.")
    preview.setStyleSheet("QTextEdit{background:#FBFCFD;color:#243757;border:1px solid #E2E6EC;border-radius:10px;padding:9px;font-size:10px;}")
    right_layout.addWidget(preview, 2)

    actions = QHBoxLayout()
    count = QLabel("0 items")
    count.setStyleSheet("color:#6B778C;font-size:10px;font-weight:800;")
    actions.addWidget(count)
    actions.addStretch(1)
    close = QPushButton("Close")
    close.setStyleSheet("QPushButton{background:#FFFFFF;color:#344563;border:1px solid #C8D0DA;border-radius:9px;padding:8px 14px;font-weight:800;}QPushButton:hover{background:#F4F5F7;}")
    use = QPushButton("Use in Protect")
    use.setEnabled(False)
    use.setStyleSheet(f"QPushButton{{background:{theme['accent']};color:#FFFFFF;border:0;border-radius:9px;padding:8px 15px;font-weight:950;}}QPushButton:hover{{background:{theme['accent2']};}}QPushButton:disabled{{background:#D8DCE3;color:#9299A5;}}")
    actions.addWidget(close)
    actions.addWidget(use)
    right_layout.addLayout(actions)
    splitter.addWidget(right)
    splitter.setSizes([275, 820])
    root.addWidget(splitter, 1)

    source_rows: dict[str, dict[str, Any]] = {}
    item_rows: dict[str, dict[str, Any]] = {}
    selected_detail: dict[str, Any] | None = None
    selected_text = ""

    def source_id(row: dict[str, Any]) -> str:
        if provider == "jira":
            return str(row.get("key") or row.get("id") or "")
        return str(row.get("gid") or row.get("id") or "")

    def source_name(row: dict[str, Any]) -> str:
        return str(row.get("name") or row.get("key") or theme["source"])

    def load_sources() -> None:
        try:
            if provider == "asana":
                rows = _run_busy(dialog, "Loading Asana", "Loading Asana projects…", lambda: _retry_network(service.asana_projects))
            elif provider == "trello":
                rows = _run_busy(dialog, "Loading Trello", "Loading Trello boards…", lambda: _retry_network(service.trello_boards))
            elif provider == "notion":
                rows = _run_busy(dialog, "Loading Notion", "Loading Notion pages and databases…", lambda: _retry_network(service.notion_items))
            elif provider == "monday":
                rows = _run_busy(dialog, "Loading monday.com", "Loading monday.com boards…", lambda: _retry_network(service.monday_boards))
            else:
                rows = _run_busy(dialog, "Loading Jira", "Loading Jira projects…", lambda: _retry_network(service.jira_projects))
        except Exception as exc:
            QMessageBox.warning(dialog, f"Unable to read {theme['title']}", _friendly_connection_error(theme["title"], exc))
            return
        sources.clear(); source_rows.clear()
        if provider == "notion":
            for row in rows:
                rid = str(row.get("id") or "")
                title = _title_for(provider, row)
                q = QListWidgetItem(title)
                q.setData(Qt.ItemDataRole.UserRole, rid)
                sources.addItem(q); source_rows[rid] = row
            breadcrumb.setText("Notion workspace")
            load_notion_items(rows)
            return
        for row in rows:
            rid = source_id(row)
            if not rid:
                continue
            q = QListWidgetItem(source_name(row))
            q.setData(Qt.ItemDataRole.UserRole, rid)
            sources.addItem(q); source_rows[rid] = row
        if sources.count():
            sources.setCurrentRow(0)

    def load_notion_items(rows) -> None:
        items.clear(); item_rows.clear()
        for row in rows:
            rid = str(row.get("id") or "")
            if not rid:
                continue
            meta = _meta_for(provider, row)
            q = QListWidgetItem(f"{_title_for(provider, row)}\n{meta}" if meta else _title_for(provider, row))
            q.setData(Qt.ItemDataRole.UserRole, rid)
            items.addItem(q); item_rows[rid] = row
        count.setText(f"{len(item_rows)} {theme['item'].lower()}")

    def load_items_for_source() -> None:
        current = sources.currentItem()
        if current is None or provider == "notion":
            return
        rid = str(current.data(Qt.ItemDataRole.UserRole) or "")
        row = source_rows.get(rid)
        if not row:
            return
        breadcrumb.setText(source_name(row))
        try:
            if provider == "asana":
                rows = _run_busy(dialog, "Loading Asana", "Loading project tasks…", lambda: _retry_network(lambda: service.asana_tasks(rid)))
            elif provider == "trello":
                rows = _run_busy(dialog, "Loading Trello", "Loading board cards…", lambda: _retry_network(lambda: service.trello_cards(rid)))
            elif provider == "monday":
                rows = _run_busy(dialog, "Loading monday.com", "Loading board items…", lambda: _retry_network(lambda: service.monday_items(rid)))
            else:
                rows = _run_busy(dialog, "Loading Jira", "Loading project issues…", lambda: _retry_network(lambda: service.jira_issues(rid)))
        except Exception as exc:
            QMessageBox.warning(dialog, f"Unable to read {theme['title']}", _friendly_connection_error(theme["title"], exc))
            return
        items.clear(); item_rows.clear()
        for item in rows:
            iid = str(item.get("gid") or item.get("id") or item.get("key") or "")
            if not iid:
                continue
            title = _title_for(provider, item); meta = _meta_for(provider, item)
            q = QListWidgetItem(f"{title}\n{meta}" if meta else title)
            q.setData(Qt.ItemDataRole.UserRole, iid)
            items.addItem(q); item_rows[iid] = item
        count.setText(f"{len(item_rows)} {theme['item'].lower()}")
        apply_filter()

    def apply_filter() -> None:
        needle = search.text().strip().lower()
        for i in range(items.count()):
            q = items.item(i)
            q.setHidden(bool(needle and needle not in q.text().lower()))

    def select_item() -> None:
        nonlocal selected_detail, selected_text
        current = items.currentItem()
        if current is None:
            selected_detail = None; selected_text = ""; preview.clear(); use.setEnabled(False); return
        iid = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if not iid:
            return
        try:
            if provider == "asana":
                detail = _run_busy(dialog, "Loading Asana task", "Loading task details…", lambda: _retry_network(lambda: service.asana_detail(iid)))
            elif provider == "trello":
                detail = _run_busy(dialog, "Loading Trello card", "Loading card details…", lambda: _retry_network(lambda: service.trello_detail(iid)))
            elif provider == "notion":
                detail = _run_busy(dialog, "Loading Notion page", "Loading page content…", lambda: _retry_network(lambda: service.notion_detail(iid)))
            elif provider == "monday":
                detail = _run_busy(dialog, "Loading monday.com item", "Loading item details…", lambda: _retry_network(lambda: service.monday_detail(iid)))
            else:
                detail = _run_busy(dialog, "Loading Jira issue", "Loading issue details…", lambda: _retry_network(lambda: service.jira_detail(iid)))
            text = service.project_item_to_text(provider, detail)
        except Exception as exc:
            QMessageBox.warning(dialog, f"Unable to load {theme['title']} item", _friendly_connection_error(theme["title"], exc)); return
        selected_detail = detail; selected_text = text
        preview.setPlainText(text)
        use.setEnabled(bool(text.strip()))

    def use_in_protect() -> None:
        if not selected_detail or not selected_text:
            return
        protect = main_window.protection_page
        paste_button = getattr(protect, "_redesign_paste_mode", None)
        if paste_button is not None and not paste_button.isChecked():
            paste_button.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(selected_text)
        protect._external_source_name = f"{theme['title']} • {_title_for(provider, selected_detail)}"
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(f"Imported from {theme['title']} — ready for local scan", 9000)

    sources.currentItemChanged.connect(lambda _current, _previous: load_items_for_source())
    items.currentItemChanged.connect(lambda _current, _previous: select_item())
    search.textChanged.connect(lambda _text: apply_filter())
    close.clicked.connect(dialog.reject)
    use.clicked.connect(use_in_protect)
    load_sources()
    dialog.exec()
