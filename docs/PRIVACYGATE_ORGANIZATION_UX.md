# PrivacyGate Organization UX

PrivacyGate Business and Enterprise are not document-collaboration products.
They distribute and enforce one company privacy policy across separate local
PrivacyGate installations.

## Navigation model

- **Organization** is the operational Business/Enterprise workspace.
- **Settings → Plan & Account** shows the canonical product tiers:
  Basic, Pro, Business and Enterprise.
- Basic and Pro remain individual plans.
- Business and Enterprise receive organization policy, membership and managed
  device capabilities.

## Role-aware views

### Owner / Admin

The Organization workspace exposes four sections:

1. **Overview**
   - seats used / seat limit
   - member count
   - managed device count
   - active policy version
   - approved AI and app destinations
   - explicit local-data privacy boundary

2. **Members**
   - account
   - role
   - status
   - join timestamp
   - invite member
   - change non-owner roles
   - disable/reactivate
   - revoke

3. **Policy**
   - required/default/user-choice/allow sensitive-data rules
   - approved AI destinations
   - approved connectors
   - publish a new immutable policy version

4. **Devices**
   - account and device label
   - platform and PrivacyGate version
   - active/disabled/revoked state
   - policy version and last sync
   - disable/reactivate/revoke

### Manager

Managers receive operational read-only visibility into Overview, Members,
Policy and Devices. They cannot edit policy, change roles or revoke access.

### Member

Members receive a deliberately smaller experience. They can verify:

- organization
- their role and plan
- current company policy version
- required protection rules
- approved AI destinations
- approved apps
- their local managed-device identity

They do not receive organization-wide member/device management controls.

## Privacy boundary

The organization control plane may store:

- account ID
- organization and role
- entitlement and seats
- device identity/status
- policy content/version
- policy sync timestamp

It must not store or expose through Organization:

- original documents
- protected documents
- Library contents
- restore mappings
- document titles/activity logs
- Gmail/Drive source contents
- connector OAuth tokens

The sales/product principle remains:

> Your company controls the privacy policy. Your employees keep their documents local.

## Enforcement

Organization is a control surface, not the enforcement boundary.

`PolicyEngine` continues to enforce company rules in:

- Protect
- AI Privacy Preflight
- Apps / connector access

Required protection is re-applied at execution time even if a UI control is
manipulated or becomes inconsistent.
