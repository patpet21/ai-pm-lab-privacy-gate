# Privacy Gate control plane

Metadata-only Cloudflare Worker for device enrollment, Named Tunnel provisioning and OAuth protected-resource discovery. Supabase Auth is the single OAuth 2.1 authorization server; the Worker does not issue AI access tokens.

It must never receive or store documents, protected text, original PII, restore mappings or local encryption keys.

Required Worker secrets:

- `CF_API_TOKEN`: scoped to Cloudflare Tunnel Edit and DNS Edit for `propertydex.xyz`.
- `PROVISIONING_FINGERPRINT_SALT`: random server-side salt used only to compare device enrollment fingerprints.

Before deployment, create the D1 database, replace the zone/database IDs in `wrangler.jsonc`, apply migrations and configure all required secrets.
