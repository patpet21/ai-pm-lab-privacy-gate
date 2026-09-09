# Privacy policy

Last updated: 2026-09-09

## PrivacyGate Desktop

AI PM LAB PrivacyGate is designed as a local-first desktop application. It does not require an AI PM LAB account, advertising service, behavioral telemetry service, cloud database, or mandatory external LLM connection for its core protection workflow.

Microsoft Presidio, spaCy analysis, document extraction, protection, local Library storage, and restoration run on the user's computer. The application does not upload original documents, detected values, or reversible mappings to AI PM LAB servers as part of the local protection workflow.

Protected Library copies may be made available to optional integrations only when the user enables those integrations. Reversible mappings remain local and are not exposed through MCP tools.

## Browser extension

PrivacyGate Browser Protection is an optional companion extension for supported AI websites. It is designed to prevent sensitive information from being sent to supported AI providers before the user has had an opportunity to review and protect it.

The extension currently operates only on:

- `https://chatgpt.com/`
- `https://claude.ai/`
- `https://gemini.google.com/`

The extension may access the following data only as needed to provide its user-facing protection features:

- text the user enters into a supported AI message composer;
- files the user explicitly selects, drops, or pastes for upload on a supported AI website;
- detected sensitive values shown to the user inside PrivacyGate review interfaces;
- protected placeholders and local restoration results;
- the supported AI website and conversation identifier needed to associate an opaque PrivacyGate session with the correct conversation;
- local extension preferences such as whether protection is enabled, selected protection profile, and document language;
- a locally generated browser client identifier and pairing credential used to authenticate the extension to PrivacyGate Desktop on the same computer.

### Local processing and loopback bridge

When protection is enabled, text and supported files are intercepted before they are submitted to the AI provider and are sent to the locally installed PrivacyGate Desktop application through a loopback-only service on `127.0.0.1`.

This loopback communication stays on the user's computer. Original text, original files, detected sensitive values, and reversible mappings are not sent by the extension to an AI PM LAB-operated remote server for analysis.

The extension uses a local pairing credential so that an unrelated webpage cannot freely use the PrivacyGate Desktop bridge. Pairing information and extension preferences are stored in browser-local extension storage (`chrome.storage.local` or the compatible Microsoft Edge extension storage implementation).

### Review and protection

PrivacyGate displays detected values in extension-owned review interfaces. The user decides which detected values to protect. Checked values are replaced with placeholders before protected text or a protected file is handed back to the supported AI website.

If the user intentionally leaves a detected item unselected, turns PrivacyGate protection off, or otherwise chooses to send unprotected content, that content may be transmitted to the selected AI provider according to that provider's own terms and privacy policy.

PrivacyGate is designed to fail closed while protection is enabled: if local analysis or file protection fails, the extension should not substitute the original file as a fallback.

### Local restore

When an AI response contains PrivacyGate placeholders, the extension may request the corresponding values from PrivacyGate Desktop and render the restored result locally inside an extension-owned restore surface. Restored values are not intentionally written into the supported AI website's page DOM by the current secure restore path.

### Conversation and session association

To reconnect protected responses with the correct local mapping, the extension may store a limited local association between the supported AI provider, a conversation identifier derived from that provider's conversation URL, an opaque PrivacyGate session identifier, and a timestamp.

This association is used only to provide the restore feature. It is not used for advertising, behavioral profiling, or sale of user data.

### What the browser extension does not do

The browser extension does not:

- sell user data;
- use user data for advertising or retargeting;
- build advertising or behavioral profiles;
- include remote analytics or remote crash reporting from the extension;
- send original text, original files, detected sensitive values, or reversible mappings to AI PM LAB servers for the local protection workflow;
- request access to arbitrary websites outside the supported AI websites listed above;
- download or execute remote JavaScript as part of the extension package.

### Third-party AI providers

After the protection workflow, content that the user chooses to submit is sent by the supported website to that AI provider. ChatGPT, Claude, and Gemini are third-party services with their own terms and privacy policies. PrivacyGate does not control how those providers process content that the user ultimately chooses to send.

### User controls

Users can:

- turn browser protection on or off from the PrivacyGate extension interface;
- review detected values before protection;
- cancel a text or file protection action;
- revoke or replace the browser pairing through PrivacyGate Desktop;
- clear extension-local storage by removing/resetting the extension through the browser;
- remove local documents and mappings through PrivacyGate Desktop where applicable.

Removing or disabling the extension stops its content scripts from operating on supported AI websites.

### Chrome Web Store Limited Use

PrivacyGate Browser Protection's use of information received from Chrome APIs and supported webpages is limited to providing and improving the extension's single user-facing purpose: local privacy protection and local restoration for user-selected AI interactions. User data is not used for personalized advertising and is not transferred for data-brokerage purposes.

## Local storage

Desktop application data is stored locally in the PrivacyGate application data directory. Depending on the platform and enabled features, this may include protected text, document titles, labels, timestamps, findings metadata, and reversible mappings. Sensitive local mappings are protected using operating-system-appropriate local security mechanisms where implemented.

The user controls retention. Updating or uninstalling the desktop application may not automatically delete all local Library data. Users should remove local data through the application or operating system when they no longer need it, after making any required backup.

## Optional external actions

PrivacyGate clearly separates local processing from optional external actions. Data may leave the computer when the user deliberately performs an action such as:

- submitting protected text or protected files to a third-party AI service;
- copying protected content into another service;
- enabling Remote MCP, n8n, email, local API, or another integration that the user configures;
- submitting information through the public website contact form.

When Remote MCP is enabled, PrivacyGate may use an outbound tunnel to make specifically enabled protected resources available to a connected AI client. Remote MCP is separate from the browser extension's loopback protection workflow.

External services have their own terms and privacy policies. Users should send only content appropriate for the selected service and should not transmit reversible mappings unless their own approved workflow specifically requires it.

## Website

The public PrivacyGate website and browser extension are separate surfaces. Website analytics or contact-form services, where enabled, do not receive text or files processed locally by the browser extension merely because the extension is installed or used.

Visitors must not place customer documents, PII, credentials, reversible mappings, passwords, or API keys in public contact forms.

## Logs and telemetry

PrivacyGate Desktop and PrivacyGate Browser Protection do not include advertising identifiers or behavioral tracking for the local protection workflow. Local diagnostic messages may be generated during development or troubleshooting but are not uploaded automatically by the extension.

Browser stores and supported AI providers may independently collect their own store, browser, site, performance, or usage information under their own policies.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`. Do not email real customer documents, original PII, reversible mappings, passwords, pairing credentials, or API keys.
