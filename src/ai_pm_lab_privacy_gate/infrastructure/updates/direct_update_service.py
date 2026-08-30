from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shlex
import ssl
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse

import httpx
import truststore

from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository
from ai_pm_lab_privacy_gate.infrastructure.updates.install_channel import (
    APP_NAME,
    InstallChannel,
    current_install_channel,
    direct_update_supported,
    mac_app_bundle_path,
    windows_direct_executable,
)


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAC_BUNDLE_ID = "xyz.propertydex.privacygate"


@dataclass(frozen=True, slots=True)
class DirectUpdateResult:
    status: str
    message: str
    artifact_path: Path | None = None
    backup_path: Path | None = None


class DirectUpdateError(RuntimeError):
    pass


class DirectUpdateService:
    """Download, verify and hand off a same-channel desktop update.

    Microsoft Store/MSIX is intentionally excluded. Store builds continue to use
    StoreContext so Microsoft remains the sole updater for that channel.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else None

    def prepare_and_launch(self, release) -> DirectUpdateResult:
        channel = current_install_channel()
        if not direct_update_supported(channel):
            return DirectUpdateResult(
                "not_direct",
                "This PrivacyGate installation is not managed by the direct updater.",
            )

        try:
            artifact = self._download_verified(release, channel)
            backup = self._create_library_backup()
            if channel == InstallChannel.WINDOWS_DIRECT:
                self._launch_windows_helper(artifact)
            elif channel == InstallChannel.MAC_DIRECT:
                self._launch_macos_helper(artifact)
            else:  # defensive; direct_update_supported already restricts this
                raise DirectUpdateError("Unsupported direct update channel.")
        except DirectUpdateError as exc:
            return DirectUpdateResult("error", str(exc))
        except Exception as exc:
            return DirectUpdateResult("error", f"Unable to start the update: {exc}")

        return DirectUpdateResult(
            "started",
            f"PrivacyGate {release.version} was downloaded and verified. The updater will finish after PrivacyGate closes.",
            artifact_path=artifact,
            backup_path=backup,
        )

    def _create_library_backup(self) -> Path | None:
        """Create a recoverable encrypted DB snapshot before replacing binaries."""
        try:
            repository = LibraryRepository(self.data_dir)
            return repository.create_backup()
        except Exception as exc:
            raise DirectUpdateError(
                "PrivacyGate could not create the pre-update Library backup, so the update was stopped. "
                f"Details: {exc}"
            ) from exc

    @staticmethod
    def _validated_download_name(release, channel: InstallChannel) -> str:
        parsed = urlparse(str(release.download_url))
        if parsed.scheme.lower() != "https":
            raise DirectUpdateError("Updates must be downloaded over HTTPS.")
        name = Path(unquote(parsed.path)).name
        expected_suffix = ".exe" if channel == InstallChannel.WINDOWS_DIRECT else ".dmg"
        if not name.lower().endswith(expected_suffix):
            raise DirectUpdateError(
                f"The release manifest does not point to the expected {expected_suffix} package."
            )
        return name

    @staticmethod
    def _validate_expected_sha256(value: str) -> str:
        expected = str(value or "").strip().lower()
        if not _SHA256_RE.fullmatch(expected):
            raise DirectUpdateError(
                "The release manifest is missing a valid SHA-256 checksum; automatic installation was blocked."
            )
        return expected

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _download_verified(self, release, channel: InstallChannel) -> Path:
        filename = self._validated_download_name(release, channel)
        expected = self._validate_expected_sha256(release.sha256)
        root = Path(tempfile.gettempdir()) / "AI-PM-LAB-PrivacyGate-Updates" / str(release.version)
        root.mkdir(parents=True, exist_ok=True)
        destination = root / filename
        temporary = destination.with_suffix(destination.suffix + ".part")

        if destination.exists() and self._sha256(destination) == expected:
            return destination

        temporary.unlink(missing_ok=True)
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        try:
            with httpx.Client(timeout=60, follow_redirects=True, verify=context) as client:
                with client.stream(
                    "GET",
                    str(release.download_url),
                    headers={"Accept": "application/octet-stream"},
                ) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            if chunk:
                                handle.write(chunk)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise DirectUpdateError(f"The update download failed: {exc}") from exc

        actual = self._sha256(temporary)
        if actual != expected:
            temporary.unlink(missing_ok=True)
            raise DirectUpdateError(
                "The downloaded update failed SHA-256 verification and was deleted."
            )
        os.replace(temporary, destination)
        return destination

    @staticmethod
    def _powershell_literal(value: str | Path) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _launch_windows_helper(self, installer: Path) -> None:
        executable = windows_direct_executable()
        if executable is None:
            raise DirectUpdateError(
                "The installed Windows Direct executable could not be located. Use the PrivacyGate website installer instead."
            )

        helper = installer.parent / "privacygate-update-windows.ps1"
        installer_literal = self._powershell_literal(installer)
        executable_literal = self._powershell_literal(executable)
        helper.write_text(
            "\n".join(
                (
                    "$ErrorActionPreference = 'Stop'",
                    f"$privacyGatePid = {os.getpid()}",
                    "Wait-Process -Id $privacyGatePid -ErrorAction SilentlyContinue",
                    f"$installer = {installer_literal}",
                    "$arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/CLOSEAPPLICATIONS')",
                    "$process = Start-Process -FilePath $installer -ArgumentList $arguments -PassThru -Wait",
                    f"$privacyGate = {executable_literal}",
                    "if ($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $privacyGate)) {",
                    "  Start-Process -FilePath $privacyGate",
                    "}",
                    "exit $process.ExitCode",
                )
            ),
            encoding="utf-8",
        )

        creationflags = 0
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creationflags,
            )
        except OSError as exc:
            raise DirectUpdateError(f"Windows could not launch the update helper: {exc}") from exc

    def _launch_macos_helper(self, dmg: Path) -> None:
        bundle = mac_app_bundle_path()
        if bundle is None:
            raise DirectUpdateError("The running macOS app bundle could not be located.")
        if str(bundle).startswith("/Volumes/"):
            raise DirectUpdateError(
                "PrivacyGate is running from the DMG. Move it to Applications, reopen it, and retry the update."
            )

        update_root = dmg.parent
        mount = update_root / "mounted-dmg"
        helper = update_root / "privacygate-update-macos.sh"
        replace_script = update_root / "privacygate-replace-macos.sh"
        source_bundle = mount / f"{APP_NAME}.app"
        backup_bundle = bundle.with_name(bundle.name + ".privacygate-update-backup")

        replace_script.write_text(
            "\n".join(
                (
                    "#!/bin/sh",
                    "set -eu",
                    f"SOURCE={shlex.quote(str(source_bundle))}",
                    f"TARGET={shlex.quote(str(bundle))}",
                    f"BACKUP={shlex.quote(str(backup_bundle))}",
                    'rm -rf "$BACKUP"',
                    'if [ -e "$TARGET" ]; then mv "$TARGET" "$BACKUP"; fi',
                    'if /usr/bin/ditto "$SOURCE" "$TARGET"; then',
                    '  rm -rf "$BACKUP"',
                    "else",
                    '  rm -rf "$TARGET"',
                    '  if [ -e "$BACKUP" ]; then mv "$BACKUP" "$TARGET"; fi',
                    "  exit 1",
                    "fi",
                )
            ),
            encoding="utf-8",
        )
        replace_script.chmod(0o700)

        helper.write_text(
            "\n".join(
                (
                    "#!/bin/sh",
                    "set -eu",
                    f"PID={os.getpid()}",
                    f"DMG={shlex.quote(str(dmg))}",
                    f"MOUNT={shlex.quote(str(mount))}",
                    f"SOURCE={shlex.quote(str(source_bundle))}",
                    f"TARGET={shlex.quote(str(bundle))}",
                    f"REPLACE={shlex.quote(str(replace_script))}",
                    'while kill -0 "$PID" 2>/dev/null; do sleep 1; done',
                    'rm -rf "$MOUNT"',
                    'mkdir -p "$MOUNT"',
                    'cleanup() { /usr/bin/hdiutil detach "$MOUNT" -quiet >/dev/null 2>&1 || true; rm -rf "$MOUNT"; }',
                    "trap cleanup EXIT",
                    '/usr/bin/hdiutil attach -nobrowse -readonly -mountpoint "$MOUNT" "$DMG" >/dev/null',
                    'test -d "$SOURCE"',
                    f'IDENTIFIER=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$SOURCE/Contents/Info.plist")',
                    f'if [ "$IDENTIFIER" != "{_MAC_BUNDLE_ID}" ]; then exit 12; fi',
                    '/usr/bin/codesign --verify --deep --strict "$SOURCE"',
                    'TARGET_PARENT=$(dirname "$TARGET")',
                    'if [ -w "$TARGET_PARENT" ]; then',
                    '  /bin/sh "$REPLACE"',
                    "else",
                    '  /usr/bin/osascript -e \'do shell script "/bin/sh " & quoted form of POSIX path of "' + str(replace_script).replace('"', '\\"') + '" with administrator privileges\'',
                    "fi",
                    '/usr/bin/open "$TARGET"',
                )
            ),
            encoding="utf-8",
        )
        helper.chmod(0o700)

        try:
            subprocess.Popen(
                ["/bin/sh", str(helper)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise DirectUpdateError(f"macOS could not launch the update helper: {exc}") from exc
