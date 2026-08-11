from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ai_pm_lab_privacy_gate.infrastructure.mcp.auth import (
    McpOAuthMiddleware,
    OAuthResourceConfiguration,
)


class FakeValidator:
    def validate(self, token: str, required_scope: str) -> dict[str, object]:
        if token != "valid" or required_scope != "protected:read":
            raise ValueError("invalid")
        return {"sub": "connector-test", "scope": required_scope}


def _app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", lambda _request: JSONResponse({"ok": True}))])
    app.add_middleware(
        McpOAuthMiddleware,
        configuration=OAuthResourceConfiguration(
            resource="https://mcp-pg-test.propertydex.xyz/mcp",
            issuer="https://auth.propertydex.xyz",
            jwks_url="https://auth.propertydex.xyz/.well-known/jwks.json",
        ),
        validator=FakeValidator(),
    )
    return app


def test_production_http_boundary_requires_bearer_token() -> None:
    with TestClient(_app()) as client:
        response = client.get("/mcp")
    assert response.status_code == 401
    assert (
        'resource_metadata="https://mcp-pg-test.propertydex.xyz/'
        '.well-known/oauth-protected-resource/mcp"'
        in response.headers["www-authenticate"]
    )


def test_resource_metadata_is_public_but_mcp_requires_valid_scope() -> None:
    with TestClient(_app()) as client:
        metadata = client.get("/.well-known/oauth-protected-resource")
        denied = client.get("/mcp", headers={"Authorization": "Bearer invalid"})
        allowed = client.get("/mcp", headers={"Authorization": "Bearer valid"})

    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://mcp-pg-test.propertydex.xyz/mcp"
    assert metadata.json()["authorization_servers"] == ["https://auth.propertydex.xyz"]
    assert denied.status_code == 401
    assert allowed.json() == {"ok": True}
