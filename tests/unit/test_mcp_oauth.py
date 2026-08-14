from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ai_pm_lab_privacy_gate.infrastructure.mcp.auth import (
    McpOAuthMiddleware,
    OAuthResourceConfiguration,
)


class FakeValidator:
    def validate(self, token: str, required_scopes: tuple[str, ...]) -> dict[str, object]:
        if token != "valid" or required_scopes != ("openid", "email", "offline_access"):
            raise ValueError("invalid")
        return {"sub": "connector-test", "scope": " ".join(required_scopes)}


def _app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", lambda _request: JSONResponse({"ok": True}))])
    app.add_middleware(
        McpOAuthMiddleware,
        configuration=OAuthResourceConfiguration(
            resource="https://mcp-pg-test.propertydex.xyz/mcp",
            issuer="https://project.supabase.co/auth/v1",
            jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
            token_audience="authenticated",
            expected_subject="account-owner",
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
    assert metadata.json()["authorization_servers"] == ["https://project.supabase.co/auth/v1"]
    assert metadata.json()["scopes_supported"] == ["openid", "email", "offline_access"]
    assert denied.status_code == 401
    assert allowed.json() == {"ok": True}
