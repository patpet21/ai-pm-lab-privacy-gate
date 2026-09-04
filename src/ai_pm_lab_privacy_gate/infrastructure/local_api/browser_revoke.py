from __future__ import annotations

from .server import LocalApiHttpServer


_BROWSER_REVOKE_PATH = "/v1/browser/pairing"


def install_browser_revoke_support(server: object) -> bool:
    """Add a scoped browser disconnect route to the current local-API handler stack.

    The route revokes only the bearer credential making the request. Other Chrome,
    Edge, Brave or AVG clients paired under the same chrome-extension origin remain
    connected. Installation is deliberately layered after the existing AI/PDF
    handlers so no proven browser protection route is replaced.
    """

    if not isinstance(server, LocalApiHttpServer):
        return False
    if bool(getattr(server, "browser_revoke_support", False)):
        return True

    base_handler = server.RequestHandlerClass

    class BrowserRevokeRequestHandler(base_handler):  # type: ignore[misc, valid-type]
        def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != _BROWSER_REVOKE_PATH:
                super().do_DELETE()
                return
            if self._reject_if_untrusted_transport():
                return

            origin = self._browser_origin()
            token = self._bearer_token()
            if not origin:
                self._send_json(403, {"error": "browser_origin_required"})
                return
            if not self._browser_authorized():
                self._send_json(401, {"error": "browser_pairing_required"})
                return

            revoked = self.server.browser_pairing.revoke_token(origin, token)
            if not revoked:
                self._send_json(401, {"error": "browser_pairing_required"})
                return
            self._send_json(200, {"revoked": True})

    BrowserRevokeRequestHandler.__name__ = "BrowserRevokeRequestHandler"
    server.RequestHandlerClass = BrowserRevokeRequestHandler
    server.browser_revoke_support = True
    return True
