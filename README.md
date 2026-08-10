# AI PM LAB Privacy Gate

Windows desktop app local-first for detecting and protecting sensitive data before using business documents with AI. The desktop engine uses Microsoft Presidio and runs on the customer's PC.

## Current customer release: 0.3.1

- pasted text and PDF files with selectable text;
- Property Management, Realtor / Brokerage, and Projects & Renovations profiles;
- selectable entity categories and individual findings;
- manual sensitive-item tagging;
- reversible, generic, and permanent protection modes;
- encrypted local library with search and labels;
- local restore of protected AI output;
- manual "Copy & Open ChatGPT" workflow with no API key;
- contextual protection for U.S. government, banking, NYC property and real-estate workflow identifiers;
- extension points for real-estate recognizers, localhost API, MCP, n8n, email, and cloud automation.

No cloud service, account, telemetry, LLM, or external database is required by the desktop app. Reversible mappings are encrypted with Windows DPAPI for the current Windows user. The SQLite library lives outside the installation folder under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`, so installing an update does not overwrite customer documents.

The 0.3.1 PDF output is a clean text-based protected copy. Pixel-perfect layout preservation and OCR for image-only PDFs are not included in that public release.

## Internal 0.4 development branch

The current `codex/0.4-dev` branch adds layout-preserving secure PDF output and a universal protection layer above Presidio. Users can select Essential PII, PII + Financial, PII + Business Confidential, Maximum Protection, or Custom Review. Context-aware local recognizers distinguish bank accounts, routing and SWIFT/BIC values, card endings, transaction IDs, amounts, merchants, counterparties, transaction references, addresses, business registration numbers, invoices, purchase orders, contracts, customer/employee IDs, and case references without using a cloud model.

The same development branch now includes a local read-only MCP server. Documents remain private by default and must be individually marked **Share with MCP** in the Library. Compatible desktop clients can list, search and read only those protected copies; original PII and encrypted restore mappings are never exposed by the MCP boundary.

## Downloads and release status

The customer-facing Windows installer is published in the [official downloads repository](https://github.com/patpet21/ai-pm-lab-privacy-gate-downloads/releases). Version 0.3.1 is the current release. The 0.3.1 installer is not yet Authenticode-signed; the project is preparing an application to SignPath Foundation.

## Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/) (pending Foundation approval; current releases remain unsigned until acceptance).

The complete policy, team roles, release controls, and privacy declaration are documented in [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md). Also see the [privacy policy](PRIVACY.md), [security policy](SECURITY.md), [third-party notices](THIRD_PARTY_NOTICES.md), and [release process](docs/RELEASE_PROCESS.md).

## Run from source

```powershell
.\.venv\Scripts\python.exe .\run_app.py
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Build Windows

```powershell
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1
```

The portable build is generated under `dist\AI PM LAB Privacy Gate`. Keep the complete folder together because the executable loads its private runtime from the adjacent `_internal` directory. The installer is generated under `release`.

GitHub Actions also performs a clean Windows build on GitHub-hosted infrastructure and retains the installer, checksums, and build manifest as workflow artifacts. After SignPath approval, the release workflow will submit those GitHub-built artifacts for signing; credentials will be stored only as encrypted GitHub Actions secrets.

Release builds install the exact dependency versions in `requirements-lock.txt`, including a SHA-256-pinned spaCy language model. Dependency updates are proposed and tested separately before the lock file is changed.

## Browser demo

`web-demo` is a separate client-side demo for Netlify. It accepts pasted text only, performs a small browser-side demonstration, and never uploads the sample. It is deliberately not presented as equivalent to the full Presidio desktop engine.

## One repository, two deliverables

- Netlify publishes only `web-demo/` as the public website and text-only demo.
- The Windows application is built from `src/`, `resources/` and `packaging/`.
- Installers and generated build folders are release artifacts and are not committed to Git.
- Customer library data stays outside the repository and installation directory in `%LOCALAPPDATA%`.

The source code is licensed under the MIT License. Product names and logos may be used to identify the original project but do not grant endorsement by AI PM LAB or Trigosat Consulting.

## Repository structure

```text
src/ai_pm_lab_privacy_gate/
  application/       orchestration and protection service
  domain/            profiles and models
  infrastructure/    Presidio, PDF, encrypted storage, future local API
  ui/                 PySide6 desktop interface
resources/            logo, Presidio configuration, future recognizers
packaging/windows/    PyInstaller and Inno Setup configuration
tests/                unit and integration tests
web-demo/             static Netlify product demo
```
