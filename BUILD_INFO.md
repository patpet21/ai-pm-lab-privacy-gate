# AI PM LAB Privacy Gate 0.2.0 — Build Information

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

## Runtime verification

The distribution contains `python312.dll`, `vcruntime140.dll`, `vcruntime140_1.dll`, and `msvcp140.dll` under `_internal`. The unpacked EXE and the installed EXE were both launched on the build PC; each produced a responsive window titled `AI PM LAB Privacy Gate`.

The installer completed with exit code `0`. A repeat update left the local library unchanged, verified by identical SHA-256 hashes before and after installation. Customer data is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`, outside the application directory.

## Artifact integrity

Portable EXE SHA-256:

```text
7C8D58E76620EA362739BE7A45D5D07049DAEF920520DC9BE0B3BDFB8A1D03CA
```

Installer 0.2.0 SHA-256:

```text
C5F73819B23399EB43D05B302B0E78D7564712B8D51271E25381358E4750D352
```

The installer is not Authenticode-signed. Windows or endpoint protection can therefore show an unknown-publisher or reputation warning until a commercial code-signing certificate is added.

## Known limitations

- image-only/scanned PDFs are rejected; OCR is not included;
- protected PDFs are clean reflowed text copies, not pixel-perfect replicas;
- English NLP is bundled for the U.S.-focused first version;
- automated detection always requires human review;
- integrations displayed under Connections are roadmap placeholders and are not active.
