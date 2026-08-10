# Release process

## Purpose

This process keeps the public source commit, Windows binary, checksum, and future SignPath signature tied together.

## Version preparation

1. Update the version in `pyproject.toml`, `src/ai_pm_lab_privacy_gate/__init__.py`, and `packaging/windows/installer.iss`.
2. Update customer-facing release notes and download links.
3. Use synthetic data only in tests and examples.
4. Open a pull request and require the Windows test/build workflows to pass.

## Build and verification

1. Build on a GitHub-hosted `windows-latest` runner.
2. Run unit, integration, privacy, and UI smoke tests.
3. Confirm `python312.dll` and the app-local Visual C++ runtime files are present.
4. Produce the Inno Setup installer and SHA-256 manifest.
5. Before SignPath approval, publish the artifact only as explicitly unsigned.
6. After SignPath approval, submit only the GitHub workflow artifact for signing.
7. Verify the returned Authenticode signature and timestamp before release publication.

## Publication

1. Create a `vX.Y.Z` tag from the reviewed `main` commit.
2. Publish the signed installer, checksum, build information, and release notes.
3. Update the website download URL.
4. Install over the previous version and verify the library under `%LOCALAPPDATA%` remains intact.
5. Launch the installed executable on Windows and confirm the application window opens.

## Emergency response

If a signing credential, workflow, repository, or release is suspected to be compromised, stop signing, remove affected assets, preserve audit evidence, notify SignPath, and publish a clear security advisory when appropriate.
