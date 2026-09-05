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

from ai_pm_lab_privacy_gate.application.protect_session_service import namespace_protection_result
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding
from ai_pm_lab_privacy_gate.domain.profiles import get_profile
from ai_pm_lab_privacy_gate.infrastructure.documents.document_pipeline import DocumentPipelineService
from ai_pm_lab_privacy_gate.infrastructure.pii.languages import normalize_document_language
from ai_pm_lab_privacy_gate.infrastructure.storage.ai_library_repository import AiLibraryRepository

from .browser_document_idempotency import document_contains_privacygate_tokens
from .browser_provider import browser_provider
from .server import LocalApiHttpServer
from .session_store import LocalSessionNotFound


MAX_BROWSER_FILE_BYTES = 12 * 1024 * 1024
MAX_BROWSER_FILE_REQUEST_BYTES = 17 * 1024 * 1024
FILE_ANALYSIS_TTL_SECONDS = 10 * 60
FILE_ANALYSIS_MAX_ITEMS = 4
_SUPPORTED_SUFFIXES = frozenset(DocumentPipelineService.SUPPORTED_SUFFIXES)
_ANALYSIS_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


@dataclass(frozen=True, slots=True)
class BrowserFileAnalysis:
    analysis_id: str
    filename: str
    suffix: str
    source_bytes: bytes
    document: AnalysisDocument
    findings: tuple[Finding, ...]
    profile_key: str
    language: str
    created_at: float


class BrowserFileAnalysisStore:
    """Small local-only cache between one browser review and one protection request."""

    def __init__(
        self,
        *,
        ttl_seconds: int = FILE_ANALYSIS_TTL_SECONDS,
        max_items: int = FILE_ANALYSIS_MAX_ITEMS,
        clock=time.monotonic,
    ) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self.max_items = int(max_items)
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, BrowserFileAnalysis] = {}

    def create(
        self,
        *,
        filename: str,
        suffix: str,
        source_bytes: bytes,
        document: AnalysisDocument,
        findings: tuple[Finding, ...],
        profile_key: str,
        language: str,
    ) -> BrowserFileAnalysis:
        with self._lock:
            now = self._clock()
            self._purge_locked(now)
            while len(self._items) >= self.max_items:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.analysis_id, None)
            item = BrowserFileAnalysis(
                analysis_id=secrets.token_hex(16),
                filename=filename,
                suffix=suffix,
                source_bytes=bytes(source_bytes),
                document=document,
                findings=findings,
                profile_key=profile_key,
                language=language,
                created_at=now,
            )
            self._items[item.analysis_id] = item
            return item

    def get(self, analysis_id: str) -> BrowserFileAnalysis:
        with self._lock:
            now = self._clock()
            self._purge_locked(now)
            item = self._items.get(analysis_id)
            if item is None:
                raise KeyError("file_analysis_not_found")
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


