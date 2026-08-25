# PrivacyGate plans and company-policy architecture

## Product tiers

PrivacyGate has four canonical plans:

- **Basic** — free individual local-first product.
- **Pro** — individual premium tier.
- **Business** — company workspace, seats, members, devices and centrally managed privacy policy.
- **Enterprise** — Business controls plus future enterprise identity/audit capabilities.

`Team` is a Business/Enterprise capability, not a fifth plan.

During the current rollout, the plan engine does **not** remove existing PrivacyGate
features from Basic. It establishes one entitlement model so future pricing does not
require scattered feature checks or a second product architecture.

## Privacy boundary

The Supabase control plane may receive:

- user/account ID
- organization ID and role
- plan/entitlement and seat limits
- device identity metadata
- company policy JSON and policy version
- policy sync status

The Supabase control plane must not receive:

- original document content
- protected document content
- local Library content
- restore mappings
- connector OAuth tokens
- connector source content

Each employee has an independent local Library and OS-protected secrets.

## Enforcement

`PolicyEngine` is the single decision layer for company policy. UI controls are
not the security boundary.

A Business/Enterprise policy can define:

- approved AI destinations
- approved app/connectors
- per-entity protection directives:
  - `required_protect`
  - `default_protect`
  - `user_choice`
  - `allow`

Required findings are unioned into the selected finding set immediately before
protection. The UI also locks the relevant finding/category controls for clarity.

AI handoff is evaluated again after the local second scan. A company-required
entity that remains after protection blocks the handoff. A blocked AI destination
never opens.

Apps show disabled-by-company state and their connect/browse entry points are
guarded by the same PolicyEngine.

## Offline behavior

The last valid Team state and company policy are stored in Windows DPAPI or the
macOS Keychain through the existing PrivacyGate secret-store abstraction.

A separate managed-device marker prevents a broken/corrupted company policy cache
from silently downgrading a managed device to Basic. In that situation managed AI
and app handoffs fail closed until policy sync is restored.

## Enrollment

Company invite codes are one-time enrollment credentials. Supabase stores only a
SHA-256 hash of each code. Codes expire and consume an available organization seat.

The code does not contain documents, mappings, OAuth tokens or the company policy.

## Database migration

Apply:

`supabase/migrations/20260825_privacy_gate_business_foundation.sql`

to the PrivacyGate Supabase project before exercising online Team creation,
invitations or policy publishing.

The migration uses RLS plus security-definer RPCs for state-changing team actions.
Self-service workspace creation creates a **Business trial** only; Enterprise is
intentionally not self-provisioned from the desktop client.
