#!/usr/bin/env python3
"""Build a deterministic, reviewable Chrome/Edge Store package for PrivacyGate.

The package is not created by zipping the historical extension directory. Instead,
this script starts from manifest.json and resolves only runtime dependencies that
are explicitly referenced by the manifest, local HTML, importScripts(), or
chrome.runtime.getURL().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "browser_extension" / "chromium_freev1_poc"
DEFAULT_OUTPUT = REPO_ROOT / "dist" / "browser-extension"

ALLOWED_TOP_LEVEL_PERMISSIONS = {"storage"}
ALLOWED_HOST_PERMISSIONS = {"http://127.0.0.1/*"}
ALLOWED_SITE_ORIGINS = {
    "https://chatgpt.com/*",
    "https://claude.ai/*",
    "https://gemini.google.com/*",
}

# These historical files must never be part of a Store package. Keeping this
# denylist makes the release build fail even if one is accidentally referenced
# again later.
FORBIDDEN_PACKAGE_FILES = {
    "legacy_restore_blocker.js",
    "restore_guard.js",
    "unified_file_guard.js",
    "unified_file_guard_v2.js",
    "multi_ai_adapter.js",
    "multi_ai_adapter_safe.js",
}

HTML_LOCAL_REF_RE = re.compile(
    r"<(?:script|img|link)\b[^>]*?\b(?:src|href)=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
IMPORT_SCRIPTS_RE = re.compile(r"\bimportScripts\s*\((.*?)\)", re.DOTALL)
QUOTED_STRING_RE = re.compile(r"[\"']([^\"']+)[\"']")
RUNTIME_URL_RE = re.compile(
    r"\b(?:chrome|browser)\.runtime\.getURL\s*\(\s*[\"']([^\"']+)[\"']\s*\)"
)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", re.IGNORECASE)

FORBIDDEN_CODE_PATTERNS = {
    "eval()": re.compile(r"(^|[^A-Za-z0-9_$])eval\s*\("),
    "new Function()": re.compile(r"\bnew\s+Function\s*\("),
    "remote importScripts()": re.compile(
        r"\bimportScripts\s*\([^)]*[\"'](?:https?:|//)", re.IGNORECASE | re.DOTALL
    ),
    "remote dynamic import()": re.compile(
        r"\bimport\s*\(\s*[\"'](?:https?:|//)", re.IGNORECASE
    ),
    "remote script tag": re.compile(
        r"<script\b[^>]*\bsrc=[\"'](?:https?:|//)", re.IGNORECASE
    ),
}

FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def normalize_local_reference(reference: str) -> str | None:
    value = reference.strip()
    if not value or value.startswith(("#", "data:", "javascript:")):
        return None
    if value.startswith(("http://", "https://", "//")):
        fail(f"Remote runtime resource is not allowed in Store package: {value}")
    if "?" in value:
        value = value.split("?", 1)[0]
    if "#" in value:
        value = value.split("#", 1)[0]
    value = value.lstrip("/")
    if not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        fail(f"Unsafe runtime path: {reference}")
    return path.as_posix()


def manifest_roots(manifest: dict) -> set[str]:
    roots: set[str] = {"manifest.json"}

    if manifest.get("manifest_version") != 3:
        fail("Store build requires Manifest V3")

    permissions = set(manifest.get("permissions") or [])
    if not permissions.issubset(ALLOWED_TOP_LEVEL_PERMISSIONS):
        fail(f"Unexpected extension permission(s): {sorted(permissions - ALLOWED_TOP_LEVEL_PERMISSIONS)}")

    host_permissions = set(manifest.get("host_permissions") or [])
    if host_permissions != ALLOWED_HOST_PERMISSIONS:
        fail(f"Unexpected host_permissions: {sorted(host_permissions)}")

    if "update_url" in manifest:
        fail("Store source manifest must not define update_url")

    background = manifest.get("background") or {}
    worker = background.get("service_worker")
    if worker:
        roots.add(normalize_local_reference(worker) or fail("Invalid background service worker"))

    action = manifest.get("action") or {}
    popup = action.get("default_popup")
    if popup:
        roots.add(normalize_local_reference(popup) or fail("Invalid popup path"))

    def add_icon_values(value: object) -> None:
        if isinstance(value, str):
            normalized = normalize_local_reference(value)
            if normalized:
                roots.add(normalized)
        elif isinstance(value, dict):
            for item in value.values():
                add_icon_values(item)

    add_icon_values(manifest.get("icons"))
    add_icon_values(action.get("default_icon"))

    declared_site_matches: set[str] = set()
    for entry in manifest.get("content_scripts") or []:
        matches = set(entry.get("matches") or [])
        declared_site_matches.update(matches)
        if not matches.issubset(ALLOWED_SITE_ORIGINS):
            fail(f"Unexpected content-script match: {sorted(matches - ALLOWED_SITE_ORIGINS)}")
        for key in ("js", "css"):
            for item in entry.get(key) or []:
                normalized = normalize_local_reference(item)
                if normalized:
                    roots.add(normalized)

    for entry in manifest.get("web_accessible_resources") or []:
        matches = set(entry.get("matches") or [])
        if not matches.issubset(ALLOWED_SITE_ORIGINS):
            fail(f"Unexpected web-accessible match: {sorted(matches - ALLOWED_SITE_ORIGINS)}")
        for item in entry.get("resources") or []:
            normalized = normalize_local_reference(item)
            if normalized:
                roots.add(normalized)

    if declared_site_matches != ALLOWED_SITE_ORIGINS:
        missing = sorted(ALLOWED_SITE_ORIGINS - declared_site_matches)
        fail(f"Expected supported AI site match(es) missing from manifest: {missing}")

    return roots


def text_dependencies(relative_path: str, text: str) -> set[str]:
    dependencies: set[str] = set()
    suffix = Path(relative_path).suffix.lower()

    if suffix in {".html", ".htm"}:
        for match in HTML_LOCAL_REF_RE.finditer(text):
            normalized = normalize_local_reference(match.group(1))
            if normalized:
                dependencies.add(normalized)
        for match in CSS_URL_RE.finditer(text):
            normalized = normalize_local_reference(match.group(1))
            if normalized:
                dependencies.add(normalized)

    if suffix == ".js":
        for match in IMPORT_SCRIPTS_RE.finditer(text):
            for quoted in QUOTED_STRING_RE.finditer(match.group(1)):
                normalized = normalize_local_reference(quoted.group(1))
                if normalized:
                    dependencies.add(normalized)
        for match in RUNTIME_URL_RE.finditer(text):
            normalized = normalize_local_reference(match.group(1))
            if normalized:
                dependencies.add(normalized)

    return dependencies


def resolve_runtime_files(source: Path, roots: set[str]) -> set[str]:
    resolved: set[str] = set()
    pending = list(sorted(roots))

    while pending:
        relative = pending.pop(0)
        if relative in resolved:
            continue
        full_path = source / relative
        if not full_path.is_file():
            fail(f"Manifest/runtime dependency does not exist: {relative}")
        resolved.add(relative)

        if full_path.suffix.lower() in {".js", ".html", ".htm", ".css"}:
            text = full_path.read_text(encoding="utf-8")
            for dependency in sorted(text_dependencies(relative, text)):
                if dependency not in resolved:
                    pending.append(dependency)

    forbidden = FORBIDDEN_PACKAGE_FILES.intersection(resolved)
    if forbidden:
        fail(f"Forbidden legacy file(s) resolved into Store package: {sorted(forbidden)}")

    return resolved


def validate_no_remote_code(source: Path, runtime_files: set[str]) -> None:
    for relative in sorted(runtime_files):
        path = source / relative
        if path.suffix.lower() not in {".js", ".html", ".htm"}:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_CODE_PATTERNS.items():
            if pattern.search(text):
                fail(f"Forbidden {label} detected in {relative}")


def run_node_checks(source: Path, runtime_files: set[str]) -> None:
    node = shutil.which("node")
    if not node:
        fail("Node.js is required for Store JavaScript syntax validation")

    for relative in sorted(runtime_files):
        if not relative.endswith(".js"):
            continue
        subprocess.run(
            [node, "--check", str(source / relative)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


def build_zip(source: Path, output_zip: Path, runtime_files: set[str]) -> str:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(
        output_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative in sorted(runtime_files):
            data = (source / relative).read_bytes()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    digest = hashlib.sha256(output_zip.read_bytes()).hexdigest()
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        fail(f"manifest.json not found under {source}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("version") or "").strip()
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
        fail(f"Invalid extension version: {version!r}")

    roots = manifest_roots(manifest)
    runtime_files = resolve_runtime_files(source, roots)
    validate_no_remote_code(source, runtime_files)
    run_node_checks(source, runtime_files)

    canonical = output / f"privacygate-browser-protection-{version}-store.zip"
    digest = build_zip(source, canonical, runtime_files)

    chrome_zip = output / f"privacygate-browser-protection-{version}-chrome.zip"
    edge_zip = output / f"privacygate-browser-protection-{version}-edge.zip"
    shutil.copyfile(canonical, chrome_zip)
    shutil.copyfile(canonical, edge_zip)

    hash_file = output / f"privacygate-browser-protection-{version}.sha256"
    hash_file.write_text(
        "\n".join(
            [
                f"{digest}  {canonical.name}",
                f"{digest}  {chrome_zip.name}",
                f"{digest}  {edge_zip.name}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    inventory = output / f"privacygate-browser-protection-{version}-inventory.txt"
    inventory.write_text("\n".join(sorted(runtime_files)) + "\n", encoding="utf-8")

    print(f"Validated {len(runtime_files)} Store runtime files")
    print(f"Version: {version}")
    print(f"SHA-256: {digest}")
    print(f"Chrome ZIP: {chrome_zip}")
    print(f"Edge ZIP: {edge_zip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"STORE BUILD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
