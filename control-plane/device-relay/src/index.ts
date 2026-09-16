interface Env {
  DEVICE_RELAY: DurableObjectNamespace;
}

const ROOM_ID = /^[A-Za-z0-9_-]{20,128}$/;
const RELAY_TOKEN = /^[A-Za-z0-9_-]{32,256}$/;
const MAX_FRAME_BYTES = 2_500_000;
const encoder = new TextEncoder();

function json(data: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function bytesEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) diff |= left[index] ^ right[index];
  return diff === 0;
}

async function digest(value: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

function websocketOpen(socket: WebSocket | null): socket is WebSocket {
  return socket !== null && socket.readyState === WebSocket.OPEN;
}

export class DeviceRelay {
  private desktop: WebSocket | null = null;
  private mobile: WebSocket | null = null;
  private tokenDigest: Uint8Array | null = null;

  constructor(
    private readonly state: DurableObjectState,
    private readonly env: Env,
  ) {}

  async fetch(request: Request): Promise<Response> {
    if (request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
      return json({ error: "websocket_required" }, 426);
    }

    const url = new URL(request.url);
    const role = url.searchParams.get("role");
    const token = url.searchParams.get("token") ?? "";
    if ((role !== "desktop" && role !== "mobile") || !RELAY_TOKEN.test(token)) {
      return json({ error: "invalid_relay_credentials" }, 400);
    }

    const incomingDigest = await digest(token);
    if (this.tokenDigest === null) {
      // Desktop is authoritative for creating a live room. A mobile client can
      // never initialize an abandoned/guessed room on its own.
      if (role !== "desktop") return json({ error: "desktop_not_connected" }, 409);
      this.tokenDigest = incomingDigest;
    } else if (!bytesEqual(this.tokenDigest, incomingDigest)) {
      return json({ error: "relay_unauthorized" }, 401);
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    server.accept();

    const previous = role === "desktop" ? this.desktop : this.mobile;
    if (websocketOpen(previous)) previous.close(4001, "Replaced by a newer Device Trust connection");
    if (role === "desktop") this.desktop = server;
    else this.mobile = server;

    server.addEventListener("message", (event) => this.forward(role, server, event.data));
    server.addEventListener("close", () => this.detach(role, server));
    server.addEventListener("error", () => this.detach(role, server));

    server.send(JSON.stringify({ type: "relay_ready", peer: role === "desktop" ? "mobile" : "desktop" }));
    this.notifyPeer(role, { type: "peer_online", peer: role });

    return new Response(null, { status: 101, webSocket: client });
  }

  private forward(role: "desktop" | "mobile", source: WebSocket, data: string | ArrayBuffer): void {
    if (data instanceof ArrayBuffer) {
      if (data.byteLength > MAX_FRAME_BYTES) {
        source.close(1009, "Frame too large");
        return;
      }
    } else if (encoder.encode(data).byteLength > MAX_FRAME_BYTES) {
      source.close(1009, "Frame too large");
      return;
    }

    if (typeof data === "string") {
      try {
        const control = JSON.parse(data) as Record<string, unknown>;
        if (control.type === "ping") {
          source.send(JSON.stringify({ type: "pong", at: Date.now() }));
          return;
        }
      } catch {
        // Encrypted application frames are JSON too, but the relay deliberately
        // does not inspect or interpret them beyond the optional ping control.
      }
    }

    const peer = role === "desktop" ? this.mobile : this.desktop;
    if (!websocketOpen(peer)) {
      source.send(JSON.stringify({ type: "peer_offline", peer: role === "desktop" ? "mobile" : "desktop" }));
      return;
    }
    peer.send(data);
  }

  private notifyPeer(role: "desktop" | "mobile", message: Record<string, unknown>): void {
    const peer = role === "desktop" ? this.mobile : this.desktop;
    if (websocketOpen(peer)) peer.send(JSON.stringify(message));
  }

  private detach(role: "desktop" | "mobile", socket: WebSocket): void {
    if (role === "desktop" && this.desktop === socket) this.desktop = null;
    if (role === "mobile" && this.mobile === socket) this.mobile = null;
    this.notifyPeer(role, { type: "peer_offline", peer: role });

    // No messages, documents, mappings, or room secrets are persisted. When
    // both peers leave, the in-memory room can disappear with the Durable Object.
    if (!websocketOpen(this.desktop) && !websocketOpen(this.mobile)) this.tokenDigest = null;
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "ok", content_storage: false, relay: "ciphertext_only" });
    }

    const match = /^\/v1\/relay\/([A-Za-z0-9_-]{20,128})$/.exec(url.pathname);
    if (!match || !ROOM_ID.test(match[1])) return json({ error: "not_found" }, 404);

    const id = env.DEVICE_RELAY.idFromName(match[1]);
    return env.DEVICE_RELAY.get(id).fetch(request);
  },
};
