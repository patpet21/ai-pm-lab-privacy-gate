from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ai_pm_lab_privacy_gate.application.feature_suite import FullEncryptedBackupService
from ai_pm_lab_privacy_gate.domain.plans import Capability, PlanCode, require_capability
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector

_MAGIC = b"PGBK2"
_SALT_SIZE = 16
_NONCE_SIZE = 12


def _key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 10:
        raise ValueError("Use a backup passphrase of at least 10 characters.")
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))


def _encrypt(raw: bytes, passphrase: str) -> bytes:
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key = _key(passphrase, salt)
    return _MAGIC + salt + nonce + AESGCM(key).encrypt(nonce, raw, _MAGIC)


def _decrypt(raw: bytes, passphrase: str) -> bytes:
    if not raw.startswith(_MAGIC) or len(raw) <= len(_MAGIC) + _SALT_SIZE + _NONCE_SIZE:
        raise ValueError("This is not a supported portable PrivacyGate backup.")
    offset = len(_MAGIC)
    salt = raw[offset : offset + _SALT_SIZE]
    offset += _SALT_SIZE
    nonce = raw[offset : offset + _NONCE_SIZE]
    offset += _NONCE_SIZE
    try:
        return AESGCM(_key(passphrase, salt)).decrypt(nonce, raw[offset:], _MAGIC)
    except InvalidTag as exc:
        raise ValueError("Incorrect backup passphrase or damaged backup file.") from exc


def _portable_snapshot(service: FullEncryptedBackupService, destination: Path) -> None:
    with service.library._connect() as source, sqlite3.connect(destination) as output:
        source.backup(output)
    protector = service.library._protector
    with sqlite3.connect(destination) as connection:
        rows = connection.execute("SELECT rowid, protected_value FROM mappings").fetchall()
        for rowid, protected_value in rows:
            original = protector.unprotect(protected_value)
            connection.execute(
                "UPDATE mappings SET protected_value = ? WHERE rowid = ?",
                (original.encode("utf-8"), rowid),
            )
        connection.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES('portable_mapping_format', 'utf8-inside-encrypted-container')"
        )


def _reprotect_snapshot(service: FullEncryptedBackupService, snapshot: Path) -> None:
    protector = LocalProtector()
    with sqlite3.connect(snapshot) as connection:
        marker = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'portable_mapping_format'"
        ).fetchone()
        if marker is None:
            raise ValueError("Portable mapping metadata is missing from this backup.")
        rows = connection.execute("SELECT rowid, protected_value FROM mappings").fetchall()
        for rowid, value in rows:
            raw = bytes(value) if not isinstance(value, bytes) else value
            original = raw.decode("utf-8")
            connection.execute(
                "UPDATE mappings SET protected_value = ? WHERE rowid = ?",
                (protector.protect(original), rowid),
            )
        connection.execute("DELETE FROM app_meta WHERE key = 'portable_mapping_format'")


def _create(self: FullEncryptedBackupService, plan: PlanCode | str, destination: str | Path, passphrase: str) -> Path:
    require_capability(plan, Capability.ENCRYPTED_BACKUP)
    target = Path(destination)
    if target.suffix.lower() != ".pgbak":
        target = target.with_suffix(".pgbak")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="privacygate_portable_backup_") as tmp:
        snapshot = Path(tmp) / "library.db"
        _portable_snapshot(self, snapshot)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format": "privacygate-portable-backup-v2",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "encryption": "AES-256-GCM + scrypt passphrase",
                        "connector_credentials": "excluded",
                    },
                    indent=2,
                ),
            )
            bundle.write(snapshot, "library.db")
            for name in self.CONFIG_FILES:
                path = self.data_dir / name
                if path.exists() and path.is_file():
                    bundle.write(path, f"config/{name}")
        encrypted = _encrypt(archive.getvalue(), passphrase)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(encrypted)
        os.replace(temporary, target)
    return target


def _restore(self: FullEncryptedBackupService, plan: PlanCode | str, source: str | Path, passphrase: str) -> Path:
    require_capability(plan, Capability.ENCRYPTED_BACKUP)
    raw = _decrypt(Path(source).read_bytes(), passphrase)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as bundle:
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        if manifest.get("format") != "privacygate-portable-backup-v2":
            raise ValueError("Unsupported PrivacyGate portable backup format.")
        with tempfile.TemporaryDirectory(prefix="privacygate_portable_restore_") as tmp:
            snapshot = Path(tmp) / "library.db"
            snapshot.write_bytes(bundle.read("library.db"))
            _reprotect_snapshot(self, snapshot)
            self.library._backup_database_file("pre_portable_restore")
            temporary_db = self.library.db_path.with_suffix(".restore.tmp")
            shutil.copy2(snapshot, temporary_db)
            os.replace(temporary_db, self.library.db_path)
        for name in self.CONFIG_FILES:
            member = f"config/{name}"
            if member not in bundle.namelist():
                continue
            destination = self.data_dir / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_bytes(bundle.read(member))
            os.replace(temporary, destination)
    self.library._initialize()
    self.library._synchronize_protected_library()
    return self.library.db_path


# Runtime upgrade of the feature service keeps the main feature module compact and
# preserves one public class used by the UI. Both methods still enforce the backend
# capability gate before touching any local data.
FullEncryptedBackupService.create = _create
FullEncryptedBackupService.restore = _restore
