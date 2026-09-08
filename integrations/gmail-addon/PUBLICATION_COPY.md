# PrivacyGate — Publication Copy

Copy-ready text for the next Google Workspace Marketplace resubmission and the matching Windows desktop release. Keep reviewer credentials, pairing codes, and private download links out of this repository.

## Google Workspace Marketplace

### App name

PrivacyGate

### Short description

Send opened Gmail™ emails to PrivacyGate for local privacy protection.

### Detailed description

PrivacyGate helps users protect sensitive information before using email content with AI tools.

The PrivacyGate Gmail™ add-on works only with the email the user explicitly opens. When the user chooses **Send to PrivacyGate**, the selected message is transferred through a short-lived relay to the PrivacyGate desktop application. PrivacyGate Desktop must be installed and running to receive the message.

After receipt, the email content enters PrivacyGate's local **Scan → Review → Protect** workflow. PrivacyGate does not request mailbox-wide Gmail™ access through this add-on. The temporary relay is used only to hand off the explicitly selected message to the paired desktop device and is not a mailbox archive.

Attachments are not imported through the Gmail™ add-on in the current version. Files can be added directly in PrivacyGate using **Upload**.

PrivacyGate is an independent product and is not made, endorsed, or sponsored by Google.

Gmail™ and Google Workspace™ are trademarks of Google LLC.

### Reviewer testing instructions

PrivacyGate is a local-first desktop application. To test the Gmail™ add-on end to end, use a Windows 10/11 computer, install the matching PrivacyGate Desktop reviewer build, and keep PrivacyGate running during the test.

**Desktop reviewer build:** `[PRIVATE_REVIEWER_BUILD_URL]`

**Reviewer credential/pairing material, if required:** `[PRIVATE_REVIEWER_CREDENTIAL]`

1. Install/open the submitted PrivacyGate Gmail™ add-on in the Google review account.
2. Install and launch the matching PrivacyGate Desktop reviewer build on Windows 10/11. Keep PrivacyGate running.
3. In PrivacyGate, open **Protect → Import source → Gmail** and add/select the Gmail™ account used for review.
4. PrivacyGate displays a pairing code. In Gmail™, open an email, open the PrivacyGate add-on from the right-side add-on bar, paste the pairing code, and choose **Connect**.
5. Wait until PrivacyGate shows the account as connected.
6. In Gmail™, open the test email to import, open the PrivacyGate add-on, and choose **Send to PrivacyGate**.
7. Return to PrivacyGate. The selected email should appear automatically while the desktop app is polling the relay.
8. Choose **Use in Protect**, then continue with the normal local **Scan → Review → Protect** workflow.

The selected-email relay is intentionally short-lived and expires after approximately 120 seconds. If PrivacyGate Desktop is closed or not polling during that period, reopen PrivacyGate and choose **Send to PrivacyGate** again.

The add-on operates only on the email explicitly opened by the reviewer and does not request mailbox-wide Gmail™ read/modify scopes. Attachments are not imported through this Gmail™ add-on flow in the current version; file testing should use PrivacyGate **Upload**.

### Private values to add only in Marketplace SDK

- Final Windows reviewer download/install URL or Microsoft Store distribution link.
- Any reviewer-only credential required by the chosen distribution method.
- Any temporary reviewer note that must not be public.

Do not paste secrets into the public listing or this repository.

## Windows desktop publication

### Suggested release notes

Adds the PrivacyGate Gmail™ add-on integration for importing the currently opened email into PrivacyGate's local **Scan → Review → Protect** workflow. This release adds device pairing, automatic short-lived relay handoff, Gmail™ account selection, and clearer connection status. PrivacyGate Desktop must be running during an email transfer. Gmail™ attachments are not imported by this flow yet and remain available through PrivacyGate **Upload**.

### Pre-publication requirements

- Use the exact desktop source that matches the submitted Gmail™ add-on and Apps Script relay.
- Run the full automated test suite and smoke checks before packaging.
- Build the Windows distribution and installer from the repository build scripts.
- Verify the packaged app contains the current production Gmail™ relay endpoint.
- Complete a clean-account Gmail™ pairing and selected-email import test with the packaged build.
- Publish/distribute the Windows build through the approved trusted channel used for the reviewer.
- Only after the reviewer build is reachable, paste the private reviewer distribution details into the Google Workspace Marketplace SDK and resubmit.

## Remaining branding action

Before Marketplace resubmission, replace the current Gmail™ product-image `logoUrl` in `integrations/gmail-addon/appsscript.json` with the stable public URL of the approved PrivacyGate-owned icon used by the Marketplace listing.
