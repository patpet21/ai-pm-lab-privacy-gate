from __future__ import annotations

"""Compatibility bridge from the current Gmail UI into generic ProtectPackage.

This is intentionally a shadow bridge first: the proven Gmail component runtime
still owns scan/protect/preview/export behavior, while every selected Gmail
package is now also represented by the UI-independent ProtectPackage contract.
The next migration checkpoint can switch analysis/protection to
ProtectSessionService without changing Gmail browsing or the visible UI.
"""

from types import MethodType

from ai_pm_lab_privacy_gate.application.gmail_protect_sources import (
    build_gmail_protect_package_from_manifest,
)


def _package_label(page, metadata: dict[str, object]) -> str:
    return str(
        metadata.get("item_title")
        or getattr(page, "_external_source_name", "")
        or "Gmail message"
    ).strip()


def apply_gmail_protect_package_bridge(main_window) -> None:
    page = getattr(main_window, "protection_page", None)
    if page is None or getattr(page, "_gmail_protect_package_bridge", False):
        return
    page._gmail_protect_package_bridge = True
    page._gmail_protect_package = None

    def build_current_package(self):
        manifest = tuple(getattr(self, "_gmail_component_manifest", ()) or ())
        if not manifest:
            self._gmail_protect_package = None
            return None
        metadata = dict(getattr(self, "_external_source_metadata", {}) or {})
        if str(metadata.get("provider") or "").strip().lower() != "gmail":
            self._gmail_protect_package = None
            return None
        package = build_gmail_protect_package_from_manifest(
            manifest,
            source_metadata=metadata,
            package_label=_package_label(self, metadata),
        )
        self._gmail_protect_package = package
        return package

    page._gmail_build_protect_package = MethodType(build_current_package, page)

    # gmail_component_session already owns the Scan signal. Add a side-effect-only
    # connection instead of replacing that proven binding: each scan captures the
    # same selected components as a generic package, but the old runtime continues
    # to produce the user-visible result until the next migration checkpoint.
    scan_button = getattr(page, "scan_button", None)
    if scan_button is not None:
        scan_button.clicked.connect(
            lambda _checked=False: page._gmail_build_protect_package()
        )

    # Clear must invalidate the shadow package as well. Again, keep the existing
    # clear implementation authoritative and only clear our new compatibility
    # state after the user's action.
    clear_button = getattr(page, "clear_button", None)
    if clear_button is not None:
        clear_button.clicked.connect(
            lambda _checked=False: setattr(page, "_gmail_protect_package", None)
        )

    # Useful for tests/debugging and for a package imported before this late bridge
    # is applied. No network or protection work is triggered here.
    page._gmail_build_protect_package()
