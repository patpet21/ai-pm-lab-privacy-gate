# Gmail action-only release

Apps manages independent Gmail account cards. Protect selects an account, waits for an explicit **Send to PrivacyGate** action, previews text, and imports into the existing local Scan/Protect pipeline. Mailbox-wide OAuth is excluded. Labels are supplied by the user; check the Gmail avatar when pairing each account. One Gmail account pairs to one device at a time.

The Gmail scopes are limited to `gmail.addons.execute` and `gmail.addons.current.message.action`; keep the manifest aligned with the production Apps Script deployment. Do not add `gmail.readonly`, `gmail.modify`, full-mailbox, or other non-current-message scopes. Public distribution still requires the applicable Google branding and Marketplace review. Never instruct customers or reviewers to bypass an unverified-app screen.

Publish the updated `Code.gs` and manifest using the standard Google Cloud project already associated with the production app. The Apps Script project, OAuth consent screen, Marketplace SDK configuration, and deployed add-on must all refer to the same intended production project/deployment. Verify installation with an unrelated consumer account and a Workspace account (administrator policy may apply). Only after publication and verified consent, set `resources/gmail-addon-release.json` to published, `consent_verified` true, the official Marketplace listing URL, and the production Apps Script `/exec` endpoint, then rebuild the app. No production URL is invented in this change.

For an existing development installation, set `PRIVACYGATE_GMAIL_ADDON_DEVELOPMENT=1` to expose endpoint configuration in Apps. This is not a customer installation path. Existing action pairing is migrated into a separate account card and its key moves into the platform secret store. Enhanced connections are not migrated. Removing an account deletes its local pairing key; uninstall/revoke the add-on separately in Google if desired.

## Marketplace review blockers and checklist

Before resubmitting the Google Workspace Marketplace listing:

- [ ] Use the **exact latest reviewed Gmail source** for the Apps Script deployment. Record the Git commit SHA used for the submission.
- [ ] Keep the PrivacyGate desktop reviewer build and deployed Apps Script relay compatible with that exact source.
- [ ] In the Marketplace short description and detailed description, apply Google-requested trademark attribution consistently, including `Gmail™` and `Google Workspace™` wherever those product names appear.
- [ ] Add the legal attribution required by the current listing, for example: `Gmail™ and Google Workspace™ are trademarks of Google LLC.`
- [ ] Provide Google privately with everything needed for end-to-end testing: the compatible desktop reviewer-build download, exact launch/pair/send instructions, and any dedicated reviewer credential or pairing material required by that build.
- [ ] Do **not** commit reviewer credentials, pairing codes, API tokens, or private download URLs to GitHub.
- [ ] Test from a clean review-style Google account with PrivacyGate desktop running. Pair the account, open a test email, choose **Send to PrivacyGate**, and verify that PrivacyGate consumes it before the 120-second cache expires.
- [ ] Treat pairing as device-channel registration, not proof that the desktop process is online. Reviewer instructions must explicitly say to keep PrivacyGate open while testing.
- [ ] Use a PrivacyGate-owned add-on icon that matches the Marketplace listing icon. Do not ship a Gmail/Google product logo as the PrivacyGate add-on identity.
- [ ] Confirm the Marketplace SDK extension points to the intended production deployment and that the Web App `/exec` relay is the one bundled/configured in the matching reviewer build.
- [ ] Re-run current-message-only scope tests and the Gmail integration test before resubmission.

### Important current manifest blocker

`appsscript.json` currently uses a Google Gmail product image as `logoUrl`. Do not silently replace it with an invented URL. Before Marketplace resubmission, upload/use the approved PrivacyGate icon through the production Marketplace/Apps Script asset path and update `logoUrl` to that stable PrivacyGate-owned asset. The icon should match the Marketplace listing.

See `MARKETPLACE_REVIEW.md` for copy-ready reviewer instructions and listing language that intentionally contains no secrets.
