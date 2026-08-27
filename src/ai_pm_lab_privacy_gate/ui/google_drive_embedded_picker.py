from __future__ import annotations

import json
import os
import re
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


_CALLBACK_PATH = "/__privacygate_drive_picker__"
_ALLOWED_MIME_TYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
)


def _configured_picker_api_key(service) -> str:
    """Return the app-level Google Picker browser key.

    The key identifies the PrivacyGate Google Cloud project; it is not a user
    credential. Local development can supply it through the environment, while a
    packaged build may cache the same app configuration in the existing encrypted
    SecretStore.
    """
    configured = os.environ.get("PRIVACY_GATE_GOOGLE_PICKER_API_KEY", "").strip()
    if configured:
        try:
            service.secret_store.set("oauth.google.picker_api_key", configured)
        except Exception:
            pass
        return configured
    try:
        return (service.secret_store.get("oauth.google.picker_api_key") or "").strip()
    except Exception:
        return ""


def _google_app_id(service) -> str:
    configured = os.environ.get("PRIVACY_GATE_GOOGLE_APP_ID", "").strip()
    if configured:
        return configured

    client_id = ""
    try:
        client_id = str(service.google_oauth_client_id() or "").strip()
    except Exception:
        try:
            client_id = (service.secret_store.get("oauth.google.client_id") or "").strip()
        except Exception:
            client_id = ""

    # Google OAuth client IDs normally begin with the Cloud project number. The
    # Picker App ID is that numeric project number.
    match = re.match(r"^(\d+)-", client_id)
    return match.group(1) if match else ""


