# Protect Session refactor safety plan

## Frozen working baseline

The last known-good Protect build is preserved at commit:

`09a2736e050d5f01171a77ac9e7ffbe80b7acdc2`

and at the branch:

`backup/protect-working-2026-08-27`

That branch is a recovery snapshot and must not be used for development.

## Development branch

All Protect architecture cleanup is performed on:

`refactor/protect-session-clean`

No change from this refactor is allowed onto `main` until the desktop flows have
been manually validated.

## Functional invariants

The refactor must preserve the behavior already working in the baseline:

- local Upload, Paste text, Gmail and Drive remain usable;
- PDF, DOCX, XLSX, PPTX and TXT continue through the local document pipeline;
- Gmail body plus multiple attachments remain independent sources;
- source switching never leaks stale Gmail/Drive/local state;
- Scan reviews every selected source locally;
- Protect produces an independent protected result per source;
- protected native file previews and protected TXT views remain available;
- Clear removes the active session and all cached preview/source state;
- Library, Restore, workspace policy, preflight/governance and connector routing remain intact;
- original provider/app icons and product branding are retained.

## Migration architecture

The target is:

```text
Connector / Upload / Paste / OCR / Batch
                |
                v
         ProtectPackage
        (N ProtectSource)
                |
                v
     ProtectSessionService
       analyze -> review
                |
                v
            protect
                |
                v
      per-source results
      + per-source export
```

`ProtectSessionService` is deliberately UI-agnostic. Connector-specific metadata
belongs to `ProtectSource.metadata`, not to the detection/protection engine.

## Runtime cleanup

Until the old UI patch modules are removed completely, all Protect startup order
is owned by `ui/protect_runtime.py`. The rest of the application must not add new
Protect patch calls directly to `ui/__init__.py`.

The final `ProtectSurfaceGuard` runs after the complete Protect/Gmail/session
composition and hides detached compatibility widgets based on the final layout
tree. This replaces the pattern of adding more visual cleanup patches whenever a
clipped legacy label or icon appears.

## Next migration steps

1. Move local Document + Paste analysis to `ProtectSessionService`.
2. Move Gmail component analysis/protection to the same service.
3. Convert Drive multi-file imports directly to `ProtectPackage`.
4. Replace hard-coded Document/Text review filters with generic source filters.
5. Move per-source export and Library save into the session layer.
6. Remove obsolete Protect/Gmail runtime patch modules once each migrated path is covered by tests.
7. Only after the workflow is consolidated, simplify/redesign the visual hierarchy without changing the underlying feature set.
