from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_import import (
    materialize_google_drive_item,
)
from ai_pm_lab_privacy_gate.infrastructure.connectors.google_drive_picker_access import (
    configured_google_app_id,
    configured_picker_api_key,
    drive_items_from_ids,
    selected_file_access_token,
)
from ai_pm_lab_privacy_gate.ui.connected_apps_browse_polish import (
    _active_account_details,
    _friendly_connection_error,
)
from ai_pm_lab_privacy_gate.ui.iconography import icon


_CALLBACK_PATH = "/__privacygate_drive_picker__"
_ALLOWED_MIME_TYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "image/png",
    "image/jpeg",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
)


def _picker_html(access_token: str, developer_key: str, app_id: str) -> str:
    """Build only the host page; Google owns and renders the Picker itself."""
    token = json.dumps(access_token)
    key = json.dumps(developer_key)
    app = json.dumps(app_id)
    mime_types = json.dumps(",".join(_ALLOWED_MIME_TYPES))
    callback_path = json.dumps(_CALLBACK_PATH)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Google Drive — import to Protect</title>
  <style>
    html,body,#picker{{width:100%;height:100%;margin:0;overflow:hidden;background:#fff}}
    body{{font-family:Arial,sans-serif}}
    #loading,#error{{position:fixed;inset:0;display:grid;place-items:center;color:#526c7d;background:#fff;font-size:14px}}
    #error{{display:none;color:#8a3340;padding:32px;white-space:pre-wrap;text-align:center;line-height:1.5}}
    iframe{{width:100%;height:100%;border:0;display:block}}
  </style>
</head>
<body>
  <div id="picker"></div><div id="loading">Loading the official Google Picker…</div><div id="error"></div>
  <script>
    const ACCESS_TOKEN={token}, DEVELOPER_KEY={key}, APP_ID={app};
    const MIME_TYPES={mime_types}, CALLBACK_PATH={callback_path};
    let started=false, builder=null;
    function fail(message){{
      document.getElementById('loading').style.display='none';
      const error=document.getElementById('error'); error.style.display='grid'; error.textContent=message;
    }}
    function finish(action,ids){{
      const query=new URLSearchParams({{action:action,ids:(ids||[]).join(',')}});
      window.location.href=window.location.origin+CALLBACK_PATH+'?'+query.toString();
    }}
    function callback(data){{
      const action=data[google.picker.Response.ACTION]||data.action;
      if(action===google.picker.Action.PICKED){{
        const docs=data[google.picker.Response.DOCUMENTS]||data.docs||[];
        finish('picked',docs.map(doc=>doc[google.picker.Document.ID]||doc.id).filter(Boolean));
      }}else if(action===google.picker.Action.CANCEL){{ finish('cancel',[]); }}
    }}
    function ready(){{
      try{{
        const view=new google.picker.DocsView(google.picker.ViewId.DOCS)
          .setIncludeFolders(true).setSelectFolderEnabled(false).setMode(google.picker.DocsViewMode.LIST);
        builder=new google.picker.PickerBuilder()
          .addView(view)
          .setOAuthToken(ACCESS_TOKEN)
          .setDeveloperKey(DEVELOPER_KEY)
          .setAppId(APP_ID)
          .setOrigin(window.location.origin)
          .setSelectableMimeTypes(MIME_TYPES)
          .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
          .setMaxItems(20)
          .setSize(1051,650)
          .setTitle('Choose files from Google Drive')
          .setCallback(callback);
        const uri=builder.toUri();
        const frame=document.createElement('iframe');
        frame.title='Official Google Drive Picker';
        frame.referrerPolicy='strict-origin-when-cross-origin';
        frame.src=(typeof uri==='string')?uri:uri.toString();
        frame.addEventListener('load',()=>document.getElementById('loading').style.display='none');
        document.getElementById('picker').appendChild(frame); started=true;
      }}catch(error){{ fail('Google Picker could not load: '+String(error?.message||error)); }}
    }}
    function apiLoaded(){{ gapi.load('picker',{{callback:ready,onerror:()=>fail('Google Picker API failed to load.')}}); }}
    setTimeout(()=>{{if(!started)fail('Google Picker did not finish loading. Check the API key and authorized origin.');}},15000);
  </script>
  <script async defer src="https://apis.google.com/js/api.js" onload="apiLoaded()" onerror="fail('Unable to reach Google Picker API.')"></script>
