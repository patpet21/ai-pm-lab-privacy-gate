# PrivacyGate Browser Protection — Chrome Privacy Policy

Last updated: 2026-09-09

PrivacyGate Browser Protection for Google Chrome is a local-first companion extension for PrivacyGate Desktop. Its single purpose is to help users review and protect sensitive information before text or files are submitted to supported AI websites, and to restore PrivacyGate placeholders locally when possible.

## Supported websites

The extension operates only on:

- `https://chatgpt.com/`
- `https://claude.ai/`
- `https://gemini.google.com/`

## Data the extension may access

To provide its user-facing protection features, the extension may access:

- text the user enters into a supported AI message composer;
- files the user explicitly selects, drops, or pastes for upload;
- sensitive values detected during local analysis and shown in PrivacyGate review interfaces;
- protected placeholders and local restoration results;
- the supported AI provider and a conversation identifier derived from the provider's conversation URL;
- an opaque PrivacyGate session identifier and timestamp used to reconnect a conversation with the correct local restore mapping;
- extension preferences such as protection state, selected profile, and document language;
- a locally generated browser client identifier and pairing credential.

## How this data is used

When protection is enabled, text and supported files are intercepted before submission to the AI provider and sent to PrivacyGate Desktop through a loopback-only service on `127.0.0.1` on the same computer.

PrivacyGate Desktop performs local analysis and protection. Original text, original files, detected sensitive values, and reversible mappings are not sent by the extension to an AI PM LAB-operated remote server for the local protection workflow.

The user reviews detected values and decides what to protect. Selected values are replaced with PrivacyGate placeholders before protected text or a protected file is returned to the supported AI website for submission.

## Local storage

The extension uses Chrome local extension storage (`chrome.storage.local`) for limited operational data such as:

- protection preferences;
- document language and related local settings;
- the local browser client identifier;
- the pairing credential used to authenticate to PrivacyGate Desktop;
- limited provider/conversation/session associations needed for local restore.

These local associations are not used for advertising or behavioral profiling.

## Local restore

If an AI response contains PrivacyGate placeholders, the extension may ask PrivacyGate Desktop for the corresponding local values. The current secure restore path renders restored values inside an extension-owned surface rather than intentionally writing those restored values into the supported AI website's page DOM.

## Third-party AI providers

Content that the user ultimately chooses to submit is processed by the selected third-party AI provider under that provider's own terms and privacy policy. If the user leaves a detected value unprotected or disables PrivacyGate protection, that content may be sent to the provider by the website at the user's direction.

## Data sharing and sale

PrivacyGate Browser Protection does not:

- sell user data;
- use user data for personalized, retargeted, or interest-based advertising;
- transfer user data for data-brokerage purposes;
- send original text, original files, detected sensitive values, or reversible mappings to AI PM LAB servers for the local protection workflow;
- include remote behavioral analytics or remote crash reporting in the extension;
- execute remotely hosted JavaScript as part of the extension package.

## User controls

Users can:

- turn PrivacyGate browser protection on or off;
- review detected values before protection;
- cancel a protection action;
- revoke or replace the browser pairing through PrivacyGate Desktop;
- remove/reset the extension to clear extension-local storage;
- manage local PrivacyGate Desktop Library data separately.

## Chrome Web Store Limited Use

PrivacyGate Browser Protection's use of information received from Chrome APIs and supported webpages is limited to providing and improving the extension's single user-facing purpose: local privacy protection and local restoration for user-selected AI interactions. User data is not used for personalized advertising and is not transferred for unrelated purposes.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`. Do not email real customer documents, original PII, reversible mappings, passwords, pairing credentials, or API keys.
