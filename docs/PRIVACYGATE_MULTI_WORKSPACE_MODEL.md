# PrivacyGate multi-workspace operating model

## Product model

One PrivacyGate account can participate in several privacy contexts:

- **Personal** — Basic or Pro, owned by the individual.
- **Business workspace(s)** — company-managed policy, members, seats and devices.
- **Enterprise workspace(s)** — Business capabilities plus enterprise identity/audit features.

Business and Enterprise are organization plans. They do not replace the user's
Personal workspace and they do not require separate PrivacyGate logins.

## One Protect engine, two UI surfaces

PrivacyGate does not create a second protection implementation for organizations.
The same `ProtectionPage` / privacy service behavior is reused in two independent UI
surfaces:

- standalone **Protect** for the normal personal/product navigation;
- embedded **Workspace Protect** inside Organization → Apps & AI.

The Organization instance has its own document state and preview, so working in a
company workspace does not redirect the user to the standalone Protect page. Both
surfaces use the same detection, protection, export, Library and policy-enforcement
code.

The active workspace selects the policy context:

1. Select Personal or a company workspace.
2. Upload/paste locally or import from an approved connected account.
3. The document opens in the Workspace Protect preview inside Organization.
4. Protect applies required/default/user-choice company directives locally.
5. A second local scan is performed before AI handoff.
6. Only AI/apps approved by the active company policy may be used.

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

## Organization Apps & AI flow

Organization → Apps & AI is a workspace suite, not a redirect page.

The left side lists connected accounts, including provider logos and the workspaces
where each account is approved. Workspace permissions remain editable from that
list; a separate Workspace bindings card is not part of the main working surface.

The document workflow is:

`active workspace → source → account → explicit workspace permission → connected-content picker → embedded Workspace Protect preview`

Google Drive and Gmail currently support direct materialization into the embedded
Workspace Protect instance. Other connected applications keep their existing
browse/search routes and can be promoted to direct import as their connector
materializers are implemented.

Local upload and paste-text actions are also available directly inside the embedded
Workspace Protect surface.

## Admin privacy boundary

Organization admins can manage:

- organization identity and plan;
- members, roles and seats;
- managed devices and policy sync;
- protection policy;
- approved AI and apps;
- whether a local connected account is approved for the workspace.

Organization admins do not receive:

- document contents;
- document titles;
- Library contents;
- restore mappings;
- connector OAuth tokens;
- connector source item lists.

The embedded Workspace Protect document state remains local to the employee device.
Any future Enterprise audit feature should use metadata-minimization by default and
must remain separate from document access.
