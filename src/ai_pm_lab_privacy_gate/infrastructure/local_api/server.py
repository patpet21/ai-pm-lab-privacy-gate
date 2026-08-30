from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.application.protect_session_service import namespace_protection_result
from ai_pm_lab_privacy_gate.domain.models import Finding
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.local_api.session_store import (
    LocalProtectionSessionStore,
    LocalSessionNotFound,
)
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 1_000_000
MAX_TEXT_CHARS = 250_000
_ALLOWED_REPLACEMENT_MODES = {"reversible", "redact", "generic", "mask"}
_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_BROWSER_PATHS = {"/v1/browser/analyze", "/v1/browser/protect"}


def _finding_payload(finding: Finding) -> dict[str, object]:
    """Return only coordinates and category metadata, never the original value."""
    return {
        "finding_id": finding.finding_id,
        "entity_type": finding.entity_type,
        "start": finding.start,
        "end": finding.end,
        "score": round(float(finding.score), 6),
        "page_number": finding.page_number,
    }


def _validated_text(payload: dict[str, Any]) -> str:
    value = payload.get("text")
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    if not value.strip():
        raise ValueError("text must not be empty")
    if len(value) > MAX_TEXT_CHARS:
        raise ValueError(f"text exceeds the {MAX_TEXT_CHARS} character limit")
    return value


def _validated_profile(payload: dict[str, Any]) -> str:
    value = payload.get("profile_key")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("profile_key must be a non-empty string")
    get_profile(value)
    return value


def _validated_language(payload: dict[str, Any]) -> str:
    value = payload.get("language", "en")
    if value is not None and not isinstance(value, str):
        raise ValueError("language must be a string")
    return normalize_document_language(value)


def _validated_finding_ids(payload: dict[str, Any]) -> tuple[str, ...] | None:
    if "finding_ids" not in payload:
        return None
    value = payload["finding_ids"]
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("finding_ids must be an array of strings")
    if len(value) > 1_000:
        raise ValueError("finding_ids contains too many items")
    return tuple(dict.fromkeys(value))


def _validated_replacement_mode(payload: dict[str, Any]) -> str:
    value = payload.get("replacement_mode", "reversible")
    if value not in _ALLOWED_REPLACEMENT_MODES:
        allowed = ", ".join(sorted(_ALLOWED_REPLACEMENT_MODES))
        raise ValueError(f"replacement_mode must be one of: {allowed}")
    return str(value)


def _validated_session_id(payload: dict[str, Any], *, required: bool = False) -> str | None:
    value = payload.get("session_id")
    if value is None:
        if required:
            raise ValueError("session_id is required")
        return None
    if not isinstance(value, str) or not _SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("session_id is invalid")
    return value


class LocalApiHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        service: PrivacyGateService,
        auth_token: str,
        allowed_origins: tuple[str, ...],
        session_store: LocalProtectionSessionStore,
    ) -> None:
        self.privacy_service = service
        self.auth_token = auth_token
        self.allowed_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)
        self.session_store = session_store
        super().__init__(server_address, LocalApiRequestHandler)

    def server_close(self) -> None:
        self.session_store.clear()
        super().server_close()


