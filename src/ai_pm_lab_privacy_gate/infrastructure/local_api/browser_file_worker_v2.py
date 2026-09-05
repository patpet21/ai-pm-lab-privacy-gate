from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def _configure_worker_resources() -> None:
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
    ):
        os.environ[key] = "1"


_SERVICE = None


def _service():
    global _SERVICE
    if _SERVICE is None:
        _configure_worker_resources()
        from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService

        _SERVICE = PrivacyGateService()
    return _SERVICE


def _finding_to_dict(finding: Any) -> dict[str, Any]:
    return {
        "finding_id": str(finding.finding_id),
        "entity_type": str(finding.entity_type),
        "text": str(finding.text),
        "start": int(finding.start),
        "end": int(finding.end),
        "score": float(finding.score),
        "page_number": int(finding.page_number),
        "context": str(finding.context),
    }


def _finding_from_dict(payload: dict[str, Any]):
    from ai_pm_lab_privacy_gate.domain.models import Finding

    return Finding(
        finding_id=str(payload["finding_id"]),
        entity_type=str(payload["entity_type"]),
        text=str(payload["text"]),
        start=int(payload["start"]),
        end=int(payload["end"]),
        score=float(payload["score"]),
        page_number=int(payload["page_number"]),
        context=str(payload.get("context") or ""),
    )


def _warmup() -> dict[str, Any]:
    from ai_pm_lab_privacy_gate.domain.profiles import get_profile

    service = _service()
    document = service.document_from_text("PrivacyGate local worker warmup.")
    service.analyze(document, get_profile("general_business"), language="en")
    return {"status": "ready", "worker_pid": os.getpid()}


def _analyze(request: dict[str, Any]) -> dict[str, Any]:
    from ai_pm_lab_privacy_gate.domain.profiles import get_profile
    from ai_pm_lab_privacy_gate.infrastructure.local_api.browser_document_idempotency import (
        document_contains_privacygate_tokens,
    )

    filename = str(request.get("filename") or "")
    suffix = str(request.get("suffix") or "")
    profile_key = str(request.get("profile_key") or "general_business")
    language = str(request.get("language") or "en")
    source_bytes = request.get("source_bytes")
    if not isinstance(source_bytes, (bytes, bytearray)) or not source_bytes:
        raise ValueError("source_bytes is required")

    with tempfile.TemporaryDirectory(prefix="privacygate-browser-v2-") as temporary:
        source = Path(temporary) / f"source{suffix}"
        source.write_bytes(bytes(source_bytes))
        service = _service()
        document = service.document_from_file(source)
        if document_contains_privacygate_tokens(document):
            raise ValueError(
                "this file already contains PrivacyGate tokens; automatic re-protection is blocked"
            )
        findings = tuple(
            service.analyze(document, get_profile(profile_key), language=language)
        )

    page_by_number = {page.page_number: page for page in document.pages}
    public_findings = []
    internal_findings = []
    for finding in findings:
        internal = _finding_to_dict(finding)
        internal_findings.append(internal)
        page = page_by_number.get(finding.page_number)
        public_findings.append(
            {
                "finding_id": finding.finding_id,
                "entity_type": finding.entity_type,
                "page_number": finding.page_number,
                "location": page.location if page is not None else "",
                "score": round(float(finding.score), 6),
                "display_value": finding.text,
            }
        )

    return {
        "filename": filename,
        "source_kind": document.source_kind,
        "findings_count": len(findings),
        "findings": public_findings,
        "internal_findings": internal_findings,
        "worker_pid": os.getpid(),
    }


def _protect(request: dict[str, Any]) -> dict[str, Any]:
    from ai_pm_lab_privacy_gate.application.protect_session_service import (
        namespace_protection_result,
    )

    suffix = str(request.get("suffix") or "")
    namespace = str(request.get("namespace") or "")
    source_bytes = request.get("source_bytes")
    finding_payloads = request.get("findings")
    if not isinstance(source_bytes, (bytes, bytearray)) or not source_bytes:
        raise ValueError("source_bytes is required")
    if not isinstance(finding_payloads, list):
        raise ValueError("findings must be an array")

    selected = tuple(_finding_from_dict(item) for item in finding_payloads)
    with tempfile.TemporaryDirectory(prefix="privacygate-browser-v2-protect-") as temporary:
        source = Path(temporary) / f"source{suffix}"
        destination = Path(temporary) / f"protected{suffix}"
        source.write_bytes(bytes(source_bytes))
        service = _service()
        document = service.document_from_file(source)

        pages = {page.page_number: page for page in document.pages}
        for finding in selected:
            page = pages.get(finding.page_number)
            if page is None:
                raise ValueError("file changed between analysis and protection")
            if page.text[finding.start:finding.end] != finding.text:
                raise ValueError("file changed between analysis and protection")

        result = service.protect(document, selected, replacement_mode="reversible")
        if result.mappings:
            if not namespace:
                raise ValueError("namespace is required for reversible file protection")
            result = namespace_protection_result(result, namespace)

        if suffix == ".pdf":
            service.save_protected_pdf(result, destination)
        else:
            service.save_protected_document(result, destination, document)
        protected_bytes = destination.read_bytes()

    return {
        "protected_file_bytes": protected_bytes,
        "source_kind": document.source_kind,
        "applied_findings_count": len(result.applied_findings),
        "applied_finding_ids": [item.finding_id for item in result.applied_findings],
        "entity_types": sorted({item.entity_type for item in result.applied_findings}),
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


def run_browser_file_worker_v2(request: dict[str, Any]) -> dict[str, Any]:
    _configure_worker_resources()
    operation = str(request.get("operation") or "")
    if operation == "warmup":
        return _warmup()
    if operation == "analyze":
        return _analyze(request)
    if operation == "protect":
        return _protect(request)
    raise ValueError("unsupported browser file worker operation")
