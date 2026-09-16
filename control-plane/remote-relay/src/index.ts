export interface Env {
  ROOMS: DurableObjectNamespace<RelayRoom>;
}

const ROOM_RE = /^[A-Za-z0-9._-]{8,128}$/;
const MAX_FRAME_BYTES = 2_000_000;

function json(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/healthz") {
      return json(200, {
        status: "ok",
        service: "privacygate-device-relay",
        stores_payloads: false,
      });
    }

    const prefix = "/v1/device/";
    if (!url.pathname.startsWith(prefix)) {
      return json(404, { error: "not_found" });
    }
    if (request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
      return json(426, { error: "websocket_required" });
    }

    const room = decodeURIComponent(url.pathname.slice(prefix.length));
    if (!ROOM_RE.test(room)) {
      return json(400, { error: "invalid_room" });
    }
    const role = url.searchParams.get("role");
    if (role !== "desktop" && role !== "mobile") {
      return json(400, { error: "invalid_role" });
    }

    // The room id is an opaque routing identifier only. PrivacyGate encrypts
    // every application frame end-to-end before it reaches this Worker.
    const id = env.ROOMS.idFromName(room);
    return env.ROOMS.get(id).fetch(request);
  },
} satisfies ExportedHandler<Env>;

export class RelayRoom implements DurableObject {
  constructor(private readonly state: DurableObjectState) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const role = url.searchParams.get("role");
    if (role !== "desktop" && role !== "mobile") {
      return json(400, { error: "invalid_role" });
    }
    if (request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
      return json(426, { error: "websocket_required" });
    }

    // There is exactly one authoritative Desktop endpoint per room. Mobile may
    // reconnect briefly while an older socket is closing, so multiple Mobile
    // sockets are tolerated; encrypted message ids keep responses correlated.
    if (role === "desktop" && this.state.getWebSockets("desktop").length > 0) {
      return json(409, { error: "desktop_already_connected" });
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    this.state.acceptWebSocket(server, [role]);
    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(
    socket: WebSocket,
    message: string | ArrayBuffer,
  ): Promise<void> {
    const size =
      typeof message === "string"
        ? new TextEncoder().encode(message).byteLength
        : message.byteLength;
    if (size <= 0 || size > MAX_FRAME_BYTES) {
      socket.close(1009, "frame_too_large");
      return;
    }

    const tags = this.state.getTags(socket);
    const role = tags.includes("desktop") ? "desktop" : "mobile";
    const targetRole = role === "desktop" ? "mobile" : "desktop";
    for (const peer of this.state.getWebSockets(targetRole)) {
      try {
        peer.send(message);
      } catch {
        // A stale peer is ignored; Cloudflare will deliver its close/error event.
      }
    }
  }

  async webSocketClose(
    socket: WebSocket,
    code: number,
    reason: string,
    wasClean: boolean,
  ): Promise<void> {
    try {
      socket.close(code, reason);
    } catch {
      // Already closed.
    }
    void wasClean;
  }

  async webSocketError(socket: WebSocket): Promise<void> {
    try {
      socket.close(1011, "relay_socket_error");
    } catch {
      // Already closed.
    }
  }
}
