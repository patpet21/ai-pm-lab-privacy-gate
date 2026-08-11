from __future__ import annotations

import ssl
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import truststore

from ai_pm_lab_privacy_gate.infrastructure.mcp.device_identity import DeviceIdentityKey
from ai_pm_lab_privacy_gate.infrastructure.mcp.identity import ConnectionIdentityStore
from ai_pm_lab_privacy_gate.infrastructure.mcp.provisioning import (
    NamedTunnelConfiguration,
    ProvisioningStore,
)


DEFAULT_CONTROL_PLANE = "https://auth.propertydex.xyz"
ENROLLMENT_SESSION_SECRET = "mcp.enrollment_session_secret"
ENROLLMENT_SESSION_ID = "mcp.enrollment_session_id"


@dataclass(frozen=True)
class EnrollmentStart:
    session_id: str
    activation_url: str


class ProvisioningHttpClient:
    """Metadata-only client. Document content is never accepted by this API."""

    def __init__(
        self,
        identity_store: ConnectionIdentityStore,
        base_url: str = DEFAULT_CONTROL_PLANE,
    ) -> None:
        self.identity_store = identity_store
        self.base_url = base_url.rstrip("/")
        self.device_key = DeviceIdentityKey(identity_store.secrets)
        self.store = ProvisioningStore(identity_store.data_dir, identity_store.secrets)

    @staticmethod
    def _client(timeout: int = 20) -> httpx.Client:
        """Use the operating-system trust store on Windows and macOS.

        This keeps TLS verification enabled while respecting locally trusted
        security products and enterprise certificate authorities.
        """
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return httpx.Client(verify=context, timeout=timeout)

    def start_enrollment(self) -> EnrollmentStart:
        identity = self.identity_store.load_or_create()
        with self._client() as client:
            response = client.post(
                f"{self.base_url}/v1/enrollments",
                json={
                    "installation_id": identity.installation_id,
                    "device_public_jwk": self.device_key.public_jwk(),
                    "app_version": "0.4.0",
                    "platform": "desktop",
                },
            )
        response.raise_for_status()
        payload = response.json()
        self.identity_store.secrets.set(ENROLLMENT_SESSION_ID, payload["session_id"])
        self.identity_store.secrets.set(ENROLLMENT_SESSION_SECRET, payload["session_secret"])
        return EnrollmentStart(payload["session_id"], payload["activation_url"])

    def poll_enrollment(self) -> str:
        session_id = self.identity_store.secrets.get(ENROLLMENT_SESSION_ID)
        session_secret = self.identity_store.secrets.get(ENROLLMENT_SESSION_SECRET)
        if not session_id or not session_secret:
            return "not_started"
        with self._client(timeout=30) as client:
            response = client.get(
                f"{self.base_url}/v1/enrollments/{session_id}",
                headers={"Authorization": f"Bearer {session_secret}"},
            )
        response.raise_for_status()
        payload = response.json()
        if payload["state"] != "ready":
            return str(payload["state"])
        configuration = NamedTunnelConfiguration(**payload["configuration"])
        self.store.save(configuration, payload["tunnel_token"])
        self.identity_store.secrets.delete(ENROLLMENT_SESSION_ID)
        self.identity_store.secrets.delete(ENROLLMENT_SESSION_SECRET)
        return "ready"

    def rotate_production_credential(self) -> NamedTunnelConfiguration:
        payload = self._signed_post("/v1/device/rotate", b"{}").json()
        configuration = NamedTunnelConfiguration(**payload["configuration"])
        self.store.save(configuration, payload["tunnel_token"])
        return configuration

    def revoke_production_device(self) -> None:
        self._signed_post("/v1/device/revoke", b"{}")
        self.store.remove()

    def _signed_post(self, path: str, body: bytes) -> httpx.Response:
        identity = self.identity_store.load_or_create()
        headers = self.device_key.sign_request(
            identity.installation_id, "POST", path, body
        ).as_http_headers()
        headers["Content-Type"] = "application/json"
        with self._client() as client:
            response = client.post(f"{self.base_url}{path}", content=body, headers=headers)
        response.raise_for_status()
        return response

    def validate_control_plane_origin(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname != "auth.propertydex.xyz":
            raise ValueError("Unexpected production control-plane origin")
