from __future__ import annotations

import ssl
from functools import lru_cache

import truststore


@lru_cache(maxsize=1)
def google_ssl_context() -> ssl.SSLContext:
    """Use the operating-system CA store without weakening TLS verification.

    Windows security products can install a local inspection CA that certifi does
    not know about. truststore keeps normal certificate and hostname validation
    while honoring the same trusted roots as the user's browser.
    """
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
