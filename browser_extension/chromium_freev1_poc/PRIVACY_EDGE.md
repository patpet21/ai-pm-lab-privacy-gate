# PrivacyGate Browser Protection — Microsoft Edge Privacy Policy

Last updated: 2026-09-09

PrivacyGate Browser Protection for Microsoft Edge is a local-first companion extension for PrivacyGate Desktop. Its single purpose is to help users review and protect sensitive information before text or files are submitted to supported AI websites, and to restore PrivacyGate placeholders locally when possible.

PrivacyGate Desktop must be installed and running for the local analysis, protection, and restore features to work.

## Supported websites in Microsoft Edge

The extension operates only on:

- `https://chatgpt.com/`
- `https://claude.ai/`
- `https://gemini.google.com/`

## Personal information the extension may access

To provide its user-facing protection features in Microsoft Edge, the extension may access:

- text the user enters into a supported AI message composer;
- files the user explicitly selects, drops, or pastes for upload;
- sensitive values detected during local analysis and shown in PrivacyGate review interfaces;
- protected placeholders and local restoration results;
- the supported AI provider and a conversation identifier derived from the provider's conversation URL;
- an opaque PrivacyGate session identifier and timestamp used to reconnect a conversation with the correct local restore mapping;
- extension preferences such as protection state, selected profile, and document language;
- a locally generated browser client identifier and pairing credential.

This access is limited to functionality the user can see and control through the extension.

## Local processing and same-computer bridge

When protection is enabled, text and supported files are intercepted before submission to the AI provider and sent to PrivacyGate Desktop through a loopback-only service on `127.0.0.1` on the same computer.

The loopback bridge is not a public AI PM LAB cloud endpoint. PrivacyGate Desktop performs the local analysis and protection. Original text, original files, detected sensitive values, and reversible mappings are not sent by the extension to an AI PM LAB-operated remote server for the local protection workflow.

The browser-to-desktop bridge uses a local pairing credential to authenticate the Microsoft Edge extension to PrivacyGate Desktop.

## Review and protection

The user reviews detected values and decides which findings to protect. Selected values are replaced with PrivacyGate placeholders before protected text or a protected file is returned to the supported AI website for submission.

If the user intentionally leaves a detected value unprotected, turns PrivacyGate protection off, or otherwise chooses to send unprotected content, that content may be sent by the supported website to the selected AI provider at the user's direction.

While protection is enabled, PrivacyGate is designed so that a local processing failure does not substitute the original file as a fallback upload.

## Microsoft Edge local extension storage

The extension uses the Microsoft Edge-compatible local extension storage implementation for limited operational data such as:

- protection preferences;
- document language and related local settings;
- the local browser client identifier;
- the pairing credential used to authenticate to PrivacyGate Desktop;
- limited provider/conversation/session associations needed for local restore.

These local associations are not used for advertising, behavioral profiling, or sale of personal information.

## Local restore

If an AI response contains PrivacyGate placeholders, the extension may ask PrivacyGate Desktop for the corresponding local values. The current secure restore path renders restored values inside an extension-owned surface rather than intentionally writing restored values into the supported AI website's page DOM.

## Third-party AI providers

Content that the user ultimately chooses to submit is processed by the selected third-party AI provider under that provider's own terms and privacy policy. PrivacyGate does not control how ChatGPT, Claude, or Gemini process content that the user chooses to send.

## Data sharing, advertising, and sale

PrivacyGate Browser Protection for Microsoft Edge does not:

- sell personal information or user data;
- use user data for personalized, retargeted, or interest-based advertising;
- transfer user data for data-brokerage purposes;
- send original text, original files, detected sensitive values, or reversible mappings to AI PM LAB servers for the local protection workflow;
- include remote behavioral analytics or remote crash reporting in the extension;
- request access to arbitrary websites outside the supported AI websites listed above;
- execute remotely hosted JavaScript as part of the extension package.

## User controls

Users can:

- turn PrivacyGate browser protection on or off;
- review detected values before protection;
- cancel a protection action;
- revoke or replace the browser pairing through PrivacyGate Desktop;
- remove/reset the extension in Microsoft Edge to clear extension-local storage;
- manage local PrivacyGate Desktop Library data separately.

Removing or disabling the Microsoft Edge extension stops its content scripts from operating on supported AI websites.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`. Do not email real customer documents, original PII, reversible mappings, passwords, pairing credentials, or API keys.
