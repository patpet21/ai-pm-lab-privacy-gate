from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import TeamServiceError
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.workspace_creation_experience import (
    CreateBusinessWorkspaceDialog,
    _clean_service_error,
)
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
GREEN = "#23824B"
BORDER = "#DCE5EA"


def _make_creation_dialog_more_readable(dialog: CreateBusinessWorkspaceDialog) -> None:
    """Increase hierarchy/readability without changing the existing fields."""
    dialog.setMinimumWidth(700)
    dialog.setStyleSheet(
        dialog.styleSheet()
        + "QDialog{background:#F8FBFC;}"
        + "QLineEdit{font-size:12px;}QSpinBox{font-size:12px;}"
    )
    for label in dialog.findChildren(QLabel):
        text = label.text().strip()
        if text == "Create a Business workspace":
            label.setStyleSheet(f"color:{NAVY};font-size:24px;font-weight:900;border:none;")
        elif text.startswith("Set up the company area"):
            label.setStyleSheet(f"color:{MUTED};font-size:12px;border:none;line-height:1.25;")
        elif text in {"Company / organization name", "Team size / seats"}:
            label.setStyleSheet(f"color:{INK};font-size:12px;font-weight:850;border:none;")
        elif text.startswith("This is the name members") or text.startswith("A seat is one active person"):
            label.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
        elif text in {"You become Owner", "Policy ready", "2 devices / member"}:
            label.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:900;border:none;")
        elif text:
            # Remaining helper/summary copy: keep it clearly readable.
            current = label.styleSheet()
            if "font-size:8px" in current:
                label.setStyleSheet(current.replace("font-size:8px", "font-size:10px"))
            elif "font-size:9px" in current:
                label.setStyleSheet(current.replace("font-size:9px", "font-size:10px"))

    for edit in dialog.findChildren(QLineEdit):
        edit.setMinimumHeight(48)
    for spin in dialog.findChildren(QSpinBox):
        spin.setMinimumHeight(48)
        spin.setMinimumWidth(150)
    for button in dialog.findChildren(QPushButton):
        button.setMinimumHeight(44)
        button.setStyleSheet(
            button.styleSheet().replace("font-size:10px", "font-size:11px")
        )


class WorkspaceCreationProgressDialog(QDialog):
    def __init__(self, workspace_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Creating workspace")
        self.setModal(True)
        self.setMinimumWidth(570)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._phase = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(14)
        bubble = QLabel()
        bubble.setFixedSize(48, 48)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon("workflow", color=TEAL, size=25).pixmap(25, 25))
        bubble.setStyleSheet("background:#E7F7F7;border:1px solid #BDE4E4;border-radius:16px;")
        top.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(4)
        title = QLabel("Creating your company workspace")
        title.setStyleSheet(f"color:{NAVY};font-size:22px;font-weight:900;border:none;")
        subtitle = QLabel(
            f"PrivacyGate is setting up {workspace_name}, its Owner access and starter privacy policy."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:11px;border:none;")
        copy.addWidget(title)
        copy.addWidget(subtitle)
        top.addLayout(copy, 1)
        root.addLayout(top)

        self.status = QLabel("Creating secure workspace…")
        self.status.setStyleSheet(f"color:{INK};font-size:12px;font-weight:800;border:none;")
        root.addWidget(self.status)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(11)
        progress.setStyleSheet(
            "QProgressBar{background:#E8EFF2;border:none;border-radius:5px;}"
            "QProgressBar::chunk{background:#10A7A3;border-radius:5px;}"
        )
        root.addWidget(progress)

        note = QLabel("This normally takes only a few seconds. Keep PrivacyGate open while setup completes.")
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#EEF8F8;color:#426675;border:none;border-radius:10px;"
            "padding:10px;font-size:10px;"
        )
        root.addWidget(note)

        self._timer = QTimer(self)
        self._timer.setInterval(850)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self) -> None:
        phases = (
            "Creating secure workspace…",
            "Applying starter privacy policy…",
            "Preparing workspace access…",
            "Refreshing your workspace list…",
        )
        self._phase = (self._phase + 1) % len(phases)
        self.status.setText(phases[self._phase])

    def finish(self) -> None:
        self._timer.stop()
        self.close()


