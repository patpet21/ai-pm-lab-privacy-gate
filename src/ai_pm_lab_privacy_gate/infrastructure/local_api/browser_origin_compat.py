from __future__ import annotations

import hmac


def _origin_for_token(registry, token: str | None) -> str:
    """Resolve the paired extension origin for a valid scoped browser token.

    Chromium normally sends ``Origin: chrome-extension://...`` for extension fetches,
    but service-worker requests can omit Origin in some runtime paths. Pairing itself
    still requires a real extension Origin; this fallback is used only after a valid
    scoped token already exists.
    """
    if not token:
        return ""

    token_hash = registry._token_hash(token)
    with registry._lock:
        records = registry._load()

    for origin, record in records.items():
        clients = record.get("clients")
        if not isinstance(clients, list):
            continue
        for client in clients:
            if not isinstance(client, dict):
                continue
            expected = client.get("token_hash")
            if isinstance(expected, str) and hmac.compare_digest(token_hash, expected):
                return origin
    return ""


def install_browser_origin_compat(server) -> bool:
    """Allow authenticated extension requests whose Chromium Origin is omitted.

    Security properties are preserved:
    - first-time pairing still requires an explicit ``chrome-extension://`` Origin;
    - an explicit non-extension Origin is never replaced or trusted;
    - the fallback activates only when Origin is absent *and* the request already
      carries a browser token that matches a credential stored by PrivacyGate.

    The manager accepts an injectable server factory for lifecycle/unit tests. Those
    lightweight servers deliberately do not expose HTTP handler internals, so this
    optional compatibility layer must safely no-op for them rather than turning an
    otherwise healthy bridge lifecycle test into an application startup error.
    """
    handler_class = getattr(server, "RequestHandlerClass", None)
    if handler_class is None:
        return False

    original_browser_origin = getattr(handler_class, "_browser_origin", None)
    if not callable(original_browser_origin):
        return False

    if getattr(handler_class, "_privacygate_browser_origin_compat", False):
        return True

    def browser_origin(self) -> str:
        origin = original_browser_origin(self)
        if origin:
            return origin

        # Never override an explicit Origin such as https://evil.example or null.
        # The normal transport policy remains responsible for rejecting it.
        if self.headers.get("Origin"):
            return ""

        return _origin_for_token(self.server.browser_pairing, self._bearer_token())

    handler_class._browser_origin = browser_origin
    handler_class._privacygate_browser_origin_compat = True
    return True
