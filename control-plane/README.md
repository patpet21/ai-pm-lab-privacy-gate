# Privacy Gate control plane

Metadata-only Cloudflare Worker for device enrollment, Named Tunnel provisioning and MCP OAuth pairing.

It must never receive or store documents, protected text, original PII, restore mappings or local encryption keys.

Required Worker secrets:

- `CF_API_TOKEN`: scoped to Cloudflare Tunnel Edit and DNS Edit for `propertydex.xyz`.
- `JWT_PRIVATE_JWK`: ES256 private signing JWK.
- `JWT_PUBLIC_JWK`: matching public JWK.
- `PILOT_APPROVAL_CODE`: temporary human approval gate for the first pilot only.

Before deployment, create the D1 database, replace the zone/database IDs in `wrangler.jsonc`, apply migrations and configure all required secrets.
