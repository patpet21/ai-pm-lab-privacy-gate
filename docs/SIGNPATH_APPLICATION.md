# SignPath Foundation application dossier

This page contains the stable information needed for the application form. Values assigned by SignPath after acceptance must not be invented in advance.

## Project information

- Project name: AI PM LAB Privacy Gate
- Suggested project handle: `ai-pm-lab-privacy-gate`
- Repository: https://github.com/patpet21/ai-pm-lab-privacy-gate
- Homepage: https://aipmlab.netlify.app/
- Downloads: https://github.com/patpet21/ai-pm-lab-privacy-gate-downloads/releases
- License: MIT
- Primary platform: Windows 10/11 x64
- Maintainer: Pietro Forestieri (`patpet21`)
- Contact: peter@propertydex.xyz

## Short description

AI PM LAB Privacy Gate is a free, local-first Windows desktop application that detects and protects personally identifiable information before property-management, brokerage, and renovation documents are used with AI. It uses Microsoft Presidio and spaCy locally, supports pasted text and text-based PDFs, provides reviewable detections, and stores protected documents and reversible mappings in a local Windows-user library.

## Why signing is requested

The project distributes a Windows EXE installer built with PyInstaller and Inno Setup. Unsigned builds can trigger unknown-publisher, SmartScreen, and antivirus reputation warnings. Signing will let users verify that official binaries were built from and approved by the public open-source project.

## Current evidence

- Public source repository and MIT license
- Public website with product documentation and browser-only demo
- Released unsigned Windows installer and SHA-256 checksum
- GitHub-hosted Windows tests and clean build workflow
- Public code signing policy, privacy policy, security policy, third-party notices, and release process
- No mandatory cloud service, account, telemetry, advertising, or external database in the desktop application

## Requested signing scope

- Project-owned PyInstaller application executable
- Project-owned Inno Setup Windows installer

The intended final pipeline is two-stage: sign the project application executable produced by GitHub Actions, package that signed executable into the installer, then sign the installer and publish its checksum. The exact SignPath artifact configurations will be generated and reviewed from sample artifacts after the Foundation project and certificate are assigned.

## Values expected only after approval

- SignPath Organization ID
- SignPath project slug confirmed by the Foundation
- Signing policy slug
- Artifact configuration slug(s)
- SignPath API token stored as an encrypted GitHub Actions secret

These values must never be committed to Git.
