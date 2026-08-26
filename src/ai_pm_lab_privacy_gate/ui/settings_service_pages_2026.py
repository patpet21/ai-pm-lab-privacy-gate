from __future__ import annotations

import os
from pathlib import Path
from types import MethodType

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.infrastructure.settings.workspace_file_locations import (
    STANDARD_WORKSPACE_FOLDERS,
    WorkspaceFileLocationStore,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
WHITE = "#FFFFFF"
BORDER = "#DDE7EC"
SOFT = "#F4F7F9"
GREEN = "#23824B"
INDIGO = "#6757D8"
AMBER = "#A96B18"
RED = "#B54747"


def _button(text: str, *, primary: bool = False, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    if icon_name:
        button.setIcon(icon(icon_name, color=WHITE if primary else NAVY, size=16))
    if primary:
        button.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:11px;"
            "padding:9px 14px;font-size:10px;font-weight:850;}"
            "QPushButton:hover{background:#096D76;}QPushButton:pressed{background:#075D65;}"
            "QPushButton:disabled{background:#DDE6EA;color:#8FA0AA;}"
        )
    else:
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#17384E;border:1px solid #D3DFE6;border-radius:11px;"
            "padding:9px 14px;font-size:10px;font-weight:800;}"
            "QPushButton:hover{background:#F1F8F8;border-color:#9ACDCF;color:#0B7F89;}"
        )
    return button


def _pill(text: str, tone: str = "teal") -> QLabel:
    palettes = {
        "teal": ("#E8F7F7", TEAL, "#C8E8E8"),
        "green": ("#EAF8F1", GREEN, "#CDE8D9"),
        "indigo": ("#F1EFFF", INDIGO, "#DDD8FF"),
        "amber": ("#FFF6E8", AMBER, "#F0D9B3"),
        "navy": ("#EEF3F7", NAVY, "#D8E2E9"),
    }
    bg, fg, border = palettes.get(tone, palettes["teal"])
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet(
        f"background:{bg};color:{fg};border:1px solid {border};border-radius:9px;"
        "padding:5px 8px;font-size:8px;font-weight:900;letter-spacing:.4px;"
    )
    return label


def _surface(title: str, subtitle: str | None = None, icon_name: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName="Settings2026Surface")
    frame.setStyleSheet(
        "QFrame#Settings2026Surface{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:18px;}"
    )
    box = QVBoxLayout(frame)
    box.setContentsMargins(18, 17, 18, 17)
    box.setSpacing(11)
    if title:
        head = QHBoxLayout()
        head.setSpacing(10)
        if icon_name:
            bubble = QLabel()
            bubble.setFixedSize(40, 40)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setPixmap(icon(icon_name, color=TEAL, size=21).pixmap(21, 21))
            bubble.setStyleSheet("background:#EAF8F8;border:none;border-radius:12px;")
            head.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        heading = QLabel(title)
        heading.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;")
        copy.addWidget(heading)
        if subtitle:
            note = QLabel(subtitle)
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
            copy.addWidget(note)
        head.addLayout(copy, 1)
        box.addLayout(head)
    return frame, box


def _find_card(settings: QWidget, heading: str) -> QFrame | None:
    for frame in settings.findChildren(QFrame):
        for label in frame.findChildren(QLabel):
            if label.text().strip() == heading:
                return frame
    return None


def _clear_layout(layout, keep: set[QWidget] | None = None) -> None:
    keep = keep or set()
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            if widget not in keep:
                widget.deleteLater()
        elif child is not None:
            _clear_layout(child, keep)


def _open_main_page(main_window, page: QWidget) -> None:
    pages = getattr(main_window, "pages", None)
    if pages is None:
        return
    index = pages.indexOf(page)
    if index < 0:
        return
    pages.setCurrentIndex(index)
    for button in getattr(main_window, "nav_buttons", []):
        button.setChecked(False)
    if 0 <= index < len(getattr(main_window, "nav_buttons", [])):
        main_window.nav_buttons[index].setChecked(True)
    else:
        for button in getattr(main_window, "nav_buttons", []):
            if button.text().strip() == "Organization" or button.toolTip().strip() == "Organization":
                if page is getattr(main_window, "team_page", None):
                    button.setChecked(True)
                    break


