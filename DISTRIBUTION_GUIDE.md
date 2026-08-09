# Distribution and updates

## Where the downloadable installer lives

The official installer belongs in the separate public downloads repository, not inside the private production repository. For version `0.3.0` the expected asset is:

```text
AI_PM_LAB_Privacy_Gate_Setup_0.3.0.exe
```

The funnel uses this stable pattern:

```text
https://github.com/patpet21/ai-pm-lab-privacy-gate-downloads/releases/download/v0.3.0/AI_PM_LAB_Privacy_Gate_Setup_0.3.0.exe
```

The production repository remains private. The public downloads repository contains only customer-facing documentation, checksums, release notes, and GitHub Release assets. Do not upload the 132 MB installer directly into Git history.

If AVG CyberCapture blocks the Inno Setup temporary file under `%LOCALAPPDATA%\Temp`, run the installer with `TEMP` and `TMP` temporarily pointed to the approved/excluded project or download folder. Do not disable antivirus protection globally.

## Release procedure

1. Update the application and installer version.
2. Run all tests and produce a clean PyInstaller build outside OneDrive.
3. Launch the unpacked EXE and confirm a responsive Windows window.
4. Compile the Inno Setup installer.
5. Install it using the standard customer path and launch the installed EXE.
6. Verify the local library remains unchanged across the update.
7. Publish the source commit and create a matching GitHub tag and Release.
8. Attach the installer and publish its SHA-256 in the release notes.
9. Update the funnel's download link to the new version.

## Netlify

Connect Netlify to the GitHub repository. The root `netlify.toml` already sets `web-demo` as the publish directory, so no build command is required. Every push to `main` can then redeploy the funnel automatically.

## Future automatic updater

The current app preserves customer data during manual updates but does not download updates automatically. A future updater can read a signed release manifest, show release notes, download the installer, verify SHA-256 or a digital signature, and launch the approved update. Code signing should be added before automatic delivery to customers.
