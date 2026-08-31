from __future__ import annotations

from typing import Any, Iterable

from ai_pm_lab_privacy_gate.domain.models import Finding

from .browser_pdf import PersistentBrowserPdfRequestHandler
from .server import LocalApiHttpServer


def add_local_review_values(
    response: dict[str, object],
    findings: Iterable[Finding],
    *,
    profile_key: str,
    language: str,
) -> dict[str, object]:
    """Add exact detected values to a browser-only analysis response.

    These values are returned only over the authenticated localhost browser
    route so the paired PrivacyGate extension can present the same review
    experience as the desktop/text flow. They are not written into ChatGPT's
    page and are never sent to the AI provider by this layer.
    """

    finding_by_id = {finding.finding_id: finding for finding in findings}
    rows = response.get("findings")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            finding = finding_by_id.get(str(row.get("finding_id") or ""))
            if finding is None:
                continue
            row["display_value"] = finding.text
            row["start"] = finding.start
            row["end"] = finding.end

    response["profile_key"] = profile_key
    response["language"] = language
    response["review_values_local_only"] = True
    return response


class ReviewBrowserPdfRequestHandler(PersistentBrowserPdfRequestHandler):
    """Browser PDF handler with local review metadata only."""

    def _analyze_pdf(self, payload: dict[str, Any]) -> dict[str, object]:
        response = super()._analyze_pdf(payload)
        analysis_id = response.get("analysis_id")
        if not isinstance(analysis_id, str):
            return response

        item = self._pdf_store.get(analysis_id)
        return add_local_review_values(
            response,
            item.findings,
            profile_key=item.profile_key,
            language=item.language,
        )


def install_browser_pdf_review(server: object) -> bool:
    """Install after browser PDF support without changing the PDF engine."""

    if not isinstance(server, LocalApiHttpServer):
        return False
    if not hasattr(server, "browser_pdf_store"):
        return False
    server.RequestHandlerClass = ReviewBrowserPdfRequestHandler
    return True
