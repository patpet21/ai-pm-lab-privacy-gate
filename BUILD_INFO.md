# AI PM LAB Privacy Gate 0.3.0 — Build Information

Build date: 2026-08-09
Target: Windows x64
Packaging: PyInstaller onedir + Inno Setup installer

## Verified capabilities

- pasted text and PDF analysis with Microsoft Presidio;
- finding review by category and individual item;
- manual sensitive-item tagging;
- reversible, generic, and permanent protection;
- encrypted local library and labels;
- local restoration of protected AI output;
- three real-estate operations profiles;
- no mandatory cloud, account, telemetry, n8n, or LLM connection;
- browser-only pasted-text demo for Netlify.
- collapsible desktop navigation and a two-column review workspace;
- color-coded protected placeholders in desktop and browser previews;
- branded Windows EXE, installer, shortcuts, and website icon;
- expanded website workflow, capability comparison, and product facts.

## Runtime verification

The distribution contains `python312.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`, and `msvcp140.dll` under `_internal`. The unpacked EXE and the installed EXE were both launched on the build PC; each produced a responsive window titled `AI PM LAB Privacy Gate`.

The installer completed with exit code `0` after its temporary extraction directory was moved into the AVG-excluded local project folder. A repeat update left the local library unchanged: one local database file remained exactly `73,728` bytes before and after installation. Customer data is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`, outside the application directory.

## Artifact integrity

Portable EXE SHA-256:

```text
0770711457E53445D762C3AE21591DFADF0BA2930573B1872DC5EF3DE112E01B
```

Installer 0.3.0 SHA-256:

```text
7397E19BA1B70BC2A93A999B405D0745683D1BAC0BC8F454DFCEFC58865093D1
```

The installer is not Authenticode-signed. Windows or endpoint protection can therefore show an unknown-publisher or reputation warning until a commercial code-signing certificate is added.

## Known limitations

- image-only/scanned PDFs are rejected; OCR is not included;
- protected PDFs are clean reflowed text copies, not pixel-perfect replicas;
- English NLP is bundled for the U.S.-focused first version;
- automated detection always requires human review;
- integrations displayed under Connections are roadmap placeholders and are not active.
