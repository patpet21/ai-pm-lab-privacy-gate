from __future__ import annotations

import json
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.detection_pack import build_detection_pack
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile, entities_for_scope, get_profile, get_scope
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.storage.protected_library import ProtectedLibraryRepository

from .library_grants import MobileLibraryGrantRegistry
from .pairing import MobilePairingRegistry

MAX_REQUEST_BYTES = 1_000_000
MAX_TEXT_CHARS = 250_000
_CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_GRANT_PATH = re.compile(r"^/v1/mobile/library/grants/([A-Za-z0-9_-]{12,128})$")


class MobileLinkHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        service: PrivacyGateService,
        pairing: MobilePairingRegistry,
        protected_library: ProtectedLibraryRepository,
        library_repository: LibraryRepository,
        library_grants: MobileLibraryGrantRegistry,
        remote_relay_url: str,
    ) -> None:
        self.privacy_service = service
        self.pairing = pairing
        self.protected_library = protected_library
        self.library_repository = library_repository
        self.library_grants = library_grants
        self.remote_relay_url = str(remote_relay_url).rstrip("/")
        self.detection_pack_sha256 = str(build_detection_pack()["sha256"])
        super().__init__(server_address, MobileLinkRequestHandler)


class MobileLinkRequestHandler(BaseHTTPRequestHandler):
    server: MobileLinkHttpServer

    def log_message(self, _format: str, *args: object) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _reject_browser_transport(self) -> bool:
        if self.headers.get("Origin"):
            self._send_json(403, {"error": "browser_transport_not_allowed"})
            return True
        return False

    def _bearer_token(self) -> str:
        value = self.headers.get("Authorization", "")
        return value[7:] if value.startswith("Bearer ") else ""

    def _authorized(self) -> bool:
        return self.server.pairing.validate(self._bearer_token())

    def _remote_relay_payload(self) -> dict[str, object] | None:
        remote = self.server.pairing.ensure_remote_for_token(self._bearer_token())
        if remote is None:
            return None
        return {
            "version": 1,
            "url": self.server.remote_relay_url,
            "room_id": remote["relay_room_id"],
            "relay_token": remote["relay_token"],
            "remote_secret": remote["remote_secret"],
            "cipher": "AES-256-GCM",
            "content_storage": False,
        }

    def _read_payload(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("application/json required")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as exc:
            raise ValueError("content length required") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid json") from exc
        if not isinstance(payload, dict):
            raise ValueError("json object required")
        return payload

    @staticmethod
    def _document_payload(
        document,
        *,
        grant_id: str,
        mode: str,
        include_content: bool,
    ) -> dict[str, object]:
        has_mapping = mode == "full_offline_session"
        payload: dict[str, object] = {
            "grant_id": grant_id,
            "mode": mode,
            "document_id": document.document_id,
            "title": document.title,
            "profile_key": document.profile_key,
            "findings_count": document.findings_count,
            "entity_types": list(document.entity_types),
            "labels": list(document.labels),
            "updated_at": document.updated_at.isoformat(),
            "favorite": document.favorite,
            "source_kind": document.source_kind,
            "has_mapping": has_mapping,
        }
        if include_content:
            payload["protected_text"] = document.protected_text
        return payload

    def _full_session_available(self, document_id: str) -> bool:
        try:
            source = self.server.library_repository.get(document_id)
        except KeyError:
            return False
        return bool(source.deleted_at is None and source.has_mapping)

    def _library_grants(self) -> None:
        if not self._authorized():
            self._send_json(401, {"error": "mobile_pairing_required"})
            return
        grants = []
        for grant in self.server.library_grants.list_for_token(self._bearer_token()):
            document_id = str(grant["document_id"])
            mode = str(grant.get("mode") or "protected_copy")
            try:
                document = self.server.protected_library.get_mcp_document(document_id)
            except KeyError:
                continue
            if mode == "full_offline_session" and not self._full_session_available(document_id):
                continue
            grants.append(
                self._document_payload(
                    document,
                    grant_id=str(grant["grant_id"]),
                    mode=mode,
                    include_content=False,
                )
            )
        self._send_json(
            200,
            {
                "grants": grants,
                "automatic_sync": False,
                "full_offline_session": True,
            },
        )

    def _library_grant(self, grant_id: str) -> None:
        if not self._authorized():
            self._send_json(401, {"error": "mobile_pairing_required"})
            return
        grant = self.server.library_grants.get_for_token(self._bearer_token(), grant_id)
        if grant is None:
            self._send_json(404, {"error": "library_grant_not_found"})
            return
        document_id = str(grant["document_id"])
        mode = str(grant.get("mode") or "protected_copy")
        try:
            document = self.server.protected_library.get_mcp_document(document_id)
        except KeyError:
            self._send_json(410, {"error": "library_item_unavailable"})
            return

        payload = self._document_payload(
            document,
            grant_id=grant_id,
            mode=mode,
            include_content=True,
        )
        if mode == "full_offline_session":
            if not self._full_session_available(document_id):
                self._send_json(410, {"error": "restore_mapping_unavailable"})
                return
            mappings = self.server.library_repository.get_mappings(document_id)
            if not mappings:
                self._send_json(410, {"error": "restore_mapping_unavailable"})
                return
            # This payload may travel either through pinned local TLS or through
            # the outer Device Trust AES-256-GCM tunnel. Mobile immediately stores
            # mappings in its separate device Vault, never in the Library document.
            payload["restore_mappings"] = [
                {
                    "token": item.token,
                    "entity_type": item.entity_type,
                    "original_text": item.original_text,
                }
                for item in mappings
            ]
            payload["mapping_storage"] = "mobile_device_vault_aes_256_gcm"
        self._send_json(200, payload)

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_browser_transport():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/v1/mobile/status":
            current = self.server.pairing.client_for_token(self._bearer_token())
            remote = self._remote_relay_payload() if current is not None else None
            self._send_json(
                200,
                {
                    "status": "ready",
                    "service": "privacy-gate-mobile-link",
                    "api_version": "v1",
                    "transport": "tls",
                    "paired": current is not None,
                    "client_id": current["client_id"] if current else "",
                    "client_name": current["client_name"] if current else "",
                    "detection_pack_sha256": self.server.detection_pack_sha256,
                    "returns_original_values": False,
                    "returns_restore_mappings": False,
                    "selective_library_transfer": True,
                    "full_offline_session": True,
                    "automatic_library_sync": False,
                    "remote_device_trust": remote is not None,
                    "remote_relay": remote or {},
                },
            )
            return
        if parsed.path == "/v1/mobile/pair/status":
            request_id = parse_qs(parsed.query).get("request_id", [""])[0]
            try:
                result = self.server.pairing.consume_pairing_result(request_id)
            except ValueError as error:
                self._send_json(400, {"error": "invalid_request", "message": str(error)})
                return
            payload: dict[str, object] = {
                "pairing_status": result["status"],
                "detection_pack_sha256": self.server.detection_pack_sha256,
            }
            token = result.get("mobile_token")
            if isinstance(token, str) and token:
                payload.update({"paired": True, "mobile_token": token, "token_type": "Bearer"})
                room_id = result.get("relay_room_id")
                relay_token = result.get("relay_token")
                remote_secret = result.get("remote_secret")
                if all(isinstance(value, str) and value for value in (room_id, relay_token, remote_secret)):
                    payload["remote_relay"] = {
                        "version": 1,
                        "url": self.server.remote_relay_url,
                        "room_id": room_id,
                        "relay_token": relay_token,
                        "remote_secret": remote_secret,
                        "cipher": "AES-256-GCM",
                        "content_storage": False,
                    }
            else:
                payload["paired"] = False
            self._send_json(200, payload)
            return
        if parsed.path == "/v1/mobile/library/grants":
            self._library_grants()
            return
        match = _GRANT_PATH.fullmatch(parsed.path)
        if match:
            self._library_grant(match.group(1))
            return
        self._send_json(404, {"error": "not_found"})

    def do_PATCH(self) -> None:  # noqa: N802
        if self._reject_browser_transport():
            return
        if urlparse(self.path).path != "/v1/mobile/device":
            self._send_json(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "mobile_pairing_required"})
            return
        try:
            payload = self._read_payload()
            client_name = payload.get("client_name")
            if not isinstance(client_name, str):
                raise ValueError("client_name must be a string")
            record = self.server.pairing.rename_for_token(self._bearer_token(), client_name)
            if record is None:
                self._send_json(401, {"error": "mobile_pairing_required"})
                return
        except ValueError as error:
            self._send_json(400, {"error": "invalid_request", "message": str(error)})
            return
        self._send_json(
            200,
            {
                "renamed": True,
                "client_id": str(record["client_id"]),
                "client_name": str(record["client_name"]),
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        if self._reject_browser_transport():
            return
        if urlparse(self.path).path != "/v1/mobile/device":
            self._send_json(404, {"error": "not_found"})
            return
        token = self._bearer_token()
        record = self.server.pairing.client_for_token(token)
        if record is None:
            self._send_json(401, {"error": "mobile_pairing_required"})
            return
        client_id = str(record["client_id"])
        removed = self.server.pairing.revoke_client(client_id)
        if removed:
            self.server.library_grants.revoke_client(client_id)
        self._send_json(200, {"removed": bool(removed), "client_id": client_id})

    def do_POST(self) -> None:  # noqa: N802
        if self._reject_browser_transport():
            return
        if self.path not in {"/v1/mobile/pair", "/v1/mobile/analyze"}:
            self._send_json(404, {"error": "not_found"})
            return
        if self.path == "/v1/mobile/analyze" and not self._authorized():
            self._send_json(401, {"error": "mobile_pairing_required"})
            return
        try:
            payload = self._read_payload()
            response = self._pair(payload) if self.path.endswith("/pair") else self._analyze(payload)
        except (KeyError, ValueError) as error:
            self._send_json(400, {"error": "invalid_request", "message": str(error)})
            return
        except Exception:
            self._send_json(500, {"error": "local_service_error"})
            return
        self._send_json(200, response)

    def _pair(self, payload: dict[str, Any]) -> dict[str, object]:
        code = payload.get("code")
        client_id = payload.get("client_id")
        client_name = payload.get("client_name", "Mobile device")
        if not isinstance(code, str) or not re.fullmatch(r"\d{8}", code.strip()):
            raise ValueError("pairing code must contain 8 digits")
        if not isinstance(client_id, str) or not _CLIENT_ID.fullmatch(client_id):
            raise ValueError("client_id is invalid")
        if client_name is not None and not isinstance(client_name, str):
            raise ValueError("client_name must be a string")
        request_id = self.server.pairing.request_pairing(
            client_id, code.strip(), client_name=str(client_name or "Mobile device")
        )
        return {
            "paired": False,
            "approval_required": True,
            "pairing_status": "pending",
            "pairing_request_id": request_id,
            "detection_pack_sha256": self.server.detection_pack_sha256,
        }

    def _analyze(self, payload: dict[str, Any]) -> dict[str, object]:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        if len(text) > MAX_TEXT_CHARS:
            raise ValueError(f"text exceeds the {MAX_TEXT_CHARS} character limit")
        profile_key = payload.get("profile_key")
        scope_key = payload.get("scope_key")
        language = payload.get("language", "en")
        threshold = payload.get("confidence_threshold", 0.35)
        if not isinstance(profile_key, str) or not profile_key:
            raise ValueError("profile_key is required")
        if not isinstance(scope_key, str) or not scope_key:
            raise ValueError("scope_key is required")
        if not isinstance(threshold, (int, float)) or not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        base_profile = get_profile(profile_key)
        get_scope(scope_key)
        selected_profile = PrivacyProfile(
            key=base_profile.key,
            name=base_profile.name,
            description=base_profile.description,
            entities=entities_for_scope(base_profile, scope_key),
            threshold=float(threshold),
        )
        code = normalize_document_language(str(language))
        document = self.server.privacy_service.document_from_text(text)
        findings = self.server.privacy_service.analyze(document, selected_profile, language=code)
        return {
            "findings_count": len(findings),
            "findings": [
                {
                    "entity_type": item.entity_type,
                    "start": item.start,
                    "end": item.end,
                    "score": round(float(item.score), 6),
                }
                for item in findings
            ],
            "detection_pack_sha256": self.server.detection_pack_sha256,
        }


def create_mobile_link_server(
    *,
    service: PrivacyGateService,
    pairing: MobilePairingRegistry,
    protected_library: ProtectedLibraryRepository,
    library_repository: LibraryRepository,
    library_grants: MobileLibraryGrantRegistry,
    remote_relay_url: str,
    host: str,
    port: int,
    certificate_path: str | Path,
    private_key_path: str | Path,
) -> MobileLinkHttpServer:
    server = MobileLinkHttpServer(
        (host, int(port)),
        service=service,
        pairing=pairing,
        protected_library=protected_library,
        library_repository=library_repository,
        library_grants=library_grants,
        remote_relay_url=remote_relay_url,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(certificate_path), keyfile=str(private_key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server