from __future__ import annotations

from typing import Any


SUPPORTED_BROWSER_AI_PROVIDERS = frozenset({"chatgpt", "claude", "gemini"})


def browser_provider(payload: dict[str, Any], *, default: str = "chatgpt") -> str:
    """Return the validated AI provider supplied by the paired browser extension.

    The provider is metadata only; sensitive values remain local.  A default keeps
    existing/local tests and older extension builds compatible while the current
    extension always sends the concrete provider for supported AI websites.
    """

    raw = payload.get("provider", default)
    provider = str(raw or default).strip().lower()
    if provider not in SUPPORTED_BROWSER_AI_PROVIDERS:
        raise ValueError("unsupported AI provider")
    return provider
