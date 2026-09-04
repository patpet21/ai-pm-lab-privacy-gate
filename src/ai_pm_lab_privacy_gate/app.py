from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
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
    """Create a branded startup surface with no blank white first frame."""

    width, height = 560, 360
    canvas = QPixmap(width, height)
    canvas.fill(QColor("#061F33"))

    # Prefer the compact application mark so the splash never inherits a white
    # background from a full-width logo asset. Fall back to the supplied logo only
    # when no application icon is available.
    mark = app_icon.pixmap(92, 92) if not app_icon.isNull() else QPixmap()
    if mark.isNull() and logo_path.exists():
        mark = QPixmap(str(logo_path))
        if not mark.isNull():
            mark = mark.scaled(
                92,
                92,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    painter = QPainter(canvas)
    if not mark.isNull():
        painter.drawPixmap((width - mark.width()) // 2, 38, mark)
    painter.fillRect(0, height - 5, width, 5, QColor("#0B858A"))
    painter.end()

    splash = QSplashScreen(canvas)
    if not app_icon.isNull():
        splash.setWindowIcon(app_icon)

    layout = QVBoxLayout(splash)
    layout.setContentsMargins(46, 146, 46, 28)
    layout.setSpacing(9)

    brand = QLabel("PRIVACY GATE", splash)
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    brand.setStyleSheet(
        "QLabel{background:transparent;color:#FFFFFF;font-size:23px;font-weight:950;letter-spacing:2px;}"
    )
    layout.addWidget(brand)

    status = QLabel("Preparing your local privacy workspace…", splash)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setStyleSheet(
        "QLabel{background:transparent;color:#D9E8EE;font-size:13px;font-weight:750;}"
    )
    layout.addWidget(status)

    progress = QProgressBar(splash)
    # Indeterminate means exactly what startup knows: work is still running. No
    # invented percentage is shown and the splash lifetime is tied to readiness.
    progress.setRange(0, 0)
    progress.setTextVisible(False)
    progress.setFixedHeight(8)
    progress.setStyleSheet(
        "QProgressBar{background:#17384E;border:0;border-radius:4px;}"
        "QProgressBar::chunk{background:#19A7A7;border-radius:4px;}"
    )
    layout.addWidget(progress)

    hint = QLabel(
        "Everything is being prepared locally.\n"
        "This screen closes automatically when PrivacyGate is ready.",
        splash,
    )
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet(
        "QLabel{background:transparent;color:#8EABB8;font-size:10px;font-weight:600;}"
    )
    layout.addWidget(hint)
    layout.addStretch(1)
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
    from ai_pm_lab_privacy_gate.ui.settings_browser_protection_polish import (
        apply_browser_protection_product_polish,
    )
    from ai_pm_lab_privacy_gate.ui.settings_services_cleanup_2026 import (
        apply_settings_services_cleanup_2026,
    )
    from ai_pm_lab_privacy_gate.ui.startup_stability_2026 import (
        install_startup_stability_2026,
    )

    # This must be installed after the UI package has assembled its runtime layers
    # but before the first MainWindow instance executes those layers.
    install_startup_stability_2026()

    window = MainWindow()
    window._privacygate_startup_ready = bool(background_start)
    local_api = LocalApiManager(
        window.service,
        window.library.data_dir,
    )
    window.local_api_manager = local_api
    window.settings_page.local_api_manager = local_api

    apply_settings_services_cleanup_2026(window)
    apply_browser_protection_product_polish(window)

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
        # MainWindow construction intentionally stays hidden behind the independent
        # splash. The old code showed the window and only then processed events,
        # exposing deferred-delete rows and intermediate layout generations.
        window.setUpdatesEnabled(False)
        controller = getattr(window, "_unified_loading", None)

        def startup_operation_active() -> bool:
            try:
                return bool(controller is not None and controller.active())
            except RuntimeError:
                return False

        def keep_startup_dialog_hidden() -> None:
            if controller is None:
                return
            try:
                controller.dialog.dismiss()
            except RuntimeError:
                pass

        def signal_ready_after_first_paint() -> None:
            # A worker may have entered a real busy state between showMaximized()
            # and the first paint. Keep the startup splash until that work ends.
            if startup_operation_active():
                keep_startup_dialog_hidden()
                QTimer.singleShot(40, signal_ready_after_first_paint)
                return

            window._privacygate_startup_ready = True
            if controller is not None:
                controller._render()
            _signal_startup_complete(startup_sentinel)

            if startup_sentinel is not None:
                def cleanup_startup_sentinel() -> None:
                    startup_sentinel.unlink(missing_ok=True)

                QTimer.singleShot(1500, cleanup_startup_sentinel)

        def show_when_startup_is_quiet() -> None:
            if startup_operation_active():
                keep_startup_dialog_hidden()
                QTimer.singleShot(40, show_when_startup_is_quiet)
                return

            # Flush every widget scheduled by earlier presentation-layer refreshes
            # while the real window is still invisible. This prevents the transient
            # duplicate/overlapping labels visible in the startup screenshot.
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            try:
                window.ensurePolished()
                central = window.centralWidget()
                if central is not None and central.layout() is not None:
                    central.layout().activate()
            except RuntimeError:
                pass

            window.setUpdatesEnabled(True)
            window.showMaximized()
            window.raise_()
            window.activateWindow()

            # Do not close the splash merely because showMaximized() returned.
            # Waiting one event-loop turn gives Qt a real first paint/layout pass.
            QTimer.singleShot(0, signal_ready_after_first_paint)

        QTimer.singleShot(0, show_when_startup_is_quiet)

    window._startup_splash_process = startup_process
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
