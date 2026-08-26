from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

import httpx

from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import ProtectionResult
from ai_pm_lab_privacy_gate.domain.plans import Capability, PlanCode, normalize_plan, require_capability
from ai_pm_lab_privacy_gate.domain.profiles import (
    BUSINESS_CONFIDENTIAL_ENTITIES,
    COMMON_US_ENTITIES,
    FINANCIAL_SENSITIVE_ENTITIES,
    OPERATIONAL_IDENTIFIER_ENTITIES,
    REAL_ESTATE_SENSITIVE_ENTITIES,
    PrivacyProfile,
    list_profiles,
)
from ai_pm_lab_privacy_gate.infrastructure.security.local_protector import LocalProtector
from ai_pm_lab_privacy_gate.infrastructure.storage.library_repository import LibraryRepository

SUPPORTED_BATCH_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
SUPPORTED_OCR_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    source: str
    output: str
    status: str
    findings_count: int = 0
    error: str = ""


@dataclass(frozen=True, slots=True)
class WatchFolderConfig:
    watch_id: str
    inbox: str
    protected: str
    workspace_key: str = "personal"
    profile_key: str = "general_business"
    replacement_mode: str = "reversible"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class WorkspaceRule:
    provider: str
    account_id: str
    workspace_key: str
    allowed_destinations: tuple[str, ...] = ()
    default_folder: str = ""


@dataclass(frozen=True, slots=True)
class PreflightReport:
    target: str
    workspace_key: str
    residual_findings: int
    policy_allowed: bool
    ready: bool
    message: str


class AdvancedProfileCatalog:
    """Industry profiles built from recognizers PrivacyGate already ships locally."""

    @staticmethod
    def all() -> tuple[PrivacyProfile, ...]:
        existing = list(list_profiles())
        extras = (
            PrivacyProfile(
                key="general_business",
                name="General Business",
                description="Identity, contact, financial, contract, customer and operational business data.",
                entities=COMMON_US_ENTITIES
                + FINANCIAL_SENSITIVE_ENTITIES
                + BUSINESS_CONFIDENTIAL_ENTITIES
                + OPERATIONAL_IDENTIFIER_ENTITIES
                + ("DATE_TIME",),
            ),
            PrivacyProfile(
                key="construction",
                name="Construction",
                description="Owner, contractor, vendor, project, permit, insurance and financial identifiers.",
                entities=COMMON_US_ENTITIES
                + FINANCIAL_SENSITIVE_ENTITIES
                + BUSINESS_CONFIDENTIAL_ENTITIES
                + OPERATIONAL_IDENTIFIER_ENTITIES
                + REAL_ESTATE_SENSITIVE_ENTITIES
                + ("DATE_TIME",),
            ),
            PrivacyProfile(
                key="legal",
                name="Legal",
                description="General legal privacy profile for people, cases, contracts, addresses and financial identifiers.",
                entities=COMMON_US_ENTITIES
                + FINANCIAL_SENSITIVE_ENTITIES
                + BUSINESS_CONFIDENTIAL_ENTITIES
                + OPERATIONAL_IDENTIFIER_ENTITIES
                + ("DATE_TIME",),
            ),
            PrivacyProfile(
                key="healthcare_general",
                name="Healthcare — General Privacy",
                description="General identity/contact privacy for healthcare documents; not a substitute for a specialized clinical/HIPAA recognizer pack.",
                entities=COMMON_US_ENTITIES
                + FINANCIAL_SENSITIVE_ENTITIES
                + BUSINESS_CONFIDENTIAL_ENTITIES
                + ("DATE_TIME",),
            ),
        )
        by_key = {profile.key: profile for profile in existing}
        for profile in extras:
            by_key.setdefault(profile.key, profile)
        return tuple(by_key.values())

    @classmethod
    def get(cls, key: str) -> PrivacyProfile:
        for profile in cls.all():
            if profile.key == key:
                return profile
        raise KeyError(f"Unknown privacy profile: {key}")


