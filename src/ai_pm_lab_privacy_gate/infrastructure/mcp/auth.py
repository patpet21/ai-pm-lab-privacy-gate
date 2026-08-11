from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import jwt
import truststore
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


REQUIRED_SCOPE = "protected:read"


@dataclass(frozen=True)
class OAuthResourceConfiguration:
    resource: str
    issuer: str
    jwks_url: str
    required_scope: str = REQUIRED_SCOPE

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": ["protected:metadata", "protected:read"],
            "resource_documentation": "https://privacygate.propertydex.xyz/#mcp",
        }

    @property
    def metadata_url(self) -> str:
        parsed = urlsplit(self.resource)
        path = parsed.path.rstrip("/") or "/mcp"
        return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{path}"


class AccessTokenValidator(Protocol):
    def validate(self, token: str, required_scope: str) -> dict[str, object]: ...


class JwtAccessTokenValidator:
    """Validate short-lived asymmetric access tokens issued for this exact MCP resource."""

    def __init__(self, configuration: OAuthResourceConfiguration) -> None:
        self.configuration = configuration
        self.jwks = jwt.PyJWKClient(
            configuration.jwks_url,
            cache_keys=True,
            headers={"User-Agent": "AI-PM-LAB-Privacy-Gate/0.4"},
            ssl_context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )

    def validate(self, token: str, required_scope: str) -> dict[str, object]:
        signing_key = self.jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=self.configuration.resource,
            issuer=self.configuration.issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
        raw_scopes = claims.get("scope", "")
        scopes = set(raw_scopes.split()) if isinstance(raw_scopes, str) else set(raw_scopes or ())
        if required_scope not in scopes:
            raise jwt.InvalidTokenError("Required scope is missing")
        return dict(claims)


class McpOAuthMiddleware(BaseHTTPMiddleware):
    """Enforce OAuth at the HTTP boundary before a request reaches MCP tools."""

    def __init__(
        self,
        app,
        *,
        configuration: OAuthResourceConfiguration,
        validator: AccessTokenValidator | None = None,
    ) -> None:
        super().__init__(app)
        self.configuration = configuration
        self.validator = validator or JwtAccessTokenValidator(configuration)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in {
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        }:
            return JSONResponse(
                self.configuration.metadata,
                headers={"Cache-Control": "public, max-age=300"},
            )
        if request.method == "OPTIONS":
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            return self._unauthorized()
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = self.validator.validate(token, self.configuration.required_scope)
        except Exception:
            return self._unauthorized()
        request.state.oauth_claims = claims
        return await call_next(request)

    def _unauthorized(self) -> JSONResponse:
        metadata_url = self.configuration.metadata_url
        challenge = (
            f'Bearer resource_metadata="{metadata_url}", '
            f'scope="{self.configuration.required_scope}"'
        )
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": challenge, "Cache-Control": "no-store"},
        )
