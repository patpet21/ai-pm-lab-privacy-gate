# Privacy policy

Last updated: 2026-08-10

## Desktop application

AI PM LAB Privacy Gate is designed as a local-first Windows desktop application. It does not require an account, telemetry service, cloud database, LLM connection, or mandatory external API.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

Microsoft Presidio, spaCy analysis, PDF text extraction, protection, local library storage, and restoration run on the customer's computer. The application does not automatically upload original documents, detected values, protected documents, reversible mappings, or library metadata.

## Local storage

Application data is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`. This may include protected text, document titles, labels, timestamps, findings metadata, and reversible mappings. Reversible mappings are protected for the current Windows user with Windows DPAPI.

The user controls retention. Uninstalling or updating the application does not automatically delete this data. Users may remove documents through the application and may remove the local data directory when they no longer need the library, after making any required backup.

## Optional external actions

Privacy Gate clearly separates local processing from optional external actions. Data may leave the computer only when the user deliberately performs an action such as:

- copying protected text into an AI or communication service;
- selecting an option that opens a third-party AI website or application;
- downloading software or documentation from GitHub, Netlify, or Google Drive;
- submitting the website contact form through Formspree;
- enabling a future n8n, MCP, email, local API, or cloud integration.

External services have their own terms and privacy policies. Users should send only protected content and should never transmit reversible mappings unless their own approved workflow specifically requires it.

## Browser demo and website

The pasted-text demo at `https://aipmlab.netlify.app/` runs in the browser and has no API connection for text analysis. Demo text is not submitted to AI PM LAB, SignPath, Microsoft Presidio, or an LLM.

The website is hosted by Netlify. The contact form is processed by Formspree and transmits the fields the visitor chooses to submit. Visitors must not place customer documents, PII, credentials, or other sensitive data in the form. The downloadable guide is hosted on Google Drive and release files are hosted on GitHub.

## Logs and telemetry

The desktop application does not include analytics, advertising identifiers, behavioral tracking, or remote crash reporting. Local diagnostic messages may be generated during development or troubleshooting but are not uploaded automatically.

## Contact

Privacy and security questions may be sent to `peter@propertydex.xyz`. Do not email real customer documents, original PII, reversible mappings, passwords, or API keys.
