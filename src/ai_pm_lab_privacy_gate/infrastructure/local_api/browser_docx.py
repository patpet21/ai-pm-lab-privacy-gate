from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.application.protect_session_service import (
    namespace_protection_result,
)
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import (
    AiLibraryRepository,
)

from .browser_pdf_review import add_local_review_values
from .server import LocalApiHttpServer
from .session_store import LocalSessionNotFound


MAX_BROWSER_DOCX_BYTES = 12 * 1024 * 1024
MAX_BROWSER_DOCX_REQUEST_BYTES = 17 * 1024 * 1024
DOCX_ANALYSIS_TTL_SECONDS = 10 * 60
DOCX_ANALYSIS_MAX_ITEMS = 8
_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_ANALYSIS_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


@dataclass(frozen=True, slots=True)
class BrowserDocxAnalysis:
    analysis_id: str
    filename: str
    source_bytes: bytes
    document: AnalysisDocument
    findings: tuple[Finding, ...]
    profile_key: str
    language: str
    created_at: float


class BrowserDocxAnalysisStore:
    """Short-lived in-memory Word analysis used only between review and protect."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DOCX_ANALYSIS_TTL_SECONDS,
        max_items: int = DOCX_ANALYSIS_MAX_ITEMS,
        clock=time.monotonic,
    ) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self.max_items = int(max_items)
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, BrowserDocxAnalysis] = {}

    def create(
        self,
        *,
        filename: str,
        source_bytes: bytes,
        document: AnalysisDocument,
        findings: tuple[Finding, ...],
        profile_key: str,
        language: str,
    ) -> BrowserDocxAnalysis:
        with self._lock:
            now = self._clock()
            self._purge_locked(now)
            while len(self._items) >= self.max_items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.analysis_id, None)
            item = BrowserDocxAnalysis(
                analysis_id=secrets.token_hex(16),
                filename=filename,
                source_bytes=bytes(source_bytes),
                document=document,
                findings=findings,
                profile_key=profile_key,
                language=language,
                created_at=now,
            )
            self._items[item.analysis_id] = item
            return item

    def get(self, analysis_id: str) -> BrowserDocxAnalysis:
        with self._lock:
            now = self._clock()
            self._purge_locked(now)
            item = self._items.get(analysis_id)
            if item is None:
                raise KeyError("docx_analysis_not_found")
            return item

    def delete(self, analysis_id: str) -> None:
        with self._lock:
            self._items.pop(analysis_id, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _purge_locked(self, now: float) -> None:
        expired = [
            analysis_id
            for analysis_id, item in self._items.items()
            if now - item.created_at > self.ttl_seconds
        ]
        for analysis_id in expired:
            self._items.pop(analysis_id, None)


def _safe_docx_filename(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("filename must be a non-empty string")
    filename = re.split(r"[\\/]", value.strip())[-1]
    if not filename.lower().endswith(".docx"):
        raise ValueError("browser Word protection accepts .docx files only")
    if len(filename) > 180:
        raise ValueError("filename is too long")
    return filename


def _decode_docx(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("file_base64 must be a non-empty string")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("file_base64 is invalid") from error
    if not raw or len(raw) > MAX_BROWSER_DOCX_BYTES:
        raise ValueError(
            f"DOCX exceeds the {MAX_BROWSER_DOCX_BYTES // (1024 * 1024)} MB browser limit"
        )
    # DOCX is an OPC/ZIP package. The document pipeline performs the full format
    # validation when it opens this local temporary copy.
    if not raw.startswith(b"PK"):
        raise ValueError("file is not a valid DOCX package")
    return raw


def _profile_key(payload: dict[str, Any]) -> str:
    value = payload.get("profile_key", "general_business")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("profile_key must be a non-empty string")
    get_profile(value)
    return value


def _language(payload: dict[str, Any]) -> str:
    value = payload.get("language", "en")
    if value is not None and not isinstance(value, str):
        raise ValueError("language must be a string")
    return normalize_document_language(value)


def _analysis_id(payload: dict[str, Any]) -> str:
    value = payload.get("analysis_id")
    if not isinstance(value, str) or not _ANALYSIS_ID_PATTERN.fullmatch(value):
        raise ValueError("analysis_id is invalid")
    return value


def _session_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id")
    if value is None:
        return None
    if not isinstance(value, str) or not _SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("session_id is invalid")
    return value


def _finding_ids(payload: dict[str, Any]) -> tuple[str, ...] | None:
    value = payload.get("finding_ids")
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("finding_ids must be an array of strings")
    if len(value) > 2_000:
        raise ValueError("finding_ids contains too many items")
    return tuple(dict.fromkeys(value))


def _protected_filename(filename: str) -> str:
    stem = Path(filename).stem
    safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._") or "document"
    return f"{safe_stem[:120]}_PrivacyGate.docx"


def install_browser_docx_support(server: object) -> bool:
    """Layer authenticated DOCX scan/protect routes onto the current browser stack."""
    if not isinstance(server, LocalApiHttpServer):
        return False
    if bool(getattr(server, "browser_docx_support", False)):
        return True

    server.browser_docx_store = BrowserDocxAnalysisStore()
    base_handler = server.RequestHandlerClass

    class BrowserDocxRequestHandler(base_handler):  # type: ignore[misc, valid-type]
        @property
        def _docx_store(self) -> BrowserDocxAnalysisStore:
            store = getattr(self.server, "browser_docx_store", None)
            if not isinstance(store, BrowserDocxAnalysisStore):
                raise RuntimeError("browser DOCX store is unavailable")
            return store

        @property
        def _ai_repository(self) -> AiLibraryRepository | None:
            value = getattr(self.server, "ai_library_repository", None)
            return value if isinstance(value, AiLibraryRepository) else None

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path not in {
                "/v1/browser/docx/analyze",
                "/v1/browser/docx/protect",
            }:
                super().do_POST()
                return

            if self._reject_if_untrusted_transport():
                return
            if not self._browser_authorized():
                self._send_json(401, {"error": "browser_pairing_required"})
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
            if length < 0 or length > MAX_BROWSER_DOCX_REQUEST_BYTES:
                self._send_json(413, {"error": "docx_request_too_large"})
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
                response = (
                    self._analyze_docx(payload)
                    if self.path.endswith("/analyze")
                    else self._protect_docx(payload)
                )
            except LocalSessionNotFound:
                self._send_json(404, {"error": "session_not_found"})
                return
            except KeyError as error:
                if error.args and error.args[0] == "docx_analysis_not_found":
                    self._send_json(404, {"error": "docx_analysis_not_found"})
                    return
                self._send_json(400, {"error": "invalid_request"})
                return
            except ValueError as error:
                self._send_json(400, {"error": "invalid_request", "message": str(error)})
                return
            except Exception:
                self._send_json(500, {"error": "local_service_error"})
                return
            self._send_json(200, response)

        def _analyze_docx(self, payload: dict[str, Any]) -> dict[str, object]:
            filename = _safe_docx_filename(payload.get("filename"))
            raw = _decode_docx(payload.get("file_base64"))
            profile_key = _profile_key(payload)
            language = _language(payload)

            with tempfile.TemporaryDirectory(prefix="privacygate-browser-docx-") as temporary:
                source = Path(temporary) / "source.docx"
                source.write_bytes(raw)
                document = self.server.privacy_service.document_from_file(source)
                findings = tuple(
                    self.server.privacy_service.analyze(
                        document,
                        get_profile(profile_key),
                        language=language,
                    )
                )

            item = self._docx_store.create(
                filename=filename,
                source_bytes=raw,
                document=document,
                findings=findings,
                profile_key=profile_key,
                language=language,
            )
            response: dict[str, object] = {
                "analysis_id": item.analysis_id,
                "filename": filename,
                "findings_count": len(findings),
                "findings": [
                    {
                        "finding_id": finding.finding_id,
                        "entity_type": finding.entity_type,
                        "page_number": finding.page_number,
                        "location": next(
                            (
                                page.location
                                for page in document.pages
                                if page.page_number == finding.page_number
                            ),
                            f"Word block {finding.page_number}",
                        ),
                        "score": round(float(finding.score), 6),
                    }
                    for finding in findings
                ],
                "requires_protection": bool(findings),
                "local_only": True,
            }
            return add_local_review_values(
                response,
                findings,
                profile_key=profile_key,
                language=language,
            )

        def _ensure_browser_session(self, session_id: str) -> None:
            try:
                self.server.session_store.touch(session_id)
                return
            except LocalSessionNotFound:
                pass
            repository = self._ai_repository
            if repository is None:
                raise LocalSessionNotFound(session_id)
            snapshot = repository.load_session(session_id)
            if snapshot is None:
                raise LocalSessionNotFound(session_id)
            self.server.session_store.rehydrate(
                snapshot.session_id,
                snapshot.mappings,
                turn=snapshot.turn,
            )

        def _protect_docx(self, payload: dict[str, Any]) -> dict[str, object]:
            item = self._docx_store.get(_analysis_id(payload))
            requested_ids = _finding_ids(payload)
            session_id = _session_id(payload)

            if requested_ids is None:
                selected = item.findings
            else:
                requested = set(requested_ids)
                known = {finding.finding_id for finding in item.findings}
                unknown = requested - known
                if unknown:
                    raise ValueError(
                        "finding_ids contains findings that are not present in this DOCX"
                    )
                selected = tuple(
                    finding for finding in item.findings if finding.finding_id in requested
                )

            result = self.server.privacy_service.protect(
                item.document,
                selected,
                replacement_mode="reversible",
            )

            if result.mappings:
                if session_id is None:
                    session_id = self.server.session_store.create()
                else:
                    self._ensure_browser_session(session_id)
                namespace = self.server.session_store.next_namespace(session_id)
                result = namespace_protection_result(result, namespace)
                self.server.session_store.add_mappings(session_id, result.mappings)

                repository = self._ai_repository
                if repository is not None:
                    turn, mappings = self.server.session_store.snapshot(session_id)
                    repository.save_session(
                        session_id=session_id,
                        provider="browser",
                        turn=turn,
                        mappings=mappings,
                    )
            elif session_id is not None:
                self._ensure_browser_session(session_id)

            with tempfile.TemporaryDirectory(prefix="privacygate-browser-docx-output-") as temporary:
                source = Path(temporary) / "source.docx"
                destination = Path(temporary) / "protected.docx"
                source.write_bytes(item.source_bytes)
                source_document = replace(item.document, source_path=source)
                self.server.privacy_service.save_protected_document(
                    result,
                    destination,
                    source_document,
                )

                # Deterministic write-back safety check: every extracted protected
                # Word block must exactly match the protection result before the
                # file is allowed to leave the localhost bridge.
                verified = self.server.privacy_service.document_from_file(destination)
                expected = [page.text for page in result.protected_pages]
                actual = [page.text for page in verified.pages]
                if actual != expected:
                    raise ValueError("Protected DOCX integrity check failed")
                protected_bytes = destination.read_bytes()

            self._docx_store.delete(item.analysis_id)
            return {
                "protected_file_base64": base64.b64encode(protected_bytes).decode("ascii"),
                "protected_filename": _protected_filename(item.filename),
                "applied_findings_count": len(result.applied_findings),
                "applied_finding_ids": [
                    finding.finding_id for finding in result.applied_findings
                ],
                "entity_types": sorted(
                    {finding.entity_type for finding in result.applied_findings}
                ),
                "session_id": session_id,
                "local_only": True,
            }

    BrowserDocxRequestHandler.__name__ = "BrowserDocxRequestHandler"
    server.RequestHandlerClass = BrowserDocxRequestHandler
    server.browser_docx_support = True
    return True
