from __future__ import annotations

import base64
import binascii
import io
import re
from collections import Counter, defaultdict
from typing import Any

from pypdf import PdfReader

from .browser_pdf import PersistentBrowserPdfRequestHandler
from .server import LocalApiHttpServer


def _occurrence_pattern(value: str) -> re.Pattern[str] | None:
    """Match one extracted value without turning substrings into false leaks.

    PDF text extraction can change runs of whitespace, so spaces are flexible.
    Word boundaries are applied only when the original begins/ends with a word
    character. This keeps values such as names, dates, phones, IDs and emails
    exact enough for a residual check while avoiding e.g. ``AI`` matching the
    middle of ``PrivacyGate``.
    """
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    chunks = re.split(r"\s+", cleaned)
    body = r"\s+".join(re.escape(chunk) for chunk in chunks if chunk)
    if not body:
        return None
    prefix = r"(?<!\w)" if cleaned[0].isalnum() or cleaned[0] == "_" else ""
    suffix = r"(?!\w)" if cleaned[-1].isalnum() or cleaned[-1] == "_" else ""
    return re.compile(prefix + body + suffix, re.IGNORECASE)


def _count_occurrences(text: str, value: str) -> int:
    pattern = _occurrence_pattern(value)
    if pattern is None:
        return 0
    return sum(1 for _match in pattern.finditer(text))


class IntegrityBrowserPdfRequestHandler(PersistentBrowserPdfRequestHandler):
    """Fail closed only when a selected source occurrence survives the output.

    The previous version searched each selected original value anywhere in the
    generated PDF. That was too strict for repeated words/values: protecting one
    occurrence while intentionally leaving another identical, unselected
    occurrence would be reported as a leak. Here we account for source counts and
    selected finding counts, then require the generated PDF to contain no more
    than the legitimately unselected remainder.
    """

    @staticmethod
    def _pdf_text(encoded: object) -> str:
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("Protected PDF integrity check failed: output payload is missing")
        try:
            raw = base64.b64decode(encoded, validate=True)
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except (binascii.Error, ValueError, TypeError) as error:
            raise ValueError(
                "Protected PDF integrity check failed: output PDF could not be verified"
            ) from error
        except Exception as error:
            raise ValueError(
                "Protected PDF integrity check failed: output PDF could not be verified"
            ) from error

    def _selected_source_findings(self, payload: dict[str, Any]):
        analysis_id = payload.get("analysis_id")
        if not isinstance(analysis_id, str) or not analysis_id:
            return None, ()
        try:
            item = self._pdf_store.get(analysis_id)
        except KeyError:
            return None, ()

        requested_ids = payload.get("finding_ids")
        if requested_ids is None:
            return item, tuple(item.findings)
        if not isinstance(requested_ids, list):
            return item, ()
        requested = {value for value in requested_ids if isinstance(value, str)}
        return item, tuple(
            finding for finding in item.findings if finding.finding_id in requested
        )

    def _protect_pdf(self, payload: dict[str, Any]) -> dict[str, object]:
        item, selected = self._selected_source_findings(payload)

        # Let the proven browser-PDF handler perform all authoritative request
        # validation, namespacing, persistence and PDF generation.
        response = super()._protect_pdf(payload)

        if item is None or not selected:
            response["integrity_verified"] = True
            response["integrity_checked_mappings"] = 0
            response["integrity_checked_findings"] = 0
            return response

        source_text = "\n".join(page.text for page in item.document.pages)
        protected_text = self._pdf_text(response.get("protected_file_base64"))

        selected_counts: Counter[str] = Counter()
        original_by_key: dict[str, str] = {}
        types_by_key: dict[str, set[str]] = defaultdict(set)
        for finding in selected:
            original = str(finding.text or "").strip()
            if not original:
                continue
            key = re.sub(r"\s+", " ", original).casefold()
            selected_counts[key] += 1
            original_by_key.setdefault(key, original)
            types_by_key[key].add(finding.entity_type)

        leaked_types: set[str] = set()
        for key, selected_count in selected_counts.items():
            original = original_by_key[key]
            source_count = _count_occurrences(source_text, original)
            output_count = _count_occurrences(protected_text, original)

            # If the detector emitted overlapping duplicate findings, source_count
            # can be lower than selected_count. In that case zero surviving exact
            # occurrences is the only safe result.
            allowed_remaining = max(0, source_count - selected_count)
            if output_count > allowed_remaining:
                leaked_types.update(types_by_key[key])

        if leaked_types:
            categories = ", ".join(sorted(leaked_types))
            raise ValueError(
                "Protected PDF integrity check failed: a selected sensitive occurrence "
                f"remains in generated PDF ({categories})"
            )

        response["integrity_verified"] = True
        response["integrity_checked_mappings"] = len(selected)
        response["integrity_checked_findings"] = len(selected)
        return response


def install_browser_pdf_integrity(server: object) -> bool:
    """Install only after browser PDF support; never changes the base local API."""
    if not isinstance(server, LocalApiHttpServer):
        return False
    if not hasattr(server, "browser_pdf_store"):
        return False
    server.RequestHandlerClass = IntegrityBrowserPdfRequestHandler
    return True
