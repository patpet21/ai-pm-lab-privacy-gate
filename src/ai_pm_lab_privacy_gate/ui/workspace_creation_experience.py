from __future__ import annotations

from types import MethodType

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.policy.policy_store import TeamState
from ai_pm_lab_privacy_gate.infrastructure.policy.supabase_team import TeamServiceError
from ai_pm_lab_privacy_gate.ui.iconography import icon
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker

NAVY = "#062B4F"
INK = "#17384E"
TEAL = "#0B7F89"
MUTED = "#61798A"
BORDER = "#DCE5EA"
GREEN = "#23824B"


class CreateBusinessWorkspaceDialog(QDialog):
    """Single, explanatory workspace-creation flow.

    Replaces the old two-step QInputDialog sequence so the user understands what
    a seat is before anything is created.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create company workspace")
        self.setMinimumWidth(620)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(13)
        badge = QLabel()
        badge.setFixedSize(46, 46)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(icon("workflow", color=TEAL, size=24).pixmap(24, 24))
        badge.setStyleSheet("background:#E8F7F7;border:none;border-radius:15px;")
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel("Create a Business workspace")
        title.setStyleSheet(f"color:{NAVY};font-size:20px;font-weight:900;border:none;")
        subtitle = QLabel(
            "Set up the company area where members, privacy policy, approved apps and managed devices will live."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color:{MUTED};font-size:10px;border:none;")
        copy.addWidget(title)
        copy.addWidget(subtitle)
        header.addLayout(copy, 1)
        root.addLayout(header)

        form = QFrame(objectName="CreateWorkspaceForm")
        form.setStyleSheet(
            "QFrame#CreateWorkspaceForm{background:#FFFFFF;border:1px solid #DCE5EA;border-radius:14px;}"
        )
        form_box = QVBoxLayout(form)
        form_box.setContentsMargins(17, 15, 17, 15)
        form_box.setSpacing(12)

        name_label = QLabel("Company / organization name")
        name_label.setStyleSheet(f"color:{INK};font-size:10px;font-weight:850;border:none;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Example: Acme Property Management")
        self.name_input.setMinimumHeight(44)
        self.name_input.setClearButtonEnabled(True)
        self.name_input.setStyleSheet(
            "QLineEdit{background:#F8FBFC;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
            "padding:9px 11px;font-size:11px;}QLineEdit:focus{background:#FFFFFF;border-color:#0B7F89;}"
        )
        name_help = QLabel("This is the name members will see in the workspace switcher.")
        name_help.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        form_box.addWidget(name_label)
        form_box.addWidget(self.name_input)
        form_box.addWidget(name_help)

        seats_row = QHBoxLayout()
        seats_row.setSpacing(14)
        seats_copy = QVBoxLayout()
        seats_copy.setSpacing(3)
        seats_label = QLabel("Team size / seats")
        seats_label.setStyleSheet(f"color:{INK};font-size:10px;font-weight:850;border:none;")
        seats_help = QLabel(
            "A seat is one active person in this company workspace, including you. "
            "For example, 5 seats = you + up to 4 teammates."
        )
        seats_help.setWordWrap(True)
        seats_help.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
        seats_copy.addWidget(seats_label)
        seats_copy.addWidget(seats_help)
        seats_row.addLayout(seats_copy, 1)

        self.seats_input = QSpinBox()
        self.seats_input.setRange(2, 100)
        self.seats_input.setValue(5)
        self.seats_input.setSuffix(" seats")
        self.seats_input.setMinimumWidth(132)
        self.seats_input.setMinimumHeight(44)
        self.seats_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seats_input.setStyleSheet(
            "QSpinBox{background:#F8FBFC;color:#17384E;border:1px solid #C9D7E0;border-radius:10px;"
            "padding:8px 10px;font-size:11px;font-weight:850;}QSpinBox:focus{background:#FFFFFF;border-color:#0B7F89;}"
        )
        seats_row.addWidget(self.seats_input, 0, Qt.AlignmentFlag.AlignVCenter)
        form_box.addLayout(seats_row)

        self.seat_summary = QLabel()
        self.seat_summary.setWordWrap(True)
        self.seat_summary.setStyleSheet(
            "background:#EEF8F8;color:#426675;border:none;border-radius:9px;padding:9px;font-size:8px;"
        )
        form_box.addWidget(self.seat_summary)
        root.addWidget(form)

        benefits = QHBoxLayout()
        benefits.setSpacing(8)
        for heading, detail in (
            ("You become Owner", "You can manage policy, members and devices."),
            ("Policy ready", "A starter company privacy policy is created automatically."),
            ("2 devices / member", "Each member can initially use up to two managed devices."),
        ):
            card = QFrame()
            card.setStyleSheet("QFrame{background:#F8FBFC;border:1px solid #E5ECEF;border-radius:10px;}")
            box = QVBoxLayout(card)
            box.setContentsMargins(10, 9, 10, 9)
            box.setSpacing(2)
            head = QLabel(heading)
            head.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:900;border:none;")
            note = QLabel(detail)
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};font-size:8px;border:none;")
            box.addWidget(head)
            box.addWidget(note)
            benefits.addWidget(card, 1)
        root.addLayout(benefits)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setMinimumHeight(42)
        cancel.setStyleSheet(
            "QPushButton{background:#F4F7F9;color:#17384E;border:1px solid #DCE5EA;border-radius:10px;"
            "padding:9px 16px;font-size:10px;font-weight:800;}QPushButton:hover{background:#EAF0F3;}"
        )
        self.create_button = QPushButton("Create workspace")
        self.create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_button.setMinimumHeight(42)
        self.create_button.setEnabled(False)
        self.create_button.setStyleSheet(
            "QPushButton{background:#0B7F89;color:#FFFFFF;border:none;border-radius:10px;"
            "padding:9px 18px;font-size:10px;font-weight:850;}QPushButton:hover{background:#096D76;}"
            "QPushButton:disabled{background:#DCE6E9;color:#91A0AA;}"
        )
        actions.addWidget(cancel)
        actions.addWidget(self.create_button)
        root.addLayout(actions)

        cancel.clicked.connect(self.reject)
        self.create_button.clicked.connect(self.accept)
        self.name_input.textChanged.connect(self._sync)
        self.seats_input.valueChanged.connect(self._sync)
        self.name_input.returnPressed.connect(
            lambda: self.accept() if self.create_button.isEnabled() else None
        )
        self._sync()

    def _sync(self, *_args) -> None:
        seats = self.seats_input.value()
        teammates = max(1, seats - 1)
        self.seat_summary.setText(
            f"{seats} seats means 1 owner + up to {teammates} teammate{'s' if teammates != 1 else ''}. "
            "This is an access limit, not a billing charge in this screen."
        )
        self.create_button.setEnabled(2 <= len(self.name_input.text().strip()) <= 120)

    def values(self) -> tuple[str, int]:
        return self.name_input.text().strip(), int(self.seats_input.value())


def _clean_service_error(message: str) -> str:
    text = " ".join(str(message or "").split())
    if "TeamServiceError:" in text:
        text = text.split("TeamServiceError:", 1)[1].strip()
    if "function digest(" in text and "does not exist" in text:
        return (
            "The workspace service could not finish its secure setup. The database configuration has been repaired; "
            "please try Create workspace again."
        )
    if not text:
        return "PrivacyGate could not create the workspace. Please try again."
    return text


def _create_workspace(self) -> None:
    if not self._require_signed_in():
        return

    dialog = CreateBusinessWorkspaceDialog(self)
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
            team_page._apply_state(result)
            QTimer.singleShot(0, team_page.refresh_silent)
            QTimer.singleShot(250, self.refresh)
        QMessageBox.information(
            self,
            "Workspace created",
            f"{name} is ready. You are the Owner and the workspace is now available in the workspace selector.",
        )

    def failed(message: str) -> None:
        QMessageBox.warning(
            self,
            "Workspace could not be created",
            _clean_service_error(message)
            + "\n\nNothing was changed. You can adjust the company name or team size and try again.",
        )

    def finished() -> None:
        team_page._worker_finished()
        self.create_button.setEnabled(True)

    worker.signals.result.connect(ready)
    worker.signals.error.connect(failed)
    worker.signals.finished.connect(finished)
    team_page.thread_pool.start(worker)


def apply_workspace_creation_experience(main_window) -> None:
    """Upgrade workspace creation without changing workspace semantics."""
    settings = getattr(main_window, "settings_page", None)
    panel = (
        getattr(settings, "_privacygate_workspace_settings_panel", None)
        if settings is not None
        else None
    )
    if panel is None or bool(getattr(panel, "_privacygate_creation_experience", False)):
        return

    panel._create_workspace = MethodType(_create_workspace, panel)
    try:
        panel.create_button.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass
    panel.create_button.clicked.connect(panel._create_workspace)
    panel.create_button.setText("Create Business workspace")
    panel.create_button.setToolTip(
        "Create a company workspace and choose the number of active member seats"
    )
    panel._privacygate_creation_experience = True
