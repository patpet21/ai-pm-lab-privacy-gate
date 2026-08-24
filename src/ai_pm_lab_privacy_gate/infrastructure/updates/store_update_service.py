from __future__ import annotations

import asyncio
import ctypes
from dataclasses import dataclass
import os
import platform


@dataclass(frozen=True, slots=True)
class StoreUpdateResult:
    status: str
    message: str = ""


def is_store_packaged_install() -> bool:
    """Return True when the current Windows process has package identity.

    Direct EXE/dev runs do not have package identity, while the Microsoft Store
    MSIX build does. The Store APIs themselves still remain the final authority.
    """
    if platform.system().lower() != "windows":
        return False
    if os.getenv("PRIVACY_GATE_SIMULATE_STORE") == "1":
        return True
    try:
        length = ctypes.c_uint32(0)
        result = ctypes.windll.kernel32.GetCurrentPackageFullName(
            ctypes.byref(length), None
        )
        # ERROR_INSUFFICIENT_BUFFER means a package identity exists and Windows
        # is telling us how large the package-name buffer must be.
        return result == 122
    except Exception:
        return False


def _state_name(result) -> str:
    state = getattr(result, "overall_state", None)
    if state is None:
        return "unknown"
    name = getattr(state, "name", None)
    if name:
        return str(name).lower()
    return str(state).split(".")[-1].lower()


class StoreUpdateService:
    """Microsoft Store update bridge for the packaged Windows build.

    The public release.json remains the lightweight release trigger. We only
    call StoreContext after that manifest reports a newer PrivacyGate release.
    """

    def try_silent_update(self) -> StoreUpdateResult:
        simulated = os.getenv("PRIVACY_GATE_SIMULATE_STORE_RESULT", "").strip().lower()
        if simulated:
            mapping = {
                "installed": StoreUpdateResult("installed", "The Store update was installed."),
                "action_required": StoreUpdateResult("action_required", "Windows requires user confirmation."),
                "preparing": StoreUpdateResult("preparing", "Microsoft Store is still preparing this update."),
                "error": StoreUpdateResult("error", "The Microsoft Store update check failed."),
            }
            if simulated in mapping:
                return mapping[simulated]
        if not is_store_packaged_install():
            return StoreUpdateResult("not_store", "This is not a Microsoft Store installation.")
        try:
            return asyncio.run(self._try_silent_update_async())
        except Exception as exc:
            return StoreUpdateResult("error", str(exc))

    async def _try_silent_update_async(self) -> StoreUpdateResult:
        from winrt.windows.services.store import StoreContext

        context = StoreContext.get_default()
        updates = await context.get_app_and_optional_store_package_updates_async()
        updates = list(updates)
        if not updates:
            return StoreUpdateResult(
                "preparing",
                "Microsoft Store is still preparing this update. PrivacyGate will try again later.",
            )

        result = await context.try_silent_download_and_install_store_package_updates_async(updates)
        state = _state_name(result)
        if state == "completed":
            return StoreUpdateResult(
                "installed",
                "The Microsoft Store update finished installing. Restart PrivacyGate to use the new version.",
            )
        # Any non-completed silent result is treated as a request for explicit
        # user action. The user can then start the official Store install UI.
        return StoreUpdateResult(
            "action_required",
            "Windows could not complete the update silently. Choose Install update to continue through the official Microsoft Store update flow.",
        )

    def install_with_store_ui(self) -> StoreUpdateResult:
        simulated = os.getenv("PRIVACY_GATE_SIMULATE_STORE_RESULT", "").strip().lower()
        if simulated:
            if simulated == "preparing":
                return StoreUpdateResult("preparing", "Microsoft Store is still preparing this update.")
            if simulated == "error":
                return StoreUpdateResult("error", "The Microsoft Store update could not be started.")
            return StoreUpdateResult("installed", "The Store update was installed.")
        if not is_store_packaged_install():
            return StoreUpdateResult("not_store", "This is not a Microsoft Store installation.")
        try:
            return asyncio.run(self._install_with_store_ui_async())
        except Exception as exc:
            return StoreUpdateResult("error", str(exc))

    async def _install_with_store_ui_async(self) -> StoreUpdateResult:
        from winrt.windows.services.store import StoreContext

        context = StoreContext.get_default()
        updates = list(await context.get_app_and_optional_store_package_updates_async())
        if not updates:
            return StoreUpdateResult(
                "preparing",
                "Microsoft Store is still preparing this update. PrivacyGate will try again later.",
            )
        result = await context.request_download_and_install_store_package_updates_async(updates)
        state = _state_name(result)
        if state == "completed":
            return StoreUpdateResult(
                "installed",
                "The Microsoft Store update finished installing. Restart PrivacyGate to use the new version.",
            )
        if state == "canceled":
            return StoreUpdateResult("canceled", "The Microsoft Store update was canceled.")
        return StoreUpdateResult(
            "error",
            "Microsoft Store could not complete the update. You can retry later or open the Store page.",
        )
