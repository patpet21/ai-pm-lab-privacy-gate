# Privacy Policy — PrivacyGate

Last updated: 2026-09-05

PrivacyGate is designed around a local-first principle: sensitive source values are processed on the user's own computer before protected content is sent to a supported AI service. PrivacyGate does not sell personal data and does not use sensitive content for advertising.

## Browser extension

The PrivacyGate browser extension supports these AI websites in version 1.0:

- ChatGPT (`https://chatgpt.com/`)
- Google Gemini (`https://gemini.google.com/`)
- Claude (`https://claude.ai/`)

The extension's site access is limited to those domains. It uses a local PrivacyGate bridge at `http://127.0.0.1:8765` to analyze, protect, and restore content.

When protection is enabled, the extension may process:

- text that the user is preparing to submit to a supported AI assistant;
- PDF files that the user deliberately selects or drops for upload;
- PrivacyGate placeholder tokens contained in an AI response, when local restoration is available.

Original sensitive values are sent to the local PrivacyGate bridge for local processing. The extension does not send those original values to an AI PM LAB cloud service. Before an outbound request is allowed, PrivacyGate replaces selected sensitive values with PrivacyGate placeholders. For a PDF upload, PrivacyGate attaches the protected PDF copy rather than the original PDF when protection succeeds.

The protected request or protected PDF is then sent to the AI provider chosen by the user through that provider's own website and network connection. ChatGPT, Google Gemini, and Claude are independent third-party services with their own terms and privacy policies.

When an AI response contains reversible PrivacyGate placeholders, restoration is requested from the local bridge. Restored sensitive text is rendered in an extension-origin local view and is not intentionally written back into the AI provider's page DOM.

The extension does not currently claim spreadsheet or Microsoft Excel protection as a supported browser-extension feature.

## Browser extension local storage

The extension uses `chrome.storage.local` only for local browser state needed to operate the product. This may include:

- whether browser protection is enabled;
- a local browser-pairing credential used to authenticate to the loopback PrivacyGate bridge;
- opaque local session identifiers that associate a supported AI conversation with a still-live local restore session;
- PDF profile and language preferences;
- other non-content UI or protection-state preferences.

The extension session registry does not store prompt text, PDF contents, detected PII values, reversible mappings, or restored values in `chrome.storage.local`.

The local PrivacyGate bridge may keep temporary reversible session state on the user's own computer so that placeholders can be restored during the active local session. Stale or unavailable session identifiers are rejected by the bridge.

## Permissions used by the browser extension

PrivacyGate version 1.0 requests:

- `storage` — to retain local extension settings, the local pairing credential, and opaque local session identifiers;
- access to `http://127.0.0.1:8765/*` — to communicate with the PrivacyGate application running on the user's own computer;
- content-script access to `chatgpt.com`, `gemini.google.com`, and `claude.ai` — to intercept user-initiated text/PDF submissions for local protection and to display locally restored responses.

PrivacyGate does not request browsing-history, bookmarks, contacts, geolocation, microphone, camera, or advertising permissions.

## Desktop application

AI PM LAB PrivacyGate is designed as a local-first Windows desktop application. It does not require an account, telemetry service, cloud database, LLM connection, or mandatory external API for its core protection workflow.

Microsoft Presidio, spaCy analysis, PDF text extraction, protection, local library storage, and restoration run on the customer's computer. The application does not intentionally upload original documents, detected sensitive values, or reversible mappings through its MCP tools. Protected Library copies become available to MCP by default when saved, but no MCP network connection is opened until the user enables the relevant connection. Individual protected documents can be blocked from AI access in the Library.

## Desktop local storage

Desktop application data is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`. This may include protected text, document titles, labels, timestamps, findings metadata, and reversible mappings. Reversible mappings are protected for the current Windows user with Windows DPAPI.

The user controls local retention. Uninstalling or updating the application does not automatically delete this data. Users may remove documents through the application and may remove the local data directory when they no longer need the library, after making any required backup.

## Optional external actions

PrivacyGate clearly separates local processing from optional external actions. Data may leave the computer only when the user deliberately performs an action such as:

- sending protected text or a protected PDF to a supported AI service;
- copying protected text into another AI or communication service;
- selecting an option that opens a third-party AI website or application;
- downloading software or documentation from GitHub, Netlify, or Google Drive;
- submitting the website contact form through Formspree;
- enabling Remote MCP, n8n, email, a local API, or another optional integration.

When Remote MCP is enabled, PrivacyGate starts a loopback-only MCP service and the bundled `cloudflared` component can create an outbound-only encrypted tunnel. The complete private URL contains a randomly generated access secret. Cloudflare carries MCP requests between the connected AI service and the local application. The tunnel address is session-based, the application must remain open, and the user may stop or revoke the connection at any time. MCP tools expose protected text and non-sensitive Library metadata according to the enabled workflow; they are not intended to expose original files or encrypted restore mappings.

External services have their own terms and privacy policies. Users should send only protected content and should never transmit reversible mappings unless their own approved workflow specifically requires it.

## Website and browser demo

The pasted-text demo at `https://privacygate.propertydex.xyz/` runs in the browser and has no API connection for text analysis. Demo text is not submitted to AI PM LAB, Microsoft Presidio, or an LLM.

The public website may use Google Analytics to understand aggregate website traffic. Google may receive browser, device, referral, interaction, and approximate-location information according to Google's own terms and privacy controls. The contact form is processed by Formspree and transmits the fields the visitor chooses to submit. Visitors must not place customer documents, PII, credentials, or other sensitive data in the form. Downloadable guides or release files may be hosted on Google Drive or GitHub.

## Logs, analytics, and advertising

The PrivacyGate desktop application and browser extension do not include advertising identifiers, behavioral advertising, or remote analytics for sensitive source content. The extension does not sell user data. Local diagnostic messages may be generated during development or troubleshooting but are not uploaded automatically by the extension.

Google Analytics, where enabled, applies to the public website only and not to the browser extension's protected text or PDF processing.

## Security

PrivacyGate's browser workflow uses an authenticated loopback connection to the local bridge. The browser extension requests only the host access needed for its supported AI sites and the local bridge.

Users remain responsible for the security and privacy settings of the third-party AI provider they choose to use. PrivacyGate reduces exposure by transforming selected sensitive values before submission; it does not control how a third-party provider handles the protected content it receives.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`.

Do not email real customer documents, original PII, reversible mappings, passwords, pairing credentials, or API keys.
