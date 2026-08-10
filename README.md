# AI PM LAB Privacy Gate

Windows desktop app local-first for detecting and protecting sensitive data before using business documents with AI. The desktop engine uses Microsoft Presidio and runs on the customer's PC.

## Version 0.3.1

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

The PDF output is a clean text-based protected copy. Pixel-perfect layout preservation and OCR for image-only PDFs are not included yet.

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
