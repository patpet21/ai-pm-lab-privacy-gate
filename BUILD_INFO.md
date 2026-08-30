# AI PM LAB Privacy Gate 0.5.0 — Build Information

Release line: 0.5.x
Targets: Windows x64, macOS Apple Silicon, macOS Intel
Packaging: PyInstaller onedir + Inno Setup / MSIX on Windows; `.app` + DMG on macOS

## Verified capabilities in source

- local-first PII detection and protection for pasted text, PDF, DOCX, XLSX, PPTX and TXT;
- local OCR for printed-text PNG/JPG/JPEG document photos and screenshots;
- pixel-level image redaction using OCR geometry plus protected TXT companion output;
- English and Italian document detection profiles;
- image handling through local upload, Google Drive and Gmail materialization paths;
- finding review by category and individual item;
- reversible, generic, masked, and permanent protection modes;
- encrypted local Library, protected copies, labels and reversible mappings;
- local restoration of protected AI output;
- local MCP / optional secure remote MCP for already-protected Library content;
- Microsoft Store package update integration for Store/MSIX installations;
- verified direct updater for installed Windows EXE and macOS DMG channels;
- SHA-256 verification and a pre-update encrypted Library backup before direct updates.

Handwriting OCR is intentionally not claimed in this release.

## User data and updates

Application binaries and user data are separate. The updater replaces application files only.

Default user-data locations:

- Windows: `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`
- macOS: `~/Library/Application Support/AI PM LAB Privacy Gate/Data`

The direct updater creates an encrypted `.pgbackup` Library snapshot before starting an EXE or DMG replacement. Windows Store updates remain managed exclusively by Microsoft Store APIs.

## Windows distribution

The Windows direct installer uses a stable Inno Setup `AppId`, allowing a newer direct installer to replace the prior direct installation in place. The Store build uses MSIX and Microsoft Store signing/update delivery.

The direct EXE is not Authenticode-signed until a production code-signing identity is configured. Windows or endpoint protection can therefore still display publisher/reputation warnings for website downloads.

## macOS distribution

The direct macOS updater verifies the release SHA-256, confirms the expected bundle identifier (`xyz.propertydex.privacygate`), verifies the bundle code signature structure, replaces the existing `.app`, keeps a rollback copy during replacement, and reopens PrivacyGate.

Current CI builds remain ad-hoc signed until Apple Developer ID credentials and notarization are configured. Developer ID signing/notarization is therefore still required before describing the website DMG as a fully production-signed macOS distribution.

## Artifact integrity

Each release build writes SHA-256 evidence alongside its generated installer/DMG. `web-demo/release.json` must only be changed after the final artifacts have been built, uploaded, and their final SHA-256 values are known.