def _service_page(title: str, subtitle: str, icon_name: str, back) -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    page.setObjectName("Settings2026DedicatedPage")
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName("Settings2026DedicatedContent")
    body = QVBoxLayout(content)
    body.setContentsMargins(30, 24, 30, 28)
    body.setSpacing(18)
    scroll.setWidget(content)
    root.addWidget(scroll)

    top = QHBoxLayout()
    back_button = QPushButton("←  Settings")
    back_button.setCursor(Qt.CursorShape.PointingHandCursor)
    back_button.setStyleSheet(
        "QPushButton{background:transparent;color:#61798A;border:none;padding:6px 4px;"
        "font-size:10px;font-weight:800;}QPushButton:hover{color:#0B7F89;}"
    )
    back_button.clicked.connect(back)
    top.addWidget(back_button)
    top.addStretch(1)
    body.addLayout(top)

    hero = QFrame(objectName="Settings2026ServiceHero")
    hero.setStyleSheet(
        "QFrame#Settings2026ServiceHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #062B4F,stop:.68 #084E69,stop:1 #0B7F89);border:none;border-radius:20px;}"
    )
    row = QHBoxLayout(hero)
    row.setContentsMargins(20, 18, 20, 18)
    row.setSpacing(14)
    bubble = QLabel()
    bubble.setFixedSize(50, 50)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color="#A9ECE8", size=27).pixmap(27, 27))
    bubble.setStyleSheet("background:rgba(255,255,255,25);border:1px solid rgba(255,255,255,45);border-radius:15px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("PRIVACYGATE SETTINGS SERVICE")
    eyebrow.setStyleSheet("color:#9FE5E2;font-size:8px;font-weight:900;letter-spacing:1px;border:none;")
    heading = QLabel(title)
    heading.setStyleSheet("color:#FFFFFF;font-size:24px;font-weight:950;border:none;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet("color:#D9EEF1;font-size:11px;border:none;")
    copy.addWidget(eyebrow)
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    body.addWidget(hero)

    content.setStyleSheet(
        "QWidget#Settings2026DedicatedContent{background:#F4F7F9;}"
        "QWidget#Settings2026DedicatedContent QLabel{background:transparent;}"
    )
    return page, body


class _HubCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, detail: str, icon_name: str, badge: str, tone: str = "teal") -> None:
        super().__init__()
        self.setObjectName("Settings2026HubCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(104)
        self.setStyleSheet(
            "QFrame#Settings2026HubCard{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:16px;}"
            "QFrame#Settings2026HubCard:hover{background:#FBFEFE;border:2px solid #91CBCD;}"
        )
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 13, 14, 12)
        box.setSpacing(7)
        head = QHBoxLayout()
        ico = QLabel()
        ico.setFixedSize(34, 34)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setPixmap(icon(icon_name, color=TEAL if tone != "indigo" else INDIGO, size=19).pixmap(19, 19))
        ico.setStyleSheet("background:#EAF8F8;border:none;border-radius:10px;")
        ico.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        head.addWidget(ico)
        head.addStretch(1)
        badge_label = _pill(badge, tone)
        badge_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        head.addWidget(badge_label)
        box.addLayout(head)
        title_label = QLabel(title)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label.setStyleSheet(f"color:{NAVY};font-size:13px;font-weight:900;border:none;")
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        detail_label.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        box.addWidget(title_label)
        box.addWidget(detail_label)
        action = QLabel("Open service  →")
        action.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        action.setStyleSheet("color:#0B7F89;font-size:9px;font-weight:900;border:none;")
        box.addWidget(action)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class WorkspaceFilesPage(QWidget):
    """Real local routing controls for Personal and organization workspaces."""

    def __init__(self, main_window, back) -> None:
        super().__init__()
        self.main_window = main_window
        self.team_page = getattr(main_window, "team_page", None)
        self.workspace_store = getattr(self.team_page, "_privacygate_workspace_store", None)
        self.routes = WorkspaceFileLocationStore(main_window.library.data_dir)
        main_window.workspace_file_location_store = self.routes

        page, body = _service_page(
            "Files & local workspace",
            "Track exactly where Personal and each company workspace keeps working files on this computer, then change or open those locations without mixing team contexts.",
            "library",
            back,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)
        self._body = body

        boundary, boundary_box = _surface(
            "Two local storage layers",
            "The encrypted PrivacyGate Library stays in the app data directory. Workspace folders below are user-visible working locations and can be different for Personal and every company.",
            "protect",
        )
        row = QHBoxLayout()
        row.setSpacing(10)
        fixed = QFrame()
        fixed.setStyleSheet("QFrame{background:#F7FAFC;border:1px solid #E3EBEF;border-radius:12px;}")
        fixed_box = QVBoxLayout(fixed)
        fixed_box.setContentsMargins(12, 10, 12, 10)
        fixed_title = QLabel("Encrypted Library")
        fixed_title.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;border:none;")
        fixed_path = QLabel(str(main_window.library.data_dir))
        fixed_path.setWordWrap(True)
        fixed_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        fixed_path.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        fixed_box.addWidget(fixed_title)
        fixed_box.addWidget(fixed_path)
        row.addWidget(fixed, 1)
        routed = QFrame()
        routed.setStyleSheet("QFrame{background:#F1FAFA;border:1px solid #D5ECEC;border-radius:12px;}")
        routed_box = QVBoxLayout(routed)
        routed_box.setContentsMargins(12, 10, 12, 10)
        routed_title = QLabel("Workspace working files")
        routed_title.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;border:none;")
        routed_note = QLabel("Personal and company roots are tracked separately and never uploaded to the Organization control plane.")
        routed_note.setWordWrap(True)
        routed_note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        routed_box.addWidget(routed_title)
        routed_box.addWidget(routed_note)
        row.addWidget(routed, 1)
        boundary_box.addLayout(row)
        body.addWidget(boundary)

        control, control_box = _surface(
            "Workspace location",
            "Choose a workspace to see its exact local path and manage its folder structure.",
            "workflow",
        )
        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumHeight(42)
        self.workspace_combo.setStyleSheet(
            "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:11px;"
            "padding:8px 12px;font-size:10px;font-weight:800;}QComboBox:hover{border-color:#9ACDCF;}"
            "QComboBox::drop-down{border:none;width:26px;}"
        )
        selector_row.addWidget(self.workspace_combo, 1)
        self.type_badge = _pill("PERSONAL", "navy")
        selector_row.addWidget(self.type_badge)
        control_box.addLayout(selector_row)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setMinimumHeight(42)
        self.path_input.setStyleSheet(
            "QLineEdit{background:#F8FBFC;color:#17384E;border:1px solid #D5E1E7;border-radius:10px;"
            "padding:9px 11px;font-size:10px;}"
        )
        path_row.addWidget(self.path_input, 1)
        copy_path = _button("Copy path", icon_name="copy")
        copy_path.clicked.connect(lambda: QApplication.clipboard().setText(self.path_input.text()))
        path_row.addWidget(copy_path)
        control_box.addLayout(path_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = _button("Open folder", primary=True, icon_name="external")
        self.change_button = _button("Change location", icon_name="settings")
        self.structure_button = _button("Create standard folders", icon_name="library")
        self.new_folder_button = _button("New folder", icon_name="document")
        self.reset_button = _button("Reset default", icon_name="restore")
        for button in (self.open_button, self.change_button, self.structure_button, self.new_folder_button, self.reset_button):
            actions.addWidget(button)
        actions.addStretch(1)
        control_box.addLayout(actions)

        self.route_note = QLabel("")
        self.route_note.setWordWrap(True)
        self.route_note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        control_box.addWidget(self.route_note)

        folders = QHBoxLayout()
        folders.setSpacing(7)
        folders.addWidget(QLabel("Standard structure:"))
        for name in STANDARD_WORKSPACE_FOLDERS:
            folders.addWidget(_pill(name.upper(), "teal"))
        folders.addStretch(1)
        control_box.addLayout(folders)
        body.addWidget(control)

        snapshot, snap_box = _surface("Storage snapshot", "A quick local-only view of the selected workspace root.", "report")
        stat_row = QHBoxLayout()
        self.files_value = QLabel("0")
        self.size_value = QLabel("0 MB")
        self.status_value = QLabel("Not created")
        for title, value in (("Files", self.files_value), ("Size", self.size_value), ("Folder status", self.status_value)):
            card = QFrame()
            card.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E3EBEF;border-radius:12px;}")
            card_box = QVBoxLayout(card)
            card_box.setContentsMargins(12, 10, 12, 10)
            name = QLabel(title)
            name.setStyleSheet(f"color:{MUTED};font-size:8px;font-weight:850;border:none;")
            value.setStyleSheet(f"color:{NAVY};font-size:16px;font-weight:950;border:none;")
            card_box.addWidget(name)
            card_box.addWidget(value)
            stat_row.addWidget(card, 1)
        snap_box.addLayout(stat_row)
        body.addWidget(snapshot)

        tracked, tracked_box = _surface(
            "Tracked workspace locations",
            "One row per PrivacyGate context. Company administrators do not receive these paths; this routing stays on the employee device.",
            "compare",
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Workspace", "Type", "Local root", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;color:#17384E;border:1px solid #E1E9ED;border-radius:10px;"
            "gridline-color:#EDF2F4;font-size:9px;}QTableWidget::item{padding:7px;}"
            "QHeaderView::section{background:#F7FAFC;color:#415C70;border:none;border-bottom:1px solid #E1E9ED;"
            "padding:8px;font-size:9px;font-weight:850;}"
        )
        tracked_box.addWidget(self.table)
        body.addWidget(tracked)

        safe, safe_box = _surface(
            "Safe routing rules",
            "Changing a workspace location changes PrivacyGate's tracked working root only. Existing files are never moved or deleted automatically.",
            "protect",
        )
        for text in (
            "Personal and each company workspace have independent local paths.",
            "Changing a route does not expose the folder path or file names to company administrators.",
            "Create standard folders is additive only: Inbox, Protected, Restored and Exports are created if missing.",
            "The encrypted PrivacyGate Library remains separate from these working folders.",
        ):
            label = QLabel("✓  " + text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color:{INK};font-size:9px;border:none;padding:2px 0;")
            safe_box.addWidget(label)
        body.addWidget(safe)
        body.addStretch(1)

        self.workspace_combo.currentIndexChanged.connect(lambda _index: self._refresh_route())
        self.open_button.clicked.connect(self._open_root)
        self.change_button.clicked.connect(self._change_root)
        self.structure_button.clicked.connect(self._ensure_structure)
        self.new_folder_button.clicked.connect(self._new_folder)
        self.reset_button.clicked.connect(self._reset_root)
        if self.team_page is not None and getattr(self.team_page, "state_changed", None) is not None:
            self.team_page.state_changed.connect(lambda _state: self.refresh_workspaces())
        sidebar_combo = getattr(main_window, "workspace_sidebar_combo", None)
        if sidebar_combo is not None:
            sidebar_combo.currentIndexChanged.connect(lambda _index: QTimer.singleShot(0, self.refresh_workspaces))
        self.refresh_workspaces()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh_workspaces()

    def _context(self):
        return self.workspace_store.load() if self.workspace_store is not None else None

    def _descriptor(self):
        context = self._context()
        if context is None:
            return None
        key = str(self.workspace_combo.currentData() or context.active_key)
        return context.workspaces.get(key)

    def refresh_workspaces(self) -> None:
        context = self._context()
        if context is None:
            return
        wanted = str(self.workspace_combo.currentData() or context.active_key)
        self.workspace_combo.blockSignals(True)
        self.workspace_combo.clear()
        for key, descriptor in context.workspaces.items():
            kind = "Personal" if descriptor.personal else descriptor.plan.label
            self.workspace_combo.addItem(f"{descriptor.name}  ·  {kind}", key)
        index = self.workspace_combo.findData(wanted)
        if index < 0:
            index = self.workspace_combo.findData(context.active_key)
        self.workspace_combo.setCurrentIndex(max(0, index))
        self.workspace_combo.blockSignals(False)
        self._refresh_route()
        self._refresh_table()

    def _refresh_route(self) -> None:
        descriptor = self._descriptor()
        if descriptor is None:
            return
        route = self.routes.route_for(descriptor.key, descriptor.name)
        root = Path(route.root)
        self.path_input.setText(str(root))
        self.type_badge.setText("PERSONAL" if descriptor.personal else "COMPANY")
        self.type_badge.setStyleSheet(
            _pill("X", "navy" if descriptor.personal else "green").styleSheet()
        )
        files, size = self.routes.snapshot(root)
        self.files_value.setText(str(files))
        self.size_value.setText(self._format_bytes(size))
        self.status_value.setText("Ready" if root.exists() else "Not created")
        self.status_value.setStyleSheet(
            f"color:{GREEN if root.exists() else AMBER};font-size:16px;font-weight:950;border:none;"
        )
        mode = "Custom location" if route.custom else "PrivacyGate default location"
        owner = "Personal" if descriptor.personal else f"{descriptor.name} · {descriptor.role.title() if descriptor.role else 'Member'}"
        self.route_note.setText(
            f"{mode}. This route belongs to {owner}. Changing it does not move files already stored in the previous folder."
        )
        self._refresh_table()

    @staticmethod
    def _format_bytes(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.0f} {unit}" if unit in {"B", "KB"} else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TB"

    def _current_root(self) -> Path | None:
        descriptor = self._descriptor()
        if descriptor is None:
            return None
        return Path(self.routes.route_for(descriptor.key, descriptor.name).root)

    def _open_root(self) -> None:
        root = self._current_root()
        if root is None:
            return
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Folder unavailable", f"PrivacyGate could not create/open this folder:\n\n{exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))
        self._refresh_route()

    def _change_root(self) -> None:
        descriptor = self._descriptor()
        if descriptor is None:
            return
        current = self._current_root()
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Choose local folder for {descriptor.name}",
            str(current.parent if current is not None else Path.home()),
        )
        if not selected:
            return
        self.routes.set_route(descriptor.key, Path(selected), custom=True)
        QMessageBox.information(
            self,
            "Workspace location changed",
            f"{descriptor.name} will use this local working folder:\n\n{selected}\n\nExisting files were not moved.",
        )
        self._refresh_route()

    def _reset_root(self) -> None:
        descriptor = self._descriptor()
        if descriptor is None:
            return
        answer = QMessageBox.question(
            self,
            "Reset workspace location?",
            f"Return {descriptor.name} to the PrivacyGate default local folder?\n\nExisting files will not be moved or deleted.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        route = self.routes.reset_route(descriptor.key, descriptor.name)
        self.path_input.setText(route.root)
        self._refresh_route()

    def _ensure_structure(self) -> None:
        root = self._current_root()
        if root is None:
            return
        try:
            created = self.routes.ensure_structure(root)
        except OSError as exc:
            QMessageBox.warning(self, "Folder setup failed", f"PrivacyGate could not prepare the workspace folders:\n\n{exc}")
            return
        QMessageBox.information(
            self,
            "Workspace folders ready",
            "PrivacyGate prepared the standard local structure:\n\n" + "\n".join(path.name for path in created),
        )
        self._refresh_route()

    def _new_folder(self) -> None:
        root = self._current_root()
        if root is None:
            return
        name, ok = QInputDialog.getText(self, "Create local folder", "Folder name:")
        if not ok:
            return
        name = name.strip()
        if not name or any(char in name for char in "\\/:*?\"<>|") or name in {".", ".."}:
            QMessageBox.warning(self, "Invalid folder name", "Use a normal folder name without path separators or reserved characters.")
            return
        try:
            root.mkdir(parents=True, exist_ok=True)
            target = root / name
            target.mkdir(exist_ok=False)
        except FileExistsError:
            QMessageBox.information(self, "Folder already exists", f"{name} already exists in this workspace.")
            return
        except OSError as exc:
            QMessageBox.warning(self, "Folder could not be created", str(exc))
            return
        self._refresh_route()

    def _refresh_table(self) -> None:
        context = self._context()
        if context is None:
            return
        self.table.setRowCount(len(context.workspaces))
        for row, (key, descriptor) in enumerate(context.workspaces.items()):
            route = self.routes.route_for(key, descriptor.name)
            root = Path(route.root)
            values = (
                descriptor.name,
                "Personal" if descriptor.personal else f"Company · {descriptor.plan.label}",
                str(root),
                "Ready" if root.exists() else "Not created",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(Qt.GlobalColor.darkGreen if root.exists() else Qt.GlobalColor.darkYellow)
                self.table.setItem(row, column, item)


class _AccountControls(QFrame):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.main_window = main_window
        self.controller = getattr(main_window, "_privacygate_account_menu_controller", None)
        self.setObjectName("SettingsAccountControls")
        self.setStyleSheet("QFrame#SettingsAccountControls{background:#FFFFFF;border:1px solid #DDE7EC;border-radius:18px;}")
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 17, 18, 17)
        box.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Account identity")
        title.setStyleSheet(f"color:{NAVY};font-size:15px;font-weight:900;border:none;")
        header.addWidget(title)
        header.addStretch(1)
        self.plan_badge = _pill("ACCOUNT", "teal")
        header.addWidget(self.plan_badge)
        box.addLayout(header)
        self.name = QLabel("")
        self.name.setStyleSheet(f"color:{NAVY};font-size:18px;font-weight:950;border:none;")
        self.email = QLabel("")
        self.email.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
        box.addWidget(self.name)
        box.addWidget(self.email)
        actions = QHBoxLayout()
        edit = _button("Edit display name", primary=True, icon_name="contact")
        refresh = _button("Refresh profile", icon_name="restore")
        apps = _button("Connected apps", icon_name="external")
        edit.clicked.connect(self._edit)
        refresh.clicked.connect(self._refresh_profile)
        apps.clicked.connect(self._apps)
        actions.addWidget(edit)
        actions.addWidget(refresh)
        actions.addWidget(apps)
        actions.addStretch(1)
        box.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        controller = self.controller
        if controller is None:
            self.name.setText("PrivacyGate account")
            self.email.setText("Account controls are unavailable in this session.")
            return
        self.name.setText(controller._display_name())
        self.email.setText(controller.email or "Not signed in")
        self.plan_badge.setText(controller._plan_line().upper())

    def _edit(self) -> None:
        if self.controller is not None:
            self.controller._edit_display_name()
            QTimer.singleShot(800, self.refresh)

    def _refresh_profile(self) -> None:
        if self.controller is not None:
            self.controller.refresh_profile()
            QTimer.singleShot(900, self.refresh)

    def _apps(self) -> None:
        if self.controller is not None:
            self.controller._open_apps()


def apply_settings_service_pages_2026(main_window) -> None:
    """Make each Settings card a dedicated functional service page.

    The old Settings controls are reparented into the relevant service instead of
    being duplicated, so existing save signals and workspace actions remain the
    source of truth. Files gains a real local routing service scoped per workspace.
    """
    settings = getattr(main_window, "settings_page", None)
    if settings is None or bool(getattr(settings, "_privacygate_dedicated_service_pages_2026", False)):
        return
    root = settings.layout()
    if not isinstance(root, QVBoxLayout):
        return

    account_panel = getattr(settings, "_privacygate_plan_account_panel", None)
    workspace_panel = getattr(settings, "_privacygate_workspace_settings_panel", None)
    desktop = _find_card(settings, "Desktop behavior")
    privacy = _find_card(settings, "Local-first privacy boundary")
    mcp = _find_card(settings, "Local MCP service")
    updates = _find_card(settings, "Updates & release channel")

    functional = {
        widget
        for widget in (account_panel, workspace_panel, desktop, privacy, mcp, updates)
        if isinstance(widget, QWidget)
    }
    for widget in functional:
        widget.setParent(settings)

    _clear_layout(root, functional)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    stack = QStackedWidget(settings)
    stack.setObjectName("Settings2026ServiceStack")
    root.addWidget(stack)

    hub = QWidget()
    hub.setObjectName("Settings2026HubPage")
    hub_root = QVBoxLayout(hub)
    hub_root.setContentsMargins(0, 0, 0, 0)
    hub_scroll = QScrollArea()
    hub_scroll.setWidgetResizable(True)
    hub_scroll.setFrameShape(QFrame.Shape.NoFrame)
    hub_content = QWidget()
    hub_content.setObjectName("Settings2026HubContent")
    hub_body = QVBoxLayout(hub_content)
    hub_body.setContentsMargins(30, 24, 30, 28)
    hub_body.setSpacing(17)
    hub_scroll.setWidget(hub_content)
    hub_root.addWidget(hub_scroll)
    stack.addWidget(hub)

    hero = QFrame(objectName="Settings2026HubHero")
    hero.setStyleSheet(
        "QFrame#Settings2026HubHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #062B4F,stop:.68 #084E69,stop:1 #0B7F89);border:none;border-radius:20px;}"
    )
    hero_row = QHBoxLayout(hero)
    hero_row.setContentsMargins(20, 18, 20, 18)
    hero_row.setSpacing(14)
    bubble = QLabel()
    bubble.setFixedSize(50, 50)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon("settings", color="#A9ECE8", size=27).pixmap(27, 27))
    bubble.setStyleSheet("background:rgba(255,255,255,25);border:1px solid rgba(255,255,255,45);border-radius:15px;")
    hero_row.addWidget(bubble)
    copy = QVBoxLayout()
    copy.setSpacing(3)
    eyebrow = QLabel("PRIVACYGATE CONTROL CENTER")
    eyebrow.setStyleSheet("color:#9FE5E2;font-size:8px;font-weight:900;letter-spacing:1px;border:none;")
    title = QLabel("Settings")
    title.setStyleSheet("color:#FFFFFF;font-size:26px;font-weight:950;border:none;")
    note = QLabel("Choose a service. Each module now opens its own focused page with real controls instead of scrolling through one oversized settings screen.")
    note.setWordWrap(True)
    note.setStyleSheet("color:#D9EEF1;font-size:11px;border:none;")
    copy.addWidget(eyebrow)
    copy.addWidget(title)
    copy.addWidget(note)
    hero_row.addLayout(copy, 1)
    status = QVBoxLayout()
    status.addWidget(_pill("LOCAL DEVICE", "navy"))
    status.addWidget(_pill("2026 CONTROL HUB", "teal"))
    hero_row.addLayout(status)
    hub_body.addWidget(hero)

    intro = QLabel("SERVICES")
    intro.setStyleSheet("color:#0B7F89;font-size:9px;font-weight:900;letter-spacing:1px;border:none;")
    hub_body.addWidget(intro)

    def back_to_hub() -> None:
        stack.setCurrentWidget(hub)

    account_page, account_body = _service_page(
        "Account",
        "Identity, display name, plan and entitlement controls for this PrivacyGate account.",
        "contact",
        back_to_hub,
    )
    account_controls = _AccountControls(main_window)
    account_body.addWidget(account_controls)
    if isinstance(account_panel, QWidget):
        account_body.addWidget(account_panel)
    account_body.addStretch(1)
    stack.addWidget(account_page)

    workspace_page, workspace_body = _service_page(
        "Workspaces",
        "Switch context, join or create companies, then follow the workspace workflow from policy to approved apps and Protect.",
        "workflow",
        back_to_hub,
    )
    if isinstance(workspace_panel, QWidget):
        workspace_body.addWidget(workspace_panel)
    workflow, workflow_box = _surface(
        "Workspace workflow",
        "The active workspace is the operating context for company policy and approved app access. Documents still stay in the normal Protect page.",
        "workflow",
    )
    steps = QGridLayout()
    for index, (heading, detail) in enumerate((
        ("1  Select context", "Choose Personal or a company workspace."),
        ("2  Team access", "Join with an invitation code or create a Business workspace."),
        ("3  Policy sync", "The company's current policy is cached and enforced locally."),
        ("4  Apps & AI", "Use only accounts and destinations approved for that workspace."),
        ("5  Protect", "Work on documents in the single Protect workflow."),
    )):
        card = QFrame()
        card.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E2EBEF;border-radius:11px;}")
        box = QVBoxLayout(card)
        box.setContentsMargins(11, 9, 11, 9)
        name = QLabel(heading)
        name.setStyleSheet(f"color:{NAVY};font-size:10px;font-weight:900;border:none;")
        desc = QLabel(detail)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        box.addWidget(name)
        box.addWidget(desc)
        steps.addWidget(card, index // 3, index % 3)
    workflow_box.addLayout(steps)
    links = QHBoxLayout()
    organization = _button("Organization control center", primary=True, icon_name="workflow")
    protect = _button("Go to Protect", icon_name="protect")
    apps = _button("Apps & AI", icon_name="external")
    if getattr(main_window, "team_page", None) is not None:
        organization.clicked.connect(lambda: _open_main_page(main_window, main_window.team_page))
    protect.clicked.connect(lambda: main_window._show_page(0))
    apps.clicked.connect(lambda: main_window._show_page(getattr(main_window, "apps_page_index", 4)))
    links.addWidget(organization)
    links.addWidget(protect)
    links.addWidget(apps)
    links.addStretch(1)
    workflow_box.addLayout(links)
    workspace_body.addWidget(workflow)
    workspace_body.addStretch(1)
    stack.addWidget(workspace_page)

    device_page, device_body = _service_page(
        "Device",
        "Control what this desktop app does on close and review the privacy boundary that remains local to this computer.",
        "settings",
        back_to_hub,
    )
    if isinstance(desktop, QWidget):
        device_body.addWidget(desktop)
    if isinstance(privacy, QWidget):
        device_body.addWidget(privacy)
    local_data, local_data_box = _surface(
        "This device's PrivacyGate data",
        "Open the local application data location used by the encrypted Library and PrivacyGate configuration.",
        "library",
    )
    data_path = QLabel(str(main_window.library.data_dir))
    data_path.setWordWrap(True)
    data_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    data_path.setStyleSheet(f"color:{INK};font-size:10px;font-weight:700;border:none;")
    local_data_box.addWidget(data_path)
    open_data = _button("Open local data folder", icon_name="external")
    open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(main_window.library.data_dir))))
    local_data_box.addWidget(open_data, 0, Qt.AlignmentFlag.AlignLeft)
    device_body.addWidget(local_data)
    save_device = _button("Save device settings", primary=True, icon_name="save")
    save_device.clicked.connect(settings._save)
    device_body.addWidget(save_device, 0, Qt.AlignmentFlag.AlignRight)
    device_body.addStretch(1)
    stack.addWidget(device_page)

    services_page, services_body = _service_page(
        "Services",
        "Configure the local MCP endpoint and jump to the existing automation and cloud connection services.",
        "cloud",
        back_to_hub,
    )
    if isinstance(mcp, QWidget):
        services_body.addWidget(mcp)
    runtime, runtime_box = _surface(
        "PrivacyGate runtime services",
        "Use the dedicated application pages for local automation, MCP/cloud connections and connector workflows.",
        "workflow",
    )
    links = QHBoxLayout()
    local_auto = _button("Local Automation / n8n", primary=True, icon_name="workflow")
    cloud_mcp = _button("Cloud / MCP / Email", icon_name="cloud")
    local_auto.clicked.connect(lambda: _open_main_page(main_window, main_window.local_automation_page))
    cloud_mcp.clicked.connect(lambda: _open_main_page(main_window, main_window.cloud_automation_page))
    links.addWidget(local_auto)
    links.addWidget(cloud_mcp)
    links.addStretch(1)
    runtime_box.addLayout(links)
    services_body.addWidget(runtime)
    save_services = _button("Save service settings", primary=True, icon_name="save")
    save_services.clicked.connect(settings._save)
    services_body.addWidget(save_services, 0, Qt.AlignmentFlag.AlignRight)
    services_body.addStretch(1)
    stack.addWidget(services_page)

    files_page = WorkspaceFilesPage(main_window, back_to_hub)
    stack.addWidget(files_page)

    updates_page, updates_body = _service_page(
        "Updates",
        "Check the installed PrivacyGate version and use the existing release workflow without mixing update controls with privacy or workspace settings.",
        "download",
        back_to_hub,
    )
    if isinstance(updates, QWidget):
        updates_body.addWidget(updates)
    release, release_box = _surface(
        "Release status",
        f"Installed version: {__version__}",
        "download",
    )
    buttons = QHBoxLayout()
    check = _button("Check for updates now", primary=True, icon_name="download")
    release_center = _button("Open release & support", icon_name="external")
    check.clicked.connect(lambda: main_window.contact_page.check_updates(silent=False))
    release_center.clicked.connect(lambda: _open_main_page(main_window, main_window.contact_page))
    buttons.addWidget(check)
    buttons.addWidget(release_center)
    buttons.addStretch(1)
    release_box.addLayout(buttons)
    updates_body.addWidget(release)
    updates_body.addStretch(1)
    stack.addWidget(updates_page)

    pages = {
        "account": account_page,
        "workspaces": workspace_page,
        "device": device_page,
        "services": services_page,
        "files": files_page,
        "updates": updates_page,
    }

    grid = QGridLayout()
    grid.setHorizontalSpacing(11)
    grid.setVerticalSpacing(11)
    specs = (
        ("Account", "Profile, plan and entitlement.", "contact", "LIVE", "teal", "account"),
        ("Workspaces", "Personal and company contexts.", "workflow", "LIVE", "green", "workspaces"),
        ("Device", "Desktop and privacy behavior.", "settings", "LOCAL", "navy", "device"),
        ("Services", "MCP, automation and connections.", "cloud", "LOCAL", "teal", "services"),
        ("Files", "Per-workspace local file routing.", "library", "NEW", "indigo", "files"),
        ("Updates", "Release and maintenance controls.", "download", "READY", "green", "updates"),
    )
    for index, (title_text, detail, icon_name, badge, tone, key) in enumerate(specs):
        card = _HubCard(title_text, detail, icon_name, badge, tone)
        card.clicked.connect(lambda key=key: stack.setCurrentWidget(pages[key]))
        grid.addWidget(card, index // 3, index % 3)
    for column in range(3):
        grid.setColumnStretch(column, 1)
    hub_body.addLayout(grid)

    footer, footer_box = _surface(
        "Settings architecture",
        "Settings is now the launcher. Each service owns its own page so new controls can grow without turning the main screen into one long form.",
        "settings",
    )
    footer_box.addWidget(_pill("PERSONAL + MULTI-WORKSPACE READY", "teal"), 0, Qt.AlignmentFlag.AlignLeft)
    hub_body.addWidget(footer)
    hub_body.addStretch(1)
    hub_content.setStyleSheet("QWidget#Settings2026HubContent{background:#F4F7F9;}QWidget#Settings2026HubContent QLabel{background:transparent;}")

    def open_service(key: str) -> None:
        try:
            settings_index = main_window.pages.indexOf(settings)
            if settings_index >= 0:
                main_window._show_page(settings_index)
        except (IndexError, RuntimeError):
            main_window.pages.setCurrentWidget(settings)
        page = pages.get(key)
        if page is not None:
            stack.setCurrentWidget(page)
        if key == "workspaces" and workspace_panel is not None:
            QTimer.singleShot(80, workspace_panel.refresh)
        if key == "files":
            QTimer.singleShot(80, files_page.refresh_workspaces)

    settings.open_settings_service = open_service
    settings.settings_service_pages = pages
    settings.settings_service_stack = stack
    settings.settings_service_hub = hub

    # Sidebar Settings always returns to the service launcher.
    for button in getattr(main_window, "nav_buttons", []):
        if button.text().strip() == "Settings" or button.toolTip().strip() == "Settings":
            button.clicked.connect(lambda _checked=False: stack.setCurrentWidget(hub))
            break

    # + Workspace should now land on the dedicated Workspace service page rather
    # than focusing a control hidden somewhere inside the old long Settings page.
    add_workspace = getattr(main_window, "workspace_add_button", None)
    if isinstance(add_workspace, QPushButton):
        try:
            add_workspace.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass

        def open_add_workspace() -> None:
            open_service("workspaces")
            if workspace_panel is not None:
                QTimer.singleShot(120, workspace_panel.focus_add_workspace)

        add_workspace.clicked.connect(open_add_workspace)

    # Expose a stable helper for other UI surfaces we add later.
    main_window.open_settings_service = open_service
    settings._privacygate_dedicated_service_pages_2026 = True
    stack.setCurrentWidget(hub)
