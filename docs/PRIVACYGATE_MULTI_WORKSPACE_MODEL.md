# PrivacyGate multi-workspace operating model

## Product model

One PrivacyGate account can participate in several privacy contexts:

- **Personal** — Basic or Pro, owned by the individual.
- **Business workspace(s)** — company-managed policy, members, seats and devices.
- **Enterprise workspace(s)** — Business capabilities plus enterprise identity/audit features.

Business and Enterprise are organization plans. They do not replace the user's
Personal workspace and they do not require separate PrivacyGate logins.

## One Protect engine, one document workspace

PrivacyGate keeps a single user-facing Protect surface.

Users who belong to at least one Business/Enterprise workspace receive an additional
workspace context bar inside the existing Protect page. The rest of Protect — upload,
paste, scan, review, two-document preview, protection, Library save/export and AI
preflight — remains the same.

The context bar provides:

- Personal or company workspace selection;
- connected source selection;
- connected account selection;
- company policy status;
- direct connected-content browsing/import;
- a link back to Organization for team/account administration.

The active workspace selects the policy context:

1. Select Personal or a company workspace in Protect.
2. Upload/paste locally or import from an approved connected account.
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
  approves workspace access.

The permission stores only local availability (`provider + account + workspace`). It
does not copy OAuth tokens or source contents into the Organization control plane.

## Organization Apps & AI

Organization is the team control plane, not a second document-protection page.

Organization → Apps & AI provides:

- active company workspace context;
- connected accounts with real provider logos;
- per-account workspace permission management;
- workspace policy/version status;
- member/device/account readiness counts;
- approved AI and connected-app visibility;
- quick navigation to Protect and to the main Apps connection page;
- privacy-boundary explanation.

Document previews and protection are deliberately absent from Organization. Team
members use the existing Protect page and select the required company workspace there.
This avoids two parallel document experiences while keeping all company controls in
Organization.

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

Any future Enterprise audit feature should use metadata-minimization by default and
must remain separate from document access.
