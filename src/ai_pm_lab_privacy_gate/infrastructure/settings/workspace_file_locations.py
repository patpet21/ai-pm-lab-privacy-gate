from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


STANDARD_WORKSPACE_FOLDERS = ("Inbox", "Protected", "Restored", "Exports")


@dataclass(slots=True)
class WorkspaceFileRoute:
    root: str
    custom: bool = False
    updated_at: str = ""


class WorkspaceFileLocationStore:
    """Local-only routing metadata for Personal and company working folders.

    This store never contains document content. It records only where the user
    wants each PrivacyGate workspace to keep normal working files on this PC.
    The encrypted PrivacyGate Library remains separate and keeps its existing
    storage behavior.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "workspace_file_locations.json"

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "-", str(value or "Workspace")).strip(" .-")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned[:80] or "Workspace"

    def default_root(self, workspace_key: str, workspace_name: str) -> Path:
        documents = Path.home() / "Documents"
        base = documents if documents.exists() else Path.home()
        name = "Personal" if workspace_key == "personal" else self._safe_name(workspace_name)
        return base / "PrivacyGate Workspaces" / name

    def _load_payload(self) -> dict[str, dict[str, object]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        if not isinstance(payload, dict):
            return {}
        routes = payload.get("routes", payload)
        return routes if isinstance(routes, dict) else {}

    def _save_payload(self, routes: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "routes": routes}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def route_for(self, workspace_key: str, workspace_name: str) -> WorkspaceFileRoute:
        routes = self._load_payload()
        raw = routes.get(workspace_key)
        if isinstance(raw, dict) and str(raw.get("root") or "").strip():
            return WorkspaceFileRoute(
                root=str(raw.get("root")),
                custom=bool(raw.get("custom", False)),
                updated_at=str(raw.get("updated_at") or ""),
            )
        return WorkspaceFileRoute(root=str(self.default_root(workspace_key, workspace_name)))

    def set_route(self, workspace_key: str, root: Path, *, custom: bool = True) -> WorkspaceFileRoute:
        route = WorkspaceFileRoute(
            root=str(Path(root).expanduser().resolve()),
            custom=custom,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        routes = self._load_payload()
        routes[workspace_key] = asdict(route)
        self._save_payload(routes)
        return route

    def reset_route(self, workspace_key: str, workspace_name: str) -> WorkspaceFileRoute:
        routes = self._load_payload()
        routes.pop(workspace_key, None)
        self._save_payload(routes)
        return WorkspaceFileRoute(root=str(self.default_root(workspace_key, workspace_name)))

    @staticmethod
    def ensure_structure(root: Path) -> tuple[Path, ...]:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        for name in STANDARD_WORKSPACE_FOLDERS:
            path = root / name
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        return tuple(created)

    @staticmethod
    def snapshot(root: Path) -> tuple[int, int]:
        root = Path(root)
        if not root.exists():
            return 0, 0
        files = 0
        total = 0
        try:
            for path in root.rglob("*"):
                try:
                    if path.is_file():
                        files += 1
                        total += path.stat().st_size
                except OSError:
                    continue
        except OSError:
            return files, total
        return files, total