</body>
</html>"""


def _start_loopback_page(html_text: str):
    payload = html_text.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Pragma", "no-cache")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; script-src 'unsafe-inline' https://apis.google.com https://www.gstatic.com; "
                    "frame-src https:; connect-src https:; img-src https: data:; "
                    "style-src 'unsafe-inline';",
                )
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if path == _CALLBACK_PATH:
                body = b"Selection received."
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _choose_ids(parent, access_token: str, developer_key: str, app_id: str) -> tuple[str, ...]:
    try:
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except Exception as exc:
        raise RuntimeError("This build does not include Qt WebEngine, required for the in-app Google Picker.") from exc

    class PickerPage(QWebEnginePage):
        selection_received = Signal(object)

        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):  # noqa: N802
            if is_main_frame and url.path() == _CALLBACK_PATH:
                query = parse_qs(urlparse(url.toString()).query)
                action = (query.get("action") or [""])[0]
                ids = tuple(value for value in (query.get("ids") or [""])[0].split(",") if value)
                self.selection_received.emit((action, ids))
                return False
            return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

        def javaScriptConsoleMessage(self, level, message, line_number, source_id):  # noqa: N802
            safe = str(message).replace(access_token, "[token]")
            print(f"[PrivacyGate Google Picker] {safe} ({source_id}:{line_number})")

    server, thread, origin = _start_loopback_page(_picker_html(access_token, developer_key, app_id))
    dialog = QDialog(parent)
    dialog.setObjectName("EmbeddedGoogleDrivePicker")
    dialog.setWindowTitle("Google Drive — import to Protect")
    dialog.setModal(True)
    dialog.resize(1120, 780)
    dialog.setMinimumSize(860, 600)
    dialog.setStyleSheet(
        "QDialog#EmbeddedGoogleDrivePicker{background:#F8FAFC;color:#062B4F;}"
        "QFrame#PickerHeader,QFrame#PickerFooter{background:#FFFFFF;border:1px solid #D9E4EB;border-radius:12px;}"
    )
    root = QVBoxLayout(dialog)
    root.setContentsMargins(18, 16, 18, 16)
    root.setSpacing(10)

    header = QFrame(objectName="PickerHeader")
    header_row = QHBoxLayout(header)
    header_row.setContentsMargins(16, 12, 16, 12)
    logo = QLabel()
    logo.setPixmap(icon("cloud", color="#1A73E8", size=26).pixmap(26, 26))
    logo.setFixedWidth(38)
    header_row.addWidget(logo)
    titles = QVBoxLayout()
    heading = QLabel("Google Drive — import to Protect")
    heading.setStyleSheet("font-size:20px;font-weight:800;color:#062B4F;")
    subheading = QLabel("Choose files in the official Google Picker without leaving PrivacyGate.")
    subheading.setStyleSheet("font-size:11px;color:#61798A;")
    titles.addWidget(heading)
    titles.addWidget(subheading)
    header_row.addLayout(titles, 1)
    badge = QLabel("DRIVE.FILE · USER SELECTED")
    badge.setStyleSheet("background:#E8F0FE;color:#174EA6;border-radius:9px;padding:8px 11px;font-size:9px;font-weight:800;")
    header_row.addWidget(badge)
    root.addWidget(header)

    web = QWebEngineView(dialog)
    web.setStyleSheet("border:1px solid #D9E4EB;border-radius:12px;background:#FFFFFF;")
    profile = QWebEngineProfile(dialog)  # unnamed profiles are off-the-record
    page = PickerPage(profile, web)
    web.setPage(page)
    web.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
    web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
    web.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    root.addWidget(web, 1)

    footer = QFrame(objectName="PickerFooter")
    footer_row = QHBoxLayout(footer)
    footer_row.setContentsMargins(14, 9, 14, 9)
    privacy = QLabel("✓ Selection stays under your control · local working copies only")
    privacy.setStyleSheet("color:#188038;font-size:10px;font-weight:700;")
    footer_row.addWidget(privacy, 1)
    close = QPushButton("Close")
    close.setObjectName("Secondary")
    close.clicked.connect(dialog.reject)
    footer_row.addWidget(close)
    root.addWidget(footer)

    chosen: dict[str, tuple[str, ...]] = {"ids": ()}

    def receive(payload) -> None:
        action, ids = payload
        if action == "picked" and ids:
            chosen["ids"] = ids
            dialog.accept()
        else:
            dialog.reject()

    page.selection_received.connect(receive)
    web.load(QUrl(origin + "/"))
    try:
        dialog.exec()
    finally:
        web.stop()
        page.deleteLater()
        profile.deleteLater()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)
    return chosen["ids"]


def _busy(parent, label: str):
    dialog = QProgressDialog(label, "", 0, 0, parent)
    dialog.setWindowTitle("Google Drive — PrivacyGate")
    dialog.setCancelButton(None)
    dialog.setMinimumDuration(0)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.show()
    return dialog


def open_embedded_drive_picker(main_window, service) -> None:
    """Run the local POC and hand the first selected document to Protect."""
    developer_key = configured_picker_api_key(service)
    app_id = configured_google_app_id(service)
    if not developer_key or not app_id:
        QMessageBox.warning(
            main_window,
            "Google Picker configuration",
            "The in-app Picker needs PRIVACY_GATE_GOOGLE_PICKER_API_KEY and the Google Cloud project number. "
            "No browser window was opened.",
        )
        return
    try:
        token = selected_file_access_token(service)
        ids = _choose_ids(main_window, token, developer_key, app_id)
        if not ids:
            return
        progress = _busy(main_window, "Preparing the selected Drive files locally…")
        try:
            rows = drive_items_from_ids(service, ids, token)
            imported = tuple(
                (remote, materialize_google_drive_item(service, remote, access_token=token))
                for remote in rows
            )
        finally:
            progress.close()
        if not imported:
            return
        remote, local_path = imported[0]
        protect = main_window.protection_page
        document_button = getattr(protect, "_redesign_document_mode", None)
        if document_button is not None and not document_button.isChecked():
            document_button.click()
        protect.input_tabs.setCurrentIndex(1)
        protect.pdf_path.setText(str(local_path))
        account_id, account_label = _active_account_details(service, "google_drive")
        protect._external_source_name = " • ".join(part for part in ("Google Drive", account_label, remote.title) if part)
        protect._external_source_metadata = {
            "provider": "google_drive",
            "provider_label": "Google Drive",
            "account_id": account_id,
            "account_label": account_label,
            "item_id": remote.item_id,
            "item_title": remote.title,
            "item_kind": remote.kind,
            "access_model": "drive.file + embedded official Google Picker",
            "selected_ids": list(ids),
            "local_paths": [str(path) for _row, path in imported],
        }
        protect._google_drive_import_queue = imported[1:]
        main_window._show_page(0)
        suffix = "" if len(imported) == 1 else f" · {len(imported)} files imported; first file ready"
        main_window.statusBar().showMessage(f"Imported from Google Drive: {remote.title}{suffix}", 10000)
    except Exception as exc:
        QMessageBox.warning(
            main_window,
            "Unable to open Google Drive inside PrivacyGate",
            _friendly_connection_error("Google Drive", exc),
        )
