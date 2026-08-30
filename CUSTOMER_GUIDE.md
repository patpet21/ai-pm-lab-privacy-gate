# AI PM LAB Privacy Gate — Customer Guide

## 1. Install PrivacyGate

PrivacyGate 0.5.0 supports Windows x64 and macOS.

On Windows, the recommended distribution is Microsoft Store. A separate direct EXE installer is also available from the official PrivacyGate distribution page. Microsoft Store installations are updated through Microsoft Store; direct EXE installations use PrivacyGate's verified direct updater after version 0.5.0 is installed.

On macOS, the direct distribution is a DMG containing `AI PM LAB Privacy Gate.app`. Move the app to **Applications** before opening it. Direct macOS updates require the app to be installed outside the mounted DMG. Until a production Apple Developer ID signature and notarization are configured, macOS may display additional Gatekeeper warnings for direct-download builds.

Windows direct downloads are not Authenticode-signed until a production Windows signing identity is configured, so Windows or endpoint protection can still display publisher/reputation warnings. Use only official PrivacyGate downloads and verify published release information.

## 2. Protect text and documents

Open **Protect**, choose the appropriate privacy profile and document language, load a supported source, then select **Scan for sensitive data**. Review every detected value before protection. PrivacyGate supports reversible placeholders when you want to restore identities later, plus non-reversible protection modes.

Supported document formats include PDF, Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx`, text `.txt`, and printed-text document images `.png`, `.jpg`, and `.jpeg`.

The original source is not overwritten. Protected document formats also receive a protected UTF-8 TXT companion where applicable.

## 3. Protect screenshots and document photos

PrivacyGate 0.5.0 includes local OCR for **printed text** in PNG and JPG/JPEG screenshots or document photos.

1. Load the image from local upload, Google Drive, or a Gmail attachment.
2. Scan it normally from Protect.
3. Review the OCR text and detected sensitive values.
4. Protect the selected values.
5. PrivacyGate creates a new raster image with the selected sensitive pixels redacted and a protected TXT companion.

OCR processing and sensitive-data detection occur locally after the source has been materialized into PrivacyGate's local working area. The protected image is a new file; PrivacyGate does not overwrite the original.

**Handwriting is not supported in this release.** OCR quality also depends on image resolution, lighting, perspective and screen/photo artifacts. Always review the protected output before sharing it.

## 4. Protect PDFs and Office documents

For PDFs with selectable text, PrivacyGate can create a layout-preserving protected PDF using secure overlays. Scanned/image-only PDF pages are a separate capability from JPG/PNG image OCR and should not be assumed to work unless the current Protect flow explicitly accepts and previews them.

For Word `.docx` and Excel `.xlsx`, PrivacyGate scans supported editable content and writes a protected copy in the same Office format. PowerPoint `.pptx` and text `.txt` use the shared document pipeline as well. Legacy `.doc`/`.xls`, macro-enabled Office files and password-protected files are not claimed as supported in this release.

When a local renderer is available, PrivacyGate can show original/protected comparisons. Protection remains functional even when an optional document-rendering dependency is unavailable.

## 5. Use protected content with AI

Use **Open with AI**, copy the protected text manually, or use an approved protected Library/MCP workflow. Keep placeholders such as `[[PG_PERSON_001]]` unchanged if you intend to restore the result later.

PrivacyGate never claims that an external AI service is local. Detection, OCR, protection, Library mappings and restoration are local PrivacyGate operations; any external AI service follows that provider's own data handling.

## 6. Restore locally

1. Open **Restore**.
2. Select the matching protected Library document.
3. Paste or load the protected AI result containing PrivacyGate placeholders.
4. Select **Restore locally**.
5. Review the restored result before saving or sharing it.

Reversible mappings are not sent through the protected MCP Library.

## 7. Local Library and data preservation

PrivacyGate stores application binaries separately from local user data.

Default data locations:

- Windows: `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`
- macOS: `~/Library/Application Support/AI PM LAB Privacy Gate/Data`

The Library contains protected-document state and encrypted reversible mappings. Updating application binaries must not delete this directory.

Before a Windows Direct or macOS Direct automatic update, PrivacyGate creates an encrypted `.pgbackup` Library snapshot. The app then downloads the matching release package over HTTPS and requires the published SHA-256 checksum to match before installation starts.

## 8. Update behavior

PrivacyGate checks the official release manifest without blocking local use.

- **Microsoft Store / MSIX:** Microsoft Store remains the update authority. PrivacyGate can request the official Store package update and restart after installation.
- **Windows Direct EXE:** PrivacyGate downloads the matching EXE installer, verifies SHA-256, creates a Library backup, closes the running app, upgrades the existing Inno Setup installation and reopens PrivacyGate.
- **macOS Direct DMG:** PrivacyGate downloads the matching DMG, verifies SHA-256, creates a Library backup, validates the expected bundle identifier/version and code-signature structure, replaces the installed `.app` with rollback protection and reopens PrivacyGate.
- **Source/development, portable builds, or a different distribution channel:** PrivacyGate does not silently replace that installation. Use the official distribution path for that channel.

The first direct release containing the self-updater is 0.5.0. Therefore an older direct build that predates this updater may require one manual installation of 0.5.0; subsequent direct releases can use the built-in update path.

## 9. MCP, connections and automations

The protected Library can be exposed to compatible MCP clients without exposing original documents or reversible mappings. Optional Google Drive and Gmail connections are used to select/materialize supported content before local protection. Organization/cloud account features may use their configured backend, but the core local Protect/OCR/Library/update pipeline does not require Supabase to process a local document.

Use **Block AI access** for Library items that should not be exposed through MCP. Keep private MCP connection URLs confidential.

## 10. Privacy checklist

- Review detections before exporting.
- Review OCR-derived detections carefully; OCR can make recognition mistakes.
- Never send reversible mappings to an AI provider.
- Keep your operating-system account and PrivacyGate Library protected.
- Back up important Library state.
- Confirm company policy before using any external AI service.
- Download updates only from the official PrivacyGate channels.

For data handling details, see [PRIVACY.md](PRIVACY.md). For release authenticity and signing responsibilities, see [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md).