class LocalActivityStore:
    """Metadata-only local activity history. Never stores document text or titles."""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "activity_center.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS activity (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    workspace_key TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    findings_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _hash_source(source: str | Path | None) -> str:
        if not source:
            return ""
        return hashlib.sha256(str(source).encode("utf-8", errors="ignore")).hexdigest()[:12]

    def record(
        self,
        event_type: str,
        *,
        workspace_key: str = "personal",
        source: str | Path | None = None,
        source_kind: str = "",
        findings_count: int = 0,
        status: str = "ok",
        detail: str = "",
    ) -> None:
        safe_detail = str(detail or "")[:240].replace("\n", " ")
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO activity VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    datetime.now(timezone.utc).isoformat(),
                    str(event_type),
                    str(workspace_key or "personal"),
                    str(source_kind or ""),
                    self._hash_source(source),
                    max(0, int(findings_count)),
                    str(status or "ok"),
                    safe_detail,
                ),
            )

    def recent(self, limit: int = 100) -> tuple[dict[str, object], ...]:
        safe_limit = max(1, min(int(limit), 500))
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM activity ORDER BY created_at DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def clear(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM activity")


class BatchProtectionService:
    def __init__(
        self,
        privacy: PrivacyGateService,
        library: LibraryRepository,
        activity: LocalActivityStore,
    ) -> None:
        self.privacy = privacy
        self.library = library
        self.activity = activity

    def run(
        self,
        plan: PlanCode | str,
        paths: Iterable[str | Path],
        output_dir: str | Path,
        *,
        profile: PrivacyProfile,
        replacement_mode: str = "reversible",
        workspace_key: str = "personal",
        progress: Callable[[int, int, BatchItemResult], None] | None = None,
    ) -> tuple[BatchItemResult, ...]:
        require_capability(plan, Capability.BATCH_PROTECTION)
        sources = [Path(path) for path in paths]
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        results: list[BatchItemResult] = []
        total = len(sources)
        for index, source in enumerate(sources, start=1):
            try:
                if source.suffix.lower() not in SUPPORTED_BATCH_EXTENSIONS:
                    raise ValueError("Batch Protect supports PDF, DOCX and XLSX files.")
                document = self.privacy.document_from_file(source)
                findings = self.privacy.analyze(document, profile)
                protected = self.privacy.protect(document, findings, replacement_mode)
                target = destination / f"{source.stem}_protected{source.suffix.lower()}"
                counter = 2
                while target.exists():
                    target = destination / f"{source.stem}_protected_{counter}{source.suffix.lower()}"
                    counter += 1
                if source.suffix.lower() == ".pdf":
                    self.privacy.save_protected_pdf(protected, target, document)
                else:
                    self.privacy.save_protected_office(protected, target, document)
                self.library.save(
                    title=f"Protected {source.suffix.lower().lstrip('.').upper()} document",
                    source_kind=document.source_kind,
                    source_name=f"local-{source.suffix.lower().lstrip('.')}",
                    profile_key=profile.key,
                    result=protected,
                    labels=("batch", workspace_key),
                )
                item = BatchItemResult(
                    source=str(source),
                    output=str(target),
                    status="protected",
                    findings_count=len(protected.applied_findings),
                )
                self.activity.record(
                    "batch_protected",
                    workspace_key=workspace_key,
                    source=source,
                    source_kind=source.suffix.lower().lstrip("."),
                    findings_count=len(protected.applied_findings),
                    detail="Protected and added to local Library",
                )
            except Exception as exc:  # one failed document must not stop the queue
                item = BatchItemResult(
                    source=str(source),
                    output="",
                    status="failed",
                    error=str(exc),
                )
                self.activity.record(
                    "batch_failed",
                    workspace_key=workspace_key,
                    source=source,
                    source_kind=source.suffix.lower().lstrip("."),
                    status="failed",
                    detail=type(exc).__name__,
                )
            results.append(item)
            if progress is not None:
                progress(index, total, item)
        return tuple(results)


class WatchFolderStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "watched_folders.json"

    def list(self) -> tuple[WatchFolderConfig, ...]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return ()
        rows = payload.get("watches", []) if isinstance(payload, dict) else []
        configs: list[WatchFolderConfig] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            try:
                configs.append(
                    WatchFolderConfig(
                        watch_id=str(row.get("watch_id") or uuid.uuid4().hex),
                        inbox=str(row.get("inbox") or ""),
                        protected=str(row.get("protected") or ""),
                        workspace_key=str(row.get("workspace_key") or "personal"),
                        profile_key=str(row.get("profile_key") or "general_business"),
                        replacement_mode=str(row.get("replacement_mode") or "reversible"),
                        enabled=bool(row.get("enabled", True)),
                    )
                )
            except (TypeError, ValueError):
                continue
        return tuple(configs)

    def save(self, configs: Iterable[WatchFolderConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"version": 1, "watches": [asdict(item) for item in configs]}, indent=2),
            encoding="utf-8",
        )

    def add(self, config: WatchFolderConfig) -> None:
        configs = [item for item in self.list() if item.watch_id != config.watch_id]
        configs.append(config)
        self.save(configs)

    def remove(self, watch_id: str) -> None:
        self.save(item for item in self.list() if item.watch_id != watch_id)


