from __future__ import annotations

import json
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.detection_pack import build_detection_pack
from ai_pm_lab_privacy_gate.domain.profiles import PrivacyProfile, entities_for_scope, get_profile, get_scope
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language

from .pairing import MobilePairingRegistry

MAX_REQUEST_BYTES = 1_000_000
MAX_TEXT_CHARS = 250_000
_CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


class MobileLinkHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], *, service: PrivacyGateService, pairing: MobilePairingRegistry) -> None:
        self.privacy_service = service
        self.pairing = pairing
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

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_browser_transport():
            return
        if self.path != "/v1/mobile/status":
            self._send_json(404, {"error": "not_found"})
            return
        self._send_json(
            200,
            {
                "status": "ready",
                "service": "privacy-gate-mobile-link",
                "api_version": "v1",
                "transport": "tls",
                "paired": self._authorized(),
                "detection_pack_sha256": self.server.detection_pack_sha256,
                "returns_original_values": False,
                "returns_restore_mappings": False,
            },
        )

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
        token = self.server.pairing.pair(client_id, code.strip(), client_name=str(client_name or "Mobile device"))
        return {
            "paired": True,
            "mobile_token": token,
            "token_type": "Bearer",
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
    host: str,
    port: int,
    certificate_path: str | Path,
    private_key_path: str | Path,
) -> MobileLinkHttpServer:
    server = MobileLinkHttpServer((host, int(port)), service=service, pairing=pairing)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(certificate_path), keyfile=str(private_key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
