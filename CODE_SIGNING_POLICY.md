# Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

Status: the SignPath Foundation application is pending. AI PM LAB Privacy Gate 0.4.0 and earlier releases are unsigned. This document does not claim that an unsigned release has already received a SignPath signature.

## Project identity

- Project: AI PM LAB Privacy Gate
- Source repository: https://github.com/patpet21/ai-pm-lab-privacy-gate
- Download releases: https://github.com/patpet21/ai-pm-lab-privacy-gate-downloads/releases
- Website and browser demo: https://aipmlab.netlify.app/
- License: MIT

## Signed artifacts

After Foundation approval, signing will be limited to Windows release artifacts built from this repository:

- `AI PM LAB Privacy Gate.exe`, produced by PyInstaller from the public source;
- `AI_PM_LAB_Privacy_Gate_Setup_<version>.exe`, produced by Inno Setup from the corresponding application build.

Third-party executables and DLLs must not be re-signed as if they were authored by this project. The SignPath artifact configuration will sign project-owned files and preserve or verify upstream signatures where applicable.

## Team roles

- Author and committer: [Pietro Forestieri (`@patpet21`)](https://github.com/patpet21)
- Reviewer: [Pietro Forestieri (`@patpet21`)](https://github.com/patpet21)
- Signing approver: [Pietro Forestieri (`@patpet21`)](https://github.com/patpet21)

The repository is currently maintained by one person. Changes from external contributors require review by the maintainer before merge. The maintainer owns and controls the project source, build scripts, repository, and release process. If the team grows, this section and the repository permissions will be updated before new members receive signing roles.

All maintainers and signing-role holders must use multi-factor authentication for GitHub and SignPath.

## Release controls

1. Development changes are proposed through a branch and pull request.
2. Tests must pass on GitHub-hosted Windows runners before merge.
3. Official release builds are created from the public repository by GitHub Actions.
4. A release version and its Git tag must match the application and installer version.
5. After SignPath approval, only GitHub-hosted workflow artifacts from the approved repository and release branch/tag may be submitted for signing.
6. Signing credentials are stored as encrypted GitHub Actions secrets and are never committed to the repository.
7. Signed artifacts are verified with Windows Authenticode tools before publication.
8. SHA-256 checksums and release notes are published with every installer.

Local developer builds, pull-request previews, test builds, manually substituted files, and artifacts built from unreviewed external branches are not eligible for release signing.

## Privacy declaration

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

The desktop detection, PDF processing, encrypted library, mapping, and restoration workflow runs locally. Optional actions that the user explicitly requests—such as opening an AI provider, submitting the website contact form, downloading an update, or using a future cloud integration—may contact third-party systems and are governed by the relevant provider's privacy policy. See [PRIVACY.md](PRIVACY.md).

## Incident response

Suspected key misuse, malicious releases, compromised workflows, or signature anomalies must be reported privately to `peter@propertydex.xyz`. Affected releases will be removed, signing will be paused, and SignPath will be notified when appropriate. Security reports must not include real customer documents or reversible mappings.
