# Privacy Policy — PrivacyGate

Last updated: 2026-09-05

PrivacyGate is designed around a local-first principle: sensitive source values are processed on the user's own computer before protected content is sent to a supported AI service. PrivacyGate does not sell personal data and does not use sensitive content for advertising.

## Browser extension

PrivacyGate browser extension version 1.0 supports:

- ChatGPT (`https://chatgpt.com/`)
- Google Gemini (`https://gemini.google.com/`)
- Claude (`https://claude.ai/`)

The extension's site access is limited to those domains. It uses the PrivacyGate bridge at `http://127.0.0.1:8765` for local analysis, protection, and restoration.

When protection is enabled, the extension may process text the user is preparing to submit, PDF files the user deliberately selects or drops for upload, and PrivacyGate placeholder tokens contained in an AI response when local restoration is available.

Original sensitive values are sent only to the local PrivacyGate bridge for local processing. The extension does not send those original values to an AI PM LAB cloud service. Before an outbound request is allowed, PrivacyGate replaces selected sensitive values with PrivacyGate placeholders. For a PDF upload, PrivacyGate attaches the protected PDF copy rather than the original PDF when protection succeeds.

The protected request or protected PDF is then sent to the AI provider chosen by the user through that provider's own website and network connection. ChatGPT, Google Gemini, and Claude are independent third-party services with their own terms and privacy policies.

When an AI response contains reversible PrivacyGate placeholders, restoration is requested from the local bridge. Restored sensitive text is rendered in an extension-origin local view and is not intentionally written back into the AI provider's page DOM.

The extension does not currently claim spreadsheet or Microsoft Excel protection as a supported browser-extension feature.

## Browser extension local storage

The extension uses `chrome.storage.local` only for local state needed to operate the product. This may include:

- whether browser protection is enabled;
- a local browser-pairing credential used to authenticate to the loopback PrivacyGate bridge;
- opaque local session identifiers associating a supported AI conversation with a still-live local restore session;
- PDF profile and language preferences;
- non-content UI or protection-state preferences.

The extension session registry does not store prompt text, PDF contents, detected PII values, reversible mappings, or restored values in `chrome.storage.local`.

The local PrivacyGate bridge may keep temporary reversible session state on the user's own computer so that placeholders can be restored during the active local session. Stale or unavailable session identifiers are rejected by the bridge.

## Permissions used by the browser extension

PrivacyGate version 1.0 requests:

- `storage` — to retain local extension settings, the local pairing credential, and opaque local session identifiers;
- access to `http://127.0.0.1:8765/*` — to communicate with the PrivacyGate application running on the user's own computer;
- content-script access to `chatgpt.com`, `gemini.google.com`, and `claude.ai` — to intercept user-initiated text/PDF submissions for local protection and display locally restored responses.

PrivacyGate does not request browsing-history, bookmarks, contacts, geolocation, microphone, camera, or advertising permissions.

## Chrome Web Store Limited Use

PrivacyGate uses user data only to provide and secure its disclosed single purpose: protecting user-selected text and PDF content before submission to supported AI assistants and restoring PrivacyGate placeholders locally when the user has a valid local session.

PrivacyGate's use of information received from Google APIs, where applicable, will adhere to the Chrome Web Store User Data Policy, including the Limited Use requirements.

## Desktop application

AI PM LAB PrivacyGate is designed as a local-first Windows desktop application. It does not require an account, telemetry service, cloud database, LLM connection, or mandatory external API for its core protection workflow.

Microsoft Presidio, spaCy analysis, PDF text extraction, protection, local library storage, and restoration run on the customer's computer. The application does not intentionally upload original documents, detected sensitive values, or reversible mappings through its MCP tools. Protected Library copies become available to MCP according to the user's enabled workflow, and individual protected documents can be blocked from AI access in the Library.

Desktop application data is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`. This may include protected text, document titles, labels, timestamps, findings metadata, and reversible mappings. Reversible mappings are protected for the current Windows user with Windows DPAPI.

The user controls local retention. Uninstalling or updating the application does not automatically delete this data. Users may remove documents through the application and may remove the local data directory when they no longer need the library, after making any required backup.

## Optional external actions

PrivacyGate separates local processing from optional external actions. Data may leave the computer only when the user deliberately performs an action such as sending protected text or a protected PDF to an AI service, copying protected text to another service, enabling an optional integration, or submitting information to a public website form.

When Remote MCP is enabled, PrivacyGate can start a loopback-only MCP service and create an outbound-only encrypted tunnel. The user may stop or revoke the connection. External services have their own terms and privacy policies. Users should send only protected content and should never transmit reversible mappings unless their own approved workflow specifically requires it.

## Website and browser demo

The pasted-text demo at `https://privacygate.propertydex.xyz/` runs in the browser and has no API connection for text analysis. Demo text is not submitted to AI PM LAB, Microsoft Presidio, or an LLM.

The public website may use Google Analytics to understand aggregate website traffic. Google Analytics, where enabled, applies to the public website only and not to the browser extension's protected text or PDF processing. The contact form is processed by Formspree and transmits only the fields the visitor chooses to submit.

## Logs, analytics, and advertising

The PrivacyGate desktop application and browser extension do not include advertising identifiers, behavioral advertising, or remote analytics for sensitive source content. The extension does not sell user data. Local diagnostic messages may be generated during troubleshooting but are not uploaded automatically by the extension.

## Security

PrivacyGate's browser workflow uses an authenticated loopback connection to the local bridge. The browser extension requests only the host access needed for its supported AI sites and local bridge.

Users remain responsible for the security and privacy settings of the third-party AI provider they choose to use. PrivacyGate reduces exposure by transforming selected sensitive values before submission; it does not control how a third-party provider handles the protected content it receives.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`.

Do not email real customer documents, original PII, reversible mappings, passwords, pairing credentials, or API keys.
