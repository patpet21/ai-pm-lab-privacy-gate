from __future__ import annotations

import base64
import http.client
import json
import os
import re
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from websockets.sync.client import ClientConnection, connect

from .pairing import MobilePairingRegistry

DEFAULT_DEVICE_RELAY_URL = os.environ.get(
    "PRIVACY_GATE_DEVICE_RELAY_URL",
    "wss://relay.propertydex.xyz/v1/relay",
).rstrip("/")
_MAX_ENCRYPTED_FRAME = 2_500_000
_ROOM_ID = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{12,128}$")
_GRANT_PATH = re.compile(r"^/v1/mobile/library/grants/[A-Za-z0-9_-]{12,128}$")


def _b64url_decode(value: str) -> bytes:
    raw = value.encode("ascii")
    return base64.urlsafe_b64decode(raw + b"=" * ((4 - len(raw) % 4) % 4))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _aad(room_id: str, direction: str, request_id: str) -> bytes:
    return f"privacygate-device-trust-remote-v1\n{room_id}\n{direction}\n{request_id}".encode(
        "utf-8"
    )


def _decrypt_frame(
    frame: str,
    *,
    room_id: str,
    secret: bytes,
    direction: str,
) -> tuple[str, dict[str, Any]]:
    if len(frame.encode("utf-8")) > _MAX_ENCRYPTED_FRAME:
        raise ValueError("relay frame is too large")
    decoded = json.loads(frame)
    if not isinstance(decoded, dict) or decoded.get("v") != 1:
        raise ValueError("relay frame is invalid")
    request_id = decoded.get("id")
    nonce = decoded.get("nonce")
    ciphertext = decoded.get("ciphertext")
    if (
        not isinstance(request_id, str)
        or not _REQUEST_ID.fullmatch(request_id)
        or not isinstance(nonce, str)
        or not isinstance(ciphertext, str)
    ):
        raise ValueError("relay frame fields are invalid")
    clear = AESGCM(secret).decrypt(
        _b64url_decode(nonce),
        _b64url_decode(ciphertext),
        _aad(room_id, direction, request_id),
    )
    payload = json.loads(clear.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("relay payload must be an object")
    return request_id, payload


def _encrypt_frame(
    request_id: str,
    payload: dict[str, Any],
    *,
    room_id: str,
    secret: bytes,
    direction: str,
) -> str:
    nonce = os.urandom(12)
    clear = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(secret).encrypt(
        nonce,
        clear,
        _aad(room_id, direction, request_id),
    )
    return json.dumps(
        {
            "v": 1,
            "id": request_id,
            "nonce": _b64url_encode(nonce),
            "ciphertext": _b64url_encode(ciphertext),
        },
        separators=(",", ":"),
    )


def _allowed_target(method: str, target: str) -> bool:
    parsed = urlsplit(target)
    path = parsed.path
    if method == "GET" and path in {
        "/v1/mobile/status",
        "/v1/mobile/library/grants",
    }:
        return True
    if method == "GET" and _GRANT_PATH.fullmatch(path):
        return True
    if method == "POST" and path == "/v1/mobile/analyze":
        return True
    if method in {"PATCH", "DELETE"} and path == "/v1/mobile/device":
        return True
    return False


def _forward_to_local_server(
    *,
    port: int,
    method: str,
    target: str,
    bearer_token: str,
    body: object,
) -> tuple[int, dict[str, Any]]:
    method = method.upper().strip()
    if not _allowed_target(method, target):
        return 403, {"error": "remote_operation_not_allowed"}
    if not bearer_token:
        return 401, {"error": "mobile_pairing_required"}

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    connection = http.client.HTTPSConnection("127.0.0.1", int(port), context=context, timeout=30)
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "Cache-Control": "no-store",
        }
        encoded: str | None = None
        if method not in {"GET", "DELETE"}:
            encoded = json.dumps(body if isinstance(body, dict) else {}, separators=(",", ":"))
            headers["Content-Type"] = "application/json"
        connection.request(method, target, body=encoded, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"error": "invalid_local_response"}
        if not isinstance(payload, dict):
            payload = {"error": "invalid_local_response"}
        return int(response.status), payload
    finally:
        connection.close()


@dataclass(frozen=True, slots=True)
class RemoteRelaySnapshot:
    configured: int
    connected: int


