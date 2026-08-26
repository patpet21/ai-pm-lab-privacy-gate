# PrivacyGate multi-workspace operating model

## Product model

One PrivacyGate account can participate in several privacy contexts:

- **Personal** — Basic or Pro, owned by the individual.
- **Business workspace(s)** — company-managed policy, members, seats and devices.
- **Enterprise workspace(s)** — Business capabilities plus enterprise identity/audit features.

Business and Enterprise are organization plans. They do not replace the user's
Personal workspace and they do not require separate PrivacyGate logins.

## One Protect engine

PrivacyGate does not create a second Protect implementation for organizations.

The active workspace selects the policy context used by the existing Protect /
Privacy Preflight path:

1. Select Personal or a company workspace.
2. Open a local document or import from an approved connected account.
3. Protect applies required/default/user-choice company directives locally.
4. A second local scan is performed before AI handoff.
5. Only AI/apps approved by the active company policy may be used.

Personal keeps the normal individual behavior and has no company policy.

## Connector ownership and consent

Connected accounts belong to the user's local PrivacyGate installation. OAuth
credentials remain in the local connector vault.

A connected account is:

- always available in **Personal**;
- **not automatically available** in a Business/Enterprise workspace;
- reusable in one or many company workspaces only after the user explicitly
  approves a workspace binding.

The binding stores only local availability (`provider + account + workspace`).
It does not copy OAuth tokens or source contents into the Organization control
plane.

## Organization import flow

Organization → Apps & AI provides the controlled bridge into the existing Protect
experience:

`workspace → source → account → explicit workspace permission → connected-content picker → Protect`

Google Drive and Gmail currently support direct materialization into Protect.
Other connected applications keep their existing browse/search routes and can be
promoted to direct import as their connector materializers are implemented.

## Admin privacy boundary

Organization admins can manage:

- organization identity and plan;
- members, roles and seats;
- managed devices and policy sync;
- protection policy;
- approved AI and apps.

Organization does not expose:

- document contents;
- document titles;
- Library contents;
- restore mappings;
- connector OAuth tokens;
- connector source item lists.

Any future Enterprise audit feature should use metadata-minimization by default
and must remain separate from document access.
