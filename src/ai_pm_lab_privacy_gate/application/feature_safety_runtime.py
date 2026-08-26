from __future__ import annotations

import shutil
from pathlib import Path

from ai_pm_lab_privacy_gate.application.feature_suite import (
    AdvancedFileService,
    WatchedFolderService,
    WatchFolderConfig,
)
from ai_pm_lab_privacy_gate.domain.plans import Capability, PlanCode, require_capability


def _safe_name(name: str) -> str:
    value = str(name or "").strip()
    if not value or value in {".", ".."} or any(char in value for char in '\\/:*?"<>|'):
        raise ValueError("Enter a normal file/folder name without reserved path characters.")
    return value


def _create_folder(self: AdvancedFileService, plan: PlanCode | str, root, name: str) -> Path:
    require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
    base = self._root(root)
    target = base / _safe_name(name)
    target.mkdir(exist_ok=False)
    return target


def _rename(self: AdvancedFileService, plan: PlanCode | str, root, source, new_name: str) -> Path:
    require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
    base, source_path = self._inside(root, source)
    if source_path == base:
        raise PermissionError("The workspace root itself cannot be renamed from PrivacyGate.")
    target = source_path.with_name(_safe_name(new_name))
    self._inside(base, target)
    if target.exists():
        raise FileExistsError(target.name)
    return source_path.rename(target)


def _move(self: AdvancedFileService, plan: PlanCode | str, root, source, destination_folder) -> Path:
    require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
    base, source_path = self._inside(root, source)
    if source_path == base:
        raise PermissionError("The workspace root itself cannot be moved from PrivacyGate.")
    _, destination = self._inside(base, destination_folder)
    if not destination.is_dir():
        raise NotADirectoryError(str(destination))
    if source_path.is_dir() and (destination == source_path or source_path in destination.parents):
        raise ValueError("A folder cannot be moved into itself or one of its child folders.")
    target = destination / source_path.name
    if target.exists():
        raise FileExistsError(target.name)
    return Path(shutil.move(str(source_path), str(target)))


def _safe_delete(self: AdvancedFileService, plan: PlanCode | str, root, source) -> Path:
    require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
    base, source_path = self._inside(root, source)
    if source_path == base:
        raise PermissionError("The workspace root itself cannot be deleted from PrivacyGate.")
    trash = base / ".PrivacyGate Trash"
    trash.mkdir(exist_ok=True)
    if source_path == trash or trash in source_path.parents:
        raise PermissionError("Items already inside .PrivacyGate Trash are not deleted by Safe Delete.")
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = trash / f"{stamp}_{source_path.name}"
    counter = 2
    while target.exists():
        target = trash / f"{stamp}_{counter}_{source_path.name}"
        counter += 1
    return Path(shutil.move(str(source_path), str(target)))


_original_scan_once = WatchedFolderService.scan_once


def _scan_once(self: WatchedFolderService, plan: PlanCode | str, config: WatchFolderConfig):
    require_capability(plan, Capability.WATCHED_FOLDERS)
    inbox = Path(config.inbox).expanduser().resolve()
    protected = Path(config.protected).expanduser().resolve()
    if inbox == protected:
        raise ValueError("Inbox and Protected output must be different folders.")
    if protected in inbox.parents:
        raise ValueError("Protected output cannot be a parent of the watched Inbox.")
    return _original_scan_once(self, plan, config)


AdvancedFileService.create_folder = _create_folder
AdvancedFileService.rename = _rename
AdvancedFileService.move = _move
AdvancedFileService.safe_delete = _safe_delete
WatchedFolderService.scan_once = _scan_once
