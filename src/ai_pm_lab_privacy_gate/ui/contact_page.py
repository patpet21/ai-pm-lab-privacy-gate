from __future__ import annotations

import httpx
from PySide6.QtCore import QProcess, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ai_pm_lab_privacy_gate import __version__
from ai_pm_lab_privacy_gate.infrastructure.updates.store_update_service import (
    StoreUpdateService,
    is_store_packaged_install,
)
from ai_pm_lab_privacy_gate.infrastructure.updates.update_service import UpdateService
from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker


class ContactPage(QWidget):
    FORM_ENDPOINT = "https://formspree.io/f/mkodolrn"
    update_available = Signal(object)
    store_update_event = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self._store_versions_attempted: set[str] = set()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)
        root.addWidget(QLabel("Contact & Custom Workflows", objectName="PageTitle"))
        intro = QLabel(
            "Privacy Gate is free and local-first. AI PM LAB can help design optional n8n, MCP, "
            "document, email and real-estate workflows around it.", objectName="Muted"
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        grid = QGridLayout()
        grid.setSpacing(12)
        offerings = (
            ("Workflow design", "n8n, email intake, watched folders and document routing."),
            ("AI connections", "ChatGPT, Claude, MCP and protected business knowledge."),
            ("Real-estate operations", "Property Management, Brokerage and Project/Renovation workflows."),
        )
        for index, (title, text) in enumerate(offerings):
            card = QFrame(objectName="ConnectionCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(4)
            layout.addWidget(QLabel(title, objectName="SectionTitle"))
            description = QLabel(text, objectName="Muted")
            description.setWordWrap(True)
            layout.addWidget(description)
            card.setMaximumHeight(92)
            grid.addWidget(card, 0, index)
        root.addLayout(grid)
        form = QFrame(objectName="Card")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(16, 12, 16, 12)
        form_layout.setSpacing(7)
        form_layout.addWidget(QLabel("Tell us what you want to automate", objectName="SectionTitle"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name or company")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Your Email")
        self.message_input = QPlainTextEdit()
        self.message_input.setPlaceholderText("Describe the workflow, documents and tools you use.")
        self.message_input.setMinimumHeight(76)
        self.message_input.setMaximumHeight(96)
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(self.email_input)
        form_layout.addWidget(self.message_input)
        buttons = QHBoxLayout()
        self.send_button = QPushButton("Send request", objectName="Primary")
        ai_pm_lab = QPushButton("Visit AI PM LAB", objectName="Secondary")
        framework = QPushButton("Explore PropertyDex Framework", objectName="Secondary")
        self.update_button = QPushButton("Check for updates", objectName="Secondary")
        for button in (self.send_button, ai_pm_lab, framework):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.update_button)
        form_layout.addLayout(buttons)
        root.addWidget(form)
        root.addStretch(1)
        self.send_button.clicked.connect(self._submit)
        ai_pm_lab.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://aipmlab.propertydex.xyz")))
        framework.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://framework.propertydex.xyz/?open=signup")))
        self.update_button.clicked.connect(lambda: self.check_updates(silent=False))

    def _run(self, function, on_result, on_error, on_finished) -> None:
        worker = FunctionWorker(function)
        self._workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        worker.signals.finished.connect(lambda: self._workers.discard(worker))
        self.thread_pool.start(worker)

    def _submit(self) -> None:
        email = self.email_input.text().strip()
        message = self.message_input.toPlainText().strip()
        if "@" not in email or not message:
            QMessageBox.information(self, "Contact form", "Enter a valid email and a short message.")
            return
        payload = {"name": self.name_input.text().strip(), "email": email, "message": message, "source": "Privacy Gate desktop"}
        self._busy(self.send_button, "Sending…")
        def submit():
            response = httpx.post(self.FORM_ENDPOINT, data=payload, headers={"Accept": "application/json"}, timeout=10)
            response.raise_for_status()
            return True
        self._run(
            submit,
            lambda _result: self._submitted(),
            lambda error: QMessageBox.critical(self, "Unable to send", error),
            lambda: self._ready(self.send_button, "Send request"),
        )

    def _submitted(self) -> None:
        self.message_input.clear()
        QMessageBox.information(self, "Request sent", "Thank you. Pietro will reply to the email you provided.")

    def check_updates(self, silent: bool = True) -> None:
        self._busy(self.update_button, "Checking…")
        self._run(
            lambda: UpdateService().check(__version__),
            lambda result: self._show_update_result(result, silent),
            lambda error: None if silent else QMessageBox.warning(self, "Update check unavailable", error),
            lambda: self._ready(self.update_button, "Check for updates"),
        )

    def _show_update_result(self, result, silent: bool) -> None:
        if result is None:
            if not silent:
                QMessageBox.information(self, "PrivacyGate updates", f"Version {__version__} is current.")
            return
        if is_store_packaged_install():
            # release.json is the trigger; StoreContext is queried only after a
            # newer PrivacyGate release is known to exist.
            if silent and result.version in self._store_versions_attempted:
                return
            self._store_versions_attempted.add(result.version)
            self._try_store_silent_update(result, silent)
            return
        if silent:
            self.update_available.emit(result)
            return
        self.show_update_dialog(result)

    def _try_store_silent_update(self, release, silent: bool) -> None:
        self._busy(self.update_button, "Updating…")
        self._run(
            lambda: StoreUpdateService().try_silent_update(),
            lambda result: self._handle_store_result(result, release, silent),
            lambda error: self._handle_store_result(
                type("StoreError", (), {"status": "error", "message": error})(), release, silent
            ),
            lambda: self._ready(self.update_button, "Check for updates"),
        )

    def _handle_store_result(self, result, release, silent: bool) -> None:
        event = {
            "status": result.status,
            "message": result.message,
            "release": release,
        }
        if silent:
            self.store_update_event.emit(event)
        else:
            self.show_store_update_event(event)

    def show_store_update_event(self, event) -> None:
        status = event["status"]
        message = event.get("message", "")
        release = event["release"]

        if status == "installed":
            box = QMessageBox(self)
            box.setWindowTitle("PrivacyGate update installed")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"PrivacyGate {release.version} has been installed by Microsoft Store.")
            box.setInformativeText(
                "Restart PrivacyGate to use the new version. Your local Library and mappings remain on this device."
            )
            restart = box.addButton("Restart PrivacyGate", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is restart:
                QProcess.startDetached(QApplication.applicationFilePath(), [])
                QApplication.quit()
            return

        if status == "action_required":
            box = QMessageBox(self)
            box.setWindowTitle("PrivacyGate update ready")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"PrivacyGate {release.version} is ready to install.")
            box.setInformativeText(
                message or "Windows requires confirmation to complete this Microsoft Store update."
            )
            install = box.addButton("Install update", QMessageBox.ButtonRole.AcceptRole)
            open_store = box.addButton("Open Microsoft Store", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is install:
                self._install_store_update(release)
            elif box.clickedButton() is open_store:
                QDesktopServices.openUrl(QUrl(release.store_url))
            return

        if status == "preparing":
            box = QMessageBox(self)
            box.setWindowTitle("Microsoft Store is preparing the update")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"PrivacyGate {release.version} has been released, but Microsoft Store is not serving it to this device yet.")
            box.setInformativeText(
                "PrivacyGate will try again the next time the release check runs. You do not need to reinstall the app."
            )
            open_store = box.addButton("Open Microsoft Store", QMessageBox.ButtonRole.ActionRole)
            box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            box.exec()
            if box.clickedButton() is open_store:
                QDesktopServices.openUrl(QUrl(release.store_url))
            return

        if status == "canceled":
            QMessageBox.information(self, "PrivacyGate update", "The Microsoft Store update was canceled. You can try again later.")
            return

        box = QMessageBox(self)
        box.setWindowTitle("Microsoft Store update unavailable")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("PrivacyGate could not complete the Microsoft Store update right now.")
        box.setInformativeText(message or "You can retry later or open the Microsoft Store page.")
        open_store = box.addButton("Open Microsoft Store", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_store:
            QDesktopServices.openUrl(QUrl(release.store_url))

    def _install_store_update(self, release) -> None:
        self._busy(self.update_button, "Installing…")
        self._run(
            lambda: StoreUpdateService().install_with_store_ui(),
            lambda result: self.show_store_update_event({
                "status": result.status,
                "message": result.message,
                "release": release,
            }),
            lambda error: self.show_store_update_event({
                "status": "error",
                "message": error,
                "release": release,
            }),
            lambda: self._ready(self.update_button, "Check for updates"),
        )

    def show_update_dialog(self, result) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("PrivacyGate update available")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"PrivacyGate {result.version} is available.")
        box.setInformativeText(
            "This installation is not managed by Microsoft Store. Open the PrivacyGate website for the current Windows EXE or macOS download. Your local Library and mappings remain on this device."
        )
        website_button = box.addButton("PrivacyGate website", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is website_button:
            QDesktopServices.openUrl(QUrl(result.website_url))

    @staticmethod
    def _busy(button: QPushButton, text: str) -> None:
        button.setEnabled(False)
        button.setText(text)

    @staticmethod
    def _ready(button: QPushButton, text: str) -> None:
        button.setEnabled(True)
        button.setText(text)
