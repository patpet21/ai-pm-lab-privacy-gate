from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen, QVBoxLayout


INSTANCE_SERVER_NAME = "AI_PM_LAB_Privacy_Gate_0_4"


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


def _startup_splash(logo_path, app_icon: QIcon) -> tuple[QSplashScreen, QLabel, QLabel]:
    """Create one persistent startup surface with live busy feedback."""
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

    # Add dedicated space below the existing brand artwork instead of drawing
    # startup controls over it.
    width = max(560, logo.width() + 40)
    canvas = QPixmap(width, logo.height() + 130)
    canvas.fill(QColor("#ffffff"))
    painter = QPainter(canvas)
    painter.drawPixmap((width - logo.width()) // 2, 8, logo)
    painter.end()

    splash = QSplashScreen(canvas)
    if not app_icon.isNull():
        splash.setWindowIcon(app_icon)

    layout = QVBoxLayout(splash)
    layout.setContentsMargins(46, 20, 46, 22)
    layout.setSpacing(8)
    layout.addStretch(1)

    status = QLabel("Starting local privacy protection…", splash)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setStyleSheet(
        "QLabel{background:transparent;color:#06243C;font-size:14px;font-weight:800;}"
    )
    layout.addWidget(status)

    progress = QProgressBar(splash)
    progress.setRange(0, 0)
    progress.setTextVisible(False)
    progress.setFixedHeight(7)
    progress.setStyleSheet(
        "QProgressBar{background:#E7EEF2;border:0;border-radius:3px;}"
        "QProgressBar::chunk{background:#0B7F89;border-radius:3px;}"
    )
    layout.addWidget(progress)

    hint = QLabel("PrivacyGate is starting. The app will open shortly.", splash)
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet(
        "QLabel{background:transparent;color:#61798A;font-size:11px;font-weight:600;}"
    )
    layout.addWidget(hint)

    return splash, status, hint


def main() -> int:
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

    from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
    from ai_pm_lab_privacy_gate.ui.resources import resource_path
    from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE

    install_app_font(app)
    app.setStyleSheet(APP_STYLE)

    # Set the PrivacyGate application icon before the splash/main window appears.
    # Source runs otherwise briefly inherit the generic Python/Qt window icon on
    # Windows even though the packaged executable has the correct embedded icon.
    icon_path = resource_path("resources", "branding", "privacy-gate.ico")
    if not icon_path.exists():
        icon_path = resource_path("resources", "branding", "privacy-gate-icon.png")
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    splash: QSplashScreen | None = None
    splash_status: QLabel | None = None
    splash_hint: QLabel | None = None
    if not background_start:
        logo_path = resource_path("resources", "branding", "privacy-gate-logo.png")
        splash, splash_status, splash_hint = _startup_splash(logo_path, app_icon)
        splash.show()
        app.processEvents()

    def update_startup(message: str, hint: str | None = None) -> None:
        if splash is None:
            return
        if splash_status is not None:
            splash_status.setText(message)
        if hint is not None and splash_hint is not None:
            splash_hint.setText(hint)
        app.processEvents()

    # Import the full UI only after the user can see immediate startup feedback.
    # Presidio itself remains lazy and is loaded on the first analysis.
    update_startup("Loading PrivacyGate interface…")
    from ai_pm_lab_privacy_gate.infrastructure.local_api.manager import LocalApiManager
    from ai_pm_lab_privacy_gate.ui.main_window import MainWindow
    from ai_pm_lab_privacy_gate.ui.settings_services_cleanup_2026 import (
        apply_settings_services_cleanup_2026,
    )

    update_startup("Preparing your workspace…")
    window = MainWindow()
    local_api = LocalApiManager(window.service, window.library.data_dir)
    window.local_api_manager = local_api
    window.settings_page.local_api_manager = local_api

    # Keep the Settings ownership cleanup UI-only. The existing MCP runtime,
    # account, tunnel and device connection paths are left untouched.
    apply_settings_services_cleanup_2026(window)

    def apply_local_api_preferences() -> None:
        local_api.apply_preferences(window.preferences.load())
        window.settings_page.refresh_local_api_status()

    # Only Local Privacy Bridge changes should start/stop/reconfigure the bridge.
    # Desktop and MCP settings still share the same local preferences file, but no
    # longer trigger LocalApiManager lifecycle work.
    window.settings_page.local_api_preferences_changed.connect(apply_local_api_preferences)
    update_startup("Starting local services…")
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
        update_startup(
            "Opening PrivacyGate…",
            "The app will open shortly. You do not need to click the icon again.",
        )

        # Let the real Qt event loop start before dismissing the splash. This keeps
        # startup feedback visible through the complete synchronous initialization
        # path and avoids the previous gap where the splash vanished just before the
        # main window became interactive.
        def reveal_main_window() -> None:
            window.showMaximized()
            window.raise_()
            window.activateWindow()
            if splash is not None:
                splash.finish(window)

        QTimer.singleShot(0, reveal_main_window)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
