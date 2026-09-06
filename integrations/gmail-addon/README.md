# PrivacyGate Gmail Add-on

This integration replaces the **Protect** Gmail entry point with a current-message
Google Workspace Add-on flow. It deliberately does **not** grant PrivacyGate
mailbox-wide `gmail.readonly` access.

## User flow

1. In PrivacyGate, open **Protect → Import source → Gmail**.
2. First use only: copy the device pairing code into the PrivacyGate Gmail Add-on.
3. Open the email to import in Gmail.
4. Click the PrivacyGate add-on in Gmail and choose **Send to PrivacyGate**.
5. PrivacyGate receives the selected message automatically. No per-message transfer
   code and no manual **Receive email text** button are required.
6. Choose **Email body** or one received attachment in PrivacyGate and continue with
   the normal local Scan / Review / Protect flow.

Google Workspace Add-ons run inside Gmail. Without mailbox-wide Gmail API access,
the desktop app cannot list the user's inbox itself; the add-on can only work with
the message the user has explicitly opened.

## Privacy boundary

The add-on requests only the Gmail add-on execution/current-message scopes plus
Apps Script storage for the one-time device pairing. The selected payload is held
in Apps Script `CacheService` for at most 120 seconds and is removed after the
desktop app consumes it.

The transfer is protected by a high-entropy device channel and an HMAC-SHA256
signature. The channel is stored locally by PrivacyGate and in the user's add-on
properties after the one-time pairing.

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
