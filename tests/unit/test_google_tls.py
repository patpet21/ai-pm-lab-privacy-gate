from __future__ import annotations

import ssl

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_tls import google_ssl_context


def test_google_tls_uses_a_verified_system_context() -> None:
    context = google_ssl_context()
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert google_ssl_context() is context
