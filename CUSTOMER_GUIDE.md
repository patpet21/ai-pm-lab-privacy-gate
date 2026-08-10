# AI PM LAB Privacy Gate — Customer Guide

## 1. Install the app

Download the latest Windows installer from the repository's Releases page and open it. Privacy Gate installs for the current Windows user and does not require Python.

Version 0.3.1 is currently unsigned while the SignPath Foundation application is pending. Windows or antivirus software may therefore show an unknown-publisher or reputation warning. Download only from the official AI PM LAB repository and verify the SHA-256 published in the release notes. Future signed releases will be identified explicitly; never assume a file is signed based only on its filename.

## 2. Protect pasted text

1. Open **Protect**.
2. Select Property Management, Realtor / Brokerage, or Projects & Renovations.
3. Keep **Reversible placeholders** when you want to restore the identities later.
4. Paste the text and select **Scan for sensitive data**.
5. Review the categories and every detected item. Deselect anything that should remain visible or use **Add sensitive item** when something was missed.
6. Use **Save + Copy** to store the protected version locally and copy it for an AI chat.

## 3. Protect a PDF

Open the **PDF file** tab, choose a PDF containing selectable text, and scan it. Image-only or scanned PDFs require OCR and are not supported in this version. The protected PDF is a clean text-based copy rather than a pixel-perfect reproduction of the original layout.

## 4. Use the protected text with AI

The free workflow does not require an API key:

1. Select **Open with AI** and then **Copy & Open ChatGPT**, or copy the protected text manually.
2. Paste it into ChatGPT or another approved AI tool.
3. Keep placeholders such as `[[PG_PERSON_001]]` unchanged in the AI response.

Privacy Gate never claims that the AI service itself is local. Only the detection, library, mapping, and restoration functions run locally.

## 5. Restore the result

1. Copy the AI response.
2. Open **Restore**.
3. Select the matching protected document from the local library.
4. Paste the AI response and select **Restore locally**.
5. Review the result before copying or downloading it.

## 6. Local library and updates

The protected library is stored under `%LOCALAPPDATA%\AI PM LAB Privacy Gate\Data`. Reinstalling or updating the program does not overwrite this folder. Reversible mappings are encrypted for the current Windows user using Windows DPAPI, so they should be restored and backed up only under that Windows account.

## 7. Automation options

- **Local Automation / n8n:** future localhost API and local workflows without a mandatory Privacy Gate cloud.
- **Cloud / MCP / Email:** optional advanced integrations using customer-owned accounts or a managed service.
- **Manual workflow:** available now and free; no API key is required.

For workflow design, onboarding, or automation consulting, contact [peter@propertydex.xyz](mailto:peter@propertydex.xyz).

For data handling details, see the project [privacy policy](PRIVACY.md). For release authenticity and signing responsibilities, see the [code signing policy](CODE_SIGNING_POLICY.md).

## 8. Privacy checklist

- Review detections before exporting.
- Do not assume automated detection is perfect.
- Keep the original document and the local library protected with Windows account security.
- Never send reversible mappings to an AI provider.
- Confirm company policy before using any external AI service.
