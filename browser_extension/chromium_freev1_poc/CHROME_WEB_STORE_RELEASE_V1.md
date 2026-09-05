# PrivacyGate — Chrome Web Store Release v1.0.0

Release branch: `release/browser-extension-v1-prepublish-20260905`

## Product identity

**Name:** PrivacyGate

**Version:** 1.0.0

**Short description:** Protect sensitive text and PDF content locally before sending it to supported AI assistants, with local restore.

## Single purpose

PrivacyGate protects user-selected sensitive text and PDF content locally before it is submitted to supported AI assistants, and locally restores PrivacyGate placeholders when a valid local restore session is available.

## Supported AI websites

- ChatGPT — `https://chatgpt.com/*`
- Google Gemini — `https://gemini.google.com/*`
- Claude — `https://claude.ai/*`

## Supported v1 content

- Text protection
- PDF protection and protected attachment
- Local reversible restore for PrivacyGate placeholders
- PDF submission with or without additional prompt text

**Not claimed in v1:** Microsoft Excel or general spreadsheet protection.

## Store description

PrivacyGate helps reduce accidental exposure of sensitive information when using supported AI assistants.

Before a text prompt or PDF is submitted, PrivacyGate routes the selected content through a local PrivacyGate bridge running on the user's computer. Selected sensitive values can be replaced with reversible PrivacyGate placeholders before the request leaves the browser. Protected PDFs are attached in place of the original PDF when protection succeeds.

If the AI response contains reversible PrivacyGate placeholders, PrivacyGate can restore the values locally for the user. Restored sensitive text is displayed in an extension-origin local view rather than being written back into the AI provider page.

PrivacyGate v1 supports ChatGPT, Google Gemini, and Claude. Core protection and restoration require the PrivacyGate local bridge to be running and paired with the extension.

PrivacyGate does not advertise Excel/spreadsheet protection in this release.

## Permission justifications

### `storage`

Required to save local protection settings, the browser-to-local-bridge pairing credential, PDF preferences, and opaque local session identifiers. The extension session registry does not store prompt text, PDF contents, detected PII values, reversible mappings, or restored values in `chrome.storage.local`.

### `http://127.0.0.1:8765/*`

Required only for authenticated communication with the PrivacyGate bridge running locally on the user's own computer. This bridge performs local analysis, protection, PDF processing, and restore operations.

### Site access: ChatGPT, Gemini, Claude

Required to intercept user-initiated text/PDF submissions for protection and to recognize PrivacyGate placeholders in AI responses for local restore. Site access is limited to the three supported AI domains.

## Privacy disclosure summary

- Sensitive source values are processed locally through the PrivacyGate loopback bridge.
- The protected text/PDF is sent to the AI provider selected by the user.
- The extension does not sell user data.
- The extension does not use sensitive source content for advertising.
- The extension does not request browsing history, bookmarks, geolocation, microphone, camera, or contacts permissions.
- Restored sensitive response text is rendered in an extension-origin iframe, not intentionally written into the provider DOM.

Privacy policy for this release branch:
`https://github.com/patpet21/ai-pm-lab-privacy-gate/blob/release/browser-extension-v1-prepublish-20260905/PRIVACY.md`

After release changes are merged, use the stable `main` privacy-policy URL for the Store listing.

## Final smoke-test matrix before Submit for review

Run this matrix against the exact folder/ZIP uploaded to the Developer Dashboard.

| Surface | Text protect/send | PDF protect/attach | PDF without prompt | Response restore |
|---|---|---|---|---|
| ChatGPT | Required | Required | Required | Required |
| Gemini | Required | Required | Required | Required |
| Claude | Required | Required | Required | **Required — especially document-based response** |

Additional checks:

1. Extension installs with no manifest errors.
2. Popup can pair with the local bridge.
3. Protection ON/OFF state survives reload.
4. Original sensitive text is not visibly substituted into the AI page during restore.
5. Restored view appears only when a valid local session exists.
6. Switching conversations does not restore values from another conversation.
7. PDF upload failure blocks unsafe fallback rather than silently attaching the original.
8. No Excel/spreadsheet claim appears in the Store listing or screenshots.
9. No `POC` wording appears in the extension name or Store-facing description.
10. Upload the exact release ZIP to the Chrome Web Store draft and allow its pre-submission installation checks to complete before submitting for review.

## Release gate

**Code gate:** manifest, provider session registry, secure provider-aware restore, PDF guidance, and privacy disclosure are prepared on this branch.

**Human smoke-test gate:** all required cells in the matrix above must pass on the exact packaged build before pressing **Submit for review**.