class WorkspaceCreatedDialog(QDialog):
    def __init__(self, workspace_name: str, seats: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workspace ready")
        self.setModal(True)
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(14)
        bubble = QLabel()
        bubble.setFixedSize(50, 50)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setPixmap(icon("check", color=GREEN, size=27).pixmap(27, 27))
        bubble.setStyleSheet("background:#EAF8F0;border:1px solid #BDE2CD;border-radius:17px;")
        top.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(4)
        title = QLabel("Workspace created successfully")
        title.setStyleSheet(f"color:{NAVY};font-size:23px;font-weight:900;border:none;")
        subtitle = QLabel(f"{workspace_name} is ready and active in PrivacyGate.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:12px;border:none;")
        copy.addWidget(title)
        copy.addWidget(subtitle)
        top.addLayout(copy, 1)
        root.addLayout(top)

        summary = QFrame(objectName="WorkspaceCreatedSummary")
        summary.setStyleSheet(
            "QFrame#WorkspaceCreatedSummary{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
        )
        row = QHBoxLayout(summary)
        row.setContentsMargins(14, 13, 14, 13)
        row.setSpacing(10)
        for heading, detail in (
            ("ACTIVE WORKSPACE", workspace_name),
            ("YOUR ROLE", "Owner"),
            ("TEAM CAPACITY", f"{seats} seats"),
        ):
            card = QFrame()
            card.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E8EEF1;border-radius:10px;}")
            box = QVBoxLayout(card)
            box.setContentsMargins(11, 10, 11, 10)
            box.setSpacing(3)
            head = QLabel(heading)
            head.setStyleSheet("color:#78909E;font-size:8px;font-weight:900;letter-spacing:.5px;border:none;")
            value = QLabel(detail)
            value.setWordWrap(True)
            value.setStyleSheet(f"color:{NAVY};font-size:11px;font-weight:850;border:none;")
            box.addWidget(head)
            box.addWidget(value)
            row.addWidget(card, 1)
        root.addWidget(summary)

        note = QLabel(
            "A starter company privacy policy has been created automatically. The workspace selector is being refreshed so the new company appears everywhere you choose a work context."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#EEF8F8;color:#426675;border:none;border-radius:10px;"
            "padding:11px;font-size:10px;"
        )
        root.addWidget(note)

        actions = QHBoxLayout()
        actions.addStretch(1)
        done = QPushButton("Done")
        done.setMinimumHeight(44)
        done.setCursor(Qt.CursorShape.PointingHandCursor)
        done.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:11px;"
            "padding:10px 22px;font-size:11px;font-weight:850;}"
            "QPushButton:hover{background:#096D76;}"
        )
        done.clicked.connect(self.accept)
        actions.addWidget(done)
        root.addLayout(actions)


def _create_workspace_with_feedback(self) -> None:
    if not self._require_signed_in():
        return

    dialog = CreateBusinessWorkspaceDialog(self)
    _make_creation_dialog_more_readable(dialog)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    name, seats = dialog.values()

    team_page = self.team_page
    if getattr(team_page, "_active_worker", None) is not None:
        QMessageBox.information(
            self,
            "Please wait",
            "PrivacyGate is already syncing an Organization action. Try again in a moment.",
        )
        return

    progress = WorkspaceCreationProgressDialog(name, self)
    progress.show()
    QApplication.processEvents()

    outcome: dict[str, object] = {"state": None, "failed": False}

    def task():
        session = team_page.account_client.restore_session()
        if session is None:
            raise TeamServiceError("Sign in to your PrivacyGate account first.")
        state = team_page.team_client.create_business_workspace(
            session, name, seat_limit=seats
        )
        return self._cache_and_activate_state(session, state)

    worker = FunctionWorker(task)
    team_page._active_worker = worker
    team_page._set_busy(True)
    self.create_button.setEnabled(False)

    def ready(result: object) -> None:
        if isinstance(result, TeamState):
            outcome["state"] = result
            team_page._apply_state(result)
            self.refresh()

    def failed(message: str) -> None:
        outcome["failed"] = True
        progress.finish()
        QMessageBox.warning(
            self,
            "Workspace could not be created",
            _clean_service_error(message)
            + "\n\nNothing was changed. You can adjust the company name or team size and try again.",
        )

    def finished() -> None:
        team_page._worker_finished()
        self.create_button.setEnabled(True)
        if outcome["failed"]:
            return

        state = outcome.get("state")
        if not isinstance(state, TeamState):
            progress.finish()
            return

        # Important: refresh only after the creation worker has been cleared.
        # TeamPage.refresh_silent() ignores refresh requests while another worker
        # is active; doing it here guarantees the just-created membership is
        # re-read from Supabase and the selector is rebuilt immediately.
        progress.status.setText("Refreshing your workspace list…")
        team_page.refresh_silent()
        self.refresh()

        def confirm_ready() -> None:
            progress.finish()
            WorkspaceCreatedDialog(name, seats, self).exec()

        QTimer.singleShot(500, confirm_ready)

    worker.signals.result.connect(ready)
    worker.signals.error.connect(failed)
    worker.signals.finished.connect(finished)
    team_page.thread_pool.start(worker)


def apply_workspace_creation_feedback(main_window) -> None:
    """Add visible creation progress, larger copy and a real completion step."""
    settings = getattr(main_window, "settings_page", None)
    panel = (
        getattr(settings, "_privacygate_workspace_settings_panel", None)
        if settings is not None
        else None
    )
    if panel is None or bool(getattr(panel, "_privacygate_creation_feedback", False)):
        return

    panel._create_workspace = MethodType(_create_workspace_with_feedback, panel)
    try:
        panel.create_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    panel.create_button.clicked.connect(panel._create_workspace)
    panel._privacygate_creation_feedback = True
