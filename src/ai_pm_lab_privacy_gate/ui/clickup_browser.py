from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import _friendly_connection_error, _retry_network, _run_busy


NAVY = "#062B4F"
PETROL = "#0B7180"
MUTED = "#5D7184"
PURPLE = "#7B68EE"
PINK = "#F65DB1"
BG = "#F7F8FC"
BORDER = "#DCE3EC"


_KIND_LABEL = {
    "workspace": "WORKSPACE",
    "space": "SPACE",
    "folder": "FOLDER",
    "list": "LIST",
}


def _date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000).astimezone().strftime("%b %d, %Y")
    except (TypeError, ValueError, OSError):
        return str(value)


def _assignees(task: dict[str, Any]) -> str:
    names = []
    for person in task.get("assignees", []) or []:
        name = str(person.get("username") or person.get("email") or "").strip()
        if name:
            names.append(name)
    return ", ".join(names)


def _tags(task: dict[str, Any]) -> str:
    return "  ".join(f"#{str(tag.get('name') or '').strip()}" for tag in task.get("tags", []) or [] if str(tag.get("name") or "").strip())


def _priority(task: dict[str, Any]) -> str:
    value = task.get("priority") or {}
    return str(value.get("priority") or "").upper()


def _status(task: dict[str, Any]) -> str:
    value = task.get("status") or {}
    return str(value.get("status") or "").upper()


def _status_color(task: dict[str, Any]) -> str:
    value = task.get("status") or {}
    raw = str(value.get("color") or "").strip()
    return raw if raw.startswith("#") else PURPLE


def _make_pill(text: str, background: str, foreground: str = "#FFFFFF") -> QLabel:
    label = QLabel(text or "—")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{background};color:{foreground};border-radius:8px;padding:4px 8px;"
        "font-size:9px;font-weight:900;"
    )
    return label