def _safe_filename(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("filename must be a non-empty string")
    filename = re.split(r"[\\/]", value.strip())[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        allowed = ", ".join(sorted(_SUPPORTED_SUFFIXES))
        raise ValueError(f"unsupported browser file type; supported extensions: {allowed}")
    if len(filename) > 180:
        raise ValueError("filename is too long")
    return filename, suffix


def _decode_file(value: object, suffix: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("file_base64 must be a non-empty string")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("file_base64 is invalid") from error
    if not raw or len(raw) > MAX_BROWSER_FILE_BYTES:
        raise ValueError(
            f"file exceeds the {MAX_BROWSER_FILE_BYTES // (1024 * 1024)} MB browser limit"
        )
    if suffix == ".pdf" and not raw.startswith(b"%PDF-"):
        raise ValueError("file is not a valid PDF")
    if suffix in {".docx", ".xlsx", ".pptx"} and not raw.startswith(b"PK"):
        raise ValueError("file is not a valid Office Open XML package")
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
    if len(value) > 4_000:
        raise ValueError("finding_ids contains too many items")
    return tuple(dict.fromkeys(value))


def _protected_filename(filename: str) -> str:
    source = Path(filename)
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", source.stem).strip(" ._") or "document"
    return f"{stem[:120]}_PrivacyGate{source.suffix.lower()}"


class _FileOperationBusy(RuntimeError):
    pass


def install_browser_file_support(server: object) -> bool:
    """Expose the desktop DocumentPipelineService through one authenticated browser route.

    One file operation is allowed at a time. Duplicate browser listeners therefore
    cannot fan out CPU-heavy PDF/OCR/model work and starve the desktop UI.
    """
    if not isinstance(server, LocalApiHttpServer):
        return False
    if bool(getattr(server, "browser_file_support", False)):
        return True

    server.browser_file_store = BrowserFileAnalysisStore()
    server.browser_file_operation_lock = threading.Lock()
    base_handler = server.RequestHandlerClass

    class BrowserFileRequestHandler(base_handler):  # type: ignore[misc, valid-type]
        @property
        def _file_store(self) -> BrowserFileAnalysisStore:
            value = getattr(self.server, "browser_file_store", None)
            if not isinstance(value, BrowserFileAnalysisStore):
                raise RuntimeError("browser file store is unavailable")
            return value

        @property
        def _file_operation_lock(self) -> threading.Lock:
            value = getattr(self.server, "browser_file_operation_lock", None)
            if value is None:
                raise RuntimeError("browser file operation lock is unavailable")
            return value

        @property
        def _ai_repository(self) -> AiLibraryRepository | None:
            value = getattr(self.server, "ai_library_repository", None)
            return value if isinstance(value, AiLibraryRepository) else None

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {
                "/v1/browser/file/analyze",
                "/v1/browser/file/protect",
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
            if length < 0 or length > MAX_BROWSER_FILE_REQUEST_BYTES:
                self._send_json(413, {"error": "file_request_too_large"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "json_object_required"})
                return

            if not self._file_operation_lock.acquire(blocking=False):
                self._send_json(
                    409,
                    {
                        "error": "file_operation_busy",
                        "message": "PrivacyGate is already processing another local file.",
                    },
                )
                return
            try:
                response = (
                    self._analyze_file(payload)
                    if self.path.endswith("/analyze")
                    else self._protect_file(payload)
                )
            except LocalSessionNotFound:
                self._send_json(404, {"error": "session_not_found"})
                return
            except KeyError as error:
                if error.args and error.args[0] == "file_analysis_not_found":
                    self._send_json(404, {"error": "file_analysis_not_found"})
                    return
                self._send_json(400, {"error": "invalid_request"})
                return
            except ValueError as error:
                message = str(error)
                if "already contains PrivacyGate tokens" in message:
                    self._send_json(409, {"error": "already_protected_document", "message": message})
                    return
                if "No selectable text was found" in message:
                    self._send_json(422, {"error": "document_has_no_readable_text", "message": message})
                    return
                self._send_json(400, {"error": "invalid_request", "message": message})
                return
            except Exception as error:
                self._send_json(
                    500,
                    {"error": "local_service_error", "message": type(error).__name__},
                )
                return
            finally:
                self._file_operation_lock.release()
            self._send_json(200, response)

        def _analyze_file(self, payload: dict[str, Any]) -> dict[str, object]:
            filename, suffix = _safe_filename(payload.get("filename"))
            raw = _decode_file(payload.get("file_base64"), suffix)
            profile_key = _profile_key(payload)
            language = _language(payload)

            with tempfile.TemporaryDirectory(prefix="privacygate-browser-file-") as temporary:
                source = Path(temporary) / f"source{suffix}"
                source.write_bytes(raw)
                document = self.server.privacy_service.document_from_file(source)
                if document_contains_privacygate_tokens(document):
                    raise ValueError(
                        "this file already contains PrivacyGate tokens; automatic re-protection is blocked"
                    )
                findings = tuple(
                    self.server.privacy_service.analyze(
                        document,
                        get_profile(profile_key),
                        language=language,
                    )
                )

            item = self._file_store.create(
                filename=filename,
                suffix=suffix,
                source_bytes=raw,
                document=document,
                findings=findings,
                profile_key=profile_key,
                language=language,
            )
            page_by_number = {page.page_number: page for page in document.pages}
            return {
                "analysis_id": item.analysis_id,
                "filename": filename,
                "source_kind": document.source_kind,
                "findings_count": len(findings),
                "findings": [
                    {
                        "finding_id": finding.finding_id,
                        "entity_type": finding.entity_type,
                        "page_number": finding.page_number,
                        "location": page_by_number.get(finding.page_number).location
                        if page_by_number.get(finding.page_number) is not None
                        else "",
                        "score": round(float(finding.score), 6),
                        "display_value": finding.text,
                    }
                    for finding in findings
                ],
                "requires_protection": bool(findings),
                "profile_key": profile_key,
                "language": language,
                "review_values_local_only": True,
                "local_only": True,
            }

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

        def _protect_file(self, payload: dict[str, Any]) -> dict[str, object]:
            item = self._file_store.get(_analysis_id(payload))
            requested_ids = _finding_ids(payload)
            session_id = _session_id(payload)
            provider = browser_provider(payload)

            if requested_ids is None:
                selected = item.findings
            else:
                requested = set(requested_ids)
                known = {finding.finding_id for finding in item.findings}
                unknown = requested - known
                if unknown:
                    raise ValueError("finding_ids contains findings not present in this file")
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
                        provider=provider,
                        turn=turn,
                        mappings=mappings,
                    )
            elif session_id is not None:
                self._ensure_browser_session(session_id)

            with tempfile.TemporaryDirectory(prefix="privacygate-browser-file-output-") as temporary:
                source = Path(temporary) / f"source{item.suffix}"
                destination = Path(temporary) / f"protected{item.suffix}"
                source.write_bytes(item.source_bytes)
                source_document = replace(item.document, source_path=source)

                # For browser PDF handoff, use the clean text reflow output so AI
                # providers receive the full reversible [[PG_...]] tokens. Desktop
                # export can continue to use its layout-preserving raster mode.
                if item.suffix == ".pdf":
                    self.server.privacy_service.save_protected_pdf(result, destination)
                else:
                    self.server.privacy_service.save_protected_document(
                        result,
                        destination,
                        source_document,
                    )
                protected_bytes = destination.read_bytes()

            self._file_store.delete(item.analysis_id)
            return {
                "protected_file_base64": base64.b64encode(protected_bytes).decode("ascii"),
                "protected_filename": _protected_filename(item.filename),
                "source_kind": item.document.source_kind,
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

    BrowserFileRequestHandler.__name__ = "BrowserFileRequestHandler"
    server.RequestHandlerClass = BrowserFileRequestHandler
    server.browser_file_support = True
    return True
