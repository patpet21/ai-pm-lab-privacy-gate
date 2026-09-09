#!/usr/bin/env python3
"""Security regression checks for the built PrivacyGate browser Store package."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

FORBIDDEN_BASENAMES = {
    "legacy_restore_blocker.js",
    "restore_guard.js",
    "unified_file_guard.js",
    "unified_file_guard_v2.js",
    "multi_ai_adapter.js",
    "multi_ai_adapter_safe.js",
}

# A wildcard targetOrigin weakens postMessage trust boundaries. Store runtime
# messaging must use an explicit provider or extension origin.
WILDCARD_POSTMESSAGE_RE = re.compile(
    r"\.postMessage\s*\(.*?,\s*[\"']\*[\"']\s*\)",
    re.DOTALL,
)

# These are signatures of the retired legacy restore model, where clear values
# were written back into the AI provider's DOM.
FORBIDDEN_RESTORE_DOM_PATTERNS = {
    "restored text assigned to text node": re.compile(
        r"\bnode\.nodeValue\s*=\s*restored(?:Text|_text)\b", re.IGNORECASE
    ),
    "restored text assigned through textContent": re.compile(
        r"\.textContent\s*=\s*restored(?:Text|_text)\b", re.IGNORECASE
    ),
    "restored text assigned through innerText": re.compile(
        r"\.innerText\s*=\s*restored(?:Text|_text)\b", re.IGNORECASE
    ),
    "restored text assigned through innerHTML": re.compile(
        r"\.innerHTML\s*=\s*restored(?:Text|_text)\b", re.IGNORECASE
    ),
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_zip(zip_path: Path) -> dict[str, bytes]:
    if not zip_path.is_file():
        fail(f"Store ZIP not found: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    return files


def decode_js(files: dict[str, bytes]) -> dict[str, str]:
    output: dict[str, str] = {}
    for name, payload in files.items():
        if name.endswith((".js", ".html")):
            output[name] = payload.decode("utf-8")
    return output


def require(text: str, snippet: str, filename: str) -> None:
    if snippet not in text:
        fail(f"Required security guard missing from {filename}: {snippet}")


def verify(files: dict[str, bytes]) -> None:
    basenames = {Path(name).name for name in files}
    forbidden = sorted(FORBIDDEN_BASENAMES & basenames)
    if forbidden:
        fail(f"Forbidden legacy file(s) found in Store ZIP: {forbidden}")

    text_files = decode_js(files)

    for filename, text in text_files.items():
        if WILDCARD_POSTMESSAGE_RE.search(text):
            fail(f"Wildcard postMessage targetOrigin found in Store runtime: {filename}")
        for label, pattern in FORBIDDEN_RESTORE_DOM_PATTERNS.items():
            if pattern.search(text):
                fail(f"Forbidden legacy restore behavior ({label}) found in {filename}")

    file_review = text_files.get("file_review_overlay.js")
    if file_review is None:
        fail("file_review_overlay.js missing from Store ZIP")
    require(file_review, "event.source !== parent", "file_review_overlay.js")
    require(file_review, "ALLOWED_PARENT_ORIGINS.has(event.origin)", "file_review_overlay.js")
    require(file_review, "trustedParentOrigin = event.origin", "file_review_overlay.js")
    for origin in ("https://chatgpt.com", "https://claude.ai", "https://gemini.google.com"):
        require(file_review, origin, "file_review_overlay.js")

    network_main = text_files.get("network_gate_main.js")
    network_bridge = text_files.get("network_gate_bridge.js")
    if network_main is None or network_bridge is None:
        fail("ChatGPT network gate runtime is incomplete")
    for filename, text in (
        ("network_gate_main.js", network_main),
        ("network_gate_bridge.js", network_bridge),
    ):
        require(text, 'const NETWORK_GATE_ORIGIN = "https://chatgpt.com";', filename)
        require(text, "event.origin !== NETWORK_GATE_ORIGIN", filename)

    for filename in ("unified_file_guard_v3.js", "csv_file_guard.js"):
        text = text_files.get(filename)
        if text is None:
            fail(f"{filename} missing from Store ZIP")
        require(text, 'const REVIEW_FRAME_ORIGIN = new URL(chrome.runtime.getURL("/")).origin;', filename)
        require(text, "event.origin !== REVIEW_FRAME_ORIGIN", filename)

    content = text_files.get("content.js", "")
    for retired_symbol in (
        "restoreTextNode",
        "scanAssistantResponses",
        "scheduleRestoreScan",
        "restoringNodes",
    ):
        if retired_symbol in content:
            fail(f"Retired legacy restore symbol still present in content.js: {retired_symbol}")

    assistant_restore = text_files.get("assistant_restore_guard.js")
    if assistant_restore is None:
        fail("assistant_restore_guard.js missing from Store ZIP")
    require(
        assistant_restore,
        "never write restoredText into ChatGPT's DOM",
        "assistant_restore_guard.js",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path, help="Built Chrome/Edge Store ZIP")
    args = parser.parse_args()

    verify(read_zip(args.zip.resolve()))
    print(f"Store security regression checks passed: {args.zip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        print(f"STORE SECURITY CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