def _tree_item(parent, title: str, kind: str, item_id: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem(parent, [title])
    item.setData(0, Qt.ItemDataRole.UserRole, {"kind": kind, "id": item_id, "title": title})
    item.setToolTip(0, f"{_KIND_LABEL.get(kind, kind.upper())} · {title}")
    return item


def open_clickup_browser(main_window) -> None:
    page = main_window.cloud_automation_page
    service = getattr(page, "_connected_apps_service", None)
    if service is None or not hasattr(service, "clickup_hierarchy"):
        QMessageBox.warning(main_window, "ClickUp", "The ClickUp connector is not available in this build.")
        return

    dialog = QDialog(main_window)
    dialog.setWindowTitle("ClickUp — connected workspace")
    dialog.resize(1180, 760)
    dialog.setMinimumSize(930, 620)
    dialog.setStyleSheet(f"QDialog{{background:{BG};}}")

    root = QVBoxLayout(dialog)
    root.setContentsMargins(18, 16, 18, 16)
    root.setSpacing(12)

    hero = QFrame()
    hero.setObjectName("ClickUpHero")
    hero.setStyleSheet(
        "QFrame#ClickUpHero{background:#FFFFFF;border:1px solid #DCE3EC;border-radius:16px;}"
    )
    hero_layout = QHBoxLayout(hero)
    hero_layout.setContentsMargins(18, 15, 18, 15)
    logo = QLabel("CU")
    logo.setFixedSize(44, 44)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setStyleSheet(
        f"background:{PURPLE};color:#FFFFFF;border-radius:12px;font-size:15px;font-weight:950;"
        f"border-bottom:4px solid {PINK};"
    )
    hero_layout.addWidget(logo)
    titles = QVBoxLayout()
    title = QLabel("ClickUp workspace")
    title.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:950;")
    subtitle = QLabel("Browse workspaces, spaces, folders, lists and tasks. Data stays local until you explicitly move a selected task into Protect.")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;")
    titles.addWidget(title)
    titles.addWidget(subtitle)
    hero_layout.addLayout(titles, 1)
    read_only = QLabel("READ ONLY")
    read_only.setStyleSheet(
        "background:#F0ECFF;color:#6C55D9;border:1px solid #D7CEFF;border-radius:10px;"
        "padding:6px 10px;font-size:9px;font-weight:950;"
    )
    hero_layout.addWidget(read_only)
    root.addWidget(hero)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)

    sidebar = QFrame()
    sidebar.setObjectName("ClickUpSidebar")
    sidebar.setStyleSheet("QFrame#ClickUpSidebar{background:#FFFFFF;border:1px solid #DCE3EC;border-radius:14px;}")
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(12, 12, 12, 12)
    sidebar_title = QLabel("HIERARCHY")
    sidebar_title.setStyleSheet(f"color:{PURPLE};font-size:9px;font-weight:950;letter-spacing:.6px;")
    sidebar_layout.addWidget(sidebar_title)
    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.setIndentation(17)
    tree.setAnimated(True)
    tree.setStyleSheet(
        "QTreeWidget{background:#FFFFFF;border:0;color:#243A4A;font-size:11px;outline:0;}"
        "QTreeWidget::item{padding:7px 5px;border-radius:7px;}"
        "QTreeWidget::item:hover{background:#F4F1FF;color:#40358D;}"
        "QTreeWidget::item:selected{background:#E9E4FF;color:#40358D;font-weight:800;}"
    )
    sidebar_layout.addWidget(tree, 1)
    splitter.addWidget(sidebar)

    content = QFrame()
    content.setObjectName("ClickUpContent")
    content.setStyleSheet("QFrame#ClickUpContent{background:#FFFFFF;border:1px solid #DCE3EC;border-radius:14px;}")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(14, 13, 14, 13)
    content_layout.setSpacing(9)

    controls = QHBoxLayout()
    breadcrumb = QLabel("Select a workspace or list")
    breadcrumb.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;")
    controls.addWidget(breadcrumb, 1)
    search = QLineEdit()
    search.setPlaceholderText("Filter tasks, assignees, status or tags…")
    search.setClearButtonEnabled(True)
    search.setMinimumWidth(290)
    search.setStyleSheet(
        "QLineEdit{background:#FAFBFD;color:#223A4C;border:1px solid #D6DEE8;border-radius:9px;padding:8px 10px;font-size:10px;}"
        "QLineEdit:focus{border-color:#7B68EE;background:#FFFFFF;}"
    )
    controls.addWidget(search)
    content_layout.addLayout(controls)

    task_table = QTableWidget(0, 6)
    task_table.setHorizontalHeaderLabels(["TASK", "STATUS", "ASSIGNEES", "TAGS", "PRIORITY", "DUE"])
    task_table.verticalHeader().setVisible(False)
    task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    task_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    task_table.setShowGrid(False)
    task_table.setAlternatingRowColors(False)
    task_table.setStyleSheet(
        "QTableWidget{background:#FFFFFF;border:1px solid #E2E7EE;border-radius:10px;gridline-color:transparent;color:#21384A;font-size:10px;outline:0;}"
        "QTableWidget::item{padding:8px;border-bottom:1px solid #EEF1F5;}"
        "QTableWidget::item:selected{background:#F1EEFF;color:#2E2760;}"
        "QHeaderView::section{background:#F8F9FC;color:#66798B;border:0;border-bottom:1px solid #E2E7EE;padding:8px;font-size:8px;font-weight:950;}"
    )
    header = task_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for column in range(1, 6):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    task_table.setColumnWidth(0, 320)
    content_layout.addWidget(task_table, 3)

    detail_label = QLabel("TASK PREVIEW")
    detail_label.setStyleSheet(f"color:{PINK};font-size:9px;font-weight:950;letter-spacing:.55px;")
    content_layout.addWidget(detail_label)
    preview = QTextEdit()
    preview.setReadOnly(True)
    preview.setPlaceholderText("Select a task to preview the exact local working copy that will enter PrivacyGate Protect.")
    preview.setMaximumHeight(220)
    preview.setStyleSheet(
        "QTextEdit{background:#FBFCFE;color:#223A4C;border:1px solid #E2E7EE;border-radius:10px;padding:10px;font-size:10px;}"
    )
    content_layout.addWidget(preview, 2)

    actions = QHBoxLayout()
    count = QLabel("0 tasks")
    count.setStyleSheet(f"color:{MUTED};font-size:10px;font-weight:800;")
    actions.addWidget(count)
    actions.addStretch(1)
    close = QPushButton("Close")
    close.setStyleSheet(
        "QPushButton{background:#FFFFFF;color:#294357;border:1px solid #CDD7E0;border-radius:9px;padding:8px 14px;font-weight:800;}"
        "QPushButton:hover{background:#F6F8FA;}"
    )
    use = QPushButton("Use task in Protect")
    use.setEnabled(False)
    use.setStyleSheet(
        f"QPushButton{{background:{PURPLE};color:#FFFFFF;border:0;border-radius:9px;padding:8px 15px;font-weight:950;}}"
        f"QPushButton:hover{{background:#6954E8;border-bottom:3px solid {PINK};}}"
        "QPushButton:disabled{background:#D8D5E6;color:#9690AA;}"
    )
    actions.addWidget(close)
    actions.addWidget(use)
    content_layout.addLayout(actions)
    splitter.addWidget(content)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([285, 850])
    root.addWidget(splitter, 1)

    tasks_by_id: dict[str, dict[str, Any]] = {}
    selected_task: dict[str, Any] | None = None
    selected_text = ""

    def build_tree() -> None:
        try:
            hierarchy = _run_busy(
                dialog,
                "Loading ClickUp",
                "Reading your ClickUp hierarchy…",
                lambda: _retry_network(lambda: service.clickup_hierarchy()),
            )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to read ClickUp", _friendly_connection_error("ClickUp", exc))
            return
        tree.clear()
        for workspace in hierarchy:
            workspace_item = _tree_item(tree, workspace["name"], "workspace", workspace["id"])
            for space in workspace.get("spaces", []):
                space_item = _tree_item(workspace_item, space["name"], "space", space["id"])
                for folder in space.get("folders", []):
                    folder_item = _tree_item(space_item, folder["name"], "folder", folder["id"])
                    for list_item in folder.get("lists", []):
                        _tree_item(folder_item, list_item["name"], "list", list_item["id"])
                for list_item in space.get("lists", []):
                    _tree_item(space_item, list_item["name"], "list", list_item["id"])
            workspace_item.setExpanded(True)
        if tree.topLevelItemCount():
            tree.setCurrentItem(tree.topLevelItem(0))

    def fill_table(tasks) -> None:
        nonlocal selected_task, selected_text
        selected_task = None
        selected_text = ""
        preview.clear()
        use.setEnabled(False)
        tasks_by_id.clear()
        task_table.setRowCount(0)
        for task in tasks:
            task_id = str(task.get("id") or "")
            if not task_id:
                continue
            row = task_table.rowCount()
            task_table.insertRow(row)
            task_table.setRowHeight(row, 48)
            name_item = QTableWidgetItem(str(task.get("name") or "Untitled task"))
            name_item.setData(Qt.ItemDataRole.UserRole, task_id)
            name_item.setToolTip(str(task.get("name") or ""))
            task_table.setItem(row, 0, name_item)
            task_table.setCellWidget(row, 1, _make_pill(_status(task) or "NO STATUS", _status_color(task)))
            task_table.setItem(row, 2, QTableWidgetItem(_assignees(task) or "—"))
            tags_text = _tags(task)
            tags_item = QTableWidgetItem(tags_text or "—")
            if tags_text:
                tags_item.setForeground(Qt.GlobalColor.darkMagenta)
                tags_item.setToolTip(tags_text)
            task_table.setItem(row, 3, tags_item)
            priority_text = _priority(task)
            if priority_text:
                task_table.setCellWidget(row, 4, _make_pill(priority_text, "#FFF0E5", "#B45120"))
            else:
                task_table.setItem(row, 4, QTableWidgetItem("—"))
            task_table.setItem(row, 5, QTableWidgetItem(_date_text(task.get("due_date")) or "—"))
            tasks_by_id[task_id] = task
        count.setText(f"{len(tasks_by_id)} tasks")
        apply_filter(search.text())

    def load_node(item: QTreeWidgetItem) -> None:
        info = item.data(0, Qt.ItemDataRole.UserRole) or {}
        kind = info.get("kind")
        item_id = str(info.get("id") or "")
        breadcrumb.setText(f"{_KIND_LABEL.get(kind, str(kind).upper())}  /  {info.get('title') or ''}")
        if kind not in {"workspace", "list"}:
            fill_table(())
            count.setText("Choose a workspace or list to load tasks")
            return
        try:
            if kind == "workspace":
                tasks = _run_busy(
                    dialog,
                    "Loading ClickUp tasks",
                    "Loading the latest tasks from this workspace…",
                    lambda: _retry_network(lambda: service.clickup_workspace_tasks(item_id, 100)),
                )
            else:
                tasks = _run_busy(
                    dialog,
                    "Loading ClickUp tasks",
                    "Loading tasks from this list…",
                    lambda: _retry_network(lambda: service.clickup_list_tasks(item_id, 100)),
                )
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to load ClickUp tasks", _friendly_connection_error("ClickUp", exc))
            return
        fill_table(tasks)

    def apply_filter(text: str) -> None:
        needle = text.strip().lower()
        visible = 0
        for row in range(task_table.rowCount()):
            task_id = str(task_table.item(row, 0).data(Qt.ItemDataRole.UserRole) or "")
            task = tasks_by_id.get(task_id, {})
            haystack = " ".join(
                [
                    str(task.get("name") or ""),
                    _status(task),
                    _assignees(task),
                    _tags(task),
                    _priority(task),
                ]
            ).lower()
            hidden = bool(needle and needle not in haystack)
            task_table.setRowHidden(row, hidden)
            if not hidden:
                visible += 1
        if needle:
            count.setText(f"{visible} matching / {len(tasks_by_id)} tasks")
        else:
            count.setText(f"{len(tasks_by_id)} tasks")

    def preview_row(row: int, _column: int = 0) -> None:
        nonlocal selected_task, selected_text
        if row < 0:
            return
        item = task_table.item(row, 0)
        if item is None:
            return
        task_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not task_id:
            return
        try:
            detail = _run_busy(
                dialog,
                "Loading task detail",
                "Preparing the selected task locally…",
                lambda: _retry_network(lambda: service.clickup_task_detail(task_id)),
            )
            text = service.clickup_task_to_text(detail)
        except Exception as exc:
            QMessageBox.warning(dialog, "Unable to read ClickUp task", _friendly_connection_error("ClickUp", exc))
            return
        selected_task = detail
        selected_text = text
        preview.setPlainText(text)
        use.setEnabled(bool(text.strip()))

    def use_in_protect() -> None:
        if not selected_task or not selected_text.strip():
            return
        protect = main_window.protection_page
        paste_button = getattr(protect, "_redesign_paste_mode", None)
        if paste_button is not None and not paste_button.isChecked():
            paste_button.click()
        protect.input_tabs.setCurrentIndex(0)
        protect.text_input.setPlainText(selected_text)
        task_name = str(selected_task.get("name") or "ClickUp task")
        protect._external_source_name = f"ClickUp • {task_name}"
        main_window._show_page(0)
        dialog.accept()
        main_window.statusBar().showMessage(f"Imported from ClickUp: {task_name} — ready for local scan", 9000)

    tree.currentItemChanged.connect(lambda current, _previous: load_node(current) if current else None)
    search.textChanged.connect(apply_filter)
    task_table.cellClicked.connect(preview_row)
    task_table.cellDoubleClicked.connect(lambda row, col: (preview_row(row, col), use.click()))
    use.clicked.connect(use_in_protect)
    close.clicked.connect(dialog.reject)

    build_tree()
    dialog.exec()
