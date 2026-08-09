# AI PM LAB Privacy Gate 0.2.1 — Build Information

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
C9DBF2F572749266FEEF812CDDB3BDDD83B8AFF7DB4DC8EB60E8EBB3E7188D08
```

Installer 0.2.1 SHA-256:

```text
1AD487761AAF745AE757F4A68AD42CC302660D424C050147A1E5609D3CF2E4CF
```

The installer is not Authenticode-signed. Windows or endpoint protection can therefore show an unknown-publisher or reputation warning until a commercial code-signing certificate is added.

## Known limitations

- image-only/scanned PDFs are rejected; OCR is not included;
- protected PDFs are clean reflowed text copies, not pixel-perfect replicas;
- English NLP is bundled for the U.S.-focused first version;
- automated detection always requires human review;
- integrations displayed under Connections are roadmap placeholders and are not active.