class WatchedFolderService:
    def __init__(
        self,
        data_dir: str | Path,
        batch: BatchProtectionService,
        activity: LocalActivityStore,
    ) -> None:
        self.state_path = Path(data_dir) / "watched_folders_state.json"
        self.batch = batch
        self.activity = activity

    def _load_state(self) -> dict[str, str]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}

    def _save_state(self, state: Mapping[str, str]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(dict(state), indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _signature(path: Path) -> str:
        stat = path.stat()
        return f"{stat.st_size}:{stat.st_mtime_ns}"

    def scan_once(self, plan: PlanCode | str, config: WatchFolderConfig) -> tuple[BatchItemResult, ...]:
        require_capability(plan, Capability.WATCHED_FOLDERS)
        if not config.enabled:
            return ()
        inbox = Path(config.inbox)
        output = Path(config.protected)
        inbox.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        state = self._load_state()
        pending: list[Path] = []
        signatures: dict[str, str] = {}
        for path in sorted(inbox.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_BATCH_EXTENSIONS:
                continue
            try:
                signature = self._signature(path)
            except OSError:
                continue
            key = f"{config.watch_id}:{path.resolve()}"
            signatures[key] = signature
            if state.get(key) != signature:
                pending.append(path)
        if not pending:
            return ()
        profile = AdvancedProfileCatalog.get(config.profile_key)
        results = self.batch.run(
            plan,
            pending,
            output,
            profile=profile,
            replacement_mode=config.replacement_mode,
            workspace_key=config.workspace_key,
        )
        for source, result in zip(pending, results):
            if result.status == "protected":
                key = f"{config.watch_id}:{source.resolve()}"
                state[key] = signatures[key]
        self._save_state(state)
        return results


class LocalOcrService:
    """Offline OCR using local Tesseract; PDFs also use local pdftoppm when available."""

    def __init__(self, activity: LocalActivityStore) -> None:
        self.activity = activity

    @staticmethod
    def availability() -> tuple[bool, str]:
        tesseract = shutil.which("tesseract")
        if not tesseract:
            return False, "Tesseract OCR is not installed or not on PATH."
        return True, tesseract

    def extract(self, plan: PlanCode | str, source: str | Path, *, workspace_key: str = "personal") -> str:
        require_capability(plan, Capability.LOCAL_OCR)
        path = Path(source)
        available, detail = self.availability()
        if not available:
            raise RuntimeError(detail)
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_OCR_IMAGES:
            text = self._ocr_image(path)
        elif suffix == ".pdf":
            text = self._ocr_pdf(path)
        else:
            raise ValueError("Local OCR supports PDF, PNG, JPG/JPEG, TIFF and BMP.")
        self.activity.record(
            "local_ocr",
            workspace_key=workspace_key,
            source=path,
            source_kind=suffix.lstrip("."),
            detail=f"OCR completed locally ({len(text)} characters)",
        )
        return text

    @staticmethod
    def _ocr_image(path: Path) -> str:
        result = subprocess.run(
            [shutil.which("tesseract") or "tesseract", str(path), "stdout", "--psm", "3"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Tesseract OCR failed.")
        return result.stdout.strip()

    def _ocr_pdf(self, path: Path) -> str:
        converter = shutil.which("pdftoppm")
        if not converter:
            raise RuntimeError("PDF OCR requires the local pdftoppm utility in addition to Tesseract.")
        with tempfile.TemporaryDirectory(prefix="privacygate_ocr_") as tmp:
            prefix = Path(tmp) / "page"
            converted = subprocess.run(
                [converter, "-png", "-r", "200", str(path), str(prefix)],
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
            if converted.returncode != 0:
                raise RuntimeError(converted.stderr.strip() or "Could not render PDF pages for OCR.")
            pages = sorted(Path(tmp).glob("page-*.png"))
            if not pages:
                raise RuntimeError("No PDF pages were rendered for OCR.")
            return "\n\n".join(self._ocr_image(page) for page in pages).strip()


class AdvancedFileService:
    """Workspace-scoped file operations with path-boundary checks and reversible delete."""

    @staticmethod
    def _root(root: str | Path) -> Path:
        value = Path(root).expanduser().resolve()
        value.mkdir(parents=True, exist_ok=True)
        return value

    @classmethod
    def _inside(cls, root: str | Path, target: str | Path) -> tuple[Path, Path]:
        base = cls._root(root)
        path = Path(target).expanduser().resolve()
        if path != base and base not in path.parents:
            raise PermissionError("This action is outside the selected PrivacyGate workspace folder.")
        return base, path

    def create_folder(self, plan: PlanCode | str, root: str | Path, name: str) -> Path:
        require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
        if not name.strip() or any(char in name for char in '\\/:*?"<>|'):
            raise ValueError("Enter a normal folder name without reserved path characters.")
        base = self._root(root)
        target = base / name.strip()
        target.mkdir(exist_ok=False)
        return target

    def rename(self, plan: PlanCode | str, root: str | Path, source: str | Path, new_name: str) -> Path:
        require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
        base, source_path = self._inside(root, source)
        if not new_name.strip() or any(char in new_name for char in '\\/:*?"<>|'):
            raise ValueError("Enter a normal file/folder name without reserved path characters.")
        target = source_path.with_name(new_name.strip())
        self._inside(base, target)
        if target.exists():
            raise FileExistsError(target.name)
        return source_path.rename(target)

    def move(self, plan: PlanCode | str, root: str | Path, source: str | Path, destination_folder: str | Path) -> Path:
        require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
        base, source_path = self._inside(root, source)
        _, destination = self._inside(base, destination_folder)
        if not destination.is_dir():
            raise NotADirectoryError(str(destination))
        target = destination / source_path.name
        if target.exists():
            raise FileExistsError(target.name)
        return Path(shutil.move(str(source_path), str(target)))

    def safe_delete(self, plan: PlanCode | str, root: str | Path, source: str | Path) -> Path:
        require_capability(plan, Capability.ADVANCED_FILE_ROUTING)
        base, source_path = self._inside(root, source)
        trash = base / ".PrivacyGate Trash"
        trash.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = trash / f"{stamp}_{source_path.name}"
        counter = 2
        while target.exists():
            target = trash / f"{stamp}_{counter}_{source_path.name}"
            counter += 1
        return Path(shutil.move(str(source_path), str(target)))


class WorkspaceRuleStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "workspace_rules.json"

    def list(self) -> tuple[WorkspaceRule, ...]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return ()
        rows = payload.get("rules", []) if isinstance(payload, dict) else []
        result: list[WorkspaceRule] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            result.append(
                WorkspaceRule(
                    provider=str(row.get("provider") or "").strip().lower(),
                    account_id=str(row.get("account_id") or "").strip(),
                    workspace_key=str(row.get("workspace_key") or "personal").strip(),
                    allowed_destinations=tuple(str(x) for x in row.get("allowed_destinations", []) if str(x)),
                    default_folder=str(row.get("default_folder") or ""),
                )
            )
        return tuple(result)

    def save(self, plan: PlanCode | str, rules: Iterable[WorkspaceRule]) -> None:
        require_capability(plan, Capability.WORKSPACE_RULES)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"version": 1, "rules": [asdict(rule) for rule in rules]}, indent=2),
            encoding="utf-8",
        )

    def allows(self, workspace_key: str, destination: str) -> bool:
        relevant = [rule for rule in self.list() if rule.workspace_key == workspace_key]
        if not relevant:
            return True
        normalized = destination.strip().lower()
        allowed = {item.strip().lower() for rule in relevant for item in rule.allowed_destinations}
        return not allowed or normalized in allowed


class PrivacyPreflightService:
    def __init__(self, privacy: PrivacyGateService, rules: WorkspaceRuleStore) -> None:
        self.privacy = privacy
        self.rules = rules

    def evaluate(
        self,
        plan: PlanCode | str,
        result: ProtectionResult,
        profile: PrivacyProfile,
        *,
        target: str,
        workspace_key: str,
    ) -> PreflightReport:
        require_capability(plan, Capability.PRIVACY_PREFLIGHT)
        residual = self.privacy.verify_protected(result, profile)
        allowed = self.rules.allows(workspace_key, target)
        ready = not residual and allowed
        if residual:
            message = f"Blocked: {len(residual)} sensitive item(s) remain in the protected output."
        elif not allowed:
            message = f"Blocked: {target} is not allowed for this workspace rule set."
        else:
            message = "Ready: protected output passed the local privacy preflight."
        return PreflightReport(target, workspace_key, len(residual), allowed, ready, message)


class AutomationActionService:
    def __init__(self, files: AdvancedFileService, activity: LocalActivityStore) -> None:
        self.files = files
        self.activity = activity

    def trigger_n8n(
        self,
        plan: PlanCode | str,
        url: str,
        payload: Mapping[str, object] | None = None,
        *,
        workspace_key: str = "personal",
    ) -> dict[str, object]:
        require_capability(plan, Capability.ADVANCED_AUTOMATION)
        target = str(url or "").strip()
        if not target.startswith(("http://", "https://")):
            raise ValueError("Enter a valid http:// or https:// webhook URL.")
        response = httpx.post(target, json=dict(payload or {}), timeout=15)
        response.raise_for_status()
        self.activity.record(
            "automation_webhook",
            workspace_key=workspace_key,
            source_kind="n8n",
            detail=f"Webhook completed with HTTP {response.status_code}",
        )
        try:
            parsed = response.json()
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except ValueError:
            return {"status_code": response.status_code, "text": response.text[:1000]}


class FullEncryptedBackupService:
    FORMAT = "privacygate-full-device-backup-v1"
    CONFIG_FILES = (
        "preferences.json",
        "workspace_file_locations.json",
        "watched_folders.json",
        "watched_folders_state.json",
        "workspace_rules.json",
    )

    def __init__(self, library: LibraryRepository) -> None:
        self.library = library
        self.data_dir = Path(library.data_dir)
        self.protector = LocalProtector()

    def create(self, plan: PlanCode | str, destination: str | Path) -> Path:
        require_capability(plan, Capability.ENCRYPTED_BACKUP)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="privacygate_full_backup_") as tmp:
            inner = Path(tmp) / "library.pgbackup"
            self.library.create_backup(inner)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr(
                    "manifest.json",
                    json.dumps(
                        {
                            "format": self.FORMAT,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "protection": "OS current-user encryption",
                        },
                        indent=2,
                    ),
                )
                bundle.write(inner, "library.pgbackup")
                for name in self.CONFIG_FILES:
                    path = self.data_dir / name
                    if path.exists() and path.is_file():
                        bundle.write(path, f"config/{name}")
            protected = self.protector.protect_bytes(archive.getvalue())
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(protected)
            temporary.replace(target)
        return target

    def restore(self, plan: PlanCode | str, source: str | Path) -> Path:
        require_capability(plan, Capability.ENCRYPTED_BACKUP)
        raw = self.protector.unprotect_bytes(Path(source).read_bytes())
        with zipfile.ZipFile(io.BytesIO(raw), "r") as bundle:
            manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != self.FORMAT:
                raise ValueError("This is not a supported PrivacyGate full backup.")
            with tempfile.TemporaryDirectory(prefix="privacygate_full_restore_") as tmp:
                inner = Path(tmp) / "library.pgbackup"
                inner.write_bytes(bundle.read("library.pgbackup"))
                restored = self.library.restore_backup(inner)
            for name in self.CONFIG_FILES:
                member = f"config/{name}"
                if member not in bundle.namelist():
                    continue
                destination = self.data_dir / name
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                temporary.write_bytes(bundle.read(member))
                temporary.replace(destination)
        return restored


def active_plan_for(main_window) -> PlanCode:
    """Resolve entitlement from the active Personal/company workspace when possible."""
    team_page = getattr(main_window, "team_page", None)
    store = getattr(team_page, "_privacygate_workspace_store", None)
    if store is not None:
        try:
            context = store.load()
            descriptor = context.workspaces.get(context.active_key)
            if descriptor is not None:
                return normalize_plan(descriptor.plan)
        except Exception:
            pass
    state = getattr(team_page, "state", None)
    return normalize_plan(getattr(state, "plan", PlanCode.BASIC))
