# Protect flow inventory before source migration

This document is the safety map for the ProtectSession refactor. It records the
working behavior that must survive while old compatibility layers are folded into
the generic session core.

## Frozen references

- Last known-good pre-refactor Protect build: `backup/protect-working-2026-08-27`
- First ProtectSession CI checkpoint: `checkpoint/protect-session-phase1-ci-green`
- Scan & Protect + Privacy Check checkpoint: `checkpoint/protect-workflow-v2-ci-green`
- Approved upper Protect UI checkpoint: `checkpoint/protect-approved-top-ui-ci-green`

The development branch is `refactor/protect-session-clean`. Checkpoint branches
are recovery references and are not development targets.

## Current flow ownership

| Flow | Current entry/state | Compatibility owners still involved | Behavior that must not regress | Migration status |
| --- | --- | --- | --- | --- |
| Local Upload | `pdf_path` + `ProtectionPage._start_analysis()` | `protect_session_upgrade.py`, `protect_session_runtime_fix.py`, redesign/runtime wrappers | PDF/DOCX/XLSX/PPTX/TXT local analysis, original preview, protected native preview, TXT companion | **Migrating first** |
| Paste text | `text_input` + `ProtectionPage._start_analysis()` | redesign + `protect_session_upgrade.py` | local detection, protected text, review choices, copy/save | **Migrating first** |
| Upload + Paste | `pdf_path` + `text_input` | `protect_session_upgrade.py` custom two-source analyzer/protector | independent findings, independent reversible namespaces, combined review/export | **Migrating first** |
| Google Drive | connector browser materializes a file and updates Protect source state | Drive route/source metadata + local document compatibility path | browse folders/back navigation, original preview, scan/protect, provenance | Later migration |
| Gmail | selected message body + N materialized attachments | `gmail_package_browser.py`, `gmail_component_session.py`, `gmail_component_capture_fix.py`, preview/runtime compatibility modules | body + every attachment independent, pre-scan original preview, per-source analyzed/protected views | Last connector migration |
| Scan & Protect | visible `Scan & Protect` action; hidden compatibility Protect action still drives result refresh | redesign + `protect_workflow_v2.py` + source-specific wrappers | one visible primary action, automatic first protected result, review changes update protection | Preserve during migration |
| Review | shared findings table; local filter currently knows `document` / `text`; Gmail has component switching | `protect_session_upgrade.py`, Gmail component runtime | source identity preserved in finding IDs and locations | Generic N-source review later |
| Preview | original/protected document renderers + text comparison + Gmail component views | protection page, document pipeline V2, Gmail preview polish | Original / Analyzed text / Protected text / Protected comparison | Generic preview controller later |
| Clear/source switch | multiple reset guards clear stale connector/session/render state | `protect_source_state_reset.py` + redesign/session/Gmail clear wrappers | Gmail must never leak into a later Drive/local upload; all preview/result state clears | Preserve before removal |
| Save/Download | original save path for one source; compatibility session export for Document + Paste; Gmail package save logic | `protect_session_upgrade.py`, `protect_session_runtime_fix.py`, Gmail session runtime | native protected file + TXT companion; local Library mappings remain restorable | Generic per-source export later |
| Privacy Check | `protect_workflow_v2.py` reconstructs current protected source set from UI compatibility state | current session/Gmail result dictionaries | LOW/MEDIUM/HIGH, per-source detected/protected/residual counts, local second scan | Read directly from ProtectSession later |

## Migration rule

No compatibility module is deleted merely because its responsibility has a new
home. For every responsibility the order is:

1. Capture the current behavior in tests/inventory.
2. Implement the behavior in `ProtectPackage` / `ProtectSessionService` or the
   new controller/adapter.
3. Keep compatibility mirrors where the current UI still expects them.
4. Pass Windows CI and desktop smoke tests.
5. Disable the old path.
6. Re-run regression tests.
7. Only then delete the obsolete module.

## Phase 1 acceptance criteria — Local Upload + Paste

The first migration is complete only when all of these remain true:

- Upload only creates a one-source `ProtectPackage` and is analyzed/protected by
  `ProtectSessionService`.
- Paste only creates a one-source `ProtectPackage` and is analyzed/protected by
  `ProtectSessionService`.
- Upload + Paste creates one package with two independent sources in stable order
  (`document`, `text`).
- Finding IDs remain source-namespaced.
- Reversible replacement tokens remain unique between sources.
- The approved Protect UI does not move or change appearance.
- Drive and Gmail are explicitly excluded from this adapter and continue through
  their current proven paths.
- Existing single-source save/download behavior continues to work.
- Existing two-source Document + Paste compatibility export continues to work.
- Clear/input replacement invalidates the new local session state as well as the
  compatibility state.
