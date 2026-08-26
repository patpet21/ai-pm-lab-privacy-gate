from __future__ import annotations

import json
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai_pm_lab_privacy_gate.application.feature_suite import (
    AdvancedFileService,
    AdvancedProfileCatalog,
    AutomationActionService,
    BatchItemResult,
    BatchProtectionService,
    FullEncryptedBackupService,
    LocalActivityStore,
    LocalOcrService,
    PrivacyPreflightService,
    WatchFolderConfig,
    WatchFolderStore,
    WatchedFolderService,
    WorkspaceRule,
    WorkspaceRuleStore,
    active_plan_for,
)
from ai_pm_lab_privacy_gate.domain.plans import Capability, PlanCode, minimum_plan_for, supports
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.settings.workspace_file_locations import WorkspaceFileLocationStore
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.settings_service_pages_2026 import (
    _HubCard,
    _button,
    _service_page,
    _surface,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
INDIGO = "#6757D8"
AMBER = "#A96B18"
RED = "#B54747"


class _ProgressBridge(QObject):
    progress = Signal(int, int, object)


def _field() -> QLineEdit:
    value = QLineEdit()
    value.setMinimumHeight(40)
    value.setStyleSheet(
        "QLineEdit{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
        "padding:8px 10px;font-size:10px;}QLineEdit:focus{border:1px solid #0B7F89;}"
    )
    return value


def _combo() -> QComboBox:
    value = QComboBox()
    value.setMinimumHeight(40)
    value.setStyleSheet(
        "QComboBox{background:#FFFFFF;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
        "padding:8px 10px;font-size:10px;font-weight:750;}QComboBox:hover{border-color:#91C8CC;}"
        "QComboBox::drop-down{border:none;width:26px;}"
    )
    return value


def _dialog_shell(dialog: QDialog, title: str, subtitle: str, icon_name: str) -> QVBoxLayout:
    dialog.setWindowTitle(title)
    dialog.resize(900, 680)
    dialog.setMinimumSize(720, 520)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(14)

    hero = QFrame(objectName="AdvancedFeatureHero")
    hero.setStyleSheet(
        "QFrame#AdvancedFeatureHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        "stop:0 #062B4F,stop:.68 #084E69,stop:1 #0B7F89);border:none;border-radius:18px;}"
    )
    row = QHBoxLayout(hero)
    row.setContentsMargins(18, 16, 18, 16)
    row.setSpacing(13)
    bubble = QLabel()
    bubble.setFixedSize(46, 46)
    bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bubble.setPixmap(icon(icon_name, color="#A9ECE8", size=25).pixmap(25, 25))
    bubble.setStyleSheet("background:rgba(255,255,255,25);border:1px solid rgba(255,255,255,45);border-radius:14px;")
    row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
    copy = QVBoxLayout()
    copy.setSpacing(2)
    heading = QLabel(title)
    heading.setStyleSheet("color:#FFFFFF;font-size:21px;font-weight:950;border:none;background:transparent;")
    note = QLabel(subtitle)
    note.setWordWrap(True)
    note.setStyleSheet("color:#D9EEF1;font-size:10px;border:none;background:transparent;")
    copy.addWidget(heading)
    copy.addWidget(note)
    row.addLayout(copy, 1)
    root.addWidget(hero)
    dialog.setStyleSheet("QDialog{background:#F4F7F9;}QLabel{background:transparent;}")
    return root


def _workspace_context(main_window):
    team_page = getattr(main_window, "team_page", None)
    store = getattr(team_page, "_privacygate_workspace_store", None)
    if store is None:
        return None
    try:
        return store.load()
    except Exception:
        return None


def _fill_workspaces(combo: QComboBox, main_window, selected: str | None = None) -> None:
    context = _workspace_context(main_window)
    combo.clear()
    if context is None:
        combo.addItem("Personal", "personal")
        return
    wanted = selected or context.active_key
    for key, descriptor in context.workspaces.items():
        suffix = "Personal" if descriptor.personal else descriptor.plan.label
        combo.addItem(f"{descriptor.name}  ·  {suffix}", key)
    index = combo.findData(wanted)
    combo.setCurrentIndex(max(0, index))


def _required_badge(capability: Capability) -> str:
    return minimum_plan_for(capability).label.upper()


class BatchProtectDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        self.paths: list[Path] = []
        self.bridge = _ProgressBridge(self)
        self.bridge.progress.connect(self._progress)
        self._worker: FunctionWorker | None = None
        root = _dialog_shell(
            self,
            "Batch Protect",
            "Protect a queue of PDF, Word and Excel files locally, with per-file progress, protected output and a final report.",
            "protect",
        )

        setup, box = _surface("Batch setup", "Choose files or a folder, then select profile, workspace and output location.", "workflow")
        first = QHBoxLayout()
        add_files = _button("Add files", primary=True, icon_name="document")
        add_folder = _button("Add folder", icon_name="library")
        clear = _button("Clear queue", icon_name="restore")
        first.addWidget(add_files)
        first.addWidget(add_folder)
        first.addWidget(clear)
        first.addStretch(1)
        box.addLayout(first)
        self.queue = QListWidget()
        self.queue.setMinimumHeight(120)
        self.queue.setStyleSheet("QListWidget{background:#FBFCFD;color:#17384E;border:1px solid #DDE7EC;border-radius:10px;padding:6px;}")
        box.addWidget(self.queue)

        options = QGridLayout()
        self.profile = _combo()
        for profile in AdvancedProfileCatalog.all():
            self.profile.addItem(profile.name, profile.key)
        self.workspace = _combo()
        _fill_workspaces(self.workspace, controller.main_window)
        self.mode = _combo()
        for label, key in (
            ("Reversible placeholders", "reversible"),
            ("Generic placeholders", "generic"),
            ("Mask values", "mask"),
            ("Permanent redaction", "redact"),
        ):
            self.mode.addItem(label, key)
        self.output = _field()
        self.output.setPlaceholderText("Protected output folder")
        browse_output = _button("Browse output", icon_name="library")
        for column, (label, widget) in enumerate((("Privacy profile", self.profile), ("Workspace", self.workspace), ("Protection mode", self.mode))):
            caption = QLabel(label)
            caption.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:850;border:none;")
            options.addWidget(caption, 0, column)
            options.addWidget(widget, 1, column)
        options.addWidget(QLabel("Output folder"), 2, 0)
        options.addWidget(self.output, 3, 0, 1, 2)
        options.addWidget(browse_output, 3, 2)
        box.addLayout(options)
        root.addWidget(setup)

        progress_surface, progress_box = _surface("Queue progress", "The queue continues even if one document fails.", "compare")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setMinimumHeight(18)
        self.status = QLabel("Ready")
        self.status.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(["Document", "Status", "Findings", "Protected output"])
        self.results.verticalHeader().setVisible(False)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        progress_box.addWidget(self.progress)
        progress_box.addWidget(self.status)
        progress_box.addWidget(self.results, 1)
        root.addWidget(progress_surface, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close = _button("Close")
        self.start = _button("Start Batch Protect", primary=True, icon_name="protect")
        actions.addWidget(close)
        actions.addWidget(self.start)
        root.addLayout(actions)

        add_files.clicked.connect(self._add_files)
        add_folder.clicked.connect(self._add_folder)
        clear.clicked.connect(self._clear)
        browse_output.clicked.connect(self._browse_output)
        close.clicked.connect(self.close)
        self.start.clicked.connect(self._start)

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add documents", "", "Supported documents (*.pdf *.docx *.xlsx)")
        self._append(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add documents from folder")
        if not folder:
            return
        paths = [str(path) for path in Path(folder).iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".xlsx"}]
        self._append(paths)
        if not self.output.text().strip():
            self.output.setText(str(Path(folder) / "Protected"))

    def _append(self, paths: list[str]) -> None:
        known = {str(path.resolve()) for path in self.paths}
        for raw in paths:
            path = Path(raw)
            key = str(path.resolve())
            if key in known:
                continue
            self.paths.append(path)
            known.add(key)
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            self.queue.addItem(item)
        self.status.setText(f"{len(self.paths)} document(s) queued")

    def _clear(self) -> None:
        self.paths.clear()
        self.queue.clear()
        self.results.setRowCount(0)
        self.progress.setValue(0)
        self.status.setText("Ready")

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose protected output folder")
        if path:
            self.output.setText(path)

    def _start(self) -> None:
        if self._worker is not None:
            return
        if not self.paths:
            QMessageBox.information(self, "Batch Protect", "Add at least one PDF, Word or Excel document.")
            return
        if not self.output.text().strip():
            QMessageBox.information(self, "Batch Protect", "Choose a protected output folder.")
            return
        workspace = str(self.workspace.currentData() or "personal")
        plan = self.controller.plan_for_workspace(workspace)
        profile = AdvancedProfileCatalog.get(str(self.profile.currentData()))
        mode = str(self.mode.currentData())
        self.results.setRowCount(0)
        self.progress.setRange(0, len(self.paths))
        self.progress.setValue(0)
        self.start.setEnabled(False)
        self.status.setText("Protecting locally…")

        def task():
            return self.controller.batch.run(
                plan,
                self.paths,
                self.output.text().strip(),
                profile=profile,
                replacement_mode=mode,
                workspace_key=workspace,
                progress=lambda current, total, item: self.bridge.progress.emit(current, total, item),
            )

        worker = FunctionWorker(task)
        self._worker = worker
        worker.signals.result.connect(self._done)
        worker.signals.error.connect(lambda message: QMessageBox.critical(self, "Batch Protect failed", message))
        worker.signals.finished.connect(self._finished)
        self.controller.pool.start(worker)

    def _progress(self, current: int, total: int, result: object) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(current)
        if isinstance(result, BatchItemResult):
            self.status.setText(f"{current}/{total} · {Path(result.source).name} · {result.status}")
            self._append_result(result)

    def _append_result(self, item: BatchItemResult) -> None:
        row = self.results.rowCount()
        self.results.insertRow(row)
        values = (Path(item.source).name, item.status, str(item.findings_count), Path(item.output).name if item.output else item.error)
        for column, value in enumerate(values):
            self.results.setItem(row, column, QTableWidgetItem(value))

    def _done(self, result: object) -> None:
        rows = tuple(result) if isinstance(result, (tuple, list)) else ()
        success = sum(1 for item in rows if isinstance(item, BatchItemResult) and item.status == "protected")
        failed = len(rows) - success
        self.status.setText(f"Complete · {success} protected · {failed} failed")

    def _finished(self) -> None:
        self._worker = None
        self.start.setEnabled(True)


class WatchedFoldersDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Watched Folders",
            "Create local Inbox → Protected automations. PrivacyGate checks enabled folders while the desktop app is running.",
            "workflow",
        )
        setup, box = _surface("Add watched folder", "Every watch is scoped to a PrivacyGate workspace and privacy profile.", "library")
        grid = QGridLayout()
        self.inbox = _field(); self.inbox.setReadOnly(True)
        self.protected = _field(); self.protected.setReadOnly(True)
        inbox_browse = _button("Choose Inbox", primary=True, icon_name="library")
        protected_browse = _button("Choose Protected", icon_name="library")
        self.workspace = _combo(); _fill_workspaces(self.workspace, controller.main_window)
        self.profile = _combo()
        for profile in AdvancedProfileCatalog.all():
            self.profile.addItem(profile.name, profile.key)
        grid.addWidget(QLabel("Inbox folder"), 0, 0); grid.addWidget(self.inbox, 1, 0); grid.addWidget(inbox_browse, 1, 1)
        grid.addWidget(QLabel("Protected output"), 2, 0); grid.addWidget(self.protected, 3, 0); grid.addWidget(protected_browse, 3, 1)
        grid.addWidget(QLabel("Workspace"), 0, 2); grid.addWidget(self.workspace, 1, 2)
        grid.addWidget(QLabel("Privacy profile"), 2, 2); grid.addWidget(self.profile, 3, 2)
        box.addLayout(grid)
        add = _button("Add & start monitoring", primary=True, icon_name="check")
        box.addWidget(add, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(setup)

        watches, watches_box = _surface("Active local watches", "Checks run every 30 seconds. Only new or changed supported documents are processed.", "compare")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Inbox", "Protected", "Workspace", "Profile", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for col in range(5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if col < 2 else QHeaderView.ResizeMode.ResizeToContents)
        watches_box.addWidget(self.table, 1)
        actions = QHBoxLayout()
        remove = _button("Remove selected")
        run = _button("Run check now", primary=True, icon_name="restore")
        self.status = QLabel("Local watcher ready")
        self.status.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        actions.addWidget(remove); actions.addWidget(run); actions.addWidget(self.status, 1)
        watches_box.addLayout(actions)
        root.addWidget(watches, 1)
        close = _button("Close")
        root.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

        inbox_browse.clicked.connect(self._choose_inbox)
        protected_browse.clicked.connect(self._choose_protected)
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        run.clicked.connect(lambda: controller.run_watches_async(self._watch_complete))
        close.clicked.connect(self.close)
        self.refresh()

    def _choose_inbox(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose watched Inbox")
        if path:
            self.inbox.setText(path)
            if not self.protected.text().strip():
                self.protected.setText(str(Path(path).parent / "Protected"))

    def _choose_protected(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose protected output folder")
        if path:
            self.protected.setText(path)

    def _add(self) -> None:
        if not self.inbox.text().strip() or not self.protected.text().strip():
            QMessageBox.information(self, "Watched Folders", "Choose both Inbox and Protected folders.")
            return
        workspace = str(self.workspace.currentData() or "personal")
        plan = self.controller.plan_for_workspace(workspace)
        if not supports(plan, Capability.WATCHED_FOLDERS):
            self.controller.show_locked(Capability.WATCHED_FOLDERS, "Watched Folders")
            return
        config = WatchFolderConfig(
            watch_id=uuid.uuid4().hex,
            inbox=self.inbox.text().strip(),
            protected=self.protected.text().strip(),
            workspace_key=workspace,
            profile_key=str(self.profile.currentData()),
            enabled=True,
        )
        self.controller.watch_store.add(config)
        self.controller.activity.record("watch_added", workspace_key=workspace, source_kind="folder", detail="Local watched folder enabled")
        self.refresh()
        self.status.setText("Monitoring enabled")

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        watch_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        if watch_id:
            self.controller.watch_store.remove(watch_id)
        self.refresh()

    def refresh(self) -> None:
        configs = self.controller.watch_store.list()
        self.table.setRowCount(len(configs))
        for row, config in enumerate(configs):
            values = (config.inbox, config.protected, config.workspace_key, config.profile_key, "Monitoring" if config.enabled else "Paused")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, config.watch_id)
                self.table.setItem(row, column, item)

    def _watch_complete(self, count: int, failures: int) -> None:
        self.status.setText(f"Check complete · {count} protected · {failures} failed")
        self.refresh()


class OcrDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        self._worker: FunctionWorker | None = None
        root = _dialog_shell(
            self,
            "Local OCR",
            "Extract selectable text from scanned PDFs or images without uploading the source to a cloud OCR service.",
            "document",
        )
        control, box = _surface("OCR source", "Tesseract runs locally. PDF OCR also uses local pdftoppm when available.", "protect")
        row = QHBoxLayout()
        self.path = _field(); self.path.setReadOnly(True); self.path.setPlaceholderText("PDF, PNG, JPG, TIFF or BMP")
        browse = _button("Choose file", primary=True, icon_name="document")
        self.run = _button("Run local OCR", primary=True, icon_name="protect")
        row.addWidget(self.path, 1); row.addWidget(browse); row.addWidget(self.run)
        box.addLayout(row)
        available, detail = controller.ocr.availability()
        self.availability = QLabel(("READY · " if available else "SETUP REQUIRED · ") + detail)
        self.availability.setWordWrap(True)
        self.availability.setStyleSheet(f"color:{GREEN if available else AMBER};font-size:9px;font-weight:850;border:none;")
        box.addWidget(self.availability)
        root.addWidget(control)
        result, result_box = _surface("OCR text", "Review extracted text before sending it to Protect.", "compare")
        self.text = QPlainTextEdit(); self.text.setMinimumHeight(260)
        self.text.setStyleSheet("QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D3DFE6;border-radius:11px;padding:10px;font-size:10px;}")
        result_box.addWidget(self.text, 1)
        actions = QHBoxLayout()
        self.status = QLabel("Ready")
        use = _button("Use OCR text in Protect", primary=True, icon_name="protect")
        actions.addWidget(self.status, 1); actions.addWidget(use)
        result_box.addLayout(actions)
        root.addWidget(result, 1)
        browse.clicked.connect(self._browse)
        self.run.clicked.connect(self._run)
        use.clicked.connect(self._use_in_protect)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose scanned document", "", "OCR sources (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
        if path:
            self.path.setText(path)

    def _run(self) -> None:
        if self._worker is not None:
            return
        if not self.path.text().strip():
            QMessageBox.information(self, "Local OCR", "Choose a scanned PDF or image first.")
            return
        plan = active_plan_for(self.controller.main_window)
        workspace = self.controller.active_workspace_key()
        self.run.setEnabled(False)
        self.status.setText("OCR running locally…")
        worker = FunctionWorker(lambda: self.controller.ocr.extract(plan, self.path.text().strip(), workspace_key=workspace))
        self._worker = worker
        worker.signals.result.connect(lambda text: self.text.setPlainText(str(text)))
        worker.signals.result.connect(lambda _text: self.status.setText("OCR complete"))
        worker.signals.error.connect(lambda message: QMessageBox.warning(self, "Local OCR unavailable", message))
        worker.signals.finished.connect(self._finished)
        self.controller.pool.start(worker)

    def _finished(self) -> None:
        self._worker = None
        self.run.setEnabled(True)

    def _use_in_protect(self) -> None:
        text = self.text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Local OCR", "Run OCR before sending text to Protect.")
            return
        page = self.controller.main_window.protection_page
        page.clear()
        page.text_input.setPlainText(text)
        page.input_tabs.setCurrentIndex(0)
        self.controller.main_window._show_page(0)
        self.close()


class ActivityDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Local Activity Center",
            "A metadata-only local history: actions, workspace, document type, finding counts and status — never document content or titles.",
            "compare",
        )
        surface, box = _surface("Recent activity", "Source identifiers are one-way hashes so sensitive filenames are not stored in the log.", "library")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Time", "Event", "Workspace", "Type", "Findings", "Status", "Detail"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for col in range(7):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if col in {1, 6} else QHeaderView.ResizeMode.ResizeToContents)
        box.addWidget(self.table, 1)
        actions = QHBoxLayout()
        refresh = _button("Refresh", primary=True, icon_name="restore")
        clear = _button("Clear local history")
        actions.addWidget(refresh); actions.addWidget(clear); actions.addStretch(1)
        box.addLayout(actions)
        root.addWidget(surface, 1)
        refresh.clicked.connect(self.refresh)
        clear.clicked.connect(self._clear)
        self.refresh()

    def refresh(self) -> None:
        rows = self.controller.activity.recent(200)
        self.table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            created = str(item.get("created_at", "")).replace("T", " ")[:19]
            values = (
                created,
                str(item.get("event_type", "")),
                str(item.get("workspace_key", "")),
                str(item.get("source_kind", "")),
                str(item.get("findings_count", 0)),
                str(item.get("status", "")),
                str(item.get("detail", "")),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _clear(self) -> None:
        if QMessageBox.question(self, "Clear activity history?", "Delete the local metadata-only activity history from this device?") != QMessageBox.StandardButton.Yes:
            return
        self.controller.activity.clear()
        self.refresh()


class ProfilesDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Privacy Profiles",
            "Choose detection profiles for different operating contexts while keeping the same local Presidio-based protection engine.",
            "protect",
        )
        surface, box = _surface("Available profiles", "The Healthcare profile is general privacy coverage, not a specialized clinical/HIPAA recognizer pack.", "compare")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Profile", "Coverage", "Entities"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        profiles = AdvancedProfileCatalog.all()
        self.table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            name = QTableWidgetItem(profile.name)
            name.setData(Qt.ItemDataRole.UserRole, profile.key)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(profile.description))
            self.table.setItem(row, 2, QTableWidgetItem(str(len(set(profile.entities)))))
        box.addWidget(self.table, 1)
        use = _button("Use selected profile in Protect", primary=True, icon_name="protect")
        box.addWidget(use, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(surface, 1)
        use.clicked.connect(self._use)

    def _use(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        key = str(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        page = self.controller.main_window.protection_page
        index = page.profile_combo.findData(key)
        if index >= 0:
            page.profile_combo.setCurrentIndex(index)
        self.controller.main_window._show_page(0)
        self.close()


class PreflightDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Advanced Privacy Preflight",
            "Before an AI handoff, verify residual PII, active workspace and workspace destination rules against the exact protected result.",
            "protect",
        )
        surface, box = _surface("Handoff check", "Run this after reviewing and protecting a document in Protect.", "workflow")
        grid = QGridLayout()
        self.target = _combo()
        for value in ("ChatGPT", "Claude", "Gemini", "Microsoft Copilot", "n8n"):
            self.target.addItem(value, value)
        self.workspace = _combo(); _fill_workspaces(self.workspace, controller.main_window)
        grid.addWidget(QLabel("Destination"), 0, 0); grid.addWidget(self.target, 1, 0)
        grid.addWidget(QLabel("Workspace"), 0, 1); grid.addWidget(self.workspace, 1, 1)
        box.addLayout(grid)
        run = _button("Run privacy preflight", primary=True, icon_name="check")
        box.addWidget(run, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(surface)
        report, report_box = _surface("Preflight result", "Nothing leaves PrivacyGate when you run this check.", "compare")
        self.result = QLabel("No preflight run yet.")
        self.result.setWordWrap(True)
        self.result.setMinimumHeight(90)
        self.result.setStyleSheet(f"color:{INK};font-size:12px;font-weight:800;border:none;")
        report_box.addWidget(self.result)
        root.addWidget(report, 1)
        run.clicked.connect(self._run)

    def _run(self) -> None:
        protect = self.controller.main_window.protection_page
        result = getattr(protect, "current_result", None)
        if result is None:
            QMessageBox.information(self, "Privacy Preflight", "Protect a document first so PrivacyGate can evaluate the exact protected result.")
            return
        profile = get_profile(str(protect.profile_combo.currentData()))
        workspace = str(self.workspace.currentData() or self.controller.active_workspace_key())
        plan = self.controller.plan_for_workspace(workspace)
        try:
            report = self.controller.preflight.evaluate(plan, result, profile, target=str(self.target.currentData()), workspace_key=workspace)
        except Exception as exc:
            QMessageBox.warning(self, "Privacy Preflight", str(exc))
            return
        self.result.setText(report.message + f"\n\nWorkspace: {report.workspace_key}  ·  Destination: {report.target}  ·  Residual findings: {report.residual_findings}")
        self.result.setStyleSheet(f"color:{GREEN if report.ready else RED};font-size:12px;font-weight:900;border:none;")
        self.controller.activity.record("privacy_preflight", workspace_key=workspace, source_kind="protected", findings_count=report.residual_findings, status="ready" if report.ready else "blocked", detail=report.message)


class AutomationDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        self._worker: FunctionWorker | None = None
        root = _dialog_shell(
            self,
            "Automation Actions",
            "Trigger an explicit n8n webhook from PrivacyGate. File operations remain workspace-scoped and destructive actions use Safe Delete.",
            "workflow",
        )
        surface, box = _surface("n8n webhook action", "PrivacyGate sends only the JSON payload you enter here. Nothing is attached automatically.", "cloud")
        self.url = _field(); self.url.setPlaceholderText("https://.../webhook/... or http://127.0.0.1:5678/...")
        self.payload = QPlainTextEdit("{}")
        self.payload.setMinimumHeight(170)
        self.payload.setStyleSheet("QPlainTextEdit{background:#FFFFFF;color:#17384E;border:1px solid #D3DFE6;border-radius:10px;padding:10px;font-family:monospace;font-size:10px;}")
        box.addWidget(QLabel("Webhook URL")); box.addWidget(self.url)
        box.addWidget(QLabel("JSON payload")); box.addWidget(self.payload)
        row = QHBoxLayout()
        self.status = QLabel("Ready")
        trigger = _button("Trigger n8n", primary=True, icon_name="workflow")
        row.addWidget(self.status, 1); row.addWidget(trigger)
        box.addLayout(row)
        root.addWidget(surface, 1)
        trigger.clicked.connect(self._trigger)

    def _trigger(self) -> None:
        if self._worker is not None:
            return
        try:
            payload = json.loads(self.payload.toPlainText() or "{}")
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Automation Action", f"Invalid JSON payload: {exc}")
            return
        if not isinstance(payload, dict):
            QMessageBox.warning(self, "Automation Action", "The webhook payload must be a JSON object.")
            return
        workspace = self.controller.active_workspace_key()
        plan = self.controller.plan_for_workspace(workspace)
        self.status.setText("Running…")
        worker = FunctionWorker(lambda: self.controller.automation.trigger_n8n(plan, self.url.text().strip(), payload, workspace_key=workspace))
        self._worker = worker
        worker.signals.result.connect(lambda result: self.status.setText("Completed · " + str(result)[:180]))
        worker.signals.error.connect(lambda message: QMessageBox.warning(self, "Automation Action failed", message))
        worker.signals.finished.connect(self._finished)
        self.controller.pool.start(worker)

    def _finished(self) -> None:
        self._worker = None


class RulesDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Workspace Rules",
            "Bind provider/account metadata to a workspace, define approved AI destinations and set a default local folder — stored locally on this device.",
            "workflow",
        )
        editor, box = _surface("Add rule", "Example: Google Drive account → Company A → ChatGPT, Claude.", "settings")
        grid = QGridLayout()
        self.provider = _field(); self.provider.setPlaceholderText("google_drive, gmail, asana…")
        self.account = _field(); self.account.setPlaceholderText("Account label or local account ID")
        self.workspace = _combo(); _fill_workspaces(self.workspace, controller.main_window)
        self.destinations = _field(); self.destinations.setPlaceholderText("ChatGPT, Claude")
        self.folder = _field(); self.folder.setPlaceholderText("Optional default local folder")
        browse = _button("Browse folder", icon_name="library")
        grid.addWidget(QLabel("Provider"), 0, 0); grid.addWidget(self.provider, 1, 0)
        grid.addWidget(QLabel("Account"), 0, 1); grid.addWidget(self.account, 1, 1)
        grid.addWidget(QLabel("Workspace"), 0, 2); grid.addWidget(self.workspace, 1, 2)
        grid.addWidget(QLabel("Allowed destinations"), 2, 0); grid.addWidget(self.destinations, 3, 0, 1, 2)
        grid.addWidget(QLabel("Default folder"), 2, 2); grid.addWidget(self.folder, 3, 2); grid.addWidget(browse, 3, 3)
        box.addLayout(grid)
        add = _button("Add rule", primary=True, icon_name="check")
        box.addWidget(add, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(editor)
        rules, rules_box = _surface("Saved rules", "Rules are local metadata and do not expose connector tokens or document contents.", "compare")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Provider", "Account", "Workspace", "Destinations", "Default folder"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for col in range(5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        rules_box.addWidget(self.table, 1)
        remove = _button("Remove selected")
        rules_box.addWidget(remove, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(rules, 1)
        browse.clicked.connect(self._browse)
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        self.refresh()

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose default workspace folder")
        if path:
            self.folder.setText(path)

    def _rules(self) -> list[WorkspaceRule]:
        rules: list[WorkspaceRule] = []
        for row in range(self.table.rowCount()):
            rules.append(
                WorkspaceRule(
                    provider=self.table.item(row, 0).text(),
                    account_id=self.table.item(row, 1).text(),
                    workspace_key=self.table.item(row, 2).text(),
                    allowed_destinations=tuple(part.strip() for part in self.table.item(row, 3).text().split(",") if part.strip()),
                    default_folder=self.table.item(row, 4).text(),
                )
            )
        return rules

    def _add(self) -> None:
        if not self.provider.text().strip() or not self.account.text().strip():
            QMessageBox.information(self, "Workspace Rules", "Enter both provider and account metadata.")
            return
        rules = list(self.controller.rules.list())
        rules.append(
            WorkspaceRule(
                provider=self.provider.text().strip().lower(),
                account_id=self.account.text().strip(),
                workspace_key=str(self.workspace.currentData() or "personal"),
                allowed_destinations=tuple(part.strip() for part in self.destinations.text().split(",") if part.strip()),
                default_folder=self.folder.text().strip(),
            )
        )
        plan = self.controller.plan_for_workspace(str(self.workspace.currentData() or "personal"))
        try:
            self.controller.rules.save(plan, rules)
        except Exception as exc:
            QMessageBox.warning(self, "Workspace Rules", str(exc))
            return
        self.refresh()

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        rules = list(self.controller.rules.list())
        if row < len(rules):
            rules.pop(row)
        plan = active_plan_for(self.controller.main_window)
        try:
            self.controller.rules.save(plan, rules)
        except Exception as exc:
            QMessageBox.warning(self, "Workspace Rules", str(exc))
            return
        self.refresh()

    def refresh(self) -> None:
        rules = self.controller.rules.list()
        self.table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            values = (rule.provider, rule.account_id, rule.workspace_key, ", ".join(rule.allowed_destinations), rule.default_folder)
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))


class BackupDialog(QDialog):
    def __init__(self, controller: "FeatureSuiteController") -> None:
        super().__init__(controller.main_window)
        self.controller = controller
        root = _dialog_shell(
            self,
            "Encrypted Backup",
            "Create a passphrase-encrypted local backup for recovery or migration. Connector OAuth credentials are intentionally excluded.",
            "download",
        )
        create, create_box = _surface("Create portable backup", "Includes the local Library and non-secret configuration. Use a strong passphrase and store it separately.", "protect")
        self.password = _field(); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.password.setPlaceholderText("Backup passphrase (10+ characters)")
        self.confirm = _field(); self.confirm.setEchoMode(QLineEdit.EchoMode.Password); self.confirm.setPlaceholderText("Confirm passphrase")
        create_button = _button("Create encrypted backup", primary=True, icon_name="save")
        create_box.addWidget(self.password); create_box.addWidget(self.confirm); create_box.addWidget(create_button, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(create)
        restore, restore_box = _surface("Restore backup", "Restoring replaces the local Library database after a safety backup and restores supported non-secret settings.", "restore")
        self.restore_password = _field(); self.restore_password.setEchoMode(QLineEdit.EchoMode.Password); self.restore_password.setPlaceholderText("Backup passphrase")
        restore_button = _button("Restore encrypted backup", icon_name="restore")
        restore_box.addWidget(self.restore_password); restore_box.addWidget(restore_button, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(restore)
        note = QLabel("PrivacyGate never includes connector OAuth tokens in portable backups. Reconnect external apps on the new device.")
        note.setWordWrap(True); note.setStyleSheet(f"color:{MUTED};font-size:9px;border:none;")
        root.addWidget(note); root.addStretch(1)
        create_button.clicked.connect(self._create)
        restore_button.clicked.connect(self._restore)

    def _create(self) -> None:
        password = self.password.text()
        if len(password) < 10 or password != self.confirm.text():
            QMessageBox.information(self, "Encrypted Backup", "Use a passphrase of at least 10 characters and confirm it exactly.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Create PrivacyGate backup", "PrivacyGate-backup.pgbak", "PrivacyGate backup (*.pgbak)")
        if not path:
            return
        try:
            target = self.controller.backup.create(active_plan_for(self.controller.main_window), path, password)
        except Exception as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return
        self.controller.activity.record("encrypted_backup_created", workspace_key=self.controller.active_workspace_key(), source_kind="backup", detail="Portable backup created")
        QMessageBox.information(self, "Backup created", f"Encrypted backup created successfully:\n\n{target}")

    def _restore(self) -> None:
        password = self.restore_password.text()
        if not password:
            QMessageBox.information(self, "Encrypted Backup", "Enter the backup passphrase.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Restore PrivacyGate backup", "", "PrivacyGate backup (*.pgbak)")
        if not path:
            return
        if QMessageBox.question(self, "Restore PrivacyGate backup?", "This will replace the local Library after creating a safety copy of the current database. Continue?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.backup.restore(active_plan_for(self.controller.main_window), path, password)
        except Exception as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        QMessageBox.information(self, "Backup restored", "PrivacyGate restored the local Library and supported settings. Restart the app before continuing work.")


class FeatureSuiteController:
    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.pool = QThreadPool.globalInstance()
        self.activity = LocalActivityStore(main_window.library.data_dir)
        self.batch = BatchProtectionService(main_window.service, main_window.library, self.activity)
        self.watch_store = WatchFolderStore(main_window.library.data_dir)
        self.watched = WatchedFolderService(main_window.library.data_dir, self.batch, self.activity)
        self.ocr = LocalOcrService(self.activity)
        self.files = AdvancedFileService()
        self.rules = WorkspaceRuleStore(main_window.library.data_dir)
        self.preflight = PrivacyPreflightService(main_window.service, self.rules)
        self.automation = AutomationActionService(self.files, self.activity)
        self.backup = FullEncryptedBackupService(main_window.library)
        self.routes = WorkspaceFileLocationStore(main_window.library.data_dir)
        self._watch_worker: FunctionWorker | None = None
        self.watch_timer = QTimer(main_window)
        self.watch_timer.setInterval(30_000)
        self.watch_timer.timeout.connect(self.run_watches_async)
        self.watch_timer.start()
        main_window.protection_page.library_changed.connect(
            lambda _document_id: self.activity.record(
                "library_saved",
                workspace_key=self.active_workspace_key(),
                source_kind="protected",
                detail="Protected document saved to encrypted local Library",
            )
        )

    def active_workspace_key(self) -> str:
        context = _workspace_context(self.main_window)
        return str(context.active_key) if context is not None else "personal"

    def plan_for_workspace(self, workspace_key: str) -> PlanCode:
        context = _workspace_context(self.main_window)
        if context is not None:
            descriptor = context.workspaces.get(workspace_key)
            if descriptor is not None:
                return PlanCode(descriptor.plan)
        return active_plan_for(self.main_window)

    def show_locked(self, capability: Capability, title: str) -> None:
        required = minimum_plan_for(capability)
        box = QMessageBox(self.main_window)
        box.setWindowTitle(f"{title} requires PrivacyGate {required.label}")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"{title} is available with PrivacyGate {required.label}.")
        box.setInformativeText(
            "The feature stays visible so you can understand what is available. Switch to an eligible workspace or upgrade the active plan to unlock it."
        )
        box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    def allowed(self, capability: Capability, title: str) -> bool:
        if supports(active_plan_for(self.main_window), capability):
            return True
        self.show_locked(capability, title)
        return False

    def run_watches_async(self, callback=None) -> None:
        if self._watch_worker is not None:
            return
        configs = [config for config in self.watch_store.list() if config.enabled]
        if not configs:
            if callable(callback):
                callback(0, 0)
            return

        def task():
            protected = 0
            failed = 0
            for config in configs:
                plan = self.plan_for_workspace(config.workspace_key)
                if not supports(plan, Capability.WATCHED_FOLDERS):
                    continue
                results = self.watched.scan_once(plan, config)
                protected += sum(1 for item in results if item.status == "protected")
                failed += sum(1 for item in results if item.status != "protected")
            return protected, failed

        worker = FunctionWorker(task)
        self._watch_worker = worker
        if callable(callback):
            worker.signals.result.connect(lambda result: callback(int(result[0]), int(result[1])))
        worker.signals.finished.connect(lambda: setattr(self, "_watch_worker", None))
        self.pool.start(worker)

    def open_feature(self, capability: Capability, title: str, dialog_type) -> None:
        if not self.allowed(capability, title):
            return
        dialog = dialog_type(self)
        dialog.exec()

    def open_files_service(self) -> None:
        if not self.allowed(Capability.ADVANCED_FILE_ROUTING, "Advanced Files"):
            return
        settings = self.main_window.settings_page
        opener = getattr(settings, "open_settings_service", None)
        if callable(opener):
            opener("files")

    def install_advanced_files_panel(self) -> None:
        settings = getattr(self.main_window, "settings_page", None)
        pages = getattr(settings, "settings_service_pages", {}) if settings is not None else {}
        files_page = pages.get("files") if isinstance(pages, dict) else None
        if files_page is None or bool(getattr(files_page, "_privacygate_advanced_actions_added", False)):
            return
        body = getattr(files_page, "_body", None)
        if body is None:
            return
        surface, box = _surface(
            "Advanced file actions",
            "Rename, move or Safe Delete a selected file/folder inside the currently selected workspace root. Safe Delete moves the item into .PrivacyGate Trash instead of permanently erasing it.",
            "workflow",
        )
        selected = _field(); selected.setReadOnly(True); selected.setPlaceholderText("Select a file or folder inside this workspace")
        row = QHBoxLayout()
        select_file = _button("Select file", primary=True, icon_name="document")
        select_folder = _button("Select folder", icon_name="library")
        row.addWidget(selected, 1); row.addWidget(select_file); row.addWidget(select_folder)
        box.addLayout(row)
        actions = QHBoxLayout()
        rename = _button("Rename", icon_name="settings")
        move = _button("Move", icon_name="workflow")
        safe_delete = _button("Safe Delete")
        safe_delete.setStyleSheet("QPushButton{background:#FFF3F3;color:#A23A3A;border:1px solid #E7B8B8;border-radius:10px;padding:9px 14px;font-weight:850;}QPushButton:hover{background:#FDE8E8;}")
        actions.addWidget(rename); actions.addWidget(move); actions.addWidget(safe_delete); actions.addStretch(1)
        box.addLayout(actions)
        body.insertWidget(max(0, body.count() - 1), surface)

        def root_path() -> Path | None:
            current = getattr(files_page, "_current_root", None)
            return current() if callable(current) else None

        def choose_file() -> None:
            root = root_path()
            if root is None:
                return
            path, _ = QFileDialog.getOpenFileName(files_page, "Select workspace file", str(root))
            if path:
                selected.setText(path)

        def choose_folder() -> None:
            root = root_path()
            if root is None:
                return
            path = QFileDialog.getExistingDirectory(files_page, "Select workspace folder", str(root))
            if path:
                selected.setText(path)

        def do_rename() -> None:
            if not self.allowed(Capability.ADVANCED_FILE_ROUTING, "Advanced Files"):
                return
            root = root_path(); source = selected.text().strip()
            if root is None or not source:
                return
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(files_page, "Rename local item", "New name:", text=Path(source).name)
            if not ok or not name.strip():
                return
            try:
                target = self.files.rename(active_plan_for(self.main_window), root, source, name)
            except Exception as exc:
                QMessageBox.warning(files_page, "Rename failed", str(exc)); return
            selected.setText(str(target)); getattr(files_page, "_refresh_route")()
            self.activity.record("file_renamed", workspace_key=self.active_workspace_key(), source_kind="file", detail="Workspace item renamed")

        def do_move() -> None:
            if not self.allowed(Capability.ADVANCED_FILE_ROUTING, "Advanced Files"):
                return
            root = root_path(); source = selected.text().strip()
            if root is None or not source:
                return
            destination = QFileDialog.getExistingDirectory(files_page, "Move into workspace folder", str(root))
            if not destination:
                return
            try:
                target = self.files.move(active_plan_for(self.main_window), root, source, destination)
            except Exception as exc:
                QMessageBox.warning(files_page, "Move failed", str(exc)); return
            selected.setText(str(target)); getattr(files_page, "_refresh_route")()
            self.activity.record("file_moved", workspace_key=self.active_workspace_key(), source_kind="file", detail="Workspace item moved")

        def do_delete() -> None:
            if not self.allowed(Capability.ADVANCED_FILE_ROUTING, "Advanced Files"):
                return
            root = root_path(); source = selected.text().strip()
            if root is None or not source:
                return
            if QMessageBox.question(files_page, "Safe Delete this item?", "Move the selected item into this workspace's .PrivacyGate Trash folder? It will not be permanently deleted.") != QMessageBox.StandardButton.Yes:
                return
            try:
                target = self.files.safe_delete(active_plan_for(self.main_window), root, source)
            except Exception as exc:
                QMessageBox.warning(files_page, "Safe Delete failed", str(exc)); return
            selected.clear(); getattr(files_page, "_refresh_route")()
            self.activity.record("file_safe_deleted", workspace_key=self.active_workspace_key(), source_kind="file", detail=f"Moved to local trash ({target.parent.name})")

        select_file.clicked.connect(choose_file)
        select_folder.clicked.connect(choose_folder)
        rename.clicked.connect(do_rename)
        move.clicked.connect(do_move)
        safe_delete.clicked.connect(do_delete)
        files_page._privacygate_advanced_actions_added = True

    def install_profile_gating(self) -> None:
        page = self.main_window.protection_page
        advanced_keys = {"general_business", "construction", "legal", "healthcare_general"}
        for index in range(page.profile_combo.count()):
            key = str(page.profile_combo.itemData(index) or "")
            if key in advanced_keys and "PRO" not in page.profile_combo.itemText(index):
                page.profile_combo.setItemText(index, page.profile_combo.itemText(index) + "  ·  PRO")
        state = {"last": max(0, page.profile_combo.currentIndex()), "guard": False}

        def changed(index: int) -> None:
            if state["guard"]:
                return
            key = str(page.profile_combo.itemData(index) or "")
            plan = active_plan_for(self.main_window)
            if key in advanced_keys and not supports(plan, Capability.PRIVACY_PROFILES):
                state["guard"] = True
                self.show_locked(Capability.PRIVACY_PROFILES, "Advanced Privacy Profiles")
                page.profile_combo.setCurrentIndex(int(state["last"]))
                state["guard"] = False
                return
            state["last"] = index

        page.profile_combo.currentIndexChanged.connect(changed)


def apply_feature_suite_2026(main_window) -> None:
    if bool(getattr(main_window, "_privacygate_feature_suite_2026", False)):
        return
    settings = getattr(main_window, "settings_page", None)
    stack = getattr(settings, "settings_service_stack", None) if settings is not None else None
    hub = getattr(settings, "settings_service_hub", None) if settings is not None else None
    if settings is None or stack is None or hub is None:
        return

    controller = FeatureSuiteController(main_window)
    main_window.privacygate_feature_suite = controller

    def back_to_hub() -> None:
        stack.setCurrentWidget(hub)

    page, body = _service_page(
        "Advanced Privacy & Automation",
        "Ten local-first services for higher-volume protection, OCR, monitored folders, safe file operations, preflight, workspace rules and recovery.",
        "workflow",
        back_to_hub,
    )

    plan_surface, plan_box = _surface(
        "Capability-based licensing",
        "Basic keeps the complete Protect / Restore / Library core. Advanced cards stay visible and explain the minimum plan required instead of disappearing.",
        "protect",
    )
    plan_label = QLabel(f"ACTIVE CONTEXT · {active_plan_for(main_window).label.upper()}")
    plan_label.setStyleSheet("background:#E8F7F7;color:#0B7F89;border:1px solid #C7E8E8;border-radius:9px;padding:6px 9px;font-size:9px;font-weight:900;")
    plan_box.addWidget(plan_label, 0, Qt.AlignmentFlag.AlignLeft)
    body.addWidget(plan_surface)

    features = (
        ("Batch Protect", "Queue folders or many documents with progress and a per-file report.", "protect", Capability.BATCH_PROTECTION, BatchProtectDialog),
        ("Watched Folders", "Inbox → Protected automatic local processing while PrivacyGate runs.", "workflow", Capability.WATCHED_FOLDERS, WatchedFoldersDialog),
        ("Local OCR", "Scanned PDF / PNG / JPG / TIFF text extraction with local tools only.", "document", Capability.LOCAL_OCR, OcrDialog),
        ("Advanced Files", "Workspace-scoped routing, rename, move and reversible Safe Delete.", "library", Capability.ADVANCED_FILE_ROUTING, None),
        ("Activity Center", "Metadata-only local history without document contents or filenames.", "compare", Capability.ACTIVITY_CENTER, ActivityDialog),
        ("Privacy Profiles", "Real Estate, Construction, Legal, Healthcare and General Business profiles.", "protect", Capability.PRIVACY_PROFILES, ProfilesDialog),
        ("Privacy Preflight", "Residual PII + active workspace + destination-rule check before handoff.", "check", Capability.PRIVACY_PREFLIGHT, PreflightDialog),
        ("Automation Actions", "Explicit n8n webhook actions and controlled local automation.", "workflow", Capability.ADVANCED_AUTOMATION, AutomationDialog),
        ("Workspace Rules", "Bind accounts, allowed destinations and default folders to company contexts.", "settings", Capability.WORKSPACE_RULES, RulesDialog),
        ("Encrypted Backup", "Passphrase-encrypted Library/config backup for recovery or migration.", "download", Capability.ENCRYPTED_BACKUP, BackupDialog),
    )
    grid = QGridLayout()
    grid.setHorizontalSpacing(11); grid.setVerticalSpacing(11)
    for index, (title, detail, icon_name, capability, dialog_type) in enumerate(features):
        tone = "indigo" if capability in {Capability.LOCAL_OCR, Capability.ENCRYPTED_BACKUP} else "teal"
        card = _HubCard(title, detail, icon_name, _required_badge(capability), tone)
        if dialog_type is None:
            card.clicked.connect(controller.open_files_service)
        else:
            card.clicked.connect(lambda _checked=False, cap=capability, title=title, dtype=dialog_type: controller.open_feature(cap, title, dtype))
        grid.addWidget(card, index // 2, index % 2)
    grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
    body.addLayout(grid)
    body.addStretch(1)
    stack.addWidget(page)

    grids = hub.findChildren(QGridLayout)
    target_grid = max(grids, key=lambda item: item.count(), default=None)
    if target_grid is not None:
        launcher = _HubCard(
            "Advanced",
            "Batch, OCR, watched folders, preflight, automation, rules and encrypted backup.",
            "workflow",
            "PRO + BUSINESS",
            "indigo",
        )
        launcher.clicked.connect(lambda: stack.setCurrentWidget(page))
        row = (target_grid.count() + 2) // 3
        target_grid.addWidget(launcher, row, 0, 1, 3)
        settings.settings_service_advanced_launcher = launcher

    pages = getattr(settings, "settings_service_pages", None)
    if isinstance(pages, dict):
        pages["advanced"] = page

    controller.install_advanced_files_panel()
    controller.install_profile_gating()

    menu = getattr(main_window.protection_page, "ai_button", None)
    if menu is not None and menu.menu() is not None:
        ai_menu = menu.menu()
        ai_menu.addSeparator()
        preflight_action = ai_menu.addAction("Advanced Privacy Preflight…")
        preflight_action.triggered.connect(
            lambda: controller.open_feature(Capability.PRIVACY_PREFLIGHT, "Advanced Privacy Preflight", PreflightDialog)
        )

    main_window._privacygate_feature_suite_2026 = True
