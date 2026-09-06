# PrivacyGate Gmail Add-on — current.message.readonly option

This directory is an **alternative** Gmail integration. It does not replace the existing
`integrations/gmail-addon/` implementation.

## Why this variant exists

The existing add-on keeps the narrow non-sensitive scope:

- `gmail.addons.current.message.action`

and only receives the open message after the user presses **Send to PrivacyGate**.

This alternative uses:

- `gmail.addons.current.message.readonly`

so the add-on can show the **subject, sender, date, body preview and attachment count of the currently open Gmail message directly in the PrivacyGate sidebar** before the user sends it to the desktop app.

The user then presses **Open in PrivacyGate**. The same short-lived relay/pairing protocol is used, so the existing desktop Gmail import flow can consume the message without mailbox-wide `gmail.readonly` access.

## Important scope difference

This variant requests a **Sensitive** Gmail add-on scope instead of the current non-sensitive action scope. It is intentionally kept separate so we can test and compare both UX/verification paths without changing or losing the working action-scope implementation.

It still does **not** request mailbox-wide `gmail.readonly`.

## User flow

1. Open PrivacyGate → Protect → Gmail and pair the device once.
2. Open an email in Gmail.
3. Open the PrivacyGate sidebar.
4. The sidebar immediately shows the currently open message preview.
5. Press **Open in PrivacyGate**.
6. PrivacyGate receives the selected message and continues with the same local Scan / Review / Protect flow already implemented.

## Test it without touching the working option

Use a **separate Apps Script test project/deployment** for this directory.

1. Copy `Code.gs` from this directory into the alternate Apps Script project.
2. Use this directory's `appsscript.json` as the project manifest.
3. Install a Gmail add-on test deployment.
4. Deploy the same script as a Web app.
5. Point the development PrivacyGate Gmail endpoint at that alternate `/exec` URL when testing this option.

The existing `integrations/gmail-addon/` deployment can remain untouched, so both versions stay available for comparison.
