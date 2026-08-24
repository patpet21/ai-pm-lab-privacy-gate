from __future__ import annotations

from dataclasses import dataclass
import platform
import ssl

import httpx
import truststore


MANIFEST_URL = "https://privacygate.propertydex.xyz/release.json"
DEFAULT_WEBSITE_URL = "https://privacygate.propertydex.xyz/"
MICROSOFT_STORE_PRODUCT_ID = "9NMPZCVJLLZ3"
DEFAULT_STORE_URL = f"ms-windows-store://pdp/?ProductId={MICROSOFT_STORE_PRODUCT_ID}"


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    download_url: str
    sha256: str
    notes_url: str
    website_url: str = DEFAULT_WEBSITE_URL
    store_url: str = DEFAULT_STORE_URL


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.strip().lstrip("v").split(".") if part.isdigit())


class UpdateService:
    def __init__(self, manifest_url: str = MANIFEST_URL) -> None:
        self.manifest_url = manifest_url

    def check(self, current_version: str) -> UpdateInfo | None:
        # The tiny public release manifest is the notification source. We do
        # not continuously query Microsoft Store. Store is contacted only when
        # the customer chooses the Store update path.
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with httpx.Client(timeout=8, follow_redirects=True, verify=context) as client:
            response = client.get(self.manifest_url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        latest = str(payload["version"])
        if _version_tuple(latest) <= _version_tuple(current_version):
            return None
        system = platform.system().lower()
        machine = platform.machine().lower()
        if system == "windows":
            package = payload["downloads"]["windows"]
        elif machine in {"arm64", "aarch64"}:
            package = payload["downloads"]["macos_apple_silicon"]
        else:
            package = payload["downloads"]["macos_intel"]
        return UpdateInfo(
            version=latest,
            download_url=str(package["url"]),
            sha256=str(package.get("sha256", "")),
            notes_url=str(payload.get("notes_url", package["url"])),
            website_url=str(payload.get("website_url", DEFAULT_WEBSITE_URL)),
            store_url=str(payload.get("store_url", DEFAULT_STORE_URL)),
        )
