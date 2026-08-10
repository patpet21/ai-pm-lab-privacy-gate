# Security policy

## Supported version

Security fixes are applied to the latest published release of AI PM LAB Privacy Gate.

## Reporting a vulnerability

Please do not publish suspected vulnerabilities or real customer documents in a GitHub issue. Report them privately to `peter@propertydex.xyz` with the application version, Windows version, steps to reproduce, and synthetic sample data where possible.

## Local data model

The desktop application does not require a cloud account, telemetry service, LLM, or external database. Its library is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`. Reversible mappings are protected for the current Windows user with Windows DPAPI.

Never attach a customer's original document, local database, reversible mapping, API key, or access token to a public issue.
