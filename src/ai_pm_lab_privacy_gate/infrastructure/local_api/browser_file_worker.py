from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.application.protect_session_service import (
    namespace_protection_result,
)
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, Finding
from ai_pm_lab_privacy_gate.domain.profiles import get_profile

from .browser_document_idempotency import document_contains_privacygate_tokens


WORKER_ANALYSIS_TTL_SECONDS = 10 * 60
WORKER_ANALYSIS_MAX_ITEMS = 4


@dataclass(slots=True)
class _WorkerAnalysis:
    analysis_id: str
    filename: str
    suffix: str
    source_bytes: bytes
    document: AnalysisDocument
    findings: tuple[Finding, ...]
    profile_key: str
    language: str
    created_at: float


class BrowserFileWorkerRuntime:
    """Own heavy document/NLP work outside the Qt desktop process.

    The runtime is deliberately stateful so one worker can keep the NLP model warm
    and preserve OCR/layout analysis between the browser review and protection
    steps. Nothing in this object is shared with the desktop GUI process when used
    through BrowserFileProcessExecutor.
    """

    def __init__(
        self,
        service: PrivacyGateService | None = None,
        *,
        clock=time.monotonic,
    ) -> None:
        self._service = service
        self._clock = clock
        self._analyses: dict[str, _WorkerAnalysis] = {}

    @property
    def service(self) -> PrivacyGateService:
        if self._service is None:
            self._service = PrivacyGateService()
        return self._service

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation") or "")
        if operation == "ping":
            return {"worker_pid": os.getpid(), "status": "ready"}
        if operation == "analyze":
            return self._analyze(request)
        if operation == "protect":
            return self._protect(request)
        raise ValueError("unsupported browser file worker operation")

    def _purge(self) -> None:
        now = self._clock()
        expired = [
            analysis_id
            for analysis_id, item in self._analyses.items()
            if now - item.created_at > WORKER_ANALYSIS_TTL_SECONDS
        ]
        for analysis_id in expired:
            self._analyses.pop(analysis_id, None)
        while len(self._analyses) >= WORKER_ANALYSIS_MAX_ITEMS:
            oldest = min(self._analyses.values(), key=lambda item: item.created_at)
            self._analyses.pop(oldest.analysis_id, None)

    def _analyze(self, request: dict[str, Any]) -> dict[str, Any]:
        analysis_id = str(request.get("analysis_id") or "")
        filename = str(request.get("filename") or "")
        suffix = str(request.get("suffix") or "")
        profile_key = str(request.get("profile_key") or "general_business")
        language = str(request.get("language") or "en")
        raw = request.get("source_bytes")
        if not analysis_id:
            raise ValueError("analysis_id is required")
        if not suffix.startswith("."):
            raise ValueError("file suffix is invalid")
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise ValueError("source_bytes is required")

        self._purge()
        source_bytes = bytes(raw)
        with tempfile.TemporaryDirectory(prefix="privacygate-browser-worker-") as temporary:
            source = Path(temporary) / f"source{suffix}"
            source.write_bytes(source_bytes)
            document = self.service.document_from_file(source)
            if document_contains_privacygate_tokens(document):
                raise ValueError(
                    "this file already contains PrivacyGate tokens; automatic re-protection is blocked"
                )
            findings = tuple(
                self.service.analyze(
                    document,
                    get_profile(profile_key),
                    language=language,
                )
            )

        self._analyses[analysis_id] = _WorkerAnalysis(
            analysis_id=analysis_id,
            filename=filename,
            suffix=suffix,
            source_bytes=source_bytes,
            document=document,
            findings=findings,
            profile_key=profile_key,
            language=language,
            created_at=self._clock(),
        )

        page_by_number = {page.page_number: page for page in document.pages}
        return {
            "analysis_id": analysis_id,
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
            "worker_pid": os.getpid(),
        }

    def _protect(self, request: dict[str, Any]) -> dict[str, Any]:
        analysis_id = str(request.get("analysis_id") or "")
        item = self._analyses.get(analysis_id)
        if item is None:
            raise KeyError("file_analysis_not_found")

        requested = request.get("finding_ids")
        if requested is None:
            selected = item.findings
        else:
            if not isinstance(requested, (list, tuple)):
                raise ValueError("finding_ids must be an array")
            requested_ids = {str(value) for value in requested}
            known = {finding.finding_id for finding in item.findings}
            unknown = requested_ids - known
            if unknown:
                raise ValueError("finding_ids contains findings not present in this file")
            selected = tuple(
                finding for finding in item.findings if finding.finding_id in requested_ids
            )

        result = self.service.protect(
            item.document,
            selected,
            replacement_mode="reversible",
        )
        if result.mappings:
            namespace = str(request.get("namespace") or "")
            if not namespace:
                raise ValueError("namespace is required for reversible file protection")
            result = namespace_protection_result(result, namespace)

        with tempfile.TemporaryDirectory(prefix="privacygate-browser-worker-output-") as temporary:
            source = Path(temporary) / f"source{item.suffix}"
            destination = Path(temporary) / f"protected{item.suffix}"
            source.write_bytes(item.source_bytes)
            source_document = replace(item.document, source_path=source)

            # Browser PDF handoff intentionally uses the clean text reflow copy so
            # the AI receives complete reversible [[PG_...]] tokens. Desktop export
            # keeps its own layout-preserving presentation path.
            if item.suffix == ".pdf":
                self.service.save_protected_pdf(result, destination)
            else:
                self.service.save_protected_document(
                    result,
                    destination,
                    source_document,
                )
            protected_bytes = destination.read_bytes()

        self._analyses.pop(analysis_id, None)
        return {
            "protected_file_bytes": protected_bytes,
            "source_kind": item.document.source_kind,
            "applied_findings_count": len(result.applied_findings),
            "applied_finding_ids": [
                finding.finding_id for finding in result.applied_findings
            ],
            "entity_types": sorted(
                {finding.entity_type for finding in result.applied_findings}
            ),
            "mappings": [
                {
                    "token": mapping.token,
                    "entity_type": mapping.entity_type,
                    "original_text": mapping.original_text,
                }
                for mapping in result.mappings
            ],
            "worker_pid": os.getpid(),
        }


_RUNTIME: BrowserFileWorkerRuntime | None = None


def run_browser_file_worker_request(request: dict[str, Any]) -> dict[str, Any]:
    """ProcessPool entrypoint. Keep one warm runtime per spawned worker process."""
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = BrowserFileWorkerRuntime()
    return _RUNTIME.execute(request)
