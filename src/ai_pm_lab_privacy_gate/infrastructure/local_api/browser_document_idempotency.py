from __future__ import annotations

import re
from typing import Any


_PG_TOKEN_RE = re.compile(
    r"\[\[PG(?:\\?_[A-Z0-9]+)+\]\]",
    re.IGNORECASE,
)


def document_contains_privacygate_tokens(document: Any) -> bool:
    for page in getattr(document, "pages", ()):
        text = str(getattr(page, "text", "") or "")
        if _PG_TOKEN_RE.search(text):
            return True
    return False


def install_browser_document_idempotency(server: object) -> bool:
    handler_class = getattr(server, "RequestHandlerClass", None)
    if handler_class is None:
        return False
    if getattr(handler_class, "_privacygate_document_idempotency", False):
        return True

    original_pdf = getattr(handler_class, "_analyze_pdf", None)
    original_docx = getattr(handler_class, "_analyze_docx", None)

    if callable(original_pdf):
        def analyze_pdf(self, payload):
            response = original_pdf(self, payload)
            analysis_id = response.get("analysis_id") if isinstance(response, dict) else None
            try:
                item = self._pdf_store.get(analysis_id) if isinstance(analysis_id, str) else None
            except Exception:
                item = None
            if item is not None and document_contains_privacygate_tokens(item.document):
                try:
                    self._pdf_store.delete(analysis_id)
                finally:
                    raise ValueError(
                        "already_protected_document: this PDF already contains PrivacyGate tokens; "
                        "automatic re-protection is blocked to prevent double tokenization"
                    )
            return response

        handler_class._analyze_pdf = analyze_pdf

    if callable(original_docx):
        def analyze_docx(self, payload):
            response = original_docx(self, payload)
            analysis_id = response.get("analysis_id") if isinstance(response, dict) else None
            try:
                item = self._docx_store.get(analysis_id) if isinstance(analysis_id, str) else None
            except Exception:
                item = None
            if item is not None and document_contains_privacygate_tokens(item.document):
                try:
                    self._docx_store.delete(analysis_id)
                finally:
                    raise ValueError(
                        "already_protected_document: this Word document already contains PrivacyGate tokens; "
                        "automatic re-protection is blocked to prevent double tokenization"
                    )
            return response

        handler_class._analyze_docx = analyze_docx

    handler_class._privacygate_document_idempotency = True
    return True
