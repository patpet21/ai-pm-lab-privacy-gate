from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen, QVBoxLayout


INSTANCE_SERVER_NAME = "AI_PM_LAB_Privacy_Gate_0_4"
STARTUP_SPLASH_WORKER_ARG = "--startup-splash-worker"


def _single_instance_enabled() -> bool:
    """Keep production single-instance behavior without hiding source test builds.

    Packaged PrivacyGate builds should remain single-instance. During local branch
    testing, however, an already-running Store/packaged instance must not swallow a
    fresh ``python -m ai_pm_lab_privacy_gate.app`` launch and make the tester see an
    older UI. Source runs therefore start their own process by default.

    Set PRIVACY_GATE_SINGLE_INSTANCE=1 to restore single-instance behavior while
    running from source when that is specifically desired.
    """
    if os.environ.get("PRIVACY_GATE_SINGLE_INSTANCE") == "1":
        return True
    return bool(getattr(sys, "frozen", False))


def _notify_running_instance(*, show_window: bool) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_SERVER_NAME)
    if not socket.waitForConnected(350):
        return False
    socket.write(b"show" if show_window else b"ping")
    socket.flush()
    socket.waitForBytesWritten(350)
    socket.disconnectFromServer()
    return True


def _packaged_smoke_test() -> int:
    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.domain.profiles import get_profile

    text = "Contact Jane Smith at jane.smith@example.com or 212-555-5555. SSN 219-09-9999."
    service = PrivacyGateService()
    document = service.document_from_text(text)
    findings = service.analyze(document, get_profile("property_management"))
    protected = service.protect(document, findings).combined_text
    required = {"EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"}
    found = {item.entity_type for item in findings}
    return 0 if required <= found and "jane.smith@example.com" not in protected else 2


