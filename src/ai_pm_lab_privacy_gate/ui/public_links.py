from __future__ import annotations

# Public PrivacyGate distribution links.
#
# Gmail is live. Edge and Chrome are intentionally left empty until their
# public store URLs are confirmed; the UI is already prepared and will enable
# those buttons as soon as the links are added here.
GMAIL_MARKETPLACE_URL = "https://gsuite.google.com/marketplace/app/foo/817932149819"
EDGE_EXTENSION_URL = ""
CHROME_EXTENSION_URL = ""

PRIVACYGATE_WEBSITE_URL = "https://privacygate.propertydex.xyz"


def chrome_family_extension_url() -> str:
    """Chrome Web Store is also the install source used by Brave."""
    return CHROME_EXTENSION_URL
