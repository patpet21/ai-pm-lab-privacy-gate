from __future__ import annotations

# Public PrivacyGate distribution links.
# Keep these centralized so Store/extension URLs can be updated without touching
# the navigation and connection flows that consume them.
GMAIL_MARKETPLACE_URL = (
    "https://workspace.google.com/marketplace/app/privacygate/817932149819?flow_type=2"
)
EDGE_EXTENSION_URL = (
    "https://microsoftedge.microsoft.com/addons/detail/"
    "privacygate-browser-prote/lbdkbiflhmlalbcblmglmccmmajnhfbd"
)
MICROSOFT_STORE_URL = (
    "https://apps.microsoft.com/detail/9nmpzcvjllz3?hl=it-IT&gl=US&ocid=pdpshare"
)

# Chrome is intentionally empty until the public Chrome Web Store listing is live.
# Brave uses the Chrome Web Store listing as well.
CHROME_EXTENSION_URL = ""

PRIVACYGATE_WEBSITE_URL = "https://privacygate.propertydex.xyz"


def chrome_family_extension_url() -> str:
    """Chrome Web Store is also the install source used by Brave."""
    return CHROME_EXTENSION_URL
