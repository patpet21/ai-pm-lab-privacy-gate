# Automation Runtime Foundation

This checkpoint starts the conversion of Automation Studio from product preview to a real local-first runtime without duplicating PrivacyGate's existing Protect engine.

## Product rule

Automation orchestrates existing services. It must not implement a second detector, protector, residual scanner, policy engine, restore mapping store, or Library.

The first production pipeline is intentionally narrow:

`Gmail -> PrivacyGate Protect -> Residual Check -> Policy -> Local Library`

AI handoff and write actions such as ClickUp task creation are later destinations. They must not be smuggled into the first runtime milestone.

## Phase 1 foundation added

### Gmail -> ProtectPackage bridge

`application/gmail_protect_sources.py` converts an already-local Gmail body and materialized attachments into the generic `ProtectPackage` contract.

Important invariants:

- Gmail API/network access remains in the existing connector layer.
- Email body stays an in-memory text source.
- Attachments stay local file sources.
- Source keys remain stable: `gmail_body`, `gmail_attachment_1`, ...
- Payload text is never copied into package metadata.
- The bridge contains no Qt/UI logic and no protection logic.

This gives the current manual Gmail flow and the future Automation runner one shared package boundary.

### Automation domain model

`domain/automation.py` introduces persistable workflow definitions and metadata-only run records.

The initial supported trigger/destination contract is deliberately small:

- trigger: Gmail or manual
- destination: local Library
- status: draft / active / paused / archived
- run outcome: running / success / needs review / blocked / failed

Persisted trigger configuration explicitly rejects payload-like fields such as email body, original text, protected text, and document content.

### Local Automation state store

`infrastructure/automation/automation_store.py` stores only:

- workflow configuration
- enable/pause state
- timestamps
- hashed trigger event key
- source count
- detected/protected/residual counts
- policy status
- terminal result/error code

It does **not** store email/document payloads. Raw trigger event identifiers are SHA-256 hashed before persistence.

The store already exposes the four real metrics needed by Automation Studio:

- Active automations
- Runs today
- Waiting approval
- Blocked by policy

The UI is not wired to these values yet; that is a later checkpoint after the execution path is real.

## Next checkpoint

Do not add a parallel Gmail protection implementation.

Next, migrate the current manual Gmail component runtime to build the new `ProtectPackage` and feed it into the existing `ProtectSessionService`, while keeping the current Gmail review/preview/export UI behavior unchanged through compatibility mirrors.

Acceptance criteria before replacing the old Gmail analysis/protection path:

1. Email body + every selected attachment appear as independent `ProtectSource` items.
2. Findings remain source-namespaced.
3. Reversible tokens remain unique across Gmail components.
4. Current Gmail component switching and original/protected previews do not regress.
5. Residual Check still evaluates every protected source.
6. Current Library save and Restore compatibility remain intact.
7. Only after the manual path is green should Automation call the same package/service path headlessly.

## Runtime milestones after the Gmail migration

1. Extract UI-independent protected-session completion/save service.
2. Add Gmail polling trigger while PrivacyGate is running.
3. Add `AutomationRunner` that selects all detected findings by default for the first Gmail-to-Library workflow.
4. Reuse `PolicyEngine` and route unsafe outcomes to `needs_review` or `blocked`.
5. Save safe results through the same Library completion service used by manual Protect.
6. Wire Automation Studio cards, metrics, Run now, Pause/Resume and Runs history to the local Automation store.
7. Add background/tray execution only after foreground execution is stable.

## Privacy boundary

The intended runtime remains:

`remote trigger -> managed local working copy -> ProtectSessionService -> residual/policy decision -> local Library`

No external destination receives original content through this foundation.
