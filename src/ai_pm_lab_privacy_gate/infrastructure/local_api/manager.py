from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)
from ai_pm_lab_privacy_gate.infrastructure.settings.preferences import (
    AppPreferences,
    PreferencesStore,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import (
    AiLibraryRepository,
)

from .browser_ai_persistence import install_browser_ai_persistence
from .browser_docx import install_browser_docx_support
from .browser_origin_compat import install_browser_origin_compat
from .browser_pairing import (
    BrowserPairingChallenge,
    BrowserPairingRegistry,
    BrowserPairingStatus,
)
from .browser_pdf import install_browser_pdf_support
from .browser_pdf_review import install_browser_pdf_review
from .browser_revoke import install_browser_revoke_support
from .server import create_local_api_server


LOCAL_API_AUTH_TOKEN_SECRET = "local-api-auth-token-v1"


@dataclass(frozen=True, slots=True)
class LocalApiStatus:
    state: str = "disabled"  # disabled | online | error
    port: int | None = None
    error: str = ""


class LocalApiManager:
    """Own the opt-in localhost bridge for the lifetime of the desktop app."""

    def __init__(
        self,
        service: PrivacyGateService,
        data_dir: str | Path,
        *,
        secret_store: SecretStore | None = None,
        server_factory: Callable[..., Any] = create_local_api_server,
        allowed_origins: tuple[str, ...] = (),
    ) -> None:
        self.service = service
        self.data_dir = Path(data_dir)
        self.preferences = PreferencesStore(self.data_dir)
        self.secrets = secret_store or platform_secret_store(self.data_dir)
        self.browser_pairing = BrowserPairingRegistry(self.secrets)
        # Uses the same library.db as Personal Library, but dedicated AI tables.
        # Real values and protected chat text are encrypted with LocalProtector.
        self.ai_library = AiLibraryRepository(self.data_dir)
        self._server_factory = server_factory
        self.allowed_origins = tuple(allowed_origins)
        self._lock = threading.RLock()
        self._server: Any | None = None
        self._thread: threading.Thread | None = None
        self._status = LocalApiStatus()

    @property
    def status(self) -> LocalApiStatus:
        with self._lock:
            return self._status

    @property
    def browser_pairing_status(self) -> BrowserPairingStatus:
        return self.browser_pairing.status()

    def create_browser_pairing_code(self) -> BrowserPairingChallenge:
        return self.browser_pairing.create_challenge()

    def revoke_browser_pairings(self) -> None:
        self.browser_pairing.revoke()

    def apply_preferences(self, prefs: AppPreferences | None = None) -> LocalApiStatus:
        selected = prefs or self.preferences.load()
        if not selected.local_api_enabled:
            self.stop()
            return self.status
        return self.start(selected.local_api_port)

    def start(self, port: int) -> LocalApiStatus:
        port = int(port)
        if not 1024 <= port <= 65535:
            raise ValueError("Local Privacy Bridge port must be between 1024 and 65535")
        with self._lock:
            if self._status.state == "online" and self._status.port == port:
                return self._status
        self.stop()
        try:
            token = self._get_or_create_auth_token()
            server = self._server_factory(
                service=self.service,
                host="127.0.0.1",
                port=port,
                auth_token=token,
                allowed_origins=self.allowed_origins,
                browser_pairing=self.browser_pairing,
            )
            # Keep production on the already validated browser stack. File support
            # is layered onto the same authenticated localhost transport so PDF and
            # Word never need their own cloud service or browser credential.
            install_browser_origin_compat(server)
            install_browser_ai_persistence(server, self.ai_library)
            install_browser_pdf_support(server)
            install_browser_pdf_review(server)
            install_browser_docx_support(server)
            # Disconnecting one extension now revokes that exact scoped browser
            # credential on the desktop without affecting other paired browsers.
            install_browser_revoke_support(server)
        except Exception as error:
            with self._lock:
                self._status = LocalApiStatus(
                    state="error",
                    port=port,
                    error=f"{type(error).__name__}: {error}",
                )
                return self._status

        def serve() -> None:
            try:
                server.serve_forever(poll_interval=0.25)
            except Exception as error:
                with self._lock:
                    if self._server is server:
                        self._server = None
                        self._thread = None
                        self._status = LocalApiStatus(
                            state="error",
                            port=port,
                            error=f"{type(error).__name__}: {error}",
                        )

        thread = threading.Thread(
            target=serve,
            name="PrivacyGateLocalPrivacyBridge",
            daemon=True,
        )
        with self._lock:
            self._server = server
            self._thread = thread
            self._status = LocalApiStatus(state="online", port=int(server.server_port))
        thread.start()
        return self.status

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self._status = LocalApiStatus(state="disabled")
        if server is None:
            return
        try:
            server.shutdown()
        finally:
            server.server_close()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _get_or_create_auth_token(self) -> str:
        current = self.secrets.get(LOCAL_API_AUTH_TOKEN_SECRET)
        if current and len(current) >= 24:
            return current
        token = secrets.token_urlsafe(32)
        self.secrets.set(LOCAL_API_AUTH_TOKEN_SECRET, token)
        return token
