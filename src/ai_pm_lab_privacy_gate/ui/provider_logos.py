from __future__ import annotations

from pathlib import Path
from typing import Callable
from urllib.parse import quote

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


PROVIDER_DOMAINS: dict[str, str] = {
    "chatgpt": "openai.com",
    "claude": "claude.ai",
    "gemini": "gemini.google.com",
    "google_drive": "drive.google.com",
    "gmail": "gmail.com",
    "google_calendar": "calendar.google.com",
    "google_contacts": "contacts.google.com",
    "onedrive": "onedrive.live.com",
    "sharepoint": "microsoft.com/sharepoint",
    "outlook": "outlook.com",
    "dropbox": "dropbox.com",
    "box": "box.com",
    "notion": "notion.so",
    "airtable": "airtable.com",
    "slack": "slack.com",
    "teams": "microsoft.com/microsoft-teams",
    "zoom": "zoom.us",
    "clickup": "clickup.com",
    "asana": "asana.com",
    "trello": "trello.com",
    "monday": "monday.com",
    "smartsheet": "smartsheet.com",
    "jira": "atlassian.com/software/jira",
    "hubspot": "hubspot.com",
    "pipedrive": "pipedrive.com",
    "zoho_crm": "zoho.com/crm",
    "salesforce": "salesforce.com",
    "docusign": "docusign.com",
    "adobe_sign": "adobe.com/acrobat/business/sign.html",
    "quickbooks": "quickbooks.intuit.com",
    "xero": "xero.com",
    "procore": "procore.com",
    "autodesk_construction": "construction.autodesk.com",
    "buildertrend": "buildertrend.com",
    "appfolio": "appfolio.com",
    "buildium": "buildium.com",
    "yardi": "yardi.com",
    "realpage": "realpage.com",
    "entrata": "entrata.com",
    "doorloop": "doorloop.com",
    "rent_manager": "rentmanager.com",
    "propertyware": "propertyware.com",
    "mri": "mrisoftware.com",
    "follow_up_boss": "followupboss.com",
    "kvcore": "insiderealestate.com/kvcore-platform",
    "boomtown": "boomtownroi.com",
    "brokermint": "brokermint.com",
    "dotloop": "dotloop.com",
    "calendly": "calendly.com",
}


class ProviderLogoLoader(QObject):
    """Fetch provider public brand/site icons asynchronously and cache them locally."""

    def __init__(self, data_dir: str | Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cache_dir = Path(data_dir) / "provider-icons"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manager = QNetworkAccessManager(self)
        self._pending: dict[QNetworkReply, tuple[str, Callable[[QPixmap], None]]] = {}

    def load(self, provider: str, callback: Callable[[QPixmap], None]) -> None:
        domain = PROVIDER_DOMAINS.get(provider)
        if not domain:
            return
        cache = self.cache_dir / f"{provider}.png"
        if cache.exists():
            pixmap = QPixmap(str(cache))
            if not pixmap.isNull():
                callback(pixmap)
                return
        url = QUrl(
            f"https://www.google.com/s2/favicons?domain={quote(domain, safe='/:')}&sz=128"
        )
        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"AI-PM-LAB-PrivacyGate/0.4")
        reply = self.manager.get(request)
        self._pending[reply] = (provider, callback)
        reply.finished.connect(lambda r=reply: self._finished(r))

    def _finished(self, reply: QNetworkReply) -> None:
        pending = self._pending.pop(reply, None)
        if pending is None:
            reply.deleteLater()
            return
        provider, callback = pending
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            data = bytes(reply.readAll())
            image = QImage.fromData(data)
            if image.isNull():
                return
            pixmap = QPixmap.fromImage(image)
            cache = self.cache_dir / f"{provider}.png"
            pixmap.save(str(cache), "PNG")
            callback(pixmap)
        finally:
            reply.deleteLater()