def _startup_splash(logo_path: Path, app_icon: QIcon) -> QSplashScreen:
    """Create the startup surface used by the independent splash worker."""
    logo = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap(560, 260)
    if logo.isNull():
        logo = QPixmap(560, 260)
        logo.fill(QColor("#ffffff"))
    else:
        logo = logo.scaled(
            520,
            280,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    width = max(560, logo.width() + 40)
    canvas = QPixmap(width, logo.height() + 190)
    canvas.fill(QColor("#ffffff"))
    painter = QPainter(canvas)
    painter.drawPixmap((width - logo.width()) // 2, 8, logo)
    painter.end()

    splash = QSplashScreen(canvas)
    if not app_icon.isNull():
        splash.setWindowIcon(app_icon)

    layout = QVBoxLayout(splash)
    layout.setContentsMargins(46, 18, 46, 24)
    layout.setSpacing(7)
    layout.addStretch(1)

    brand = QLabel("PRIVACY GATE", splash)
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    brand.setStyleSheet(
        "QLabel{background:transparent;color:#06243C;font-size:21px;font-weight:950;letter-spacing:2px;}"
    )
    layout.addWidget(brand)

    status = QLabel("Starting local privacy protection…", splash)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setStyleSheet(
        "QLabel{background:transparent;color:#17384E;font-size:13px;font-weight:750;}"
    )
    layout.addWidget(status)

    progress = QProgressBar(splash)
    progress.setRange(0, 0)
    progress.setTextVisible(False)
    progress.setFixedHeight(8)
    progress.setStyleSheet(
        "QProgressBar{background:#E5EDF1;border:0;border-radius:4px;}"
        "QProgressBar::chunk{background:#0B7F89;border-radius:4px;}"
    )
    layout.addWidget(progress)

    hint = QLabel(
        "PrivacyGate is starting. The app will open shortly.\n"
        "You do not need to click the icon again.",
        splash,
    )
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet(
        "QLabel{background:transparent;color:#61798A;font-size:10px;font-weight:600;}"
    )
    layout.addWidget(hint)
    return splash


def _process_is_alive(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if sys.platform == "win32":
        try:
            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, int(process_id)
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return True
    try:
        os.kill(int(process_id), 0)
    except OSError:
        return False
    return True


def _run_startup_splash_worker(parent_pid: int, sentinel_path: Path) -> int:
    """Animate startup feedback independently from the main UI initialization."""
    app = QApplication([sys.argv[0]])
    app.setApplicationName("AI PM LAB Privacy Gate Startup")
    app.setOrganizationName("AI PM LAB")

    from ai_pm_lab_privacy_gate.ui.resources import resource_path

    icon_path = resource_path("resources", "branding", "privacy-gate.ico")
    if not icon_path.exists():
        icon_path = resource_path("resources", "branding", "privacy-gate-icon.png")
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
    splash = _startup_splash(logo_path, app_icon)
    splash.show()
    splash.raise_()
    app.processEvents()

    monitor = QTimer(splash)
    monitor.setInterval(100)

    def finish_if_ready() -> None:
        if sentinel_path.exists() or not _process_is_alive(parent_pid):
            splash.close()
            app.quit()

    monitor.timeout.connect(finish_if_ready)
    monitor.start()
    QTimer.singleShot(120_000, app.quit)
    return app.exec()


def _start_startup_splash_process() -> tuple[subprocess.Popen[bytes] | None, Path | None]:
    sentinel = Path(tempfile.gettempdir()) / (
        f"privacygate-startup-{os.getpid()}-{uuid.uuid4().hex}.ready"
    )
    sentinel.unlink(missing_ok=True)

    if getattr(sys, "frozen", False):
        command = [
            sys.executable,
            STARTUP_SPLASH_WORKER_ARG,
            str(os.getpid()),
            str(sentinel),
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "ai_pm_lab_privacy_gate.app",
            STARTUP_SPLASH_WORKER_ARG,
            str(os.getpid()),
            str(sentinel),
        ]

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            env=os.environ.copy(),
        )
    except OSError:
        return None, None
    return process, sentinel


def _signal_startup_complete(sentinel: Path | None) -> None:
    if sentinel is None:
        return
    try:
        sentinel.write_text("ready", encoding="utf-8")
    except OSError:
        return


def main() -> int:
    if STARTUP_SPLASH_WORKER_ARG in sys.argv:
        try:
            index = sys.argv.index(STARTUP_SPLASH_WORKER_ARG)
            parent_pid = int(sys.argv[index + 1])
            sentinel_path = Path(sys.argv[index + 2])
        except (ValueError, IndexError):
            return 2
        return _run_startup_splash_worker(parent_pid, sentinel_path)

    if os.environ.get("PRIVACY_GATE_SMOKE_TEST") == "1":
        return _packaged_smoke_test()
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AIPMLAB.PrivacyGate.0.1")
        except Exception:
            pass
    background_start = "--background" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("AI PM LAB Privacy Gate")
    app.setOrganizationName("AI PM LAB")

    single_instance = _single_instance_enabled()
    if single_instance and _notify_running_instance(show_window=not background_start):
        return 0

    instance_server: QLocalServer | None = None
    if single_instance:
        instance_server = QLocalServer(app)
        QLocalServer.removeServer(INSTANCE_SERVER_NAME)
        if not instance_server.listen(INSTANCE_SERVER_NAME):
            return 1

    startup_process: subprocess.Popen[bytes] | None = None
    startup_sentinel: Path | None = None
    if not background_start:
        startup_process, startup_sentinel = _start_startup_splash_process()

    from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
    from ai_pm_lab_privacy_gate.ui.resources import resource_path
    from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE

    install_app_font(app)
    app.setStyleSheet(APP_STYLE)

    icon_path = resource_path("resources", "branding", "privacy-gate.ico")
    if not icon_path.exists():
        icon_path = resource_path("resources", "branding", "privacy-gate-icon.png")
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    from ai_pm_lab_privacy_gate.infrastructure.local_api.manager import LocalApiManager
    from ai_pm_lab_privacy_gate.ui.main_window import MainWindow
    from ai_pm_lab_privacy_gate.ui.settings_services_cleanup_2026 import (
        apply_settings_services_cleanup_2026,
    )

    window = MainWindow()
    local_api = LocalApiManager(
        window.service,
        window.library.data_dir,
    )
    window.local_api_manager = local_api
    window.settings_page.local_api_manager = local_api

    apply_settings_services_cleanup_2026(window)

    def apply_local_api_preferences() -> None:
        local_api.apply_preferences(window.preferences.load())
        window.settings_page.refresh_local_api_status()

    window.settings_page.local_api_preferences_changed.connect(apply_local_api_preferences)
    apply_local_api_preferences()
    app.aboutToQuit.connect(local_api.stop)

    if not app_icon.isNull():
        window.setWindowIcon(app_icon)

    if instance_server is not None:
        def show_existing_window() -> None:
            while instance_server.hasPendingConnections():
                connection = instance_server.nextPendingConnection()
                if connection is None:
                    continue
                connection.waitForReadyRead(350)
                message = bytes(connection.readAll())
                if message == b"show":
                    window.show_from_background()
                connection.disconnectFromServer()

        instance_server.newConnection.connect(show_existing_window)

    if not background_start:
        window.showMaximized()
        window.raise_()
        window.activateWindow()
        app.processEvents()
        _signal_startup_complete(startup_sentinel)

        if startup_sentinel is not None:
            def cleanup_startup_sentinel() -> None:
                startup_sentinel.unlink(missing_ok=True)

            QTimer.singleShot(1500, cleanup_startup_sentinel)

    window._startup_splash_process = startup_process
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