def _picker_html(access_token: str, developer_key: str, app_id: str) -> str:
    token = json.dumps(access_token)
    key = json.dumps(developer_key)
    app = json.dumps(app_id)
    mime_types = json.dumps(",".join(_ALLOWED_MIME_TYPES))
    callback_path = json.dumps(_CALLBACK_PATH)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PrivacyGate · Google Drive</title>
  <style>
    html, body {{ width:100%; height:100%; margin:0; overflow:hidden; background:#f7fafc; font-family:Segoe UI, Arial, sans-serif; }}
    #loading {{ position:fixed; inset:0; display:grid; place-items:center; color:#526c7d; font-size:14px; }}
    #error {{ display:none; padding:28px; color:#7a2633; white-space:pre-wrap; }}
  </style>
</head>
<body>
  <div id="loading">Loading your Google Drive…</div>
  <div id="error"></div>
  <script>
    const ACCESS_TOKEN = {token};
    const DEVELOPER_KEY = {key};
    const APP_ID = {app};
    const MIME_TYPES = {mime_types};
    const CALLBACK_PATH = {callback_path};

    function finish(action, ids) {{
      const params = new URLSearchParams();
      params.set('action', action);
      if (ids && ids.length) params.set('ids', ids.join(','));
      window.location.href = window.location.origin + CALLBACK_PATH + '?' + params.toString();
    }}

    function showError(message) {{
      document.getElementById('loading').style.display = 'none';
      const target = document.getElementById('error');
      target.style.display = 'block';
      target.textContent = 'Google Drive Picker could not load.\n\n' + message;
    }}

    function pickerCallback(data) {{
      if (!window.google || !google.picker) return;
      if (data.action === google.picker.Action.PICKED) {{
        const docs = data[google.picker.Response.DOCUMENTS] || [];
        const ids = docs.map(doc => doc[google.picker.Document.ID]).filter(Boolean);
        finish('picked', ids);
      }} else if (data.action === google.picker.Action.CANCEL) {{
        finish('cancel', []);
      }}
    }}

    function pickerReady() {{
      try {{
        document.getElementById('loading').style.display = 'none';
        const view = new google.picker.DocsView(google.picker.ViewId.DOCS);
        view.setIncludeFolders(true);
        view.setSelectFolderEnabled(false);
        view.setMode(google.picker.DocsViewMode.LIST);
        view.setMimeTypes(MIME_TYPES);

        const picker = new google.picker.PickerBuilder()
          .addView(view)
          .setOAuthToken(ACCESS_TOKEN)
          .setDeveloperKey(DEVELOPER_KEY)
          .setAppId(APP_ID)
          .setOrigin(window.location.protocol + '//' + window.location.host)
          .setTitle('Choose a file from Google Drive')
          .setCallback(pickerCallback)
          .build();
        picker.setVisible(true);
      }} catch (error) {{
        showError(String(error && error.message ? error.message : error));
      }}
    }}

    function onGoogleApiLoad() {{
      try {{
        gapi.load('picker', {{callback: pickerReady, onerror: () => showError('Google Picker API failed to load.')}});
      }} catch (error) {{
        showError(String(error && error.message ? error.message : error));
      }}
    }}
  </script>
  <script async defer src="https://apis.google.com/js/api.js" onload="onGoogleApiLoad()" onerror="showError('Unable to reach Google Picker API.')"></script>
</body>
</html>"""


def pick_google_drive_file_ids(parent, service) -> tuple[str, ...]:
    """Show Google Picker inside PrivacyGate and return explicitly selected IDs.

    OAuth account connection remains a system-browser operation, as required for
    native apps. Normal file browsing/import after connection stays inside the
    PrivacyGate desktop window.
    """
    try:
        from PySide6.QtCore import Signal
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except Exception as exc:
        raise RuntimeError(
            "The embedded Google Drive Picker requires Qt WebEngine. Reinstall the PrivacyGate Python environment and try again."
        ) from exc

    developer_key = _configured_picker_api_key(service)
    if not developer_key:
        raise RuntimeError(
            "Google Picker is enabled, but PrivacyGate's Google Picker API key is not configured for this build. "
            "Set PRIVACY_GATE_GOOGLE_PICKER_API_KEY to the API key from the PrivacyGate Google Cloud project, then restart PrivacyGate."
        )

    app_id = _google_app_id(service)
    if not app_id:
        raise RuntimeError(
            "PrivacyGate could not determine the Google Cloud project number required by Google Picker. "
            "Set PRIVACY_GATE_GOOGLE_APP_ID to the project's numeric Project number and restart PrivacyGate."
        )

    access_token = service._token("google_drive")
    if not access_token:
        raise RuntimeError("Google Drive is not connected.")

    class PickerPage(QWebEnginePage):
        selectionReceived = Signal(object)

        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):  # noqa: N802
            if is_main_frame and url.path() == _CALLBACK_PATH:
                query = parse_qs(urlparse(url.toString()).query)
                action = (query.get("action") or [""])[0]
                ids_raw = (query.get("ids") or [""])[0]
                ids = tuple(part.strip() for part in ids_raw.split(",") if part.strip())
                self.selectionReceived.emit((action, ids))
                return False
            return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

    dialog = QDialog(parent)
    dialog.setWindowTitle("Google Drive — PrivacyGate")
    dialog.setModal(True)
    dialog.resize(1120, 760)
    dialog.setMinimumSize(820, 560)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    note = QLabel(
        "Google Drive is displayed securely inside PrivacyGate. Select the file you want to import; "
        "PrivacyGate receives access only to files you explicitly choose."
    )
    note.setWordWrap(True)
    note.setStyleSheet("color:#526C7D;font-size:11px;padding:3px 4px;")
    root.addWidget(note)

    web = QWebEngineView(dialog)
    page = PickerPage(web)
    web.setPage(page)
    root.addWidget(web, 1)

    selected: dict[str, tuple[str, ...]] = {"ids": ()}

    def on_selection(payload) -> None:
        action, ids = payload
        if action == "picked" and ids:
            selected["ids"] = tuple(ids)
            dialog.accept()
        else:
            dialog.reject()

    page.selectionReceived.connect(on_selection)

    # A loopback-style origin keeps the embedded page isolated from application
    # files while still giving Google Picker a conventional web origin.
    web.setHtml(
        _picker_html(access_token, developer_key, app_id),
        QUrl("http://127.0.0.1/"),
    )

    dialog.exec()
    return selected["ids"]
