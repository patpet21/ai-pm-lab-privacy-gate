from __future__ import annotations

import socket
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.detection_pack import build_detection_pack
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)
from ai_pm_lab_privacy_gate.infrastructure.storage.protected_library import (
    ProtectedLibraryRepository,
)

from .certificate import MobileLinkCertificateStore
from .library_grants import MobileLibraryGrantRegistry
from .pairing import MobilePairingRegistry
from .server import create_mobile_link_server

DEFAULT_MOBILE_LINK_PORT = 8767


@dataclass(frozen=True, slots=True)
class MobileLinkStatus:
    state: str = "disabled"
    port: int | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class MobilePairingBundle:
    endpoints: tuple[str, ...]
    pairing_code: str
    expires_at: float
    certificate_pem: str
    certificate_sha256: str
    detection_pack_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "endpoints": list(self.endpoints),
            "pairing_code": self.pairing_code,
            "expires_at": self.expires_at,
            "certificate_pem": self.certificate_pem,
            "certificate_sha256": self.certificate_sha256,
            "detection_pack_sha256": self.detection_pack_sha256,
        }


class MobileLinkManager:
    """Own the opt-in TLS bridge used only by explicitly paired mobile devices."""

    def __init__(
        self,
        service: PrivacyGateService,
        data_dir: str | Path,
        *,
        secret_store: SecretStore | None = None,
        server_factory: Callable[..., Any] = create_mobile_link_server,
    ) -> None:
        self.service = service
        self.data_dir = Path(data_dir)
        self.secrets = secret_store or platform_secret_store(self.data_dir)
        self.pairing = MobilePairingRegistry(self.secrets)
        self.certificates = MobileLinkCertificateStore(self.secrets)
        # LibraryRepository keeps the physically isolated protected-only copy
        # under Data/Protected. Mobile Link must read that exact store rather
        # than creating a second empty Data/protected_library.db beside it.
        self.protected_library = ProtectedLibraryRepository(self.data_dir / "Protected")
        self.library_grants = MobileLibraryGrantRegistry(self.secrets)
        self._server_factory = server_factory
        self._lock = threading.RLock()
        self._server: Any | None = None
        self._thread: threading.Thread | None = None
        self._status = MobileLinkStatus()
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None

    @property
    def status(self) -> MobileLinkStatus:
        with self._lock:
            return self._status

    def grant_protected_copy(self, *, client_id: str, document_id: str) -> dict[str, object]:
        # A protected-copy grant is useful only while the authenticated local
        # bridge is reachable. Bring the service online before publishing the
        # grant so Mobile can refresh immediately after the Desktop action.
        status = self.start()
        if status.state != "online" or status.port is None:
            raise RuntimeError(status.error or "Mobile Link could not start")

        # Verify the item exists in the physically separate protected-only store.
        self.protected_library.get_mcp_document(document_id)
        client_record = next(
            (item for item in self.pairing._load() if item["client_id"] == client_id),
            None,
        )
        if client_record is None:
            raise ValueError("device is not paired")
        return self.library_grants.grant_protected_copy(
            client_id=client_id,
            token_hash=str(client_record["token_hash"]),
            document_id=document_id,
        )

    def start(self, port: int = DEFAULT_MOBILE_LINK_PORT) -> MobileLinkStatus:
        port = int(port)
        if not 1024 <= port <= 65535:
            raise ValueError("Mobile Link port must be between 1024 and 65535")
        with self._lock:
            if self._status.state == "online" and self._status.port == port:
                return self._status
        self.stop()
        temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            identity = self.certificates.load_or_create()
            temporary = tempfile.TemporaryDirectory(prefix="privacygate-mobile-link-")
            temp_dir = Path(temporary.name)
            certificate_path = temp_dir / "certificate.pem"
            private_key_path = temp_dir / "private-key.pem"
            certificate_path.write_text(identity.certificate_pem, encoding="ascii")
            private_key_path.write_text(identity.private_key_pem, encoding="ascii")
            server = self._server_factory(
                service=self.service,
                pairing=self.pairing,
                protected_library=self.protected_library,
                library_grants=self.library_grants,
                host="0.0.0.0",
                port=port,
                certificate_path=certificate_path,
                private_key_path=private_key_path,
            )
        except Exception as error:
            if temporary is not None:
                temporary.cleanup()
            with self._lock:
                self._status = MobileLinkStatus(
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
                        self._status = MobileLinkStatus(
                            state="error",
                            port=port,
                            error=f"{type(error).__name__}: {error}",
                        )

        thread = threading.Thread(
            target=serve,
            name="PrivacyGateMobileLink",
            daemon=True,
        )
        with self._lock:
            self._server = server
            self._thread = thread
            self._temp_dir = temporary
            self._status = MobileLinkStatus(state="online", port=int(server.server_port))
        thread.start()
        return self.status

    def create_pairing_bundle(self, port: int = DEFAULT_MOBILE_LINK_PORT) -> MobilePairingBundle:
        status = self.start(port)
        if status.state != "online" or status.port is None:
            raise RuntimeError(status.error or "Mobile Link could not start")
        identity = self.certificates.load_or_create()
        challenge = self.pairing.create_challenge()
        endpoints = tuple(
            f"https://{address}:{status.port}" for address in self._local_ipv4_addresses()
        )
        return MobilePairingBundle(
            endpoints=endpoints,
            pairing_code=challenge.code,
            expires_at=challenge.expires_at,
            certificate_pem=identity.certificate_pem,
            certificate_sha256=identity.certificate_sha256,
            detection_pack_sha256=str(build_detection_pack()["sha256"]),
        )

    @staticmethod
    def _local_ipv4_addresses() -> tuple[str, ...]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("192.0.2.1", 9))
                address = sock.getsockname()[0]
                if address and not address.startswith("127.") and address != "0.0.0.0":
                    return (address,)
        except OSError:
            pass
        candidates: set[str] = set()
        try:
            _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
            candidates.update(
                address
                for address in addresses
                if address
                and not address.startswith("127.")
                and not address.startswith("169.254.")
                and address != "0.0.0.0"
            )
        except OSError:
            pass
        return tuple(sorted(candidates))

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            temporary = self._temp_dir
            self._server = None
            self._thread = None
            self._temp_dir = None
            self._status = MobileLinkStatus()
        if server is not None:
            try:
                server.shutdown()
            finally:
                server.server_close()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        if temporary is not None:
            temporary.cleanup()