class LocalApiRequestHandler(BaseHTTPRequestHandler):
    server: LocalApiHttpServer

    def log_message(self, _format: str, *args: object) -> None:
        # Never put prompt contents, PII or bearer credentials in default HTTP logs.
        return

    def _host_allowed(self) -> bool:
        raw = self.headers.get("Host", "")
        hostname = raw.rsplit(":", 1)[0].strip("[]").lower()
        return hostname in {"127.0.0.1", "localhost"}

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return origin.rstrip("/") in self.server.allowed_origins

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        supplied = header[len(prefix) :]
        return hmac.compare_digest(supplied, self.server.auth_token)

    def _cors_headers(self) -> dict[str, str]:
        origin = self.headers.get("Origin")
        if not origin or origin.rstrip("/") not in self.server.allowed_origins:
            return {}
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Vary": "Origin",
        }

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in self._cors_headers().items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def _reject_if_untrusted_transport(self) -> bool:
        if not self._host_allowed():
            self._send_json(403, {"error": "invalid_local_host"})
            return True
        if not self._origin_allowed():
            self._send_json(403, {"error": "origin_not_allowed"})
            return True
        return False

    def _browser_origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "").rstrip("/")
        return (
            origin.startswith("chrome-extension://")
            and origin in self.server.allowed_origins
        )

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self._reject_if_untrusted_transport():
            return
        origin = self.headers.get("Origin")
        if not origin:
            self._send_json(400, {"error": "origin_required"})
            return
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        for name, value in self._cors_headers().items():
            self.send_header(name, value)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self._reject_if_untrusted_transport():
            return
        if self.path != "/v1/status":
            self._send_json(404, {"error": "not_found"})
            return
        self._send_json(
            200,
            {
                "status": "ready",
                "service": "privacy-gate-local-api",
                "api_version": "v1",
                "mode": "local-only",
                "authentication": "bearer",
                "returns_restore_mappings": False,
                "can_restore_session_text": True,
                "can_access_library": False,
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self._reject_if_untrusted_transport():
            return

        if self.path not in {
            "/v1/analyze",
            "/v1/browser/analyze",
            "/v1/protect",
            "/v1/browser/protect",
            "/v1/restore",
        }:
            self._send_json(404, {"error": "not_found"})
            return

        if self.path in _BROWSER_PATHS:
            # FreeV1 browser POC: keep browser access constrained to the exact
            # allowlisted Chromium extension origin. This is intentionally not
            # the final pairing/authentication design.
            if not self._browser_origin_allowed():
                self._send_json(403, {"error": "browser_origin_not_allowed"})
                return
        elif not self._authorized():
            self._send_json(401, {"error": "authentication_required"})
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_json(415, {"error": "application_json_required"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(411, {"error": "content_length_required"})
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "request_too_large"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "json_object_required"})
            return
        try:
            if self.path in {"/v1/analyze", "/v1/browser/analyze"}:
                response = self._analyze(payload)
            elif self.path in {"/v1/protect", "/v1/browser/protect"}:
                response = self._protect(payload)
            else:
                response = self._restore(payload)
        except LocalSessionNotFound:
            self._send_json(404, {"error": "session_not_found"})
            return
        except (KeyError, ValueError) as error:
            self._send_json(400, {"error": "invalid_request", "message": str(error)})
            return
        except Exception:
            self._send_json(500, {"error": "local_service_error"})
            return
        self._send_json(200, response)

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self._reject_if_untrusted_transport():
            return
        if not self._authorized():
            self._send_json(401, {"error": "authentication_required"})
            return
        prefix = "/v1/sessions/"
        if not self.path.startswith(prefix):
            self._send_json(404, {"error": "not_found"})
            return
        session_id = self.path[len(prefix) :]
        if not _SESSION_ID_PATTERN.fullmatch(session_id):
            self._send_json(400, {"error": "invalid_session_id"})
            return
        deleted = self.server.session_store.delete(session_id)
        if not deleted:
            self._send_json(404, {"error": "session_not_found"})
            return
        self._send_json(200, {"status": "deleted"})

    def _analyze(self, payload: dict[str, Any]) -> dict[str, object]:
        text = _validated_text(payload)
        profile_key = _validated_profile(payload)
        language = _validated_language(payload)
        document = self.server.privacy_service.document_from_text(text)
        findings = self.server.privacy_service.analyze(
            document,
            get_profile(profile_key),
            language=language,
        )
        return {
            "findings_count": len(findings),
            "findings": [_finding_payload(item) for item in findings],
        }

    def _protect(self, payload: dict[str, Any]) -> dict[str, object]:
        text = _validated_text(payload)
        profile_key = _validated_profile(payload)
        language = _validated_language(payload)
        finding_ids = _validated_finding_ids(payload)
        replacement_mode = _validated_replacement_mode(payload)
        session_id = _validated_session_id(payload)
        document = self.server.privacy_service.document_from_text(text)
        findings = self.server.privacy_service.analyze(
            document,
            get_profile(profile_key),
            language=language,
        )
        if finding_ids is None:
            selected = findings
        else:
            requested = set(finding_ids)
            known = {item.finding_id for item in findings}
            unknown = requested - known
            if unknown:
                raise ValueError("finding_ids contains findings that are not present in this text")
            selected = tuple(item for item in findings if item.finding_id in requested)
        result = self.server.privacy_service.protect(
            document,
            selected,
            replacement_mode=replacement_mode,
        )
        if replacement_mode == "reversible" and result.mappings:
            if session_id is None:
                session_id = self.server.session_store.create()
            else:
                self.server.session_store.touch(session_id)
            namespace = self.server.session_store.next_namespace(session_id)
            result = namespace_protection_result(result, namespace)
            self.server.session_store.add_mappings(session_id, result.mappings)
        elif session_id is not None:
            self.server.session_store.touch(session_id)
        return {
            "protected_text": result.combined_text,
            "applied_findings_count": len(result.applied_findings),
            "applied_finding_ids": [item.finding_id for item in result.applied_findings],
            "entity_types": sorted({item.entity_type for item in result.applied_findings}),
            "session_id": session_id,
        }

    def _restore(self, payload: dict[str, Any]) -> dict[str, object]:
        text = _validated_text(payload)
        session_id = _validated_session_id(payload, required=True)
        assert session_id is not None
        mappings = self.server.session_store.mappings(session_id)
        restored = self.server.privacy_service.restore_text(text, mappings)
        return {"restored_text": restored, "session_id": session_id}


def create_local_api_server(
    service: PrivacyGateService | None = None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    auth_token: str | None = None,
    allowed_origins: tuple[str, ...] = (),
    session_store: LocalProtectionSessionStore | None = None,
) -> LocalApiHttpServer:
    """Create the opt-in local bridge. It can never bind to a LAN/WAN interface."""
    normalized_host = host.strip().lower()
    if normalized_host not in {"127.0.0.1", "localhost"}:
        raise ValueError("PrivacyGate Local API may bind only to 127.0.0.1/localhost")
    if not 0 <= int(port) <= 65535:
        raise ValueError("port must be between 0 and 65535")
    token = auth_token or secrets.token_urlsafe(32)
    if len(token) < 24:
        raise ValueError("auth_token must contain at least 24 characters")
    return LocalApiHttpServer(
        (DEFAULT_HOST, int(port)),
        service=service or PrivacyGateService(),
        auth_token=token,
        allowed_origins=allowed_origins,
        session_store=session_store or LocalProtectionSessionStore(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="PrivacyGate opt-in localhost protection API")
    parser.add_argument("--host", default=DEFAULT_HOST, choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--allow-origin", action="append", default=[])
    arguments = parser.parse_args()
    token = os.environ.get("PRIVACY_GATE_LOCAL_API_TOKEN", "")
    if len(token) < 24:
        parser.error(
            "Set PRIVACY_GATE_LOCAL_API_TOKEN to a random value of at least 24 characters. "
            "The local API never starts without authentication."
        )
    server = create_local_api_server(
        host=arguments.host,
        port=arguments.port,
        auth_token=token,
        allowed_origins=tuple(arguments.allow_origin),
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
