# PrivacyGate Gmail Add-on

This integration replaces the **Protect** Gmail entry point with a current-message
Google Workspace Add-on flow. It deliberately does **not** grant PrivacyGate
mailbox-wide `gmail.readonly` access.

## User flow

1. In PrivacyGate, open **Protect → Import source → Gmail**.
2. First use only: copy the device pairing code into the PrivacyGate Gmail Add-on.
3. Open the email to import in Gmail.
4. Click the PrivacyGate add-on in Gmail and choose **Send to PrivacyGate**.
5. PrivacyGate receives the selected message automatically while the desktop app is
   running and polling the production relay. No per-message transfer code and no
   manual **Receive email text** button are required.
6. Choose **Email body** or one received attachment in PrivacyGate and continue with
   the normal local Scan / Review / Protect flow.

Google Workspace Add-ons run inside Gmail. Without mailbox-wide Gmail API access,
the desktop app cannot list the user's inbox itself; the add-on can only work with
the message the user has explicitly opened.

## Pairing and desktop availability

Pairing registers the high-entropy device channel for the current Google account.
It does **not** prove that the PrivacyGate desktop app is online. For an end-to-end
transfer, PrivacyGate must be running and polling the deployed Apps Script relay
when the user chooses **Send to PrivacyGate**.

The selected email is available in the Apps Script cache for at most 120 seconds.
If the desktop app is closed or cannot reach the relay during that window, the
transfer expires and the user must send the selected email again. This relay is a
short-lived handoff, not a durable queue or mailbox archive.

## Privacy boundary

The add-on requests only the Gmail add-on execution/current-message scopes plus
Apps Script storage for the one-time device pairing. The selected payload is held
in Apps Script `CacheService` for at most 120 seconds and is removed after the
desktop app consumes it.

The transfer is protected by a high-entropy device channel and an HMAC-SHA256
signature. The channel is stored locally by PrivacyGate and in the user's add-on
properties after the one-time pairing.

## Marketplace reviewer requirement

Google Marketplace reviewers need both sides of this local-first integration:

1. the Gmail add-on installed in the review Google account; and
2. a PrivacyGate desktop reviewer build that matches the exact add-on/relay source
   being submitted.

The reviewer must launch PrivacyGate, keep it running, pair the Gmail add-on using
the code shown by that reviewer build, open a test email, and send it while
PrivacyGate is polling. A pairing code by itself is not enough if no compatible
desktop process is running.

Do not commit reviewer pairing codes, private download links, test credentials, or
API tokens to this repository. Put those only in the Google Workspace Marketplace
SDK testing-credentials/reviewer-instructions fields.

See `MARKETPLACE_REVIEW.md` for the sanitized, copy-ready review procedure.

## Test deployment

Create or open the Apps Script project used for the test add-on.

1. Replace `Code.gs` with the file in this directory.
2. Replace the project manifest with `appsscript.json`.
3. Create/install a **test deployment** for the Google Workspace Add-on.
4. Deploy the same script as a **Web app** so the desktop client can poll `doPost`.
5. Set the web-app `/exec` URL once in the development build through
   **Configure test deployment**, or set the environment variable:

   `PRIVACYGATE_GMAIL_ADDON_ENDPOINT=https://script.google.com/macros/s/.../exec`

The raw deployment field is intentionally not part of the normal Protect UX.
For a packaged/public build, ship the production relay URL through application
configuration so end users never see this developer setup.

## Current limits

The relay rejects very large messages/attachments. Large files should continue to
use PrivacyGate Upload or Google Drive. The relay is intentionally short-lived and
is not a mailbox archive.
