# PrivacyGate Device Relay

This Cloudflare Worker + Durable Object is a routing layer for PrivacyGate Device Trust when Mobile and Desktop are not on the same LAN.

## Privacy boundary

- The relay never receives plaintext PrivacyGate application messages.
- Mobile and Desktop derive an end-to-end AES-256-GCM key from the existing per-device pairing credential.
- The relay room is the random `client_id`; it is a routing identifier, not an encryption key.
- The Worker does not write frames to D1, KV, R2, Durable Object storage, logs, or analytics code.
- The Desktop opens an outbound WebSocket only; no public inbound Desktop port is required.
- Local LAN remains the preferred transport. Remote relay is fallback only.

## Endpoint

Production default expected by Desktop and Mobile:

`wss://relay.propertydex.xyz/v1/device/<client_id>?role=desktop|mobile`

Health check:

`https://relay.propertydex.xyz/healthz`

## Deploy

From this directory, after Cloudflare authentication:

```bash
npm install
npx wrangler deploy
```

The custom domain in `wrangler.jsonc` is `relay.propertydex.xyz`. Change it before deployment if a different PrivacyGate domain is desired, and use the same base URL in Desktop via `PRIVACY_GATE_RELAY_URL` and Mobile via `--dart-define=PRIVACY_GATE_RELAY_URL=...`.

## Message size

The relay rejects frames larger than 2 MB. Large-file transfer should remain chunked at the PrivacyGate protocol layer rather than increasing the relay limit.