class _DeviceRelayConnector:
    def __init__(
        self,
        *,
        client_id: str,
        room_id: str,
        relay_token: str,
        remote_secret: str,
        local_port: int,
        relay_base_url: str,
    ) -> None:
        self.client_id = client_id
        self.room_id = room_id
        self.relay_token = relay_token
        self.secret = _b64url_decode(remote_secret)
        if len(self.secret) != 32:
            raise ValueError("remote E2E secret must contain 32 bytes")
        self.local_port = int(local_port)
        self.relay_base_url = relay_base_url.rstrip("/")
        self.stop_event = threading.Event()
        self.connected = False
        self._socket_lock = threading.RLock()
        self._socket: ClientConnection | None = None
        self.thread = threading.Thread(
            target=self._run,
            name=f"PrivacyGateRemoteRelay-{client_id[-8:]}",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        with self._socket_lock:
            socket = self._socket
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass
        if self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)

    def _run(self) -> None:
        delay = 1.0
        while not self.stop_event.is_set():
            try:
                url = (
                    f"{self.relay_base_url}/{quote(self.room_id, safe='')}"
                    f"?role=desktop&token={quote(self.relay_token, safe='')}"
                )
                with connect(
                    url,
                    open_timeout=5,
                    close_timeout=2,
                    max_size=_MAX_ENCRYPTED_FRAME,
                    compression=None,
                ) as socket:
                    with self._socket_lock:
                        self._socket = socket
                    self.connected = True
                    delay = 1.0
                    self._serve(socket)
            except Exception:
                self.connected = False
            finally:
                self.connected = False
                with self._socket_lock:
                    self._socket = None
            if self.stop_event.wait(delay):
                break
            delay = min(delay * 2.0, 20.0)

    def _serve(self, socket: ClientConnection) -> None:
        while not self.stop_event.is_set():
            message = socket.recv(timeout=45)
            if not isinstance(message, str):
                continue
            try:
                control = json.loads(message)
            except json.JSONDecodeError:
                control = None
            if isinstance(control, dict) and isinstance(control.get("type"), str):
                message_type = str(control["type"])
                if message_type in {"relay_ready", "peer_online", "peer_offline", "pong"}:
                    if message_type == "peer_offline":
                        socket.send(json.dumps({"type": "ping"}, separators=(",", ":")))
                    continue

            request_id = ""
            try:
                request_id, request = _decrypt_frame(
                    message,
                    room_id=self.room_id,
                    secret=self.secret,
                    direction="mobile_to_desktop",
                )
                method = str(request.get("method") or "").upper()
                target = str(request.get("target") or "")
                token = str(request.get("bearer_token") or "")
                status, payload = _forward_to_local_server(
                    port=self.local_port,
                    method=method,
                    target=target,
                    bearer_token=token,
                    body=request.get("body"),
                )
            except Exception:
                if not request_id:
                    continue
                status, payload = 502, {"error": "desktop_remote_bridge_error"}

            socket.send(
                _encrypt_frame(
                    request_id,
                    {"status": status, "body": payload},
                    room_id=self.room_id,
                    secret=self.secret,
                    direction="desktop_to_mobile",
                )
            )


class RemoteRelayHub:
    """Maintain outbound-only encrypted relay connections for trusted devices."""

    def __init__(
        self,
        pairing: MobilePairingRegistry,
        *,
        relay_base_url: str = DEFAULT_DEVICE_RELAY_URL,
    ) -> None:
        self.pairing = pairing
        self.relay_base_url = relay_base_url.rstrip("/")
        self._lock = threading.RLock()
        self._connectors: dict[str, _DeviceRelayConnector] = {}
        self._port: int | None = None

    @property
    def snapshot(self) -> RemoteRelaySnapshot:
        with self._lock:
            return RemoteRelaySnapshot(
                configured=len(self._connectors),
                connected=sum(1 for item in self._connectors.values() if item.connected),
            )

    def sync(self, local_port: int) -> RemoteRelaySnapshot:
        port = int(local_port)
        records = self.pairing.list_clients()
        desired = {str(item["client_id"]) for item in records}
        with self._lock:
            self._port = port
            stale = [client_id for client_id in self._connectors if client_id not in desired]
            for client_id in stale:
                connector = self._connectors.pop(client_id)
                connector.stop()

            for client_id in sorted(desired):
                remote = self.pairing.ensure_remote_for_client(client_id)
                if remote is None:
                    continue
                current = self._connectors.get(client_id)
                if current is not None and current.local_port == port:
                    continue
                if current is not None:
                    current.stop()
                connector = _DeviceRelayConnector(
                    client_id=client_id,
                    room_id=remote["relay_room_id"],
                    relay_token=remote["relay_token"],
                    remote_secret=remote["remote_secret"],
                    local_port=port,
                    relay_base_url=self.relay_base_url,
                )
                self._connectors[client_id] = connector
                connector.start()
        return self.snapshot

    def remove_client(self, client_id: str) -> None:
        with self._lock:
            connector = self._connectors.pop(str(client_id), None)
        if connector is not None:
            connector.stop()

    def stop(self) -> None:
        with self._lock:
            connectors = list(self._connectors.values())
            self._connectors.clear()
            self._port = None
        for connector in connectors:
            connector.stop()
