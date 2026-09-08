# Google Workspace Marketplace Reviewer Instructions — PrivacyGate

This file is the **sanitized template** for the Google Workspace Marketplace review. It intentionally contains no live pairing code, API token, private reviewer URL, or other credential.

## What the reviewer needs

PrivacyGate is a local-first desktop privacy application with a Gmail™ add-on. The Gmail™ add-on can hand off only the email that the reviewer explicitly opens. The PrivacyGate desktop application must be installed and running during the end-to-end test because the desktop process polls the deployed Apps Script relay and consumes the selected email locally.

Provide the following values privately in the Marketplace SDK testing-credentials/reviewer-instructions fields:

- **PrivacyGate desktop reviewer build:** `[PRIVATE_REVIEWER_BUILD_URL]`
- **Reviewer credential/pairing material, if the reviewer build requires one:** `[PRIVATE_REVIEWER_CREDENTIAL]`
- **Any reviewer-only setup note:** `[PRIVATE_SETUP_NOTE]`

Do not put those values in this repository.

## End-to-end test procedure

1. Install the submitted PrivacyGate Gmail™ add-on in the Google review account.
2. Download and install the matching PrivacyGate desktop reviewer build from the private reviewer link supplied in the Marketplace SDK.
3. Launch PrivacyGate and keep it running for the whole test.
4. In PrivacyGate, open **Protect → Import source → Gmail** and select/add the Gmail™ account used for the review.
5. Use the pairing code shown by PrivacyGate for that account in the Gmail™ add-on. Pairing stores the device channel; it does not by itself prove that the desktop process is online.
6. In Gmail™, open a test email.
7. Open the PrivacyGate add-on and choose **Send to PrivacyGate**.
8. Return to PrivacyGate. The desktop app should receive the selected email while it is polling the relay.
9. Continue with the received email body through PrivacyGate's normal local **Scan → Review → Protect** workflow. Attachments are not imported by this Gmail flow yet; use PrivacyGate Upload for files.

### Timing note

The selected-email relay is intentionally short-lived. The payload is cached for at most **120 seconds** and is removed after the desktop consumes it. If the desktop app is closed, offline, or not polling during that period, reopen PrivacyGate and send the selected email again.

### Privacy behavior the reviewer can verify

- The add-on operates on the email the reviewer explicitly opened.
- The submitted manifest does not request mailbox-wide `gmail.readonly` or `gmail.modify` access.
- Pairing is scoped to the current Google user through Apps Script user properties.
- The selected payload is a temporary relay handoff, not a mailbox archive.
- PrivacyGate performs its privacy Scan/Review/Protect workflow locally on the desktop after receipt.

## Copy-ready testing-credentials text

Use this text in the Marketplace SDK after replacing the bracketed private values:

> PrivacyGate is a local-first desktop application. To test the Gmail™ add-on end to end, please install the matching PrivacyGate desktop reviewer build and keep it running while testing.
>
> Desktop reviewer build: `[PRIVATE_REVIEWER_BUILD_URL]`
>
> Reviewer credential/pairing material (if required): `[PRIVATE_REVIEWER_CREDENTIAL]`
>
> Test steps: Launch PrivacyGate → open Protect → Import source → Gmail → add/select the review Gmail™ account → use the pairing code displayed by PrivacyGate in the Gmail™ add-on → open a test email in Gmail™ → choose Send to PrivacyGate → return to PrivacyGate and confirm the selected email is received. The temporary relay expires after approximately 120 seconds, so PrivacyGate must remain open during the send.
>
> The add-on works only with the email explicitly opened by the reviewer and does not require mailbox-wide Gmail access.

## Listing trademark pass

Before resubmission, inspect **every occurrence** of Google product names in both the Marketplace short and detailed descriptions. Apply the attribution requested by the Google review team, including `Gmail™` and `Google Workspace™` where those names appear.

Suggested legal attribution for the bottom of the detailed description:

`Gmail™ and Google Workspace™ are trademarks of Google LLC.`

Do not claim that PrivacyGate is made, endorsed, or sponsored by Google.

## Branding blocker

The current Apps Script manifest still points `logoUrl` at a Google Gmail product image. Replace that before resubmission with the approved PrivacyGate-owned icon used by the Marketplace listing. Do not invent an asset URL; use the stable production asset actually approved for the PrivacyGate listing.
